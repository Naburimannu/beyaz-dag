import libtcodpy as libtcod

import algebra
import map
import actions
import ai

import miscellany
import bestiary

MIN_CARAVANSERAI_SIZE = 14
MAX_CARAVANSERAI_SIZE = 26
BANDIT_COUNT_GOAL = 3

def _new_item(actor, obj):
    actor.inventory.append(obj)
    obj.always_visible = True


def _new_equipment(actor, obj):
    _new_item(actor, obj)
    actions.equip(actor, obj.equipment, False)


def _random_position_in_rect(room):
    """
    Given a rect, return an algebra.Location *inside* the rect (not along the borders)
    """
    return algebra.Location(libtcod.random_get_int(0, room.x1+1, room.x2-1),
                            libtcod.random_get_int(0, room.y1+1, room.y2-1))


def inhabit_caravanserai(new_map, player):
    # print('Caravanserai between ' + str(map.caravanserai.x1) + ' ' + str(map.caravanserai.y1) +
    #       ' and ' + str(map.caravanserai.x2) + ' ' + str(map.caravanserai.y2))
    for i in range(BANDIT_COUNT_GOAL):
        bandit = bestiary.bandit(new_map,
            _random_position_in_rect(new_map.caravanserai), player)

        choice = libtcod.random_get_int(0, 1, 3)
        # HACK: guarantee at least one spear
        if i == 0:
            choice = 2

        if choice == 1:
            _new_equipment(bandit, miscellany.sword())
        elif choice == 2:
            _new_equipment(bandit, miscellany.spear())
        else:
            _new_equipment(bandit, miscellany.arrow(4))
            _new_equipment(bandit, miscellany.horn_bow())
            bandit.name = 'bandit archer'
            bandit.ai._turn_function = ai.hostile_archer
            bandit.game_state = 'playing'


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
    new_map.objects.append(door_obj)


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

    new_map.caravanserai = bounds

    if (bounds.width > bounds.height):
        new_map.terrain[center.x][bounds.y2] = map.TERRAIN_GROUND
        new_map.terrain[bounds.x2][center.y+2] = map.TERRAIN_GROUND

        # Rooms in west half
        wall_offset = libtcod.random_get_int(new_map.rng,
            2, (center.x - bounds.x1) / 3)
        for y in range(bounds.y1, bounds.y2+1):
            new_map.terrain[center.x - wall_offset][y] = map.TERRAIN_WALL

        north_door = libtcod.random_get_int(new_map.rng, bounds.y1+1, center.y-2)
        _place_door(new_map, algebra.Location(center.x - wall_offset, north_door))
        south_door = libtcod.random_get_int(new_map.rng, center.y+1, bounds.y2-1)
        _place_door(new_map, algebra.Location(center.x - wall_offset, south_door))

        wall_y = (north_door + south_door) / 2
        for x in range(bounds.x1, center.x - wall_offset):
            new_map.terrain[x][wall_y] = map.TERRAIN_WALL

        # outer rooms
        courtyard_mid_x = (center.x - wall_offset + bounds.x2) / 2
        outer_wall_y = (bounds.y1 + center.y+2)/2
        if outer_wall_y < north_door:
            outer_wall_y = north_door + 1
        for x in range(center.x - wall_offset, bounds.x2):
            new_map.terrain[x][outer_wall_y] = map.TERRAIN_WALL

        west_door = libtcod.random_get_int(new_map.rng, center.x - wall_offset + 2, courtyard_mid_x - 2)
        _place_door(new_map, algebra.Location(west_door, outer_wall_y))
        east_door = libtcod.random_get_int(new_map.rng, courtyard_mid_x + 2, bounds.x2 - 2)
        _place_door(new_map, algebra.Location(west_door, outer_wall_y))

        wall_x = (east_door + west_door) / 2
        for y in range(bounds.y1, outer_wall_y):
            new_map.terrain[wall_x][y] = map.TERRAIN_WALL

        courtyard_bounds = algebra.Rect(
            center.x - wall_offset + 1, outer_wall_y + 1,
            bounds.x2 - center.x + wall_offset - 1,
            bounds.y2 - outer_wall_y - 1)

    else:
        new_map.terrain[center.x+2][bounds.y2] = map.TERRAIN_GROUND
        new_map.terrain[bounds.x2][center.y] = map.TERRAIN_GROUND

        # Rooms in north half
        wall_offset = libtcod.random_get_int(new_map.rng,
            2, (center.y - bounds.y1) / 3)
        for x in range(bounds.x1, bounds.x2+1):
            new_map.terrain[x][center.y - wall_offset] = map.TERRAIN_WALL

        west_door = libtcod.random_get_int(new_map.rng, bounds.x1+1, center.x-2)
        _place_door(new_map, algebra.Location(west_door, center.y - wall_offset))
        east_door = libtcod.random_get_int(new_map.rng, center.x+1, bounds.x2-1)
        _place_door(new_map, algebra.Location(east_door, center.y - wall_offset))

        wall_x = (east_door + west_door) / 2
        for y in range(bounds.y1, center.y - wall_offset):
            new_map.terrain[wall_x][y] = map.TERRAIN_WALL

        # outer rooms
        courtyard_mid_y = (center.y - wall_offset + bounds.y2) / 2
        outer_wall_x = (bounds.x1 + center.x+2)/2
        if outer_wall_x < west_door:
            outer_wall_x = west_door + 1
        for y in range(center.y - wall_offset, bounds.y2):
            new_map.terrain[outer_wall_x][y] = map.TERRAIN_WALL

        north_door = libtcod.random_get_int(new_map.rng, center.y - wall_offset + 2, courtyard_mid_y - 2)
        _place_door(new_map, algebra.Location(outer_wall_x, north_door))
        south_door = libtcod.random_get_int(new_map.rng, courtyard_mid_y + 2, bounds.y2 - 2)
        _place_door(new_map, algebra.Location(outer_wall_x, south_door))

        wall_y = (south_door + north_door) / 2
        for x in range(bounds.x1, outer_wall_x):
            new_map.terrain[x][wall_y] = map.TERRAIN_WALL

        courtyard_bounds = algebra.Rect(
            outer_wall_x + 1, center.y - wall_offset + 1,
            bounds.x2 - outer_wall_x - 1,
            bounds.y2 - center.y + wall_offset - 1)

    _clear_courtyard(new_map, courtyard_bounds)

    # TODO: create an upstairs and a cellar
    # TODO: track these rooms correctly and populate them intentionally
    # TODO: generate total bandit population and then divide between areas

