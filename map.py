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
                libtcod.Color(200, 180, 50), libtcod.Color(50, 50, 150), False, False),
        Terrain('slope', 'slope', '^', None,
                None, libtcod.black, False, False),
        Terrain('water', 'water', '~', libtcod.azure,
                None, libtcod.black, True, False),
        Terrain('boulder', None, '*', libtcod.black,
                None, libtcod.black, True, True),
        # 5
        Terrain('reeds', None, '|', libtcod.green,
                None, libtcod.black, False, True),
        Terrain('saxaul', None, '%', libtcod.dark_green,
                None, libtcod.black, True, True),
        Terrain('nitraria', None, '%', libtcod.dark_green,
                None, libtcod.black, True, True),
        Terrain('ephedra', None, '"', libtcod.dark_amber,
                None, libtcod.black, False, False),
        Terrain('poplar', None, 'T', libtcod.darker_green,
                None, libtcod.black, True, True)
            ]

terrain_colors_seen =  {
    'lake' : libtcod.dark_azure,
    'marsh' : libtcod.darker_chartreuse,
    'desert' : libtcod.lightest_sepia,
    'scrub' : libtcod.lighter_sepia,
    'forest' : libtcod.sepia,
    'rock' : libtcod.darker_sepia,
    'ice' : libtcod.gray
}

terrain_colors_unseen = {
    'lake' : libtcod.darkest_azure,
    'marsh' : libtcod.darkest_chartreuse,
    'desert' : libtcod.light_sepia,
    'scrub' : libtcod.sepia,
    'forest' : libtcod.darker_sepia,
    'rock' : libtcod.darkest_sepia,
    'ice' : libtcod.dark_gray
}

# terrain_types = [
#        Terrain('wall', None, None, None,
#                libtcod.Color(130, 110, 50), libtcod.Color(0, 0, 100), True, True),
#        Terrain('ground', None, None, None,
#                libtcod.Color(200, 180, 50), libtcod.Color(50, 50, 150), False, False),
#        Terrain('slope', 'slope', '^', None,
#                libtcod.light_gray, libtcod.darker_gray, False, False),
#        Terrain('water', 'water', '~', None,
#                libtcod.azure, libtcod.darker_azure, True, False),
#        Terrain('boulder', None, '*', None,
#                libtcod.sepia, libtcod.darker_sepia, True, True),
#        # 5
#        Terrain('reeds', None, '|', None,
#                libtcod.light_green, libtcod.darker_green, False, True),
#        Terrain('saxaul', None, '%', None,
#                libtcod.dark_green, libtcod.darker_green, True, True),
#        Terrain('nitraria', None, '%', None,
#                libtcod.dark_green, libtcod.darker_green, True, True),
#        Terrain('ephedra', None, '"', None,
#                libtcod.dark_amber, libtcod.darker_amber, False, False),
#        Terrain('poplar', None, 'T', None,
#                libtcod.dark_green, libtcod.darker_green, True, True)
#            ]

class Map(object):
    """
    A (width x height) region of tiles, presumably densely occupied.
    Has a dungeon_level and a collection of (rectangular) rooms.
    Has portals connecting to other maps.
    """
    def __init__(self, height, width, dungeon_level):
        self.height = height
        self.width = width
        self.dungeon_level = dungeon_level
        self.objects = []
        self.rooms = []
        self.portals = []

        self.random_seed = None
        self.rng = None

        self.fov_map = None

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

    def is_blocked_at(self, pos):
        """
        Returns true if impassible map terrain or any blocking objects
        are at (x, y).
        """
        if terrain_types[self.terrain[pos.x][pos.y]].blocks:
            return True
        for object in self.objects:
            if object.blocks and object.pos == pos:
                return True
        return False

    def is_blocked_from(self, origin, dest):
        return is_blocked_at(dest)

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
        self.dungeon_level = dungeon_level  # cut?
        self.objects = []
        self.rooms = []  # cut?
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
        self.region_terrain = [None for xy in range(height * width)]

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

    def is_blocked_at(self, pos):
        """
        Returns true if impassible map terrain or any blocking objects
        are at (x, y).
        """
        if terrain_types[self.terrain[pos.x][pos.y]].blocks:
            return True
        for object in self.objects:
            if object.blocks and object.pos == pos:
                return True
        return False

    def is_blocked_from(self, origin, dest):
        """
        Returns true if impassible map terrain or any blocking objects
        prevent travel from origin to dest.
        """
        if terrain_types[self.terrain[dest.x][dest.y]].blocks:
            return True
        for object in self.objects:
            if object.blocks and object.pos == dest:
                return True
        eo = self.region_elevations[self.region[origin.x][origin.y]]
        do = self.region_elevations[self.region[dest.x][dest.y]]
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