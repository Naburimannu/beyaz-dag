import libtcodpy as libtcod

import cProfile
import scipy.spatial.kdtree

import config
import algebra
import map
from components import *
import miscellany
import bestiary
import ai
import actions
import spells
import quest
import ca_cartographer

ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 30

MAX_CARAVANSERAI_SIZE = 24
QUARRY_ELEVATION = 3

def _random_position_in_rect(room):
    """
    Given a rect, return an algebra.Location *inside* the rect (not along the borders)
    """
    return algebra.Location(libtcod.random_get_int(0, room.x1+1, room.x2-1),
                            libtcod.random_get_int(0, room.y1+1, room.y2-1))


def _random_position_in_region(new_map, region):
    """
    Given a region of a map, return an algebra.Location in the region
    """
    center = new_map.region_seeds[region]
    while True:
        candidate = algebra.Location(
                libtcod.random_get_int(0, center[0]-5, center[0]+5),
                libtcod.random_get_int(0, center[1]-5, center[1]+5))
        if new_map.region[candidate.x][candidate.y] == region:
            return candidate


def _random_choice_index(chances):
    """
    choose one option from list of chances, returning its index
    """
    dice = libtcod.random_get_int(0, 1, sum(chances))

    running_sum = 0
    choice = 0
    for w in chances:
        running_sum += w

        if dice <= running_sum:
            return choice
        choice += 1


def _random_choice(chances_dict):
    """
    choose one option from dictionary of chances, returning its key
    """
    chances = chances_dict.values()
    strings = chances_dict.keys()

    return strings[_random_choice_index(chances)]


def _place_random_creatures(new_map, player):
    start_region = new_map.region[player.pos.x][player.pos.y]
    terrain_chances = {
        'lake' : { None : 10 },
        'marsh' : { None : 10, bestiary.swamp_goblin : 10 },
        'desert' : { None : 20, bestiary.hyena : 5, bestiary.gazelle : 10 },
        'scrub' : { None : 20, bestiary.hyena : 2, bestiary.gazelle : 4,
                    bestiary.deer : 4, bestiary.wolf : 2 },
        'forest' : { None : 20, bestiary.deer : 10, bestiary.wolf : 5,
                     bestiary.bear : 3 },
        'rock' : { None : 10, bestiary.snow_leopard : 1 },
        'ice' : { None : 10, bestiary.snow_leopard : 1 }
    }
    for r in range(len(new_map.region_seeds)):
        if (r == start_region or
            (new_map.quarry_region and r == new_map.quarry_region)):
            continue
        fn = _random_choice(terrain_chances[new_map.region_terrain[r]])
        if fn is not None:
            pos = algebra.Location(new_map.region_seeds[r][0], new_map.region_seeds[r][1])
            while new_map.is_blocked_at(pos):
                pos += actions.random_direction()
                pos.bound(algebra.Rect(0, 0, new_map.width-1, new_map.height-1))
            if new_map.caravanserai and new_map.caravanserai.contains(pos):
                continue
            # print('Creature in region ' + str(r) + ' at ' + str(pos.x) + ' ' + str(pos.y))
            fn(new_map, pos, player)


def _new_item(actor, obj):
    actor.inventory.append(obj)
    obj.always_visible = True


def _new_equipment(actor, obj):
    _new_item(actor, obj)
    actions.equip(actor, obj.equipment, False)


def _inhabit_rotunda(new_map, peak):
    goddess = Object(algebra.Location(peak[0], peak[1]), '@', 'The White Goddess', libtcod.white, blocks=True,
        interactable=Interactable(use_function=quest.goddess_charge))
    new_map.objects.append(goddess)


def _inhabit_caravanserai(new_map, player):
    # print('Caravanserai between ' + str(map.caravanserai.x1) + ' ' + str(map.caravanserai.y1) +
    #       ' and ' + str(map.caravanserai.x2) + ' ' + str(map.caravanserai.y2))
    for i in range(3):
        bandit = bestiary.bandit(new_map,
            _random_position_in_rect(new_map.caravanserai), player)

        choice = libtcod.random_get_int(0, 1, 3)
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


def _inhabit_quarry(new_map, player):
    # print('Quarry near ', new_map.region_seeds[new_map.quarry_region])
    for i in range(3):
        ghul = bestiary.ghul(new_map,
            _random_position_in_region(new_map, new_map.quarry_region),
            player)


def _interpolate_heights(new_map, peak):
    print('Climbing the shoulders of the mountain')
    for p in range(len(new_map.region_elevations)):
        if new_map.region_elevations[p] > -1:
            continue
        dx = new_map.region_seeds[p][0] - peak[0]
        dy = new_map.region_seeds[p][1] - peak[1]
        p_distance = math.sqrt(dx*dx+dy*dy)

        # Hack - conical mountain, but not horrible.
        if dx < 0:
            cand_x = peak[0]
        elif dx == 0:
            cand_x = new_map.width
        else:
            cand_x = new_map.width - peak[0]
        if dy < 0:
            cand_y = peak[1]
        elif dy == 0:
            cand_y = new_map.height
        else:
            cand_y = new_map.height - peak[1]
        edge_distance = min(cand_x, cand_y)

        elevation = int(9 * ((edge_distance - p_distance) / edge_distance))
        new_map.region_elevations[p] = max(elevation, 0)


def _ensure_penultimate_height(new_map, peak, region_tree):
    """
    Worldgen will frequently generate a map with a peak at elevation 9,
    and nothing else above elevation 7, which prevents easy access to
    the summit.
    """
    for r in new_map.region_elevations:
        if r == 8:
            print('Found height 8 at index ' + str(r))
            return

    (d, i) = region_tree.query(peak, 8)
    for r in i:
        if new_map.region_elevations[r] == 9:
            continue
        if new_map.region_elevations[r] == 8:
            print('Error? There was no 8, and now there is.')
            return
        if new_map.region_elevations[r] == 7:
            new_map.region_elevations[r] = 8
            print('Changed height 7 to 8 at index ' + str(r))
            return

    print("Couldn't find elevation 8 near the peak.")


def _extend_hills(new_map, peak):
    print('Raising the southern hills')
    dy = new_map.height - peak[1]
    x_intercept = peak[0] + dy / 2
    for r in range(len(new_map.region_seeds)):
        seed = new_map.region_seeds[r]
        if new_map.region_elevations[r] > 4:
            continue
        if seed[1] < peak[1]:
            continue
        local_dy = seed[1] - peak[1]
        midline = peak[0] + local_dy / 2
        dx = abs(midline - seed[0])
        if (dx > 40):
            continue
        e = int(4 - dx / 10)
        if new_map.region_elevations[r] < e:
            new_map.region_elevations[r] = e


def _place_seaside_height(new_map):
    """
    Guarantee that there's at least one elevated spot along the seaside
    """
    for r in range(20, 80):
        if (new_map.region_elevations[r] >= 2 and
                new_map.region_terrain[r-20] == 'lake'):
            new_map.grotto_region = r
            return

    # Rather than looking for a "best" location,
    # place it as soon as possible.
    for r in range(20, 80):
        print(r, new_map.region_terrain[r], new_map.region_elevations[r])
        if (new_map.region_terrain[r] == 'lake' or
                new_map.region_terrain[r] == 'marsh'):
            continue
        if new_map.region_terrain[r-20] != 'lake':
            print('Not lakeside...')
            continue
        new_map.region_elevations[r] = 1
        new_map.region_terrain[r] = 'scrub'
        new_map.grotto_region = r
        if (r+1)/20 == r/20:
            new_map.region_elevations[r+1] = 2
            new_map.region_terrain[r+1] = 'forest'
            new_map.grotto_region = r
        if (r+2)/20 == r/20:
            new_map.region_elevations[r+2] = 1
            new_map.region_terrain[r+2] = 'scrub'
        return

    print("Whoops! Can't find anywhere to place a seaside grotto.")
    new_map.grotto_region = None


def _should_slope(new_map, x, y):
    """
    True if any adjacent tile is higher than this one.
    """
    el = new_map.region_elevations[new_map.region[x][y]]
    return (new_map.elevation(x-1, y-1) == el+1 or
            new_map.elevation(x, y-1) == el+1 or
            new_map.elevation(x+1, y-1) == el+1 or
            new_map.elevation(x-1, y) == el+1 or
            new_map.elevation(x+1, y) == el+1 or
            new_map.elevation(x-1, y+1) == el+1 or
            new_map.elevation(x, y+1) == el+1 or
            new_map.elevation(x+1, y+1) == el+1)


def _mark_slopes(new_map):
    print('Finding the slopes')
    for x in range(1, config.OUTDOOR_MAP_WIDTH - 1):
        for y in range(1, config.OUTDOOR_MAP_HEIGHT - 1):
            if _should_slope(new_map, x, y):
                new_map.terrain[x][y] = 2


def _clump_terrain(new_map):
    print('Determining terrain clumps')
    for r in range(len(new_map.region_seeds)):
        el = new_map.region_elevations[r]
        seed = new_map.region_seeds[r]
        if el == 0:
            # Fill in the upper-left-hand-corner so that the mountain
            # tends to be flush against the marsh & lake.
            in_corner = seed[0] + seed[1] < new_map.width * 0.75
            if seed[0] < 20 or (in_corner and seed[0] <= seed[1]):
                new_map.region_terrain[r] = 'lake'
            elif seed[1] < 20 or (in_corner and seed[1] < seed[0]):
                new_map.region_terrain[r] = 'marsh'
            else:
                new_map.region_terrain[r] = 'desert'
        elif el < 3:
            new_map.region_terrain[r] = 'scrub'
        elif el < 6:
            new_map.region_terrain[r] = 'forest'
        elif el < 7:
            new_map.region_terrain[r] = 'rock'
        else:
            new_map.region_terrain[r] = 'ice'


def _assign_terrain(new_map):
    terrain_lookup = { map.terrain_types[i].name : i
                       for i in range(len(map.terrain_types)) }

    marsh_chances = { 'water' : 10, 'ground' : 40, 'reeds' : 10, 'saxaul' : 10 }
    desert_chances = { 'ground' : 80, 'nitraria' : 5, 'ephedra' : 5, 'boulder' : 5 }
    scrub_chances = { 'ground' : 40, 'nitraria' : 10, 'ephedra' : 10, 'boulder' : 5 }
    forest_chances = { 'ground' : 45, 'poplar' : 15, 'boulder' : 5 }

    terrain_chances = {
        'lake' : { 'water' : 10 },
        'marsh' : marsh_chances,
        'desert' : desert_chances,
        'scrub' : scrub_chances,
        'forest' : forest_chances,
        'rock' : { 'ground' : 45, 'boulder' : 5 },
        'ice' : { 'ground' : 75, 'boulder' : 5 }
    }

    print('Assigning narrow terrain')
    for x in range(config.OUTDOOR_MAP_WIDTH):
        for y in range(config.OUTDOOR_MAP_HEIGHT):
           t = new_map.region_terrain[new_map.region[x][y]]
           if new_map.terrain[x][y] != 1 and t != 'lake':
                # For now don't overwrite slopes, except underwater
                continue
           new_map.terrain[x][y] = terrain_lookup[_random_choice(terrain_chances[t])]


def _make_rotunda(new_map, peak):
    """
    Create a rotunda on top of the mountain.
    This is always at the peak.
    """
    for x in range(peak[0]-3, peak[0]+4):
        for y in range(peak[1]-3, peak[1]+4):
            if new_map.elevation(x, y) != 9:
                # in theory would be better to glom onto a closer region
                # if one exists
                new_map.region[x][y] = new_map.region[peak[0]][peak[1]]
            # interior of rotunda is floor, edges are bare ground
            if (x > peak[0]-3 and x < peak[0]+3 and
                    y > peak[1]-3 and y < peak[1]+3):
                new_map.terrain[x][y] = map.TERRAIN_FLOOR
            elif new_map.terrain[x][y] != map.TERRAIN_SLOPE:
                new_map.terrain[x][y] = map.TERRAIN_GROUND
            if (x == peak[0]-2 or x == peak[0]+2 or
                    y == peak[1]-2 or y == peak[1]+2):
                # borders have alternating pillars
                if ((x - peak[0]) % 2 == 0 and
                        (y - peak[1]) % 2 == 0):
                    new_map.terrain[x][y] = map.TERRAIN_WALL


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


def _make_caravanserai(new_map):
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
                          min(br[0] - tl[0] + 1, MAX_CARAVANSERAI_SIZE),
                          min(br[1] - tl[1] + 1, MAX_CARAVANSERAI_SIZE))
    for x in range(bounds.x1, bounds.x2+1):
        for y in range(bounds.y1, bounds.y2+1):
            if (x == bounds.x1 or x == bounds.x2 or
                y == bounds.y1 or y == bounds.y2):
                new_map.terrain[x][y] = map.TERRAIN_WALL
            else:
                new_map.terrain[x][y] = map.TERRAIN_FLOOR

    # Cut gates in it facing east and south
    center = bounds.center()
    new_map.terrain[center.x][bounds.y2] = map.TERRAIN_FLOOR
    new_map.terrain[bounds.x2][center.y] = map.TERRAIN_FLOOR

    new_map.caravanserai = bounds

    if (bounds.width > bounds.height):
        # Rooms in west half
        wall_offset = libtcod.random_get_int(new_map.rng,
            2, (center.x - bounds.x1) / 3)
        for y in range(bounds.y1, bounds.y2+1):
            new_map.terrain[center.x - wall_offset][y] = map.TERRAIN_WALL

        north_door = libtcod.random_get_int(new_map.rng, bounds.y1+1, center.y-1)
        _place_door(new_map, algebra.Location(center.x - wall_offset, north_door))
        south_door = libtcod.random_get_int(new_map.rng, center.y+1, bounds.y2-1)
        _place_door(new_map, algebra.Location(center.x - wall_offset, south_door))

        # print('Doors at y= ' + str(north_door) + ' and ' + str(south_door))
        wall_y = (north_door + south_door) / 2
        for x in range(bounds.x1, center.x - wall_offset):
            new_map.terrain[x][wall_y] = map.TERRAIN_WALL
    else:
        # Rooms in north half
        wall_offset = libtcod.random_get_int(new_map.rng,
            2, (center.y - bounds.y1) / 3)
        for x in range(bounds.x1, bounds.x2+1):
            new_map.terrain[x][center.y - wall_offset] = map.TERRAIN_WALL

        east_door = libtcod.random_get_int(new_map.rng, bounds.x1+1, center.x-1)
        _place_door(new_map, algebra.Location(east_door, center.y - wall_offset))
        west_door = libtcod.random_get_int(new_map.rng, center.x+1, bounds.x2-1)
        _place_door(new_map, algebra.Location(west_door, center.y - wall_offset))

        # print('Doors at x= ' + str(east_door) + ' and ' + str(west_door))
        wall_x = (east_door + west_door) / 2
        for y in range(bounds.y1, center.y - wall_offset):
            new_map.terrain[wall_x][y] = map.TERRAIN_WALL

    # TODO: rooms should be floor, but courtyard should be ground
    # TODO: add two more rooms
    # TODO: create an upstairs and a cellar
    # TODO: track these rooms correctly and populate them intentionally
    # TODO: generate total bandit population and then divide between areas


def _test_quarry_placement(new_map, region_span):
    """
    Look for a site of a given elevation in a particular consecutive range of regions.
    """
    for r in range(region_span[0], region_span[1]):
        if new_map.region_elevations[r] == QUARRY_ELEVATION:
            return r

    return None


def _mark_quarry_slopes(new_map, region):
    # BUG still not quite right
    center = new_map.region_seeds[region]
    print('Centering quarry at ' + str(center[0]) + ' ' + str(center[1]))
    
    for x in range(max(center[0] - 10, 0), min(center[0] + 10, new_map.width - 1)):
        for y in range(max(center[1] - 10, 0), min(center[1] + 10, new_map.height - 1)):
            if _should_slope(new_map, x, y):
                # add new slopes within the quarry, if necessary
                if new_map.region[x][y] != region:
                    continue
                new_map.terrain[x][y] = 2
            else:
                if new_map.region[x][y] == region:
                    new_map.terrain[x][y] = 1
                elif new_map.terrain[x][y] == 2:
                    # get rid of now-obsolete slopes nearby
                    new_map.terrain[x][y] = 1


def _place_quarry(new_map, peak):
    """
    Looks for a site just below the top of the hills,
    south and ideally a little east of the peak.
    Sets new_map.quarry_region
    """
    peak_region = new_map.region[peak[0]][peak[1]]
    column_start = peak_region + 20 * libtcod.random_get_int(0, 0, 2)
    column_end = (column_start / 20) * 20 + 19
    print('Searching for quarry between ' + str(column_start) + ' and ' + str(column_end))
    new_map.quarry_region = _test_quarry_placement(new_map, (column_start, column_end))
    if not new_map.quarry_region:
        new_map.quarry_region = _test_quarry_placement(new_map, (column_start+20, column_end+20))
    if not new_map.quarry_region:
        new_map.quarry_region = _test_quarry_placement(new_map, (column_start+40, column_end+40))
    if not new_map.quarry_region:
        new_map.quarry_region = _test_quarry_placement(new_map, (column_start-20, column_end-20))
    if not new_map.quarry_region:
        new_map.quarry_region = _test_quarry_placement(new_map, (column_start-40, column_end-40))
       

def _dig_quarry(new_map, peak):
    """
    """
    _place_quarry(new_map, peak)
    if not new_map.quarry_region:
        print("Couldn't find anywhere to dig a quarry; sorry!")
        return

    # Doing this as originally envisioned would require switching to per-tile elevation
    # instead of per-region elevation.

    # Stopgap: drop the entire region, reevaluate for slopes,
    # and rewrite terrain.
    new_map.region_elevations[new_map.quarry_region] = 2
    new_map.region_terrain[new_map.quarry_region] = 'rock'
    _mark_quarry_slopes(new_map, new_map.quarry_region)

    # Extend east, or west if that doesn't work
    if new_map.region_elevations[new_map.quarry_region+20] > 2:
        new_map.region_elevations[new_map.quarry_region+20] = 2
        new_map.region_terrain[new_map.quarry_region+20] = 'rock'
        _mark_quarry_slopes(new_map, new_map.quarry_region+20)
    elif new_map.region_elevations[new_map.quarry_region-20] > 2:
        new_map.region_elevations[new_map.quarry_region-20] = 2
        new_map.region_terrain[new_map.quarry_region-20] = 'rock'
        _mark_quarry_slopes(new_map, new_map.quarry_region-20)

    # TODO: dig multiple mines underneath


def _make_grotto(new_map):
    if not new_map.grotto_region:
        return

    region_center = algebra.Location(new_map.region_seeds[new_map.grotto_region][0],
                                     new_map.region_seeds[new_map.grotto_region][1])
    print('Grotto at ' + str(region_center.x) + ' ' + str(region_center.y))
    stairs = Object(region_center, '<', 'stairs down', libtcod.white, always_visible=True)
    stairs.destination = None
    stairs.dest_position = None
    stairs.generator = ca_cartographer.make_map
    new_map.objects.insert(0, stairs)
    new_map.portals.insert(0, stairs)

    # Would be nice to have a structure around it, but for now just keep the top clear.
    for x in range(region_center.x - 2, region_center.x + 3):
        for y in range(region_center.y - 2, region_center.y + 3):
            if new_map.region[x][y] == new_map.grotto_region:
                new_map.terrain[x][y] = 1


def _debug_region_heights(new_map):
    for u in range(20):
        print(new_map.region_elevations[u:400:20])


def _debug_region_terrain(new_map):
    rt = ''
    for r in range(len(new_map.region_seeds)):
        if new_map.region_terrain[r] != None:
            rt += new_map.region_terrain[r][0]
        else:
            rt += str(new_map.region_elevations[r])
    for u in range(20):
        print(rt[u:400:20])


def _build_map(new_map):
    new_map.rng = libtcod.random_new_from_seed(new_map.random_seed)

    print('Seeding regions')
    for u in range(config.OUTDOOR_MAP_WIDTH / 10):
        for v in range(config.OUTDOOR_MAP_HEIGHT / 10):
            x = libtcod.random_get_int(new_map.rng, 0, 9) + u * 10
            y = libtcod.random_get_int(new_map.rng, 0, 9) + v * 10
            new_map.region_seeds.append([x, y])

    print('Growing the world-tree')
    region_tree = scipy.spatial.KDTree(new_map.region_seeds)

    new_map.region_terrain = [None for i in range(len(new_map.region_seeds))]
    new_map.region_elevations = [-1 for r in range(len(new_map.region_seeds))]
    new_map.region_entered = [False for i in range(len(new_map.region_seeds))]
    new_map.elevation_visited = [False for i in range(0,10)]

    print('Assigning regions')
    for x in range(config.OUTDOOR_MAP_WIDTH):
        for y in range(config.OUTDOOR_MAP_HEIGHT):
            (d, i) = region_tree.query([[x, y]])
            new_map.region[x][y] = i[0]
            new_map.terrain[x][y] = 1

    peak = [libtcod.random_get_int(new_map.rng, int(config.OUTDOOR_MAP_WIDTH * .35), int(config.OUTDOOR_MAP_WIDTH * .65)),
            libtcod.random_get_int(new_map.rng, int(config.OUTDOOR_MAP_WIDTH * .35), int(config.OUTDOOR_MAP_WIDTH * .65))]
    print('The peak is at ' + str(peak[0]) + ', ' + str(peak[1]))

    for r in range(20):
        new_map.region_elevations[r] = 0
        new_map.region_elevations[380+r] = 0
        new_map.region_elevations[r*20] = 0
        new_map.region_elevations[r*20+19] = 0

    (d, peak_regions) = region_tree.query([peak], 3)
    for p in peak_regions[0]:
        new_map.region_elevations[p] = 9

    _interpolate_heights(new_map, peak)
    _ensure_penultimate_height(new_map, peak, region_tree)
    _extend_hills(new_map, peak)
    _debug_region_heights(new_map)

    _clump_terrain(new_map)
    _place_seaside_height(new_map)
    # TODO: level_desert() here to guarantee caravanserai is in the northeast
    # TODO: sink_quarry() here before we _mark_slopes
    # to get rid of messy after-the-fact slope fixup in dig_quarry()
    _debug_region_terrain(new_map)

    _mark_slopes(new_map)
    _assign_terrain(new_map)

    _make_rotunda(new_map, peak)
    _make_caravanserai(new_map)
    _dig_quarry(new_map, peak)
    _make_grotto(new_map)

    new_map.peak = peak


def make_map(player, dungeon_level):
    """
    Creates a new simple map at the given dungeon level.
    Sets player.current_map to the new map, and adds the player as the first
    object.
    """
    new_map = map.OutdoorMap(config.OUTDOOR_MAP_WIDTH, config.OUTDOOR_MAP_HEIGHT, dungeon_level)
    new_map.objects.append(player)
    player.current_map = new_map
    player.camera_position = algebra.Location(0, 0)
    new_map.random_seed = libtcod.random_save(0)
    _build_map(new_map)

    _place_random_creatures(new_map, player)
    _inhabit_rotunda(new_map, new_map.peak)
    if new_map.caravanserai:
        _inhabit_caravanserai(new_map, player)
    if new_map.quarry_region:
        _inhabit_quarry(new_map, player)

    player.pos = algebra.Location(config.OUTDOOR_MAP_WIDTH - 8, 12)

    # make sure we're not starting on top of an object or terrain feature
    while (new_map.terrain_at(player.pos).name != 'ground'):
        # subtle bug? doesn't use the map-building random number generator
        player.pos = player.pos + actions.random_direction()
        player.pos.bound(algebra.Rect(0, 0, new_map.width - 1, new_map.height - 1))

    new_map.initialize_fov()
    return new_map


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
    for i in range(len(map1.rooms)):
        assert map1.rooms[i] == map2.rooms[i]

if __name__ == '__main__':
    _test_map_repeatability()
    print('Cartographer tests complete.')
