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
        Terrain('wall', None, None, None,
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
                None, None, True, True)
            ]


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


class Map(object):
    """
    A (width x height) region of tiles, presumably densely occupied.
    Has a dungeon_level and a collection of (rectangular) rooms.
    Has portals connecting to other maps.
    """
    def __init__(self, height, width, dungeon_level):
        self.height = height
        self.width = width
        self.is_outdoors = False
        self.dungeon_level = dungeon_level
        self.objects = []
        self.rooms = []
        self.portals = []

        self.random_seed = None
        self.rng = None

        self.fov_map = None
        self.fov_elevation_changed = False  # HACK

        # Maps default to walls (blocked) & unexplored
        self.terrain = [[0 for y in range(height)] for x in range(width)]
        self._explored = [[False for y in range(height)] for x in range(width)]

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

    def is_blocked_from(self, origin, dest, ignore=None):
        return self.is_blocked_at(dest, ignore)

    def is_explored(self, pos):
        return self._explored[pos.x][pos.y]

    def explore(self, pos):
        self._explored[pos.x][pos.y] = True

    def out_of_bounds(self, pos):
        return "You can't go that way!"


class OutdoorMap(object):
    """
    A (width x height) region of tiles, presumably densely occupied.
    Has a dungeon_level and a collection of (rectangular) rooms.
    Has portals connecting to other maps.
    """
    def __init__(self, height, width, dungeon_level):
        self.height = height
        self.width = width
        self.is_outdoors = True
        self.dungeon_level = 0  # HACK
        self.objects = []
        self.portals = []

        self.random_seed = None
        self.rng = None

        self.fov_map = None
        self.fov_needs_recompute = True
        self.fov_elevation_changed = False

        # OutdoorMaps default to open (unblocked) & unexplored
        self.terrain = [[1 for y in range(height)] for x in range(width)]
        self._explored = [[False for y in range(height)] for x in range(width)]

        self.region = [[-1 for y in range(height)] for x in range(width)]

        self.region_seeds = []
        self.region_elevations = []
        self.region_tree = None
        self.region_terrain = []

        self.region_entered = []
        self.elevation_visited = []

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

    def set_fov_elevation(self, e):
        for y in range(self.height):
            for x in range(self.width):
                bs = (terrain_types[self.terrain[x][y]].blocks_sight or
                      (self.region_elevations[self.region[x][y]] > e + 1))
                libtcod.map_set_properties(
                    self.fov_map, x, y,
                    not bs, not terrain_types[self.terrain[x][y]].blocks)

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

    def is_explored(self, pos):
        return self._explored[pos.x][pos.y]

    def explore(self, pos):
        self._explored[pos.x][pos.y] = True

    def out_of_bounds(self, pos):
        return "You can't go that way!"

    def elevation(self, x, y):
        return self.region_elevations[self.region[x][y]]