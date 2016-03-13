"""
Spells (magic item effects) and targeting utility functions.

Could be folded into actions.py.
"""
# Copyright 2016 Thomas C. Hudson
# Governed by the license described in LICENSE.txt
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
    actor.fighter.inebriation += actor.fighter.inebriation + 150
    actor.fighter.exhaustion /= 2
    log.message("The kumiss is revitalizing.", libtcod.dark_fuchsia)
    if actor.fighter.inebriation > 300:
        log.message("You're feeling rather drunk!", libtcod.dark_fuchsia)
    elif actor.fighter.inebriation > 150:
        log.message("You're getting a bit tipsy.", libtcod.dark_fuchsia)
