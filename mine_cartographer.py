import copy

import libtcodpy as libtcod

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
import ca_cartographer


MINE_SIZE = 60
MINE_SCALE = 5

def _create_room(new_map, room):
    """
    Make the tiles in a rectangle passable.
    # Returns True if any were already passable.
    """
    retval = False
    for x in range(room.x1 + 1, room.x2):
        for y in range(room.y1 + 1, room.y2):
            # if new_map.terrain[x][y] != map.TERRAIN_WALL:
            #     retval = True
            new_map.terrain[x][y] = map.TERRAIN_GROUND
    return retval


def _create_h_tunnel(new_map, x1, x2, y):
    retval = False
    for x in range(min(x1, x2), max(x1, x2) + 1):
        # if new_map.terrain[x][y] != map.TERRAIN_WALL:
        #     retval = True
        new_map.terrain[x][y] = map.TERRAIN_GROUND
    return retval


def _create_v_tunnel(new_map, y1, y2, x):
    retval = False
    for y in range(min(y1, y2), max(y1, y2) + 1):
        # if new_map.terrain[x][y] != map.TERRAIN_WALL:
        #     retval = True
        new_map.terrain[x][y] = map.TERRAIN_GROUND
    return retval


def _link_up_stairs(new_map, old_map, old_quarry_stairs):
    old_quarry_stairs[1].dest_position = algebra.Location(new_map.width / 2, new_map.height / 2)
    old_quarry_stairs[0].dest_position = old_quarry_stairs[1].dest_position + MINE_SCALE * (old_quarry_stairs[0].pos - old_quarry_stairs[1].pos)
    old_quarry_stairs[2].dest_position = old_quarry_stairs[1].dest_position + MINE_SCALE * (old_quarry_stairs[2].pos - old_quarry_stairs[1].pos)

    map_inset = algebra.Rect(10, 10, new_map.width - 20, new_map.height - 20)
    old_quarry_stairs[0].dest_position.bound(map_inset)
    old_quarry_stairs[2].dest_position.bound(map_inset)

    print('Map is ' + str(new_map.width) + ' x ' + str(new_map.height))
    print('Stairs come from ', [i.pos for i in old_quarry_stairs])
    print('Stairs to mines connect to ', [i.dest_position for i in old_quarry_stairs])

    for i in range(3):
        old_quarry_stairs[i].destination = new_map
        stairs = Object(old_quarry_stairs[i].dest_position, '>', 'stairs up', libtcod.white, always_visible=True)
        stairs.destination = old_map
        stairs.dest_position = old_quarry_stairs[i].pos
        new_map.objects.insert(0, stairs)
        new_map.portals.insert(0, stairs)


def _create_entries(new_map, old_quarry_stairs):
    for i in range(3):
        w = libtcod.random_get_int(new_map.rng, 1, 3) * 2 + 3
        h = libtcod.random_get_int(new_map.rng, 1, 3) * 2 + 3
        x = old_quarry_stairs[i].dest_position.x - w / 2
        y = old_quarry_stairs[i].dest_position.y - h / 2

        new_room = algebra.Rect(x, y, w, h)
        _create_room(new_map, new_room)
        print('Room #' + str(i) + ' at ' + str(new_room))
        new_map.rooms.append(new_room)

        new_ctr = new_room.center()
        assert(new_ctr == old_quarry_stairs[i].dest_position)

def _descend_stairs(new_map, player, old_quarry_stairs):
    print('Player was at ', player.pos)
    for i in range(3):
        if player.pos == old_quarry_stairs[i].pos:
            player.pos = old_quarry_stairs[i].dest_position
            print('Came down stair #' + str(i) + ' to ' + str(player.pos))
            return

def _dig_some_caves(new_map, old_quarry_stairs):
    new_map.spare_terrain = copy.deepcopy(new_map.terrain) # [[0 for y in range(new_map.height)] for x in range(new_map.width)]

    new_map.cave_zones = []
    x = libtcod.random_get_int(new_map.rng, 3, old_quarry_stairs[1].dest_position.x / 2)
    w = libtcod.random_get_int(new_map.rng, 20, old_quarry_stairs[1].dest_position.x - x - 3)
    if old_quarry_stairs[0].dest_position.y < old_quarry_stairs[1].dest_position.y:
        # staircase 0 in top left quadrant, put caves in bottom left quadrant
        y = libtcod.random_get_int(new_map.rng, old_quarry_stairs[1].dest_position.y + 3, old_quarry_stairs[1].dest_position.y * 3 / 2)
        h = libtcod.random_get_int(new_map.rng, 20, new_map.height - y - 3)
    else:
        # staircase 0 in bottom left quadrant, put caves in top left quadrant
        y = libtcod.random_get_int(new_map.rng, 3, old_quarry_stairs[1].dest_position.y / 2)
        h = libtcod.random_get_int(new_map.rng, 20, old_quarry_stairs[1].dest_position.y - y - 3)

    target_zone = algebra.Rect(x, y, w, h)
    print("Target zone 0 ", target_zone)
    ca_cartographer.dig_ca_region(new_map, target_zone, 4, 3)
    new_map.cave_zones.append(target_zone)

    x = libtcod.random_get_int(new_map.rng, old_quarry_stairs[1].dest_position.x + 3, old_quarry_stairs[1].dest_position.x * 3 / 2)
    w = libtcod.random_get_int(new_map.rng, 20, new_map.width - x - 3)
    if old_quarry_stairs[2].dest_position.y < old_quarry_stairs[1].dest_position.y:
        y = libtcod.random_get_int(new_map.rng, old_quarry_stairs[1].dest_position.y + 3, old_quarry_stairs[1].dest_position.y * 3 / 2)
        h = libtcod.random_get_int(new_map.rng, 20, new_map.height - y - 3)
    else:
        y = libtcod.random_get_int(new_map.rng, 3, old_quarry_stairs[1].dest_position.y / 2)
        h = libtcod.random_get_int(new_map.rng, 20, old_quarry_stairs[1].dest_position.y - y - 3)

    target_zone = algebra.Rect(x, y, w, h)
    print("Target zone 1 ", target_zone)
    ca_cartographer.dig_ca_region(new_map, target_zone, 4, 3)
    new_map.cave_zones.append(target_zone)


def make_map(player, dungeon_level):
    """
    """
    old_map = player.current_map

    new_map = map.DungeonMap(MINE_SIZE, MINE_SIZE, dungeon_level)
    new_map.objects.append(player)
    player.current_map = new_map
    player.camera_position = algebra.Location(0, 0)
    new_map.random_seed = libtcod.random_save(0)
    new_map.rng = libtcod.random_new_from_seed(new_map.random_seed)

    old_quarry_stairs = old_map.quarry_stairs
    _link_up_stairs(new_map, old_map, old_quarry_stairs)
    _create_entries(new_map, old_quarry_stairs)
    _descend_stairs(new_map, player, old_quarry_stairs)
    _dig_some_caves(new_map, old_quarry_stairs)

    # TODO: build map conecting (not directly!) all three entrances
    # TODO: add inhabitants

    x = new_map.rooms[0].center().x
    top = new_map.rnd(3, new_map.rooms[0].y1 / 2)
    _create_v_tunnel(new_map, new_map.rooms[0].y1, top, x)
    cross_tunnel_count = new_map.rnd(2, 4)
    tunnel_interval = (new_map.rooms[0].y1 - 2 - top) / cross_tunnel_count
    for i in range(cross_tunnel_count):
        y = new_map.rnd(0, tunnel_interval - 1) + top + i * tunnel_interval
        if new_map.cave_zones[0].contains(algebra.Location(x, y)):
            continue
        left = new_map.rnd(3, x / 2)
        right = new_map.rnd(x + 3, new_map.width - 3)
        _create_h_tunnel(new_map, left, right, y)

    bottom = new_map.rnd(new_map.rooms[0].y2 * 3 / 2, new_map.height - 3)
    _create_v_tunnel(new_map, new_map.rooms[0].y2, bottom, x)
    cross_tunnel_count = new_map.rnd(2, 4)
    tunnel_interval = (bottom - new_map.rooms[0].y2 - 2) / cross_tunnel_count
    for i in range(cross_tunnel_count):
        y = new_map.rnd(0, tunnel_interval - 1) + new_map.rooms[0].y2 + 3 + i * tunnel_interval
        if new_map.cave_zones[0].contains(algebra.Location(x, y)):
            continue
        left = new_map.rnd(3, x / 2)
        right = new_map.rnd(x + 3, new_map.width - 3)
        _create_h_tunnel(new_map, left, right, y)

    #####

    x = new_map.rooms[1].center().x
    top = new_map.rnd(3, new_map.rooms[1].y1 / 2)
    _create_v_tunnel(new_map, new_map.rooms[1].y1, top, x)
    cross_tunnel_count = new_map.rnd(2, 4)
    tunnel_interval = (new_map.rooms[1].y1 - 2 - top) / cross_tunnel_count
    for i in range(cross_tunnel_count):
        y = new_map.rnd(0, tunnel_interval - 1) + top + i * tunnel_interval
        left = new_map.rnd(x / 2, x - 3)
        right = new_map.rnd(x + 3, x * 3 / 2)
        _create_h_tunnel(new_map, left, right, y)

    bottom = new_map.rnd(new_map.rooms[1].y2 * 3 / 2, new_map.height - 3)
    _create_v_tunnel(new_map, new_map.rooms[1].y2, bottom, x)
    cross_tunnel_count = new_map.rnd(2, 4)
    tunnel_interval = (bottom - new_map.rooms[1].y2 - 2) / cross_tunnel_count
    for i in range(cross_tunnel_count):
        y = new_map.rnd(0, tunnel_interval - 1) + new_map.rooms[1].y2 + 3 + i * tunnel_interval
        left = new_map.rnd(x / 2, x - 3)
        right = new_map.rnd(x + 3, x * 3 / 2)
        _create_h_tunnel(new_map, left, right, y)

    #####

    x = new_map.rooms[2].center().x
    top = new_map.rnd(3, new_map.rooms[2].y1 / 2)
    _create_v_tunnel(new_map, new_map.rooms[2].y1, top, x)
    cross_tunnel_count = new_map.rnd(2, 4)
    tunnel_interval = (new_map.rooms[2].y1 - 2 - top) / cross_tunnel_count
    for i in range(cross_tunnel_count):
        y = new_map.rnd(2, tunnel_interval - 1) + top + i * tunnel_interval
        if new_map.cave_zones[1].contains(algebra.Location(x, y)):
            continue
        left = new_map.rnd(3, x / 2)
        right = new_map.rnd(x + (new_map.width - x) / 2, new_map.width - 3)
        _create_h_tunnel(new_map, left, right, y)

    bottom = new_map.rnd(new_map.rooms[2].y2 * 3 / 2, new_map.height - 3)
    _create_v_tunnel(new_map, new_map.rooms[2].y2, bottom, x)
    cross_tunnel_count = new_map.rnd(2, 4)
    tunnel_interval = (bottom - new_map.rooms[2].y2 - 2) / cross_tunnel_count
    for i in range(cross_tunnel_count):
        y = new_map.rnd(0, tunnel_interval - 1) + new_map.rooms[2].y2 + 3 + i * tunnel_interval
        if new_map.cave_zones[1].contains(algebra.Location(x, y)):
            continue
        left = new_map.rnd(3, x / 2)
        right = new_map.rnd(x + (new_map.width - x) / 2, new_map.width - 3)
        _create_h_tunnel(new_map, left, right, y)


    # TEST
    for x in range(new_map.width):
        for y in range(new_map.height):
            new_map._explored[x][y] = True

    new_map.initialize_fov()
    return False  # Don't need to generate stairs in caller thanks to _link_up_stairs()