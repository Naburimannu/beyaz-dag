import copy

import libtcodpy as libtcod

import config
import algebra
import map
import log
from components import *
import actions
import miscellany
import bestiary
import quest
import ai
import spells
import ca_cartographer


# Doesn't look good at sizes as small as 40
MINE_SIZE = 70
MINE_SCALE = 5


def _random_position_in_room(room):
    return algebra.Location(libtcod.random_get_int(0, room.x1+1, room.x2-1),
                            libtcod.random_get_int(0, room.y1+1, room.y2-1))


def _check(new_map, candidates, x, y):
    if (x < 0 or y < 0 or x >= new_map.width or y >= new_map.height):
        return
    if new_map.terrain[x][y] == map.TERRAIN_FLOOR:
        candidates.append(algebra.Location(x, y))

def _find_floor_near_room(new_map, room):
    pos = _random_position_in_room(room)
    if new_map.terrain[pos.x][pos.y] == map.TERRAIN_FLOOR:
        return pos
    dist = 0
    candidates = []
    while len(candidates) == 0:
        dist += 1
        for x in range(pos.x - dist, pos.x + dist + 1):
            _check(new_map, candidates, x, pos.y - dist)
            _check(new_map, candidates, x, pos.y + dist)
        for y in range(pos.y - dist + 1, pos.y + dist):
            _check(new_map, candidates, pos.x - dist, y)
            _check(new_map, candidates, pos.x + dist, y)
    return candidates[new_map.rnd(0, len(candidates) - 1)]


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


def _link_up_stairs(new_map, old_map, old_quarry_stairs):
    old_quarry_stairs[1].dest_position = algebra.Location(new_map.width / 2, new_map.height / 2)
    old_quarry_stairs[0].dest_position = old_quarry_stairs[1].dest_position + MINE_SCALE * (old_quarry_stairs[0].pos - old_quarry_stairs[1].pos)
    old_quarry_stairs[2].dest_position = old_quarry_stairs[1].dest_position + MINE_SCALE * (old_quarry_stairs[2].pos - old_quarry_stairs[1].pos)

    map_inset = algebra.Rect(10, 10, new_map.width - 20, new_map.height - 20)
    old_quarry_stairs[0].dest_position.bound(map_inset)
    old_quarry_stairs[2].dest_position.bound(map_inset)

    # print('Map is ' + str(new_map.width) + ' x ' + str(new_map.height))
    # print('Stairs come from ', [i.pos for i in old_quarry_stairs])
    # print('Stairs to mines connect to ', [i.dest_position for i in old_quarry_stairs])

    for i in range(3):
        old_quarry_stairs[i].destination = new_map
        stairs = Object(old_quarry_stairs[i].dest_position, '>', 'mine exit', libtcod.white, always_visible=True)
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
        # print('Room #' + str(i) + ' at ' + str(new_room))
        new_map.rooms.append(new_room)
        new_map.room_entered.append(False)

        new_ctr = new_room.center()
        assert(new_ctr == old_quarry_stairs[i].dest_position)

def _descend_stairs(new_map, player, old_quarry_stairs):
    # print('Player was at ', player.pos)
    for i in range(3):
        if player.pos == old_quarry_stairs[i].pos:
            player.pos = old_quarry_stairs[i].dest_position
            # print('Came down stair #' + str(i) + ' to ' + str(player.pos))
            return

def _dig_some_caves(new_map, old_quarry_stairs):
    new_map.spare_terrain = copy.deepcopy(new_map.terrain) # [[0 for y in range(new_map.height)] for x in range(new_map.width)]

    new_map.cave_zones = []
    x = new_map.rnd(3, old_quarry_stairs[1].dest_position.x / 2)
    w = new_map.rnd(20, old_quarry_stairs[1].dest_position.x - x - 3)
    if old_quarry_stairs[0].dest_position.y < old_quarry_stairs[1].dest_position.y:
        # staircase 0 in top left quadrant, put caves in bottom left quadrant
        y = new_map.rnd(old_quarry_stairs[1].dest_position.y + 3, old_quarry_stairs[1].dest_position.y * 3 / 2)
        h = new_map.rnd(20, new_map.height - y - 3)
    else:
        # staircase 0 in bottom left quadrant, put caves in top left quadrant
        y = new_map.rnd(3, old_quarry_stairs[1].dest_position.y / 2)
        h = new_map.rnd(20, old_quarry_stairs[1].dest_position.y - y - 3)

    target_zone = algebra.Rect(x, y, w, h)
    target_zone.x2 = min(target_zone.x2, new_map.width - 2)
    target_zone.y2 = min(target_zone.y2, new_map.height - 2)
    # print("Target zone 0 ", target_zone)
    ca_cartographer.dig_ca_region(new_map, target_zone, 4, 3)
    new_map.cave_zones.append(target_zone)

    x = new_map.rnd(old_quarry_stairs[1].dest_position.x + 3, old_quarry_stairs[1].dest_position.x * 3 / 2)
    w = new_map.rnd(20, new_map.width - x - 3)
    if old_quarry_stairs[2].dest_position.y < old_quarry_stairs[1].dest_position.y:
        y = new_map.rnd(old_quarry_stairs[1].dest_position.y + 3, old_quarry_stairs[1].dest_position.y * 3 / 2)
        h = new_map.rnd(20, new_map.height - y - 3)
    else:
        y = new_map.rnd(3, old_quarry_stairs[1].dest_position.y / 2)
        h = new_map.rnd(20, old_quarry_stairs[1].dest_position.y - y - 3)

    target_zone = algebra.Rect(x, y, w, h)
    target_zone.x2 = min(target_zone.x2, new_map.width - 2)
    target_zone.y2 = min(target_zone.y2, new_map.height - 2)
    # print("Target zone 1 ", target_zone)
    ca_cartographer.dig_ca_region(new_map, target_zone, 4, 3)
    new_map.cave_zones.append(target_zone)


def _consider_terminal_room(new_map, x, y):
    new_room = algebra.Rect(x - 2, y - 2, 4, 4)
    _create_room(new_map, new_room)
    count = len(new_map.rooms)
    new_map.rooms.append(new_room)
    new_map.room_entered.append(False)
    for ii in range(x - 2, x + 3):
        for jj in range(y - 2, y + 3):
            if (ii >= 0 and jj >= 0 and ii < new_map.width and jj < new_map.height):
                new_map.room[ii][jj] = count


def _dig_about(new_map, room_rect, left_min, left_max, right_min, right_max):
    x = room_rect.center().x
    top = new_map.rnd(3, room_rect.y1 / 2)
    _create_v_tunnel(new_map, room_rect.y1, top, x)
    _consider_terminal_room(new_map, x, top)
    cross_tunnel_count = new_map.rnd(2, 4)
    tunnel_interval = (room_rect.y1 - 2 - top) / cross_tunnel_count
    for i in range(cross_tunnel_count):
        y = new_map.rnd(0, tunnel_interval - 1) + top + i * tunnel_interval
        if new_map.cave_zones[0].contains(algebra.Location(x, y)):
            continue
        left = new_map.rnd(left_min, left_max)
        right = new_map.rnd(right_min, right_max)
        _create_h_tunnel(new_map, left, right, y)
        _consider_terminal_room(new_map, left, y)
        _consider_terminal_room(new_map, right, y)

    bottom = new_map.rnd(room_rect.y2 + (new_map.height - room_rect.y2) / 2, new_map.height - 3)
    _create_v_tunnel(new_map, room_rect.y2, bottom, x)
    _consider_terminal_room(new_map, x, bottom)
    cross_tunnel_count = new_map.rnd(2, 4)
    tunnel_interval = (bottom - room_rect.y2 - 2) / cross_tunnel_count
    for i in range(cross_tunnel_count):
        y = new_map.rnd(0, tunnel_interval - 1) + room_rect.y2 + 3 + i * tunnel_interval
        if new_map.cave_zones[0].contains(algebra.Location(x, y)):
            continue
        left = new_map.rnd(left_min, left_max)
        right = new_map.rnd(right_min, right_max)
        _create_h_tunnel(new_map, left, right, y)
        _consider_terminal_room(new_map, left, y)
        _consider_terminal_room(new_map, right, y)


def _dig_mine_tunnels(new_map):
    x = new_map.rooms[0].center().x
    _dig_about(new_map, new_map.rooms[0], 3, x / 2, x + 3, new_map.width / 2 + 3)
    x = new_map.rooms[1].center().x
    _dig_about(new_map, new_map.rooms[1], x / 2, x - 3, x + 3, x * 3 / 2)
    x = new_map.rooms[2].center().x
    _dig_about(new_map, new_map.rooms[2], new_map.width / 2 - 3,
               x - 3, x + (new_map.width - x) / 2, new_map.width - 3)


def _dungeon_exploration(self, player):
    delta = 0
    room = self.room[player.pos.x][player.pos.y]
    if room >= 0 and not self.room_entered[room]:
        self.room_entered[room] = True
        delta += config.REGION_EXPLORATION_SP
    if delta > 0:
        player.skill_points += delta
        point = 'point'
        if delta > 1:
            point += 's'
        log.message('You gained ' + str(delta) + ' skill ' + point + ' for exploration.')


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
    _dig_mine_tunnels(new_map)

    map_bounds = algebra.Rect(1, 1, new_map.width-1, new_map.height-1)
    for x in range(1, new_map.width-1):
        for y in range(1, new_map.height-1):
            if libtcod.random_get_float(new_map.rng, 0., 1.) < 0.2:
                new_map.terrain[x][y] = map.TERRAIN_GROUND

    ca_cartographer._generation(new_map, map_bounds, 7, 1)
    ca_cartographer._generation(new_map, map_bounds, 5, 1)

    # Redig the initial rooms because the CA can fill in the stairs
    for i in range(3):
        _create_room(new_map, new_map.rooms[i])

    for i in range(3):
        stair_pos = old_quarry_stairs[i].dest_position
        ca_cartographer._floodfill(new_map, stair_pos.x, stair_pos.y,
            map.TERRAIN_GROUND, map.TERRAIN_FLOOR)

    for x in range(1, new_map.width-1):
        for y in range(1, new_map.height-1):
            if new_map.terrain[x][y] == map.TERRAIN_GROUND:
                new_map.terrain[x][y] = map.TERRAIN_WALL

    #for x in range(0, new_map.width):
    #    new_map.terrain[x][0] = map.TERRAIN_WALL
    #    new_map.terrain[x][new_map.height-1] = map.TERRAIN_WALL
    #for y in range(0, new_map.height):
    #    new_map.terrain[0][y] = map.TERRAIN_WALL
    #    new_map.terrain[new_map.width-1][y] = map.TERRAIN_WALL

    zone_divisor = MINE_SIZE / 3
    slime_zone = new_map.rnd(0, 2)
    while True:
        undead_zone = new_map.rnd(0, 2)
        if undead_zone != slime_zone:
            break

    for r in range(3, len(new_map.rooms)):
        if new_map.rnd(1, 4) < 3:
            room = new_map.rooms[r]
            zone = room.center().x / zone_divisor
            if zone == slime_zone:
                if new_map.rnd(1, 2) == 1:
                    bestiary.slime(new_map, _find_floor_near_room(new_map, room), player)
                    bestiary.slime(new_map, _find_floor_near_room(new_map, room), player)
                else:
                    bestiary.jelly(new_map, _find_floor_near_room(new_map, room), player)
            elif zone == undead_zone:
                bestiary.ghul(new_map, _find_floor_near_room(new_map, room), player)
            else:
                bestiary.worm(new_map, _find_floor_near_room(new_map, room), player)

    r = new_map.rnd(3, len(new_map.rooms) - 1)
    pos = new_map.rooms[r].center()
    while new_map.is_blocked_at(pos):
        pos += actions.random_direction()

    new_map.objects.insert(0, Object(pos, '%', "hero's corpse", libtcod.dark_red))
    sword = miscellany.the_black_sword()
    sword.pos = pos
    new_map.objects.insert(0, sword)

    new_map.initialize_fov()
    new_map.xp_visit = _dungeon_exploration
    return False  # Don't need to generate stairs in caller thanks to _link_up_stairs()