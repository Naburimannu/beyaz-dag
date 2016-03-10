import libtcodpy as libtcod
import cProfile

import config
import algebra
import map
from components import *
import ai
import spells


def _count_neightboring_walls(new_map, x, y):
    neighbors = 0
    for ii in range(x-1, x+2):
        for jj in range(y-1, y+2):
            if new_map.terrain[ii][jj] == 0:
                neighbors += 1
    return neighbors


def _count_farther_walls(new_map, x, y):
    """
    Count walls in a "fat plus" around x,y.
    """
    neighbors = 0
    for ii in range(x-2, x+3):
        for jj in range(y-2, y+3):
            if abs(x-ii) == 2 and abs(y-jj) == 2:
                continue
            if (ii < 0 or jj < 0 or
                    ii > new_map.width - 1 or
                    jj > new_map.height - 1):
                continue
            if new_map.terrain[ii][jj] == 0:
                neighbors += 1
    return neighbors


def _quickly_count_interior_walls(new_map, x, y):
    """
    Once off the edge of the map we can reduce conditionals in the loop
    for a 3x speedup. (Although this *might* ping-pong the cache a bit...)
    """
    neighbors = 0
    far_neighbors = 0
    for ii in range(x-1, x+2):
        if new_map.terrain[ii][y-2] == 0:
            far_neighbors += 1
        if new_map.terrain[ii][y+2] == 0:
            far_neighbors += 1
    for jj in range(y-1, y+2):
        if new_map.terrain[x-2][jj] == 0:
            far_neighbors += 1
        if new_map.terrain[x+2][jj] == 0:
            far_neighbors += 1
    for ii in range(x-1, x+2):
        for jj in range(y-1, y+2):
            if new_map.terrain[ii][jj] == 0:
                neighbors += 1
    return (neighbors, neighbors + far_neighbors)


def _assign(new_map, near_min, far_max, x, y, near_count, far_count):
        if (near_count >= near_min or
                far_count <= far_max):
            new_map.spare_terrain[x][y] = 0
        else:
            new_map.spare_terrain[x][y] = 1


def _assess_edge(new_map, near_min, far_max, x, y):
        _assign(new_map, near_min, far_max, x, 1,
            _count_neightboring_walls(new_map, x, y),
            _count_farther_walls(new_map, x, y))


def _generation(new_map, near_min, far_max):
    for x in range(1, new_map.width - 1):
        _assess_edge(new_map, near_min, far_max, x, 1)
        _assess_edge(new_map, near_min, far_max, x, new_map.height - 2)

    for y in range(1, new_map.height - 1):
        _assess_edge(new_map, near_min, far_max, 1, y)
        _assess_edge(new_map, near_min, far_max, new_map.width - 2, y)

    for x in range(2, new_map.width - 2):
        for y in range(2, new_map.height - 2):
            neighboring_walls, farther_walls = _quickly_count_interior_walls(new_map, x, y)
            _assign(new_map, near_min, far_max, x, y, neighboring_walls, farther_walls)

    new_map.terrain, new_map.spare_terrain = new_map.spare_terrain, new_map.terrain


def _build_map(new_map):
    new_map.rng = libtcod.random_new_from_seed(new_map.random_seed)

    new_map.spare_terrain = [[0 for y in range(new_map.height)] for x in range(new_map.width)]

    for x in range(1, new_map.width - 1):
        for y in range(1, new_map.height - 1):
            if libtcod.random_get_float(new_map.rng, 0., 1.) < 0.6:
                new_map.terrain[x][y] = 1

    for i in range(4):
        _generation(new_map, 5, 2)
    for i in range(3):
        _generation(new_map, 5, -1)


    # TODO: floodfill for largest connected component
    # TODO: sanity check and reject if necessary
    # TODO: stairs down



def make_map(player, dungeon_level):
    """
    Creates a new simple map at the given dungeon level.
    Sets player.current_map to the new map, and adds the player as the first
    object.
    """
    new_map = map.Map(config.MAP_HEIGHT, config.MAP_WIDTH, dungeon_level)
    new_map.objects.append(player)
    player.current_map = new_map
    player.camera_position = algebra.Location(0, 0)
    new_map.random_seed = libtcod.random_save(0)
    _build_map(new_map)
    # for new_room in new_map.rooms:
    #     _place_objects(new_map, new_room, player)
    # player.pos = new_map.rooms[0].center()

    # new_map.initialize_fov()
    return new_map


def _dump(new_map):
    for y in range(new_map.height):
        s = ''
        for x in range(new_map.width):
            s += str(new_map.terrain[x][y])
        print(s)


def _test_display_ca(count):
    mock_player = Object(None, '@', 'you', libtcod.white)
    for i in range(count):
        new_map = make_map(mock_player, 1)
        # _dump(new_map)


def _test_map_repeatability():
    """
    Require that two calls to _build_map() with the same seed produce the
    same corridors and rooms.
    """
    map1 = map.Map(config.MAP_HEIGHT, config.MAP_WIDTH, 3)
    map1.random_seed = libtcod.random_save(0)
    _build_map(map1)

    map2 = map.Map(config.MAP_HEIGHT, config.MAP_WIDTH, 3)
    map2.random_seed = map1.random_seed
    _build_map(map2)

    assert map1.terrain == map2.terrain


if __name__ == '__main__':
    # cProfile.run('_test_display_ca(10)')
    _test_display_ca(10)
    _test_map_repeatability()
    print('Cartographer tests complete.')
