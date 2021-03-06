#!/usr/bin/python
# Copyright 2016 Thomas C. Hudson
# Governed by the license described in LICENSE.txt
import sys

import libtcodpy as libtcod
import shelve
import cProfile

import config
import log
import algebra
from components import *
import renderer
import interface
import miscellany
import actions
import ai
import spells
import quest
import dungeon_cartographer
import mountain_cartographer

INVENTORY_WIDTH = 50
CHARACTER_SCREEN_WIDTH = 30


class Skill(object):
    def __init__(self, name, cost, description):
        self.name = name
        self.cost = cost
        self.description = description


skill_list = [
    Skill('axe', 6, 'Attack and defend with an axe.'),
    Skill('bow', 5, 'Shoot with a bow.'),
#    Skill('climb', 3, 'Climb trees and rock faces. **UNIMPLEMENTED**'),
    Skill('first aid', 3, 'Tend to minor wounds and bleeding; requires bandages.'),
    Skill('grappling', 3, 'Fight with bare hands or a knife.'),
    Skill('shield', 4, 'Defend with a shield.'),
    Skill('spear', 4, 'Attack and defend with a spear.'),
    Skill('sword', 4, 'Attack and defend with a sword.')
]


def display_character_info(player):
    data = ['Skill points: ' + str(player.skill_points),
        'Current health: ' + str(int(player.fighter.hp)),
        'Maximum wounds: ' + str(player.fighter.max_hp),
        'Skills:']
    for key, value in player.fighter.skills.items():
        data.append('  ' + key + ': ' + str(value))

    info_string = '\n'.join(data)
    renderer.msgbox(info_string, CHARACTER_SCREEN_WIDTH)


def try_drop(player):
    chosen_item = inventory_menu(
        player,
        'Press the key next to an item to drop it, x to examine, or any other to cancel.\n')
    if chosen_item is not None:
        actions.drop(player, chosen_item.owner)
        return True
    return False


def try_fire(player):
    weapon = actions.get_equipped_in_slot(player, 'left hand')
    if not weapon.owner.missile_weapon:
        log.message('No missile weapon ready to fire.')
        return False
    ammo = actions.get_equipped_in_slot(player, 'quiver')
    if not ammo or ammo.owner.name != weapon.owner.missile_weapon.ammo:
        log.message('You need at least one ' + weapon.owner.missile_weapon.ammo + ' to fire the ' + weapon.owner.name)
        return False
    actions.draw(player, weapon.owner)


def try_pick_up(player):
    for object in player.current_map.objects:
        if object.x == player.x and object.y == player.y and object.item:
            return actions.pick_up(player, object)
    return False


def try_use(player):
    chosen_item = inventory_menu(
        player,
        'Press the key next to an item to use it, x to examine, or any other to cancel.\n')
    if chosen_item is not None:
        actions.use(player, chosen_item.owner)
        return True
    return False


def increase_player_skills(player):
    while True:
        options = [s.name + ': currently ' + str(player.fighter.skills.get(s.name, 0)) +
                   ', costs ' + str(s.cost) + ' sp'
            for s in skill_list]

        # Make sure log.message() displays as we loop
        renderer.render_all(player, None)
        (key, target) = renderer.menu('Choose skill to increase, or x to explain:\n' +
                                      '(' + str(player.skill_points) + ' skill points available)\n',
                                      options, INVENTORY_WIDTH)
        if key == ord('x'):
            (c2, i2) = renderer.menu('Choose skill to describe, or any other to cancel.\n\n', options, INVENTORY_WIDTH)
            if i2 is not None:
                log.message(skill_list[i2].name + ': ' + skill_list[i2].description)
            
        if target is None:  # 0 *is* a valid target
            return

        if skill_list[target].cost > player.skill_points:
            log.message(skill_list[target].name.capitalize() + ' costs ' + str(skill_list[target].cost) +
                        ' skill points, you only have ' + str(player.skill_points))
            continue

        value = player.fighter.skills.get(skill_list[target].name, 10)
        if value >= 250:
            log.message(skill_list[target].name.capitalize() + ' is already at its maximum.')
            continue

        player.skill_points -= skill_list[target].cost
        if value < 100:
            value += libtcod.random_get_int(0, 1, 8)
        elif value < 150:
            value += libtcod.random_get_int(0, 1, 4)
        elif value < 200:
            value += libtcod.random_get_int(0, 1, 2)
        elif value < 250:
            value += 1
        player.fighter.skills[skill_list[target].name] = value
        log.message('Increased ' + skill_list[target].name + ' to ' + str(value))


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


def display_help():
    renderer.msgbox('move using numpad or "vi" keys:\n' +
                    '  7 8 9   y k u\n' +
                    '   \|/     \|/ \n' +
                    '  4-+-6   h-+-l\n' +
                    '   /|\     /|\ \n' +
                    '  1 2 3   b j m\n' +
                    '\n' +
                    '  numpad 5 or . (period) to wait,\n' +
                    '  shift-move to run\n' +
                    '\n' +
                    'g/get, d/drop, c/character information\n' +
                    'f/fire your bow\n  (use mouse or movement keys to aim)\n' +
                    'i/view inventory\n  (equip, use, or examine carried items)\n' +
                    's/increase skills\n' +
                    '</traverse stairs\n' +
                    '\n' +
                    'control-p/scroll through old log messages\n' +
                    'mouse over objects to look at them\n',
                    INVENTORY_WIDTH)


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
    target_obj = None
    for obj in player.current_map.objects:
        if obj.fighter and obj.pos == goal:
            target_obj = obj
            break
    if target_obj is not None:
        # Make sure we're not going up or down a cliff
        if not player.current_map.is_blocked_from(player.pos, target_obj.pos, ignore=target_obj):
            actions.attack(player.fighter, target_obj)
            return True
        return False

    # Is there an interactable object?
    target_obj = None
    for obj in player.current_map.objects:
        if obj.interactable and obj.pos == goal:
            target_obj = obj
            break
    if target_obj is not None:
        target_obj.interactable.use_function(player, target_obj)
        return True

    elevation_before_moving = player.current_map.elevation(player.pos.x, player.pos.y)
    if actions.move(player, direction):
        player.current_map.fov_needs_recompute = True
        if player.current_map.xp_visit:
            player.current_map.xp_visit(player.current_map, player)
        if player.current_map.is_outdoors:
            new_region = player.current_map.region[player.pos.x][player.pos.y]
            new_elevation = player.current_map.region_elevations[new_region]
            if new_elevation != elevation_before_moving:
                player.current_map.fov_elevation_changed = True
                player.fighter.exhaustion += actions.CLIMB_EXHAUSTION
        if try_running:
            player.game_state = 'running'
            player.run_direction = direction
        # Automatically sweep up ammunition after a shooting spree
        ammo_eq = actions.get_equipped_in_slot(player, 'quiver')
        if ammo_eq:
            for obj in player.current_map.objects:
                if (obj.pos == player.pos and obj.item and 
                        obj.item.can_combine(ammo_eq.owner)):
                    actions.pick_up(player, obj)
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
    (Or None?!)
    """
    key_char = chr(key.c)

    if key.vk == libtcod.KEY_ENTER and key.lalt:
        # Alt+Enter: toggle fullscreen
        libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())

    elif key.vk == libtcod.KEY_ESCAPE:
        return 'exit'

    elif key_char == 'p' and (key.lctrl or key.rctrl):
        interface.log_display()

    if player.game_state == 'shooting':
        weapon_eq = actions.get_equipped_in_slot(player, 'left hand')
        ammo_eq = actions.get_equipped_in_slot(player, 'quiver')
        target = spells._target_monster(player, weapon_eq.owner.missile_weapon.max_range)
        player.game_state = 'playing'
        if not target:
            return 'didnt-take-turn'
        actions.fire(player, weapon_eq, ammo_eq, target)
        return

    if player.game_state == 'running':
        if (player.endangered or
                key.vk != libtcod.KEY_NONE or
                _running_lookahead(player) or
                not player_move_or_attack(player, player.run_direction, False)):
            player.game_state = 'playing'
            return 'didnt-take-turn'
        return

    if player.game_state == 'playing':
        # movement keys
        (parsed, direction, shift) = interface.parse_move(key)
        if parsed and direction and (key.lctrl or key.rctrl):
            # Would like to move the camera here, but current
            # implementation of render_all() forces camera_update()
            # to refocus on the player every frame.
            # move_camera(direction)
            return 'didnt-take-turn'

        if parsed:
            if direction:
                player_move_or_attack(player, direction, shift)
            else:
                # Do nothing
                pass
        else:
            if key_char == 'c':
                display_character_info(player)
            if key_char == 'd':
                try_drop(player)
            if key_char == 'f':
                try_fire(player)
                return  # takes turn!
            if key_char == 'g':
                try_pick_up(player)
            if key_char == 'i':
                if try_use(player):
                    return  # takes turn!
            if key_char == 's':
                increase_player_skills(player)
            if key_char == '<':
                try_stairs(player)
            if (key_char == '?' or key.vk == libtcod.KEY_F1):
                display_help()

            return 'didnt-take-turn'


EPITAPHS = [
    'The dead cannot come back to life; the departed soul does not return.',
    'You stayed for a while and then moved along, just as a caravan does.',
    'The hizir on the gray horse has claimed you for his own.'
]

def player_death(player):
    """
    End the game!
    """
    log.message(EPITAPHS[libtcod.random_get_int(0, 0, len(EPITAPHS)-1)], libtcod.crimson)
    log.message('You died!', libtcod.crimson)
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
    libtcod.map_compute_fov(
        player.current_map.fov_map, player.x,
        player.y, config.TORCH_RADIUS, config.FOV_LIGHT_WALLS, config.FOV_ALGO)

    return player


def _new_item(player, obj):
    player.inventory.append(obj)
    obj.always_visible = True


def _new_equipment(player, obj):
    _new_item(player, obj)
    actions.equip(player, obj.equipment, False)


def _start_near_quarry(player):
    if player.current_map.quarry_regions:
        quarry_center = player.current_map.region_seeds[player.current_map.quarry_regions[0]]
        player.pos = algebra.Location(quarry_center[0]+20, quarry_center[1]-20)

def _start_near_grotto(player):
    if player.current_map.grotto_region:
        grotto_center = player.current_map.region_seeds[player.current_map.grotto_region]
        player.pos = algebra.Location(grotto_center[0]+20, grotto_center[1])

def _start_near_peak(player):
    player.pos = algebra.Location(player.current_map.peak[0] + 20,
                                  player.current_map.peak[1] - 20)

def _start_near_end(player):
    stairwell = player.current_map.dungeon_stairs[0]
    player.pos = algebra.Location(stairwell.x + 20, stairwell.y - 20)

def new_game():
    """
    Starts a new game, with a default player on level 1 of the dungeon.
    Returns the player object.
    """
    # Must initialize the log before we do anything that might emit a message.
    log.init()
    quest.display_welcome()

    player = Object(None, '@', 'player', libtcod.white, blocks=True,
        fighter=Fighter(
            hp=36,
            death_function=player_death,
            skills={'bow':70, 'first aid':24, 'grappling':40}))
    player.inventory = []
    player.level = 1
    player.game_state = 'playing'
    player.skill_points = 0
    player.turn_count = 0
    # True if there's a (hostile) fighter in FOV
    player.endangered = False

    _new_equipment(player,
        Object(None, '(', 'silk undertunic', libtcod.dark_sky,
            item=Item(description='A thick under-tunic of raw silk; prevents 2 bleeding.'),
            equipment=Equipment(slot='underclothes', bleeding_defense=2)))

    _new_equipment(player,
        Object(None, '(', 'quilt kaftan', libtcod.dark_sky,
            item=Item(description='A heavy quilted kaftan; keeps you warm and prevents 2 wound.'),
            equipment=Equipment(slot='robes', defense_bonus=2)))

    _new_equipment(player,
        Object(None, '(', 'felt cap', libtcod.dark_sky,
            item=Item(description='A Phrygian felt cap with a loose veil to keep the sun off.'),
            equipment=Equipment(slot='head')))

    _new_equipment(player, miscellany.horn_bow())
    _new_equipment(player, miscellany.arrow(12))
    _new_equipment(player, miscellany.dagger())

    _new_item(player, miscellany.kumiss(4))
    _new_item(player, miscellany.bandage(4))

    mountain_cartographer.make_map(player, 1)
    renderer.update_camera(player)

    renderer.finish_welcome()

    log.message('At last you have reached the foot of the mountain. She waits above.', libtcod.red)
    log.message('Press ? or F1 for help.')

    # _start_near_quarry(player)
    # _start_near_grotto(player)
    # _start_near_peak(player)
    # _start_near_end(player)

    # TEST
    # actions.add_to_map(player.current_map, player.pos, miscellany.sword())
    # actions.add_to_map(player.current_map, player.pos, miscellany.roundshield())

    libtcod.map_compute_fov(
        player.current_map.fov_map, player.x,
        player.y, config.TORCH_RADIUS, config.FOV_LIGHT_WALLS, config.FOV_ALGO)

    return player


def next_level(player, portal):
    """
    Advance to the next level (changing player.current_map).
    Heals the player 50%.
    Returns the Map of the new level.
    """
    actions.heal(player.fighter, player.fighter.max_hp / 2)
    old_map = player.current_map
    generator = portal.generator
    need_stairs = generator(player, player.current_map.dungeon_level + 1)
    renderer.clear_console()
    renderer.update_camera(player)

    if need_stairs:
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
    for obj in player.current_map.objects:
        if obj == player:
            continue
        if (libtcod.map_is_in_fov(player.current_map.fov_map, obj.x, obj.y) or
                (obj.always_visible and
                 player.current_map.is_explored(obj.pos))):
            visible_objects.append(obj)
            if obj.fighter:
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

        # Recompute FOV *here*, not during rendering the way the tutorial did,
        # so that monsters can react to the player's movement!
        # This is a d'oh! sort of issue, because FOV is about gameplay, not
        # just about rendering.
        if player.current_map.fov_needs_recompute:
            libtcod.map_compute_fov(
                player.current_map.fov_map, player.x,
                player.y, config.TORCH_RADIUS, config.FOV_LIGHT_WALLS, config.FOV_ALGO)

        if (player_action != 'didnt-take-turn' and
                (player.game_state == 'playing' or
                 player.game_state == 'running' or
                 player.game_state == 'shooting')):
            for object in player.current_map.objects:
                if object.ai:
                    object.ai.take_turn(player)
                if object.fighter and object.fighter.bleeding > 0:
                    # this will also include the player
                    actions.bleed(object)
            player.turn_count += 1
            if player.fighter.inebriation > 0:
                player.fighter.inebriation -= 1


if __name__ == '__main__':
    renderer.renderer_init()
    # cProfile.run('renderer.main_menu(new_game, play_game, load_game)')
    renderer.main_menu(new_game, play_game, load_game)
    sys.exit()
