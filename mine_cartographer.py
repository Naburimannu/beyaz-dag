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


MINE_SIZE = 100
MINE_SCALE = 5

def _create_room(new_map, room):
    """
    Make the tiles in a rectangle passable.
    """
    for x in range(room.x1 + 1, room.x2):
        for y in range(room.y1 + 1, room.y2):
            new_map.terrain[x][y] = map.TERRAIN_GROUND


def _create_h_tunnel(new_map, x1, x2, y):
    for x in range(min(x1, x2), max(x1, x2) + 1):
        new_map.terrain[x][y] = map.TERRAIN_GROUND


def _create_v_tunnel(new_map, y1, y2, x):
    for y in range(min(y1, y2), max(y1, y2) + 1):
        new_map.terrain[x][y] = map.TERRAIN_GROUND

def _link_up_stairs(new_map, old_quarry_stairs):
    oqs[1].dest_position = algebra.Location(new_map.width / 2, new_map.height / 2)
    oqs[0].dest_position = oqs[1].dest_position + MINE_SCALE * (oqs[0].pos - oqs[1].pos)
    oqs[2].dest_position = oqs[1].dest_position + MINE_SCALE * (oqs[2].pos - oqs[1].pos)

    map_inset = algebra.Rect(10, 10, new_map.width - 20, new_map.height - 20)
    oqs[0].dest_position.bound(map_inset)
    oqs[2].dest_position.bound(map_inset)

    print('Map is ' + str(new_map.width) + ' x ' + str(new_map.height))
    print('Stairs come from ', [i.pos for i in oqs])
    print('Stairs to mines connect to ', [i.dest_position for i in oqs])

    # Conflicts with stair generation in roguelike.next_level()
    for i in range(3):
        oqs[i].destination = new_map
        stairs = Object(oqs[i].dest_position, '>', 'stairs up', libtcod.white, always_visible=True)
        stairs.destination = old_map
        stairs.dest_position = oqs[i].pos
        player.current_map.objects.insert(0, stairs)
        player.current_map.portals.insert(0, stairs)


def _create_entries(new_map, old_quarry_stairs):
    for i in range(3):
        w = libtcod.random_get_int(new_map.rng, 1, 3) * 2 + 3
        h = libtcod.random_get_int(new_map.rng, 1, 3) * 2 + 3
        x = old_quarry_stairs[i].dest_position.x - w / 2
        y = old_quarry_stairs[i].dest_position.y - h / 2

        new_room = algebra.Rect(x, y, w, h)
        _create_room(new_map, new_room)
        print('Room #' + str(i) + ' at ' + str(new_room))
        new_map.rooms[i] = new_room

        new_ctr = new_room.center()
        assert(new_ctr == oqs[i].dest_position)

def _descend_stairs(new_map, player, old_quarry_stairs):
    print('Player was at ', player.pos)
    for i in range(3):
        if player.pos == old_quarry_stairs[i].pos:
            player.pos = old_quarry_stairs[i].dest_position
            print('Came down stair #' + str(i) + ' to ' + str(player.pos))
            return

def _dig_some_caves(new_map, old_quarry_stairs):
    new_map.spare_terrain = copy.deepcopy(new_map.terrain) # [[0 for y in range(new_map.height)] for x in range(new_map.width)]

    x = libtcod.random_get_int(new_map.rng, 3, old_quarry_stairs[1].dest_position.x / 2)
    w = libtcod.random_get_int(new_map.rng, 20, old_quarry_stairs[1].dest_position.x - x - 3)
    if old_quarry_stairs[0].dest_position.y < oqs[1].dest_position.y:
        y = libtcod.random_get_int(new_map.rng, old_quarry_stairs[1].dest_position.y + 3, old_quarry_stairs[1].dest_position.y * 3 / 2)
        h = libtcod.random_get_int(new_map.rng, 20, new_map.height - y - 3)
    else:
        y = libtcod.random_get_int(new_map.rng, 3, old_quarry_stairs[1].dest_position.y * 2)
        h = libtcod.random_get_int(new_map.rng, 20, old_quarry_stairs[1].dest_position.y - y - 3)

    target_zone = algebra.Rect(x, y, w, h)
    ca_cartographer.dig_ca_region(new_map, target_zone, 3, 2)

    x = libtcod.random_get_int(new_map.rng, old_quarry_stairs[1].dest_position.x + 3, oqs[1].dest_position.x * 3 / 2)
    w = libtcod.random_get_int(new_map.rng, 20, new_map.width - x - 3)
    if old_quarry_stairs[2].dest_position.y < oqs[1].dest_position.y:
        y = libtcod.random_get_int(new_map.rng, oqs[1].dest_position.y + 3, old_quarry_stairs[1].dest_position.y * 3 / 2)
        h = libtcod.random_get_int(new_map.rng, 20, new_map.height - y - 3)
    else:
        y = libtcod.random_get_int(new_map.rng, 3, old_quarry_stairs[1].dest_position.y * 2)
        h = libtcod.random_get_int(new_map.rng, 20, old_quarry_stairs[1].dest_position.y - y - 3)

    target_zone = algebra.Rect(x, y, w, h)
    ca_cartographer.dig_ca_region(new_map, target_zone, 3, 2)


def make_map(player, dungeon_level):
    """
    Creates a new simple map at the given dungeon level.
    Sets player.current_map to the new map, and adds the player as the first
    object.
    """
    old_map = player.current_map

    new_map = map.DungeonMap(MINE_SIZE, MINE_SIZE, dungeon_level)
    new_map.objects.append(player)
    player.current_map = new_map
    player.camera_position = algebra.Location(0, 0)
    new_map.random_seed = libtcod.random_save(0)
    new_map.rng = libtcod.random_new_from_seed(new_map.random_seed)

    oqs = old_map.quarry_stairs
    _link_up_stairs(new_map, oqs)
    _create_entries(new_map, oqs)
    _descend_stairs(new_map, player, oqs)
    _dig_some_caves(new_map, oqs)

    # TODO: build map conecting (not directly!) all three entrances
    # TODO: add inhabitants

    # TEST
    for x in range(new_map.width):
        for y in range(new_map.height):
            new_map._explored[x][y] = True

    new_map.initialize_fov()
    return False