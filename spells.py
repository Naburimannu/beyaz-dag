"""
Spells (magic item effects) and targeting utility functions.

Could be folded into actions.py.
"""
import libtcodpy as libtcod

import log
from components import *
import actions
import ai
import interface

HEAL_AMOUNT = 40
LIGHTNING_DAMAGE = 40
LIGHTNING_RANGE = 5
CONFUSE_RANGE = 8
FIREBALL_RADIUS = 3
FIREBALL_DAMAGE = 25


def _target_monster(actor, max_range=None):
    """
    Returns a clicked monster inside FOV up to a range,
    or None if right-clicked.
    """
    while True:
        pos = interface.target_tile(actor, max_range)
        if pos is None:
            return None

        for obj in actor.current_map.objects:
            if (obj.x == pos.x and obj.y == pos.y and obj.fighter and
                    obj != actor):
                return obj


def _closest_monster(actor, max_range):
    """
    Find closest enemy in the player's FOV, up to a maximum range.
    """
    closest_enemy = None
    closest_dist = max_range + 1

    for object in actor.current_map.objects:
        if (object.fighter and not object == actor and
                libtcod.map_is_in_fov(actor.current_map.fov_map,
                                      object.x, object.y)):
            dist = actor.distance_to(object)
            if dist < closest_dist:
                closest_enemy = object
                closest_dist = dist
    return closest_enemy


def use_bandage(actor):
    """
    First aid skill needs to be at least 2x wounds + 5x bleeding to have a 50-50 chance of making
    things better, but if so it does quite a lot.
    """
    effective_skill = actor.fighter.skills.get('first aid', 0) - actor.fighter.action_penalty
    difficulty = actor.fighter.wounds + actor.fighter.bleeding * 4

    attack_roll = libtcod.random_get_int(0, 1, effective_skill)
    defense_roll = libtcod.random_get_int(0, 1, difficulty)

    if defense_roll > attack_roll:
        log.message("Your efforts don't help.", libtcod.red)
        return

    if actor.fighter.bleeding > 0:
        if actor.fighter.bleeding < attack_roll / 8:
            attack_roll -= actor.fighter.bleeding * 4
            actor.fighter.bleeding = 0
        else:
            attack_roll /= 2
            actor.fighter.bleeding /= 2

    actor.fighter.wounds = max(actor.fighter.wounds - attack_roll, 0)
    log.message("You bandage your wounds.")


def drink_kumiss(actor):
    """
    Drunkenness accumulates quickly if you drink more kumiss before
    you've recovered from the first.
    """
    actor.fighter.inebriation += actor.fighter.inebriation + 100
    actor.fighter.exhaustion /= 2
    log.message("The kumiss is revitalizing.")
    if actor.fighter.inebriation > 300:
        log.message("You're feeling rather drunk!", libtcod.red)
    elif actor.fighter.inebriation > 100:
        log.message("You're getting a bit tipsy.")


def cast_heal(actor):
    """
    Heal the caster.
    """
    if actor.fighter.hp == actor.fighter.max_hp:
        log.message('You are already at full health.', libtcod.red)
        return 'cancelled'

    log.message('Your wounds start to feel better!', libtcod.light_violet)
    actions.heal(actor.fighter, HEAL_AMOUNT)


def cast_lightning(actor):
    """
    Find closest enemy (inside a maximum range) and damage it.
    """
    monster = _closest_monster(actor, LIGHTNING_RANGE)
    if monster is None:
        log.message('No enemy is close enough to strike.', libtcod.red)
        return 'cancelled'

    log.message('A lighting bolt strikes the ' + monster.name +
                ' with a loud thunder! The damage is ' +
                str(LIGHTNING_DAMAGE) + ' hit points.', libtcod.light_blue)
    actions.inflict_damage(actor, monster.fighter, LIGHTNING_DAMAGE)


def cast_fireball(actor):
    log.message('Left-click a target tile for the fireball, '
                'or right-click to cancel.', libtcod.light_cyan)
    pos = interface.target_tile(actor)
    if pos is None:
        return 'cancelled'
    log.message('The fireball explodes, burning everything within ' +
                str(FIREBALL_RADIUS) + ' tiles!', libtcod.orange)

    for obj in actor.current_map.objects:
        if obj.distance(pos) <= FIREBALL_RADIUS and obj.fighter:
            log.message('The ' + obj.name + ' gets burned for ' +
                        str(FIREBALL_DAMAGE) + ' hit points.',
                        libtcod.orange)
            actions.inflict_damage(actor, obj.fighter, FIREBALL_DAMAGE)


def cast_confuse(actor):
    log.message('Left-click an enemy to confuse it, or right-click to cancel.',
                libtcod.light_cyan)
    monster = _target_monster(actor, CONFUSE_RANGE)
    if monster is None:
        return 'cancelled'

    old_ai = monster.ai
    monster.ai = AI(ai.confused_monster, ai.confused_monster_metadata(old_ai))
    monster.ai.set_owner(monster)
    log.message('The eyes of the ' + monster.name +
                ' look vacant, as he starts to stumble around!',
                libtcod.light_green)
