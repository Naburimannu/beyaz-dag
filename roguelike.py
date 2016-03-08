#!/usr/bin/python
#
# libtcod python tutorial
#

import libtcodpy as libtcod
import shelve
import cProfile

import config
import log
import algebra
from components import *
import renderer
import interface
import actions
import ai
import cartographer
import mountain_cartographer

INVENTORY_WIDTH = 50
CHARACTER_SCREEN_WIDTH = 30

# Experience and level-ups
REGION_EXPLORATION_SP = 1
ELEVATION_EXPLORATION_SP = 5

# Every 100 pts of exhaustion = -1 to all skills
#   is equivalent to 1 wound point
ATTACK_EXHAUSTION = 20
CLIMB_EXHAUSTION = 10
MOVE_EXHAUSTION = 1


def try_pick_up(player):
    for object in player.current_map.objects:
        if object.x == player.x and object.y == player.y and object.item:
            return actions.pick_up(player, object)
    return False


def try_drop(player):
    chosen_item = inventory_menu(
        player,
        'Press the key next to an item to drop it, x to examine, or any other to cancel.\n')
    if chosen_item is not None:
        actions.drop(player, chosen_item.owner)
        return True
    return False


def try_use(player):
    chosen_item = inventory_menu(
        player,
        'Press the key next to an item to use it, x to examine, or any other to cancel.\n')
    if chosen_item is not None:
        actions.use(player, chosen_item.owner)
        return True
    return False


def _check_exploration_xp(player, new_region, new_elevation):
    delta = 0
    if not player.current_map.region_entered[new_region]:
        delta += REGION_EXPLORATION_SP
        player.current_map.region_entered[new_region] = True
    if not player.current_map.elevation_visited[new_elevation]:
        delta += ELEVATION_EXPLORATION_SP
        player.current_map.elevation_visited[new_elevation] = True
    if delta > 0:
        player.skill_points += delta
        point = 'point'
        if delta > 1:
            point += 's'
        log.message('You gained ' + str(delta) + ' skill ' + point + ' for exploration.')


def player_move_or_attack(player, direction, try_running):
    """
    Returns true if the player makes an attack or moves successfully;
    false if the attempt to move fails.
    """
    goal = player.pos + direction
    if (goal.x < 0 or goal.y < 0 or
            goal.x >= player.current_map.width or
            goal.y >= player.current_map.height):
        log.message(player.current_map.out_of_bounds(goal))
        return False

    # Is there an attackable object?
    target = None
    for object in player.current_map.objects:
        if object.fighter and object.pos == goal:
            target = object
            break

    if target is not None:
        actions.attack(player.fighter, target)
        player.fighter.exhaustion += ATTACK_EXHAUSTION
        return True
    else:
        old_elevation = player.current_map.region_elevations[player.current_map.region[player.pos.x][player.pos.y]]
        if actions.move(player, direction):
            player.current_map.fov_needs_recompute = True
            new_region = player.current_map.region[player.pos.x][player.pos.y]
            new_elevation = player.current_map.region_elevations[new_region]
            _check_exploration_xp(player, new_region, new_elevation)
            if new_elevation != old_elevation:
                player.current_map.fov_elevation_changed = True
                player.fighter.exhaustion += CLIMB_EXHAUSTION
            else:
                player.fighter.exhaustion += MOVE_EXHAUSTION
            if try_running:
                player.game_state = 'running'
                player.run_direction = direction
            return True

    return False


def inventory_menu(player, header):
    """
    Show a menu with each item of the inventory as an option.
    """
    if len(player.inventory) == 0:
        renderer.menu(header, 'Inventory is empty.', INVENTORY_WIDTH)
        return None

    options = []
    for obj in player.inventory:
        text = obj.name
        # Show additional information, in case it's equipped.
        if obj.item.count > 1:
            text = text + ' (x' + str(obj.item.count) + ')'
        if obj.equipment and obj.equipment.is_equipped:
            text = text + ' (' + obj.equipment.slot + ')'
        options.append(text)

    (char, index) = renderer.menu(header, options, INVENTORY_WIDTH)

    if index is not None:
        return player.inventory[index].item

    if char == ord('x'):
        (c2, i2) = renderer.menu('Press the key next to an item to examine it, or any other to cancel.\n', options, INVENTORY_WIDTH)
        if i2 is not None and player.inventory[i2].item.description is not None:
            # renderer.msgbox(player.inventory[i2].item.description)
            log.message(player.inventory[i2].item.description)

    return None


def display_character_info(player):
    data = ['Skill points: ' + str(player.skill_points),
        'Current health: ' + str(int(player.fighter.hp)),
        'Maximum wounds: ' + str(player.fighter.max_hp),
        'Skills:']
    for key, value in player.fighter.skills.items():
        data.append('  ' + key + ': ' + str(value))

    info_string = '\n'.join(data)
    renderer.msgbox(info_string, CHARACTER_SCREEN_WIDTH)


class Skill(object):
    def __init__(self, name, cost, description):
        self.name = name
        self.cost = cost
        self.description = description


skill_list = [
    Skill('bow', 5, 'Shoot with a bow.'),
    Skill('climb', 3, 'Climb trees and rock faces. **UNIMPLEMENTED**'),
    Skill('first aid', 3, 'Tend to minor wounds and bleeding; requires bandages. **UNIMPLEMENTED**'),
    Skill('grappling', 3, 'Fight with bare hands or a knife.'),
    Skill('spear', 4, 'Attack and defend with a spear.'),
    Skill('sword', 4, 'Attack and defend with a sword.')
]


def increase_player_skills(player):
    options = [s.name + ': currently ' + str(player.fighter.skills.get(s.name, 0)) + ', costs ' + str(s.cost) + ' sp'
                for s in skill_list]
    while True:
        (key, target) = renderer.menu('Choose skill to increase, or x to explain:',
                                      options, INVENTORY_WIDTH)
        if key == ord('x'):
            (c2, i2) = renderer.menu('Choose skill to describe, or any other to cancel.\n', options, INVENTORY_WIDTH)
            if i2 is not None:
                log.message(skill_list[i2].name + ': ' + skill_list[i2].description)
            
        if not target:
            return
        if skill_list[target].cost < player.skill_points:
            break

    player.skill_points -= skill_list[target].cost
    value = player.fighter.skills.get(skill_list[target].name, 0)
    if value < 100:
        value += libtcod.random_get_int(0, 1, 8)
    elif value < 150:
        value += libtcod.random_get_int(0, 1, 4)
    elif value < 200:
        value += libtcod.random_get_int(0, 1, 2)
    else:
        value += 1
    player.fighter.skills[skill_list[target].name] = value
    log.message('Increased ' + skill_list[target].name + ' to ' + str(value))


def display_help():
    renderer.msgbox('numpad keys to move, or:\n' +
                    '  h (west) j (south) k (north) l (east)\n' +
                    '  y (nw) u (ne) b (sw) n (se) . (wait)\n' +
                    '  shift-move to run\n' +
                    '\n' +
                    'g/get, d/drop, c/character information\n' +
                    's/increase skills\n' +
                    'i/inventory, equip, or use item\n' +
                    '</traverse stairs\n' +
                    '\n' +
                    'control-p/scroll through old log messages\n',
                    INVENTORY_WIDTH)


def try_stairs(player):
    for f in player.current_map.portals:
        if f.pos == player.pos:
            if f.destination is None:
                f.destination = next_level(player, f)
                # player.pos was changed by next_level()!
                f.dest_position = player.pos
                return True
            else:
                revisit_level(player, f)
                return True
    return False


def _running_lookahead(player):
    """
    Returns true if the upcoming terrain doesn't match the current terrain,
    or if there's an object in the upcoming space.
    If the player stops running when true, they should stop in the doorway to
    a room, or just before rounding a bend in a corridor or entering an
    intersection.
    """
    map = player.current_map
    dir = player.run_direction
    if (map.terrain_at(player.pos) != map.terrain_at(player.pos + dir) or
            (map.terrain_at(player.pos + dir.left.left) != map.terrain_at(player.pos + dir.left)) or
            (map.terrain_at(player.pos + dir.right.right) != map.terrain_at(player.pos + dir.right))):
        return True
    for o in map.objects:
        if (o.pos == player.pos + dir or
                o.pos == player.pos + dir.left or
                o.pos == player.pos + dir.right):
            return True
    return False


def handle_keys(player, key):
    """
    Returns 'playing', 'didnt-take-turn', or 'exit'.
    """
    key_char = chr(key.c)

    if key.vk == libtcod.KEY_ENTER and key.lalt:
        # Alt+Enter: toggle fullscreen
        libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())

    elif key.vk == libtcod.KEY_ESCAPE:
        return 'exit'

    elif key_char == 'p' and (key.lctrl or key.rctrl):
        interface.log_display()

    if player.game_state == 'running':
        if (player.endangered or
                key.vk != libtcod.KEY_NONE or
                _running_lookahead(player) or
                not player_move_or_attack(player, player.run_direction, False)):
            player.game_state = 'playing'
            return 'didnt-take-turn'

    if player.game_state == 'playing':
        # movement keys
        (parsed, direction, shift) = interface.parse_move(key)
        if parsed:
            if direction:
                player_move_or_attack(player, direction, shift)
            else:
                # Do nothing
                pass
        else:
            if key_char == 'g':
                try_pick_up(player)
            if key_char == 'i':
                # interface.debounce()
                try_use(player)
            if key_char == 'd':
                # interface.debounce()
                try_drop(player)
            if key_char == 'c':
                display_character_info(player)
            if key_char == 's':
                increase_player_skills(player)
            if key_char == '<':
                try_stairs(player)
            if (key_char == '?' or key.vk == libtcod.KEY_F1):
                display_help()

            return 'didnt-take-turn'


def player_death(player):
    """
    End the game!
    """
    log.message('You died!', libtcod.red)
    player.game_state = 'dead'

    # For added effect, transform the player into a corpse!
    player.char = '%'
    player.color = libtcod.dark_red


def save_game(player):
    """
    Save the game to file "savegame";
    overwrites any existing data.
    """
    file = shelve.open('savegame', 'n')
    # Can't shelve kdtree
    player.current_map.region_tree = None
    file['current_map'] = player.current_map
    file['player_index'] = player.current_map.objects.index(player)
    file['game_msgs'] = log.game_msgs
    file.close()


def load_game():
    """
    Loads from "savegame".
    Returns the player object.
    """
    file = shelve.open('savegame', 'r')
    current_map = file['current_map']
    player = current_map.objects[file['player_index']]
    log.game_msgs = file['game_msgs']
    file.close()

    current_map.initialize_fov()

    return player


def _new_equipment(player, obj):
    player.inventory.append(obj)
    obj.always_visible = True
    actions.equip(player, obj.equipment, False)
    

def new_game():
    """
    Starts a new game, with a default player on level 1 of the dungeon.
    Returns the player object.
    """
    # Must initialize the log before we do anything that might emit a message.
    log.init()

    fighter_component = Fighter(hp=25, death_function=player_death)
    fighter_component.skills['bow'] = 50
    fighter_component.skills['climb'] = 10
    fighter_component.skills['grappling'] = 30
    player = Object(algebra.Location(0, 0), '@', 'player', libtcod.white, blocks=True, fighter=fighter_component)
    player.inventory = []
    player.level = 1
    player.game_state = 'playing'
    player.skill_points = 0
    player.turn_count = 0
    # True if there's a (hostile) fighter in FOV
    player.endangered = False

    _new_equipment(player,
        Object(None, '/', 'dagger', libtcod.dark_sky,
            item=Item(description='A leaf-shaped iron knife; inflicts 4 damage'),
            equipment=Equipment(slot='right hand'),
            melee=MeleeWeapon(skill='grappling', damage=4)))

    _new_equipment(player,
        Object(None, '[', 'silk undertunic', libtcod.dark_sky,
            item=Item(description='A thick under-tunic of raw silk; prevents 2 bleeding.'),
            equipment=Equipment(slot='underclothes', bleeding_defense=2)))

    _new_equipment(player,
        Object(None, '[', 'quilt kaftan', libtcod.dark_sky,
            item=Item(description='A heavy quilted kaftan; keeps you warm and prevents 1 wound.'),
            equipment=Equipment(slot='robes', defense_bonus=1)))

    _new_equipment(player,
        Object(None, '[', 'felt cap', libtcod.dark_sky,
            item=Item(description='A Phrygian felt cap with a loose veil to keep the sun off.'),
            equipment=Equipment(slot='head')))

    _new_equipment(player,
        Object(None, '/', 'horn bow', libtcod.dark_sky,
            item=Item(description='A short, sharply-curved, horn-backed bow.'),
            equipment=Equipment(slot='missile weapon')))

    _new_equipment(player,
        Object(None, '/', 'arrow', libtcod.dark_sky,
            item=Item(description='A gold-feathered beech arrow.', count=12),
            equipment=Equipment(slot='quiver')))

    # cartographer.make_map(player, 1)
    mountain_cartographer.make_map(player, 1)
    renderer.clear_console()
    renderer.update_camera(player)

    log.message('At last you have reached the foot of the mountain. She waits above.', libtcod.red)
    log.message('Press ? or F1 for help.')

    return player


def next_level(player, portal):
    """
    Advance to the next level (changing player.current_map).
    Heals the player 50%.
    Returns the Map of the new level.
    """
    log.message('You take a moment to rest, and recover your strength.', libtcod.light_violet)
    actions.heal(player.fighter, player.fighter.max_hp / 2)

    log.message('After a rare moment of peace, you descend deeper into the heart of the dungeon...', libtcod.red)
    old_map = player.current_map
    cartographer.make_map(player, player.current_map.dungeon_level + 1)
    renderer.clear_console()
    renderer.update_camera(player)

    # Create the up stairs at the current position.
    stairs = Object(player.pos, '>', 'stairs up', libtcod.white, always_visible=True)
    stairs.destination = old_map
    stairs.dest_position = portal.pos
    player.current_map.objects.insert(0, stairs)
    player.current_map.portals.insert(0, stairs)

    return player.current_map


def revisit_level(player, portal):
    """
    Return to a level the player has previously visited (changing player.current_map).
    Does *not* heal the player.
    """
    player.current_map = portal.destination
    player.pos = portal.dest_position
    # Call to initialize_fov() should be redundant but in practice seems to have
    # worked around an intermittent bug.
    player.current_map.initialize_fov()
    player.current_map.fov_needs_recompute = True
    renderer.update_camera(player)
    renderer.clear_console()


def process_visible_objects(player):
    """
    We will show the object if it's visible to the player
    or it's set to "always visible" and on an explored tile.
    If we're showing a hostile monster, set player.endangered.
    """
    player.endangered = False
    visible_objects = []
    for o in player.current_map.objects:
        if o == player:
            continue
        if (libtcod.map_is_in_fov(player.current_map.fov_map, o.x, o.y) or
                (o.always_visible and
                 player.current_map.is_explored(o.pos))):
            visible_objects.append(o)
            if o.fighter:
                player.endangered = True
    return visible_objects


def play_game(player):
    """
    Main loop.
    """
    player_action = None

    while not libtcod.console_is_window_closed():
        (key, mouse) = interface.poll()
        player.visible_objects = process_visible_objects(player)
        renderer.render_all(player, (mouse.cx, mouse.cy))
        player.current_map.fov_needs_recompute = False

        libtcod.console_flush()

        # Erase all objects at their old locations, before they move.
        for object in player.current_map.objects:
            renderer.clear_object(player, object)

        player_action = handle_keys(player, key)
        if player_action == 'exit':
            save_game(player)
            break

        if (player_action != 'didnt-take-turn' and
            (player.game_state == 'playing' or
             player.game_state == 'running')):
            for object in player.current_map.objects:
                if object.ai:
                    object.ai.take_turn(player)
                if object.fighter and object.fighter.bleeding > 0:
                    # this will also include the player
                    actions.bleed(object)
            player.turn_count += 1


if __name__ == '__main__':
    renderer.renderer_init()
    # cProfile.run('renderer.main_menu(new_game, play_game, load_game)')
    renderer.main_menu(new_game, play_game, load_game)
