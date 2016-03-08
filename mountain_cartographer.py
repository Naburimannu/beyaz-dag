import libtcodpy as libtcod

import cProfile
import scipy.spatial.kdtree

import config
import algebra
import map
from components import *
import ai
import spells

ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 30


def _random_position_in_room(room):
    return algebra.Location(libtcod.random_get_int(0, room.x1+1, room.x2-1),
                            libtcod.random_get_int(0, room.y1+1, room.y2-1))


def _create_room(new_map, room):
    """
    Make the tiles in a rectangle passable
    """
    for x in range(room.x1 + 1, room.x2):
        for y in range(room.y1 + 1, room.y2):
            new_map.terrain[x][y] = 1


def _create_h_tunnel(new_map, x1, x2, y):
    for x in range(min(x1, x2), max(x1, x2) + 1):
        new_map.terrain[x][y] = 1


def _create_v_tunnel(new_map, y1, y2, x):
    for y in range(min(y1, y2), max(y1, y2) + 1):
        new_map.terrain[x][y] = 1


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


def _from_dungeon_level(new_map, table):
    # Returns a value that depends on level.
    # The table specifies what value occurs after each level, default is 0.
    for (value, level) in reversed(table):
        if new_map.dungeon_level >= level:
            return value
    return 0


def _place_objects(new_map, room, player):
    max_monsters = _from_dungeon_level(new_map, [[2, 1], [3, 4], [5, 6]])

    monster_chances = {}
    # orc always shows up, even if all other monsters have 0 chance.
    monster_chances['orc'] = 80
    monster_chances['troll'] = _from_dungeon_level(new_map, [[15, 3], [30, 5], [60, 7]])

    max_items = _from_dungeon_level(new_map, [[1, 1], [2, 4]])

    item_chances = {}
    # Healing potion always shows up, even if all other items have 0 chance.
    item_chances['heal'] = 35
    item_chances['lightning'] = _from_dungeon_level(new_map, [[25, 4]])
    item_chances['fireball'] = _from_dungeon_level(new_map, [[25, 6]])
    item_chances['confuse'] = _from_dungeon_level(new_map, [[10, 2]])
    item_chances['sword'] = _from_dungeon_level(new_map, [[5, 4]])
    item_chances['shield'] = _from_dungeon_level(new_map, [[15, 8]])

    num_monsters = libtcod.random_get_int(0, 0, max_monsters)
    for i in range(num_monsters):
        pos = _random_position_in_room(room)

        if not new_map.is_blocked_at(pos):
            choice = _random_choice(monster_chances)
            if choice == 'orc':
                fighter_component = Fighter(hp=20, defense=0, power=4, xp=35, death_function=ai.monster_death)
                ai_component = AI(ai.basic_monster, ai.basic_monster_metadata(player))
                monster = Object(pos, 'o', 'orc', libtcod.desaturated_green,
                                 blocks=True, fighter=fighter_component, ai=ai_component)

            elif choice == 'troll':
                fighter_component = Fighter(hp=30, defense=2, power=8, xp=100, death_function=ai.monster_death)
                ai_component = AI(ai.basic_monster, ai.basic_monster_metadata(player))
                monster = Object(pos, 'T', 'troll', libtcod.darker_green,
                                 blocks=True, fighter=fighter_component, ai=ai_component)

            new_map.objects.append(monster)
            monster.current_map = new_map

    num_items = libtcod.random_get_int(0, 0, max_items)
    for i in range(num_items):
        pos = _random_position_in_room(room)

        if not new_map.is_blocked_at(pos):
            choice = _random_choice(item_chances)
            if choice == 'heal':
                item_component = Item(use_function=spells.cast_heal,
                    description='A flask of revivifying alchemical mixtures; heals ' + str(spells.HEAL_AMOUNT) + ' hp.')
                item = Object(pos, '!', 'healing potion', libtcod.violet, item=item_component)

            elif choice == 'lightning':
                item_component = Item(use_function=spells.cast_lightning,
                    description='Reading these runes will strike your nearest foe with lightning for ' +
                        str(spells.LIGHTNING_DAMAGE) + ' hp.')
                item = Object(pos, '#', 'scroll of lightning bolt', libtcod.light_yellow, item=item_component)

            elif choice == 'fireball':
                item_component = Item(use_function=spells.cast_fireball,
                    description='Reading these runes will cause a burst of flame inflicting ' + str(spells.FIREBALL_DAMAGE) +
                        ' hp on nearby creatures.')
                item = Object(pos, '#', 'scroll of fireball', libtcod.light_yellow, item=item_component)

            elif choice == 'confuse':
                item_component = Item(use_function=spells.cast_confuse,
                    description='Reading these runes will confuse the creature you focus on for a short time.')
                item = Object(pos, '#', 'scroll of confusion', libtcod.light_yellow, item=item_component)

            elif choice == 'sword':
                equipment_component = Equipment(slot='right hand', power_bonus=3)
                item_component = Item(description='A heavy-tipped bronze chopping sword; provides +3 Attack')
                item = Object(pos, '/', 'sword', libtcod.sky,
                              item=item_component, equipment=equipment_component)

            elif choice == 'shield':
                equipment_component = Equipment(slot='left hand', defense_bonus=1)
                item_component = Item(description='A bronze-edged oval shield; provides +1 Defense')
                item = Object(pos, '[', 'shield', libtcod.darker_orange, equipment=equipment_component)

            new_map.objects.insert(0, item)
            item.always_visible = True  # Items are visible even out-of-FOV, if in an explored area


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


def _ensure_penultimate_height(new_map, peak):
    for r in new_map.region_elevations:
        if r == 8:
            return

    (d, i) = new_map.region_tree.query(peak, 6)
    for r in i:
        if new_map.region_elevations[i] == 9:
            continue
        if new_map.region_elevations[i] == 7:
            new_map.region_elevations[i] == 8
            return


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
def _mark_slopes(new_map):
    print('Finding the slopes')
    for x in range(1, config.OUTDOOR_MAP_WIDTH - 1):
        for y in range(1, config.OUTDOOR_MAP_HEIGHT - 1):
            el = new_map.region_elevations[new_map.region[x][y]]
            if (new_map.region_elevations[new_map.region[x-1][y-1]] == el+1 or
                    new_map.region_elevations[new_map.region[x][y-1]] == el+1 or
                    new_map.region_elevations[new_map.region[x+1][y-1]] == el+1 or
                    new_map.region_elevations[new_map.region[x-1][y]] == el+1 or
                    new_map.region_elevations[new_map.region[x+1][y]] == el+1 or
                    new_map.region_elevations[new_map.region[x-1][y+1]] == el+1 or
                    new_map.region_elevations[new_map.region[x][y+1]] == el+1 or
                    new_map.region_elevations[new_map.region[x+1][y+1]] == el+1):
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
    for x in range(peak[0]-3, peak[0]+4):
        for y in range(peak[1]-3, peak[1]+4):
            if new_map.elevation(x, y) != 9:
                # in theory would be better to glom onto a closer region
                # if one exists
                new_map.region[x][y] = new_map.region[peak[0]][peak[1]]
            # interior of rotunda is clear
            new_map.terrain[x][y] = 1
            if (x == peak[0]-3 or x == peak[0]+3 or
                    y == peak[1]-3 or y == peak[1]+3):
                # borders have alternating pillars
                if ((x - peak[0]) % 2 == 1 and
                        (y - peak[1]) % 2 == 1):
                    new_map.terrain[x][y] = 0


def _build_map(new_map):
    new_map.rng = libtcod.random_new_from_seed(new_map.random_seed)

    print('Seeding regions')
    for u in range(config.OUTDOOR_MAP_WIDTH / 10):
        for v in range(config.OUTDOOR_MAP_HEIGHT / 10):
            x = libtcod.random_get_int(new_map.rng, 0, 9) + u * 10
            y = libtcod.random_get_int(new_map.rng, 0, 9) + v * 10
            new_map.region_seeds.append([x, y])

    print('Growing the world-tree')
    new_map.region_tree = scipy.spatial.KDTree(new_map.region_seeds)

    print('Assigning regions')
    for x in range(config.OUTDOOR_MAP_WIDTH):
        for y in range(config.OUTDOOR_MAP_HEIGHT):
            (d, i) = new_map.region_tree.query([[x, y]])
            new_map.region[x][y] = i[0]
            # DEBUG
            # new_map._explored[x][y] = True
            new_map.terrain[x][y] = 1

    peak = [libtcod.random_get_int(new_map.rng, int(config.OUTDOOR_MAP_WIDTH * .35), int(config.OUTDOOR_MAP_WIDTH * .65)),
            libtcod.random_get_int(new_map.rng, int(config.OUTDOOR_MAP_WIDTH * .35), int(config.OUTDOOR_MAP_WIDTH * .65))]
    print('The peak is at ' + str(peak[0]) + ', ' + str(peak[1]))

    new_map.region_elevations = [-1 for r in range(len(new_map.region_seeds))]
    for r in range(20):
        new_map.region_elevations[r] = 0
        new_map.region_elevations[380+r] = 0
        new_map.region_elevations[r*20] = 0
        new_map.region_elevations[r*20+19] = 0

    (d, peak_regions) = new_map.region_tree.query([peak], 3)
    for p in peak_regions[0]:
        new_map.region_elevations[p] = 9

    _interpolate_heights(new_map, peak)
    _ensure_penultimate_height(new_map, peak)
    _extend_hills(new_map, peak)

    for u in range(20):
        print(new_map.region_elevations[u:400:20])

    _mark_slopes(new_map)
    _clump_terrain(new_map)

    # DEBUG
    rt = ''
    for r in range(len(new_map.region_seeds)):
        if new_map.region_terrain[r] != None:
            rt += new_map.region_terrain[r][0]
        else:
            rt += str(new_map.region_elevations[r])
    for u in range(20):
        print(rt[u:400:20])

    _assign_terrain(new_map)

    _make_rotunda(new_map, peak)


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

    # TODO: place objects and creatures
    # TODO: make sure we're not starting on top of an object or terrain feature
    player.pos = algebra.Location(config.OUTDOOR_MAP_WIDTH - 8, 8)

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
