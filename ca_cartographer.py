import libtcodpy as libtcod
import cProfile

import config
import algebra
import map
from components import *
import actions
import miscellany
import bestiary
import quest
import ai
import spells


RUSALKA_GOAL = 2
VODANYOI_CLUSTER_GOAL = 3
VODANYOI_CLUSTER_SIZE = 3


def _new_item(actor, obj):
    actor.inventory.append(obj)
    obj.always_visible = True


def _new_equipment(actor, obj):
    _new_item(actor, obj)
    actions.equip(actor, obj.equipment, False)


def _place_vodanyoi_cluster(new_map, player, vc_pos):
    # print('trying to place vc around ' + str(vc_pos.x) + ' ' + str(vc_pos.y))
    for v_count in range(0, VODANYOI_CLUSTER_SIZE):
        while True:
            v_pos = algebra.Location(libtcod.random_get_int(new_map.rng, vc_pos.x - 2, vc_pos.x + 2),
                                   libtcod.random_get_int(new_map.rng, vc_pos.y - 2, vc_pos.y + 2))
            if new_map.terrain[v_pos.x][v_pos.y] != map.TERRAIN_WALL:
                break
        # print('  v at ' + str(v_pos.x) + ' ' + str(v_pos.y))
        v = bestiary.vodanyoi(new_map, v_pos, player)
        choice = libtcod.random_get_int(0, 1, 3)
        if choice == 1:
            _new_equipment(v, miscellany.spear())


def _place_random_creatures(new_map, player):
    for r_count in range(0, RUSALKA_GOAL):
        while True:
            r_pos = algebra.Location(libtcod.random_get_int(new_map.rng, new_map.pool_x, new_map.width-3),
                                   libtcod.random_get_int(new_map.rng, 3, new_map.height-3))
            if new_map.terrain[r_pos.x][r_pos.y] != map.TERRAIN_WALL:
                break
        # TODO: can we ensure this doesn't block the passage?
        for x in range(r_pos.x-2, r_pos.x+3):
            for y in range(r_pos.y-2, r_pos.y+3):
                if new_map.terrain[x][y] == map.TERRAIN_FLOOR:
                    new_map.terrain[x][y] = map.TERRAIN_WATER
        bestiary.rusalka(new_map, r_pos, player)

    for vc_count in range(0, VODANYOI_CLUSTER_GOAL):
        while True:
            vc_pos = algebra.Location(libtcod.random_get_int(new_map.rng, new_map.pool_x, new_map.width-3),
                                   libtcod.random_get_int(new_map.rng, 3, new_map.height-3))
            if new_map.terrain[vc_pos.x][vc_pos.y] == map.TERRAIN_FLOOR:
                break
        _place_vodanyoi_cluster(new_map, player, vc_pos)


def _inhabit_pool(new_map):
    pos = algebra.Location(new_map.pool_x, new_map.height / 2)
    nymph = Object(pos, '@', 'nymph', libtcod.azure, blocks=True,
        interactable=Interactable(use_function=quest.nymph_info))
    new_map.objects.append(nymph)


# After code by Eric S. Raymond
# https://mail.python.org/pipermail/image-sig/2005-September/003559.html
def _floodfill(new_map, x, y, convert_from, convert_to):
    edge = [(x, y)]
    new_map.terrain[x][y] = convert_to
    while edge:
        newedge = []
        for (x, y) in edge:
            for (s, t) in ((x-1, y-1), (x, y-1), (x+1, y-1), (x-1, y), (x+1, y), (x-1, y+1), (x, y+1), (x+1, y+1)):
                if (s >= 0 and t >= 0 and s < new_map.width and t < new_map.height and
                        new_map.terrain[s][t] == convert_from):
                    new_map.terrain[s][t] = convert_to
                    newedge.append((s, t))
        edge = newedge
    

def _count_neightboring_walls(new_map, x, y):
    neighbors = 0
    for ii in range(x-1, x+2):
        for jj in range(y-1, y+2):
            if new_map.terrain[ii][jj] == map.TERRAIN_WALL:
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
            if new_map.terrain[ii][jj] == map.TERRAIN_WALL:
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
        if new_map.terrain[ii][y-2] == map.TERRAIN_WALL:
            far_neighbors += 1
        if new_map.terrain[ii][y+2] == map.TERRAIN_WALL:
            far_neighbors += 1
    for jj in range(y-1, y+2):
        if new_map.terrain[x-2][jj] == map.TERRAIN_WALL:
            far_neighbors += 1
        if new_map.terrain[x+2][jj] == map.TERRAIN_WALL:
            far_neighbors += 1
    for ii in range(x-1, x+2):
        for jj in range(y-1, y+2):
            if new_map.terrain[ii][jj] == map.TERRAIN_WALL:
                neighbors += 1
    return (neighbors, neighbors + far_neighbors)


def _assign(new_map, near_min, far_max, x, y, near_count, far_count):
        if (near_count >= near_min or
                far_count <= far_max):
            new_map.spare_terrain[x][y] = map.TERRAIN_WALL
        else:
            new_map.spare_terrain[x][y] = map.TERRAIN_GROUND


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


def _probe_for_stair(new_map, x_range, center_y):
    for y in (center_y, center_y - 1, center_y + 1, center_y - 2, center_y + 2):
        for x in x_range:
         if new_map.terrain[x][y] != map.TERRAIN_WALL:
            return algebra.Location(x, y)
    return None


def _build_map(new_map):
    new_map.rng = libtcod.random_new_from_seed(new_map.random_seed)

    new_map.spare_terrain = [[0 for y in range(new_map.height)] for x in range(new_map.width)]

    for x in range(1, new_map.width - 1):
        for y in range(1, new_map.height - 1):
            if libtcod.random_get_float(new_map.rng, 0., 1.) < 0.6:
                new_map.terrain[x][y] = map.TERRAIN_GROUND

    # Algorithm from http://www.roguebasin.com/index.php?title=Cellular_Automata_Method_for_Generating_Random_Cave-Like_Levels
    # Builds using map.TERRAIN_GROUND; we'll replace that with map.TERRAIN_FLOOR in a post-process
    for i in range(4):
        _generation(new_map, 5, 2)
    for i in range(3):
        _generation(new_map, 5, -1)

    center = algebra.Location(new_map.width / 2, new_map.height / 2)

    stair_loc = _probe_for_stair(new_map,
                                 range(new_map.width - 2, center.x, -1),
                                 center.y)
    if not stair_loc:
        # Uh-oh; no guarantee of completion
        print('Recursing with unenterable map:')
        # _dump(new_map)
        new_map.random_seed = libtcod.random_save(new_map.rng)
        return _build_map(new_map)

    pool_x = new_map.width / 4
    for x in range(pool_x - 6, pool_x + 7):
        for y in range(center.y - 6, center.y + 7):
            dx = x - pool_x
            dy = y - center.y
            if math.sqrt(dx ** 2 + dy ** 2) > 6:
                continue
            if new_map.terrain[x][y] == map.TERRAIN_WALL:
                new_map.terrain[x][y] = map.TERRAIN_GROUND

    # Can we reach from the stairs to the center of the pool?
    _floodfill(new_map, stair_loc.x, stair_loc.y, map.TERRAIN_GROUND, map.TERRAIN_FLOOR)
    if new_map.terrain[pool_x][center.y] != map.TERRAIN_FLOOR:
         # Uh-oh; no guarantee of completion
        print('Recursing with disconnected map:')
        # _dump(new_map)
        new_map.random_seed = libtcod.random_save(new_map.rng)
        return _build_map(new_map)

    # Close up any unconnected subcaves; flood any western bits
    for x in range(1, new_map.width-1):
        for y in range(1, new_map.height-1):
            if new_map.terrain[x][y] == map.TERRAIN_GROUND:
                new_map.terrain[x][y] = map.TERRAIN_WALL
            elif x < pool_x and new_map.terrain[x][y] == map.TERRAIN_FLOOR:
                new_map.terrain[x][y] = map.TERRAIN_WATER

    new_map.pool_x = pool_x
    return stair_loc


def make_map(player, dungeon_level):
    """
    Creates a new simple map at the given dungeon level.
    Sets player.current_map to the new map, and adds the player as the first
    object.
    """
    new_map = map.DungeonMap(config.MAP_WIDTH, config.MAP_HEIGHT, dungeon_level)
    new_map.objects.append(player)
    player.current_map = new_map
    player.camera_position = algebra.Location(0, 0)
    new_map.random_seed = libtcod.random_save(0)
    player.pos = _build_map(new_map)

    _inhabit_pool(new_map)
    _place_random_creatures(new_map, player)

    new_map.initialize_fov()
    return new_map


def _dump(new_map):
    desc = []
    for y in range(new_map.height):
        s = ''
        for x in range(new_map.width):
            if new_map.terrain[x][y] == map.TERRAIN_WALL:
                s += '#'
            elif new_map.terrain[x][y] == map.TERRAIN_FLOOR:
                s += '+'
            elif new_map.terrain[x][y] == map.TERRAIN_WATER:
                s += '~'
            else:
                s += '.'
        desc.append(s)

    for y in range(new_map.height):
        print desc[y]


def _test_display_ca(count):
    mock_player = Object(None, '@', 'you', libtcod.white)
    for i in range(count):
        new_map = make_map(mock_player, 1)
        _dump(new_map)


def _test_map_repeatability():
    """
    Require that two calls to _build_map() with the same seed produce the
    same corridors and rooms.
    """
    map1 = map.DungeonMap(config.MAP_WIDTH, config.MAP_HEIGHT, 3)
    map1.random_seed = libtcod.random_save(0)
    _build_map(map1)

    map2 = map.DungeonMap(config.MAP_WIDTH, config.MAP_HEIGHT, 3)
    map2.random_seed = map1.random_seed
    _build_map(map2)

    assert map1.terrain == map2.terrain


if __name__ == '__main__':
    #cProfile.run('_test_display_ca(10)')
    _test_display_ca(10)
    _test_map_repeatability()
    print('Cartographer tests complete.')
