import libtcodpy as libtcod

import algebra


class Room(algebra.Rect):
    def __init__(self, x, y, w, h):
        super(self.__class__, self).__init__(x, y, w, h)


class Terrain(object):
    def __init__(self, name, display_name, icon,
                 icon_color, seen_color, unseen_color, blocks, blocks_sight):
        self.name = name
        self.display_name = display_name  # text displayed on mouseover
        self.icon = icon  # character drawn on screen
        self.icon_color = icon_color
        self.seen_color = seen_color
        self.unseen_color = unseen_color
        self.blocks = blocks
        self.blocks_sight = blocks_sight


terrain_types = [
        Terrain('wall', 'wall', None, None,
                libtcod.Color(130, 110, 50), libtcod.Color(0, 0, 100), True, True),
        Terrain('ground', None, None, None,
                None, None, False, False),
        Terrain('slope', 'slope', '^', None,
                None, None, False, False),
        Terrain('water', 'water', '~', libtcod.azure,
                None, None, True, False),
        Terrain('boulder', 'boulder', '*', libtcod.black,
                None, None, True, False),
        # 5
        Terrain('reeds', 'reeds', '|', libtcod.green,
                None, None, False, True),
        Terrain('saxaul', 'bush', '%', libtcod.dark_green,
                None, None, True, True),
        Terrain('nitraria', 'bush', '%', libtcod.dark_green,
                None, None, True, True),
        Terrain('ephedra', 'shrub', '"', libtcod.dark_amber,
                None, None, False, False),
        Terrain('poplar', 'tree', 'T', libtcod.darker_green,
                None, None, True, True),

        # 10
        Terrain('floor', None, None, None,
                libtcod.Color(200, 180, 50), libtcod.Color(50, 50, 150), False, False)
            ]

TERRAIN_WALL = 0
TERRAIN_GROUND = 1
TERRAIN_SLOPE = 2
TERRAIN_WATER = 3
TERRAIN_FLOOR = 10

region_colors_seen =  {
    'lake' : libtcod.dark_azure,
    'marsh' : libtcod.darker_chartreuse,
    'desert' : libtcod.lightest_sepia,
    'scrub' : libtcod.lighter_sepia,
    'forest' : libtcod.sepia,
    'rock' : libtcod.darker_sepia,
    'ice' : libtcod.gray
}


region_colors_unseen = {
    'lake' : libtcod.darkest_azure,
    'marsh' : libtcod.darkest_chartreuse,
    'desert' : libtcod.light_sepia,
    'scrub' : libtcod.sepia,
    'forest' : libtcod.dark_sepia,
    'rock' : libtcod.darkest_sepia,
    'ice' : libtcod.dark_gray
}


class BaseMap(object):
    def __init__(self, width, height, default_terrain):
        self.width = width
        self.height = height
        self.objects = []
        self.portals = []

        self.random_seed = None
        self.rng = None

        self.fov_map = None
        self.fov_needs_recompute = True

        self.terrain = [[default_terrain for y in range(height)] for x in range(width)]
        self._explored = [[False for y in range(height)] for x in range(width)]

    def rnd(self, mi, ma):
        """
        All random numbers used in map generation should use the map's
        random number generator, which is initialized with a known seed
        and is therefore repeatable.
        """
        return libtcod.random_get_int(self.rng, mi, ma)

    def initialize_fov(self):
        """
        Set up corresponding C state for libtcod.
        Must be called explicitly after loading from savegame or entering from
        another map.
        """
        self.fov_needs_recompute = True
        self.fov_map = libtcod.map_new(self.width, self.height)
        for y in range(self.height):
            for x in range(self.width):
                libtcod.map_set_properties(
                    self.fov_map, x, y,
                    not terrain_types[self.terrain[x][y]].blocks_sight,
                    not terrain_types[self.terrain[x][y]].blocks)
        for obj in self.objects:
            if obj.blocks_sight or obj.blocks:
                blocks = obj.blocks or terrain_types[self.terrain[obj.pos.x][obj.pos.y]].blocks
                blocks_sight = obj.blocks_sight or terrain_types[self.terrain[obj.pos.x][obj.pos.y]].blocks_sight
                libtcod.map_set_properties(self.fov_map, obj.pos.x, obj.pos.y, not blocks_sight, not blocks)


    def terrain_index_at(self, pos):
        return self.terrain[pos.x][pos.y]

    def terrain_at(self, pos):
        """
        Returns the Terrain at (pos).
        position *must* be within the current map.
        """
        return terrain_types[self.terrain[pos.x][pos.y]]

    def is_blocked_at(self, pos, ignore=None):
        """
        Returns true if impassible map terrain or any blocking objects
        are at (x, y).
        """
        if terrain_types[self.terrain[pos.x][pos.y]].blocks:
            return True
        for object in self.objects:
            if object.blocks and object.pos == pos and object != ignore:
                return True
        return False

    def is_explored(self, pos):
        return self._explored[pos.x][pos.y]

    def explore(self, pos):
        self._explored[pos.x][pos.y] = True

    def is_blocked_from(self, origin, dest, ignore=None):
        return self.is_blocked_at(dest, ignore)

    def out_of_bounds(self, pos):
        return "You can't go that way!"

    def elevation(self, x, y):
        return 0  # hackish?


class DungeonMap(BaseMap):
    """
    A (width x height) region of tiles, presumably densely occupied.
    Has a dungeon_level and a collection of (rectangular) rooms.
    Has portals connecting to other maps.
    """
    def __init__(self, width, height, dungeon_level):
        super(DungeonMap, self).__init__(width, height, TERRAIN_WALL)
        self.is_outdoors = False
        self.dungeon_level = dungeon_level
        self.rooms = []

        self.fov_elevation_changed = False  # HACK


class OutdoorMap(BaseMap):
    """
    A (width x height) region of tiles, presumably densely occupied.
    Has a dungeon_level and a collection of (rectangular) rooms.
    Has portals connecting to other maps.
    """
    def __init__(self, width, height, dungeon_level):
        super(OutdoorMap, self).__init__(width, height, TERRAIN_GROUND)
        self.is_outdoors = True
        self.dungeon_level = 0  # HACK

        self.fov_elevation_changed = False

        self.region = [[-1 for y in range(height)] for x in range(width)]

        self.region_seeds = []
        self.region_elevations = []
        self.region_terrain = []

        self.region_entered = []
        self.elevation_visited = []

    def set_fov_elevation(self, player):
        elevation = self.elevation(player.pos.x, player.pos.y)
        self.fov_needs_recompute = True
        self.fov_map = libtcod.map_new(self.width, self.height)
        for y in range(self.height):
            for x in range(self.width):
                blocks_sight = (terrain_types[self.terrain[x][y]].blocks_sight or
                                (self.region_elevations[self.region[x][y]] > elevation + 1))
                libtcod.map_set_properties(
                    self.fov_map, x, y,
                    not blocks_sight, not terrain_types[self.terrain[x][y]].blocks)
        for obj in self.objects:
            if obj.blocks_sight or obj.blocks:
                blocks = obj.blocks or terrain_types[self.terrain[obj.pos.x][obj.pos.y]].blocks
                blocks_sight = (obj.blocks_sight or
                    terrain_types[self.terrain[obj.pos.x][obj.pos.y]].blocks_sight or
                    (self.region_elevations[self.region[x][y]] > elevation + 1))
                libtcod.map_set_properties(self.fov_map, obj.pos.x, obj.pos.y, not blocks_sight, not blocks)


    def is_blocked_from(self, origin, dest, ignore=None):
        """
        Returns true if impassible map terrain or any blocking objects
        prevent travel from origin to dest.
        """
        if self.is_blocked_at(dest, ignore):
            return True
        eo = self.elevation(origin.x, origin.y)
        do = self.elevation(dest.x, dest.y)
        delta = eo - do
        if (delta > 1 or delta < -1):
            return True
        return False

    def out_of_bounds(self, pos):
        if pos.x < 0:
            return "There's no point in crossing the lake; your fate led you to the mountain."
        if pos.y < 0:
            return "There's no point in recrossing the Mother River; you came here with a purpose."
        if pos.x < 100:
            return "You're not sure the townsfolk would accept a foreigner like you; there's no safety that way."
        return "You're not prepared to cross the full width of the desert; right now, that way lies only death."

    def elevation(self, x, y):
        return self.region_elevations[self.region[x][y]]