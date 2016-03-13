# Copyright 2016 Thomas C. Hudson
# Governed by the license described in LICENSE.txt
import libtcodpy as libtcod

import config
import algebra
import log
import map
from components import *
import actions
import bestiary
import miscellany
import ai
import spells

import mine_cartographer
import ca_cartographer

ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 40

FINAL_DUNGEON_SIZE = 80


def _random_position_in_room(room):
    return algebra.Location(libtcod.random_get_int(0, room.x1+1, room.x2-1),
                            libtcod.random_get_int(0, room.y1+1, room.y2-1))


def _new_item(actor, obj):
    actor.inventory.append(obj)
    obj.always_visible = True


def _new_equipment(actor, obj):
    _new_item(actor, obj)
    actions.equip(actor, obj.equipment, False)



def _create_room(new_map, room, room_number):
    """
    Make the tiles in a rectangle passable
    """
    for x in range(room.x1 + 1, room.x2):
        for y in range(room.y1 + 1, room.y2):
            new_map.terrain[x][y] = map.TERRAIN_GROUND
            new_map.room[x][y] = room_number


def _create_h_tunnel(new_map, x1, x2, y):
    for x in range(min(x1, x2), max(x1, x2) + 1):
        new_map.terrain[x][y] = map.TERRAIN_GROUND


def _create_v_tunnel(new_map, y1, y2, x):
    for y in range(min(y1, y2), max(y1, y2) + 1):
        new_map.terrain[x][y] = map.TERRAIN_GROUND


def _place_door(new_map, pos):
    new_map.terrain[pos.x][pos.y] = map.TERRAIN_FLOOR
    door_obj = miscellany.closed_door(pos)
    new_map.objects.insert(0, door_obj)


def _check_door_configuration(new_map, pos, direction):
    if (new_map.terrain(pos + direction) == map.TERRAIN_FLOOR and
            new_map.terrain(pos + direction.left) == map.TERRAIN_FLOOR and
            new_map.terrain(pos + direction.right) == map.TERRAIN_FLOOR and
            new_map.terrain(pos - direction) == map.TERRAIN_FLOOR):
        return True
    return False

def _add_doors(new_map):
    for x in range(1, new_map.width-1):
        for y in range(1, new_map.height-1):
            pos = algebra.Location(x, y)
            if new_map.terrain[x][y] != map.TERRAIN_FLOOR:
                continue
            adjacent_walls = 0
            for ii in range(x-1, x+2):
                for jj in range(y-1, y+2):
                    if new_map.terrain[x][y] == map.TERRAIN_WALL:
                        adjacent_walls += 1
            if adjacent_walls != 4:
                continue
            if (_check_door_configuration(new_map, pos, algebra.north) or
                    _check_door_configuration(new_map, pos, algebra.east) or
                    _check_door_configuration(new_map, pos, algebra.south) or
                    _check_door_configuration(new_map, pos, algebra.west)):
                _place_door(new_map, pos)


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


def make_final_map(player, dungeon_level):
    """
    """
    old_map = player.current_map

    new_map = map.DungeonMap(FINAL_DUNGEON_SIZE, FINAL_DUNGEON_SIZE, dungeon_level)
    new_map.objects.append(player)
    player.current_map = new_map
    player.camera_position = algebra.Location(0, 0)
    new_map.random_seed = libtcod.random_save(0)
    new_map.rng = libtcod.random_new_from_seed(new_map.random_seed)

    entry_stairs = old_map.dungeon_stairs
    mine_cartographer._link_up_stairs(new_map, old_map, entry_stairs)
    mine_cartographer._create_entries(new_map, entry_stairs)
    mine_cartographer._descend_stairs(new_map, player, entry_stairs)

    num_rooms = 3
    for r in range(3, MAX_ROOMS):
        w = libtcod.random_get_int(new_map.rng, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
        h = libtcod.random_get_int(new_map.rng, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
        x = libtcod.random_get_int(new_map.rng, 0, new_map.width - w - 1)
        y = libtcod.random_get_int(new_map.rng, 0, new_map.height - h - 1)

        new_room = map.Room(x, y, w, h)

        failed = False
        for other_room in new_map.rooms:
            if new_room.intersect(other_room):
                failed = True
                break

        if not failed:
            # There are no intersections, so this room is valid.
            _create_room(new_map, new_room, num_rooms)
            new_ctr = new_room.center()
            prev_ctr = new_map.rooms[num_rooms-3].center()

            if libtcod.random_get_int(new_map.rng, 0, 1) == 1:
                _create_h_tunnel(new_map, prev_ctr.x, new_ctr.x, prev_ctr.y)
                _create_v_tunnel(new_map, prev_ctr.y, new_ctr.y, new_ctr.x)
            else:
                _create_v_tunnel(new_map, prev_ctr.y, new_ctr.y, prev_ctr.x)
                _create_h_tunnel(new_map, prev_ctr.x, new_ctr.x, new_ctr.y)

            new_map.rooms.append(new_room)
            new_map.room_entered.append(False)
            num_rooms += 1

    # TODO: should be floodfill from one stair, make *sure* the other two are
    # connected
    for i in range(3):
        stair_pos = entry_stairs[i].dest_position
        ca_cartographer._floodfill(new_map, stair_pos.x, stair_pos.y,
            map.TERRAIN_GROUND, map.TERRAIN_FLOOR)

    _add_doors(new_map)

    for i in range(3, num_rooms - 1):
        if (new_map.rnd(1, 2) == 1):
            foe = bestiary.dvergr(new_map, new_map.rooms[i].center(), player)
            _new_equipment(foe, miscellany.handaxe())
            _new_equipment(foe, miscellany.roundshield())
            if new_map.rnd(1, 2) == 1:
                _new_item(foe, miscellany.bandage(1))
            if new_map.rnd(1, 2) == 1:
                _new_item(foe, miscellany.kumiss(1))

    foe = bestiary.tepegoz(new_map, new_ctr, player)
    _new_equipment(foe, miscellany.maguffin())
    _new_equipment(foe, miscellany.spear())
    _new_equipment(foe, miscellany.roundshield())

    new_map.initialize_fov()
    new_map.xp_visit = _dungeon_exploration
    return False  # Don't need to generate stairs in caller thanks to _link_up_stairs()
