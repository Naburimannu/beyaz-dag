# Copyright 2016 Thomas C. Hudson
# Governed by the license described in LICENSE.txt
import libtcodpy as libtcod

import cProfile
import scipy.spatial.kdtree

import config
import algebra
import map
import log
from components import *
import miscellany
import bestiary
import ai
import actions
import spells
import quest
import compound_cartographer
import mine_cartographer
import ca_cartographer
import dungeon_cartographer

ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 30

QUARRY_ELEVATION = 3
GHUL_COUNT_GOAL = 2
MINE_ENTRANCE_COUNT = 3


def _random_position_in_region(new_map, region):
    """
    Given a region of a map, return an algebra.Location in the region
    """
    center = new_map.region_seeds[region]
    while True:
        candidate = algebra.Location(
                libtcod.random_get_int(0, center[0]-5, center[0]+5),
                libtcod.random_get_int(0, center[1]-5, center[1]+5))
        if (candidate.x < 0 or candidate.y < 0 or
                candidate.x >= new_map.width or
                candidate.y >= new_map.height):
            continue
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
        'desert' : { None : 20, bestiary.hyena_pair : 5, bestiary.gazelle : 10 },
        'scrub' : { None : 20, bestiary.hyena : 2, bestiary.gazelle : 4,
                    bestiary.deer : 4, bestiary.wolf : 2 },
        'forest' : { None : 20, bestiary.deer : 10, bestiary.wolf_pair : 5,
                     bestiary.bear : 3 },
        'rock' : { None : 10, bestiary.snow_leopard : 1 },
        'ice' : { None : 10, bestiary.snow_leopard : 1 }
    }
    for r in range(len(new_map.region_seeds)):
        if (r == start_region or
            (new_map.quarry_regions and r in new_map.quarry_regions)):
            continue
        fn = _random_choice(terrain_chances[new_map.region_terrain[r]])
        if fn is not None:
            pos = algebra.Location(new_map.region_seeds[r][0], new_map.region_seeds[r][1])
            while new_map.is_blocked_at(pos):
                pos += actions.random_direction()
                pos.bound(algebra.Rect(0, 0, new_map.width-1, new_map.height-1))
            if new_map.caravanserai and new_map.caravanserai.bounds.contains(pos):
                continue
            # print('Creature in region ' + str(r) + ' at ' + str(pos.x) + ' ' + str(pos.y))
            fn(new_map, pos, player)


def _inhabit_rotunda(new_map, peak):
    goddess = Object(algebra.Location(peak[0], peak[1]), '@', 'The White Goddess', libtcod.white, blocks=True,
        interactable=Interactable(use_function=quest.goddess_charge))
    new_map.objects.append(goddess)


def _inhabit_quarry(new_map, player):
    for i in range(GHUL_COUNT_GOAL):
        rgn = new_map.quarry_regions[_random_choice_index([1 for ii in range(len(new_map.quarry_regions))])]
        ghul = bestiary.ghul(new_map, _random_position_in_region(new_map, rgn), player)


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


def _find_terrain_types(new_map):
    strata = { x : [] for x in map.region_colors_seen.keys() }
    for r in range(len(new_map.region_terrain)):
        type = strata.get(new_map.region_terrain[r])
        type.append(r)

    return strata


def _mark_slopes(new_map):
    print('Finding the slopes')
    for x in range(1, config.OUTDOOR_MAP_WIDTH - 1):
        for y in range(1, config.OUTDOOR_MAP_HEIGHT - 1):
            if _should_slope(new_map, x, y):
                new_map.terrain[x][y] = map.TERRAIN_SLOPE


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
           if new_map.terrain[x][y] != map.TERRAIN_GROUND and t != 'lake':
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


def _test_quarry_placement(new_map, region_span):
    """
    Look for a site of a given elevation in a particular consecutive range of regions.
    """
    for r in range(region_span[0], region_span[1]):
        if new_map.region_elevations[r] == QUARRY_ELEVATION:
            return r

    return None


def _mark_quarry_slopes(new_map, region):
    # BUG still not quite right?
    center = new_map.region_seeds[region]
    print('Centering quarry at ' + str(center[0]) + ' ' + str(center[1]))
    
    for x in range(max(center[0] - 10, 0), min(center[0] + 10, new_map.width - 1)):
        for y in range(max(center[1] - 10, 0), min(center[1] + 10, new_map.height - 1)):
            if _should_slope(new_map, x, y):
                # add new slopes within the quarry, if necessary
                if new_map.region[x][y] != region:
                    continue
                new_map.terrain[x][y] = map.TERRAIN_SLOPE
            else:
                if new_map.region[x][y] == region:
                    new_map.terrain[x][y] = map.TERRAIN_GROUND
                elif new_map.terrain[x][y] == map.TERRAIN_SLOPE:
                    # get rid of now-obsolete slopes nearby
                    new_map.terrain[x][y] = map.TERRAIN_GROUND


def _place_quarry(new_map, peak):
    """
    Looks for a site just below the top of the hills,
    south and ideally a little east of the peak.
    Sets new_map.quarry_regions
    """
    peak_region = new_map.region[peak[0]][peak[1]]
    column_start = peak_region + 20 * libtcod.random_get_int(0, 0, 2)
    column_end = (column_start / 20) * 20 + 19
    print('Searching for quarry between ' + str(column_start) + ' and ' + str(column_end))

    new_map.quarry_regions = None
    q_rgn = _test_quarry_placement(new_map, (column_start, column_end))
    if not q_rgn:
        q_rgn = _test_quarry_placement(new_map, (column_start+20, column_end+20))
    if not q_rgn:
        q_rgn = _test_quarry_placement(new_map, (column_start+40, column_end+40))
    if not q_rgn:
        q_rgn = _test_quarry_placement(new_map, (column_start-20, column_end-20))
    if not q_rgn:
        q_rgn = _test_quarry_placement(new_map, (column_start-40, column_end-40))

    if not q_rgn:
        return

    new_map.quarry_regions = [q_rgn]

    # Extend east, or west if that doesn't work
    if new_map.region_elevations[q_rgn+20] > 2:
        new_map.quarry_regions += [q_rgn+20]
    elif new_map.region_elevations[q_rgn-20] > 2:
        new_map.quarry_regions += [q_rgn-20]

    print('Quarry regions: ', new_map.quarry_regions)


def _dig_quarry(new_map, peak):
    """
    """
    _place_quarry(new_map, peak)
    if not new_map.quarry_regions:
        print("Couldn't find anywhere to dig a quarry; sorry!")
        return

    # Doing this as originally envisioned would require switching to per-tile elevation
    # instead of per-region elevation.

    # Stopgap: drop the entire region, reevaluate for slopes,
    # and rewrite terrain.
    for rgn in new_map.quarry_regions:
        new_map.region_elevations[rgn] = 2
        new_map.region_terrain[rgn] = 'rock'

    for rgn in new_map.quarry_regions:
        _mark_quarry_slopes(new_map, rgn)

    stairheads = []
    for ii in range(MINE_ENTRANCE_COUNT):
        while True:
            rgn = new_map.quarry_regions[_random_choice_index([1 for ii in range(len(new_map.quarry_regions))])]
            pos = _random_position_in_region(new_map, rgn)
            sufficiently_distant = True
            for stair_pos in stairheads:
                # print('distance between ', pos, stair_pos, pos.distance(stair_pos))
                if pos.distance(stair_pos) < 5:
                    sufficiently_distant = False
            # Maybe try to enforce that it's near a cliff / slope...
            if sufficiently_distant:
                break
        stairheads.append(pos)

    # Arrange west-to-east to make it easier to dig below
    stairheads.sort(key = lambda pos : pos.x)

    new_map.quarry_stairs = []
    for ii in stairheads:
        stairs = Object(ii, '<', 'mine entrance', libtcod.white, always_visible=True)
        stairs.destination = None
        stairs.dest_position = None
        stairs.generator = mine_cartographer.make_map
        new_map.objects.insert(0, stairs)
        new_map.portals.insert(0, stairs)
        new_map.quarry_stairs.append(stairs)


def _make_grotto(new_map):
    if not new_map.grotto_region:
        return

    region_center = algebra.Location(new_map.region_seeds[new_map.grotto_region][0],
                                     new_map.region_seeds[new_map.grotto_region][1])
    print('Grotto at ' + str(region_center.x) + ' ' + str(region_center.y))
    stairs = Object(region_center, '<', 'cave mouth', libtcod.white, always_visible=True)
    stairs.destination = None
    stairs.dest_position = None
    stairs.generator = ca_cartographer.make_map
    new_map.objects.insert(0, stairs)
    new_map.portals.insert(0, stairs)
    new_map.grotto_stairs = region_center

    # Would be nice to have a structure around it, but for now just keep the top clear.
    for x in range(region_center.x - 2, region_center.x + 3):
        for y in range(region_center.y - 2, region_center.y + 3):
            if (new_map.region[x][y] == new_map.grotto_region
                    and new_map.terrain[x][y] != map.TERRAIN_SLOPE):
                new_map.terrain[x][y] = map.TERRAIN_GROUND


def _check_stair_position(stairheads, candidate):
    for prev_pos in stairheads:
        if candidate.distance(prev_pos) < 20:
            return False
    return True


def _site_final_dungeon(new_map, strata):
    other_stairs = new_map.quarry_stairs + [new_map.grotto_stairs]
    stairheads = []
    for type in ['rock', 'forest', 'forest']:
        regions = strata[type]
        while True:
            r = regions[new_map.rnd(0, len(regions) - 1)]
            pos = _random_position_in_region(new_map, r)
            if _check_stair_position(stairheads + other_stairs, pos):
                break
        stairheads.append(pos)
        print('Final dungeon entrance at ', pos)

    stairheads.sort(key = lambda pos : pos.x)

    new_map.dungeon_stairs = []
    for ii in stairheads:
        new_map.terrain[ii.x][ii.y] = map.TERRAIN_GROUND
        stairs = Object(ii, '<', 'cave mouth', libtcod.white, always_visible=True)
        stairs.destination = None
        stairs.dest_position = None
        stairs.generator = dungeon_cartographer.make_final_map
        new_map.objects.insert(0, stairs)
        new_map.portals.insert(0, stairs)
        new_map.dungeon_stairs.append(stairs)
        for x in range(ii.x - 2, ii.x + 3):
            for y in range(ii.y - 2, ii.y + 3):
                if (new_map.region[x][y] == new_map.region[ii.x][ii.y]
                        and new_map.terrain[x][y] != map.TERRAIN_SLOPE):
                    new_map.terrain[x][y] = map.TERRAIN_GROUND

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
            new_map.terrain[x][y] = map.TERRAIN_GROUND

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
    strata = _find_terrain_types(new_map)
    _debug_region_terrain(new_map)

    _mark_slopes(new_map)
    _assign_terrain(new_map)

    _make_rotunda(new_map, peak)
    compound_cartographer.make_caravanserai(new_map)
    _dig_quarry(new_map, peak)
    _make_grotto(new_map)
    _site_final_dungeon(new_map, strata)

    new_map.peak = peak


def _mountain_exploration(self, player):
    new_region = self.region[player.pos.x][player.pos.y]
    new_elevation = self.region_elevations[new_region]
    delta = 0
    if not self.region_entered[new_region]:
        delta += config.REGION_EXPLORATION_SP
        self.region_entered[new_region] = True
    if not self.elevation_visited[new_elevation]:
        delta += config.ELEVATION_EXPLORATION_SP
        self.elevation_visited[new_elevation] = True
    if delta > 0:
        player.skill_points += delta
        point = 'point'
        if delta > 1:
            point += 's'
        log.message('You gained ' + str(delta) + ' skill ' + point + ' for exploration.')


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

    # Might want to change this later, but this is required in creature placement
    # routines so we know what region the player starts in so there isn't a
    # wandering monster jumping down their throat. Unless, of course, this
    # start point is on a *region border* and there's a monster in the next
    # region over...
    player.pos = algebra.Location(config.OUTDOOR_MAP_WIDTH - 8, 12)

    _place_random_creatures(new_map, player)
    _inhabit_rotunda(new_map, new_map.peak)
    if new_map.caravanserai:
        compound_cartographer.inhabit_caravanserai(new_map, player)
    if new_map.quarry_regions:
        _inhabit_quarry(new_map, player)

    # make sure we're not starting on top of an object or terrain feature
    while (new_map.terrain_at(player.pos).name != 'ground'):
        # subtle bug? doesn't use the map-building random number generator
        player.pos = player.pos + actions.random_direction()
        player.pos.bound(algebra.Rect(0, 0, new_map.width - 1, new_map.height - 1))

    new_map.initialize_fov()
    # setting an instancemethod breaks shelve save games
    # new_map.xp_visit = type(map.BaseMap.xp_visit)(_mountain_exploration, new_map, map.BaseMap)
    new_map.xp_visit = _mountain_exploration
    return True


def _test_map_repeatability():
    """
    Require that two calls to _build_map() with the same seed produce the
    same corridors and rooms.
    """
    map1 = map.OutdoorMap(config.MAP_WIDTH, config.MAP_HEIGHT, 3)
    map1.random_seed = libtcod.random_save(0)
    _build_map(map1)

    map2 = map.OutdoorMap(config.MAP_WIDTH, config.MAP_HEIGHT, 3)
    map2.random_seed = map1.random_seed
    _build_map(map2)

    assert map1.terrain == map2.terrain
    for i in range(len(map1.rooms)):
        assert map1.rooms[i] == map2.rooms[i]

if __name__ == '__main__':
    _test_map_repeatability()
    print('Cartographer tests complete.')
