# Copyright 2016 Thomas C. Hudson
# Governed by the license described in LICENSE.txt
import libtcodpy as libtcod

import algebra
import map
import actions
import ai

import miscellany
import bestiary

MIN_CARAVANSERAI_SIZE = 14
MAX_CARAVANSERAI_SIZE = 26
BANDIT_COUNT_GOAL = 4


class Caravanserai(object):
    def __init__(self, bounds):
        self.bounds = bounds
        self.courtyard = None
        self.rooms = []


def _new_item(actor, obj):
    actor.inventory.append(obj)
    obj.always_visible = True


def _new_equipment(actor, obj):
    _new_item(actor, obj)
    actions.equip(actor, obj.equipment, False)


def _random_position_in_rect(new_map, room):
    """
    Given a rect, return an algebra.Location *inside* the rect (not along the borders)
    """
    return algebra.Location(new_map.rnd(room.x1+1, room.x2-1),
                            new_map.rnd(room.y1+1, room.y2-1))


def _add_one_bandit(new_map, rect, player, force_spear=False):
    bandit = bestiary.bandit(new_map, _random_position_in_rect(new_map, rect), player)

    choice = new_map.rnd(1, 3)
    if force_spear or choice == 1:
        _new_equipment(bandit, miscellany.spear())
        if new_map.rnd(1, 3) < 2:
            _new_equipment(bandit, miscellany.roundshield())
    elif choice == 2:
        _new_equipment(bandit, miscellany.sword())
        if new_map.rnd(1, 3) < 2:
            _new_equipment(bandit, miscellany.roundshield())
    else:
        _new_equipment(bandit, miscellany.arrow(4))
        _new_equipment(bandit, miscellany.horn_bow())
        bandit.name = 'bandit archer'
        bandit.ai._turn_function = ai.hostile_archer
        bandit.game_state = 'playing'

    if new_map.rnd(1, 2) == 1:
        _new_equipment(bandit, miscellany.leather_armor())

    if new_map.rnd(1, 3) < 3:
        _new_item(bandit, miscellany.bandage(1))
    if new_map.rnd(1, 3) == 1:
        _new_item(bandit, miscellany.kumiss(1))


def _add_loot(new_map, function, count):
    r = new_map.rnd(0, len(new_map.caravanserai.rooms) - 1)
    pos = _random_position_in_rect(new_map, new_map.caravanserai.rooms[r])
    # probably horribly nonpythonic
    if count > 1:
        loot = function(count)
    else:
        loot = function()
    loot.pos = pos
    new_map.objects.insert(0, loot)


def inhabit_caravanserai(new_map, player):
    # print('Caravanserai between ' + str(map.caravanserai.x1) + ' ' + str(map.caravanserai.y1) +
    #       ' and ' + str(map.caravanserai.x2) + ' ' + str(map.caravanserai.y2))
    courtyard_count = new_map.rnd(1, 2)
    for i in range(courtyard_count):
        _add_one_bandit(new_map, new_map.caravanserai.courtyard, player)
    # HACK: guarantee at least one spear
    for i in range(courtyard_count, BANDIT_COUNT_GOAL):
        r = new_map.rnd(0, len(new_map.caravanserai.rooms) - 1)
        _add_one_bandit(new_map, new_map.caravanserai.rooms[r], player, (i == courtyard_count))


def _place_caravanserai(new_map, size):
    """
    Find a 3x3 region of desert near but not on the east or south edges.
    """
    # find a space to fit it along the eastern edge,
    # starting from the north
    found_y = -1
    rows = 0
    for y in range(2, 19):
        cols = 0
        for x in range(19 - size, 19):
            # print(x, y, new_map.region_terrain[x*20+y])
            if new_map.region_terrain[x*20+y] != 'desert':
                break
            cols += 1
        if cols < size:
            rows = 0
            continue
        rows += 1
        if rows == size:
            found_y = y - size + 1
            break

    if found_y > 1:
        # print('Can place size ' + str(size) + ' at y=' + str(found_y))
        return (19 - size, found_y)

    # find a space to fit it along the southern edge,
    # starting from the west
    found_x = -1
    rows = 0
    for x in range(2, 19):
        cols = 0
        for y in range(19 - size, 19):
            # print(x, y, new_map.region_terrain[x*20+y])
            if new_map.region_terrain[x*20+y] != 'desert':
                break
            cols += 1
        if cols < size:
            rows = 0
            continue
        rows += 1
        if rows == size:
            found_x = x - size + 1
            break

    if found_x > 1:
        # print('Can place size ' + str(size) + ' at x=' + str(found_x))
        return (found_x, 19 - size)

    return (-1, -1)



def _place_door(new_map, pos):
    new_map.terrain[pos.x][pos.y] = map.TERRAIN_FLOOR
    door_obj = miscellany.closed_door(pos)
    new_map.objects.insert(0, door_obj)


def _clear_outside_walls(new_map, bounds):
    """
    Simple way to make it unlikely that terrain will block one of
    the entrance gates.
    """
    for x in range(bounds.x1-1, bounds.x2+2):
        if map.terrain_types[new_map.terrain[x][bounds.y1-1]].blocks:
            new_map.terrain[x][bounds.y1-1] = map.TERRAIN_GROUND
        if map.terrain_types[new_map.terrain[x][bounds.y2+1]].blocks:
            new_map.terrain[x][bounds.y2+1] = map.TERRAIN_GROUND

    for y in range(bounds.y1-1, bounds.y2+2):
        if map.terrain_types[new_map.terrain[bounds.x1-1][y]].blocks:
            new_map.terrain[bounds.x1-1][y] = map.TERRAIN_GROUND
        if map.terrain_types[new_map.terrain[bounds.x2+1][y]].blocks:
            new_map.terrain[bounds.x2+1][y] = map.TERRAIN_GROUND


def _clear_courtyard(new_map, courtyard_bounds):
    for x in range(courtyard_bounds.x1, courtyard_bounds.x2):
        for y in range(courtyard_bounds.y1, courtyard_bounds.y2):
            if new_map.terrain[x][y] != map.TERRAIN_SLOPE:
                new_map.terrain[x][y] = map.TERRAIN_GROUND


def make_caravanserai(new_map):
    size = 3
    (found_x, found_y) = _place_caravanserai(new_map, size)
    if found_x < 0 or found_y < 0:
        # Better undersized than none at all?
        size = 2
        (found_x, found_y) = _place_caravanserai(new_map, size)
        if found_x < 0 or found_y < 0:
            print("Couldn't fit caravanserai anywhere; sorry!")
            new_map.caravanserai = None
            return

    tl = new_map.region_seeds[found_x * 20 + found_y]
    br = new_map.region_seeds[found_x * 20 + found_y + (size - 1) * 20 + (size - 1)]
    print('Caravanserai stretches from ', tl, ' to ', br, ' or so')
    bounds = algebra.Rect(tl[0], tl[1],
                          max(min(br[0] - tl[0] + 1, MAX_CARAVANSERAI_SIZE),
                              MIN_CARAVANSERAI_SIZE),
                          max(min(br[1] - tl[1] + 1, MAX_CARAVANSERAI_SIZE),
                              MIN_CARAVANSERAI_SIZE))
    for x in range(bounds.x1, bounds.x2+1):
        for y in range(bounds.y1, bounds.y2+1):
            if (x == bounds.x1 or x == bounds.x2 or
                y == bounds.y1 or y == bounds.y2):
                new_map.terrain[x][y] = map.TERRAIN_WALL
            else:
                new_map.terrain[x][y] = map.TERRAIN_FLOOR
    _clear_outside_walls(new_map, bounds)

    # Cut gates in it facing east and south
    center = bounds.center()

    new_map.caravanserai = Caravanserai(bounds)

    if (bounds.width > bounds.height):
        new_map.terrain[center.x][bounds.y2] = map.TERRAIN_GROUND
        new_map.terrain[bounds.x2][center.y+2] = map.TERRAIN_GROUND

        # Rooms in west half
        wall_offset = new_map.rnd(2, (center.x - bounds.x1) / 3)
        for y in range(bounds.y1, bounds.y2+1):
            new_map.terrain[center.x - wall_offset][y] = map.TERRAIN_WALL

        north_door = new_map.rnd(bounds.y1+1, center.y-2)
        _place_door(new_map, algebra.Location(center.x - wall_offset, north_door))
        south_door = new_map.rnd(center.y+1, bounds.y2-1)
        _place_door(new_map, algebra.Location(center.x - wall_offset, south_door))

        wall_y = (north_door + south_door) / 2
        for x in range(bounds.x1, center.x - wall_offset):
            new_map.terrain[x][wall_y] = map.TERRAIN_WALL

        new_map.caravanserai.rooms.append(
            algebra.Rect(bounds.x1, bounds.y1, center.x - wall_offset - bounds.x1, wall_y - bounds.y1))
        new_map.caravanserai.rooms.append(
            algebra.Rect(bounds.x1, wall_y, center.x - wall_offset - bounds.x1, bounds.y2 - wall_y))

        # outer rooms
        courtyard_mid_x = (center.x - wall_offset + bounds.x2) / 2
        outer_wall_y = (bounds.y1 + center.y+2)/2
        if outer_wall_y < north_door:
            outer_wall_y = north_door + 1
        for x in range(center.x - wall_offset, bounds.x2):
            new_map.terrain[x][outer_wall_y] = map.TERRAIN_WALL

        west_door = new_map.rnd(center.x - wall_offset + 2, courtyard_mid_x - 2)
        _place_door(new_map, algebra.Location(west_door, outer_wall_y))
        east_door = new_map.rnd(courtyard_mid_x + 2, bounds.x2 - 2)
        _place_door(new_map, algebra.Location(west_door, outer_wall_y))

        wall_x = (east_door + west_door) / 2
        for y in range(bounds.y1, outer_wall_y):
            new_map.terrain[wall_x][y] = map.TERRAIN_WALL

        new_map.caravanserai.rooms.append(
            algebra.Rect(center.x - wall_offset, bounds.y1, wall_x - center.x + wall_offset, wall_y - bounds.y1))
        new_map.caravanserai.rooms.append(
            algebra.Rect(wall_x, bounds.y1, center.x - wall_offset - bounds.x1, bounds.x2 - wall_x))

        courtyard_bounds = algebra.Rect(
            center.x - wall_offset + 1, outer_wall_y + 1,
            bounds.x2 - center.x + wall_offset - 1,
            bounds.y2 - outer_wall_y - 1)

    else:
        new_map.terrain[center.x+2][bounds.y2] = map.TERRAIN_GROUND
        new_map.terrain[bounds.x2][center.y] = map.TERRAIN_GROUND

        # Rooms in north half
        wall_offset = new_map.rnd(2, (center.y - bounds.y1) / 3)
        for x in range(bounds.x1, bounds.x2+1):
            new_map.terrain[x][center.y - wall_offset] = map.TERRAIN_WALL

        west_door = new_map.rnd(bounds.x1+1, center.x-2)
        _place_door(new_map, algebra.Location(west_door, center.y - wall_offset))
        east_door = new_map.rnd(center.x+1, bounds.x2-1)
        _place_door(new_map, algebra.Location(east_door, center.y - wall_offset))

        wall_x = (east_door + west_door) / 2
        for y in range(bounds.y1, center.y - wall_offset):
            new_map.terrain[wall_x][y] = map.TERRAIN_WALL

        new_map.caravanserai.rooms.append(
            algebra.Rect(bounds.x1, bounds.y1, wall_x - bounds.x1, center.y - wall_offset - bounds.y1))
        new_map.caravanserai.rooms.append(
            algebra.Rect(wall_x, bounds.y1, bounds.x2 - center.x + wall_offset, center.y - wall_offset - bounds.y1))

        # outer rooms
        courtyard_mid_y = (center.y - wall_offset + bounds.y2) / 2
        outer_wall_x = (bounds.x1 + center.x+2)/2
        if outer_wall_x < west_door:
            outer_wall_x = west_door + 1
        for y in range(center.y - wall_offset, bounds.y2):
            new_map.terrain[outer_wall_x][y] = map.TERRAIN_WALL

        north_door = new_map.rnd(center.y - wall_offset + 2, courtyard_mid_y - 2)
        _place_door(new_map, algebra.Location(outer_wall_x, north_door))
        south_door = new_map.rnd(courtyard_mid_y + 2, bounds.y2 - 2)
        _place_door(new_map, algebra.Location(outer_wall_x, south_door))

        wall_y = (south_door + north_door) / 2
        for x in range(bounds.x1, outer_wall_x):
            new_map.terrain[x][wall_y] = map.TERRAIN_WALL

        new_map.caravanserai.rooms.append(
            algebra.Rect(bounds.x1, center.y - wall_offset, center.x - wall_offset - bounds.x1, wall_y - center.y + wall_offset))
        new_map.caravanserai.rooms.append(
            algebra.Rect(bounds.x1, wall_y, center.x - wall_offset - bounds.x1, bounds.x2 - wall_y))

        courtyard_bounds = algebra.Rect(
            outer_wall_x + 1, center.y - wall_offset + 1,
            bounds.x2 - outer_wall_x - 1,
            bounds.y2 - center.y + wall_offset - 1)

    print('Caravanserai court ', courtyard_bounds)
    print('Caravanserai rooms ',
          new_map.caravanserai.rooms[0], new_map.caravanserai.rooms[1],
          new_map.caravanserai.rooms[2], new_map.caravanserai.rooms[3])

    new_map.caravanserai.courtyard = courtyard_bounds
    _clear_courtyard(new_map, courtyard_bounds)

    # TODO: create an upstairs and a cellar

    _add_loot(new_map, miscellany.leather_armor, 1)
    _add_loot(new_map, miscellany.bandage, 3)
    _add_loot(new_map, miscellany.bandage, 3)
    _add_loot(new_map, miscellany.kumiss, 4)
    _add_loot(new_map, miscellany.arrow, 6)
