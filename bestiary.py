# Copyright 2016 Thomas C. Hudson
# Governed by the license described in LICENSE.txt
import libtcodpy as libtcod

import algebra
from components import *
import log
import ai
import actions
import miscellany


def _insert(creature, new_map):
    new_map.objects.append(creature)
    creature.current_map = new_map


def _ignoring_monster(new_map, pos, player, glyph, name, color, hp=12, unarmed_damage=2, on_idle=None):
    pos.bound(new_map.loc_bound)
    creature = Object(pos, glyph, name, color, blocks=True,
        fighter=Fighter(hp=hp, unarmed_damage=unarmed_damage, death_function=ai.monster_death),
        ai=AI(ai.ignoring_monster, ai.ignoring_monster_metadata(on_idle)))
    _insert(creature, new_map)
    return creature


def _hostile_monster(new_map, pos, player, glyph, name, color, hp=12, unarmed_damage=2, on_strike=None, skills={}):
    pos.bound(new_map.loc_bound)
    creature = Object(pos, glyph, name, color, blocks=True,
        fighter=Fighter(hp=hp, unarmed_damage=unarmed_damage,
                        death_function=ai.monster_death, skills=skills),
        ai=AI(ai.hostile_monster, ai.hostile_monster_metadata(player)))
    creature.fighter.on_unarmed_strike = on_strike
    _insert(creature, new_map)
    return creature


def _territorial_monster(new_map, pos, player, glyph, name, color, hp=12, unarmed_damage=2, skills={}, radius=3):
    pos.bound(new_map.loc_bound)
    creature = Object(pos, glyph, name, color, blocks=True,
        fighter=Fighter(hp=hp, unarmed_damage=unarmed_damage, death_function=ai.monster_death,
                        skills=skills),
        ai=AI(ai.territorial_monster, ai.territorial_monster_metadata(pos, radius)))
    _insert(creature, new_map)
    return creature


def _add_inventory(creature):
    creature.inventory = []
    return creature


def bandit(new_map, pos, player):
    return _add_inventory(
        _hostile_monster(new_map, pos, player,
                         'p', 'bandit', libtcod.blue, hp=24,
                         skills={'grappling':30, 'sword':30, 'spear':30, 'bow':30, 'shield':20}))

def ghul(new_map, pos, player):
    return _hostile_monster(new_map, pos, player,
                            'z', 'ghul', libtcod.dark_orange, hp=30, unarmed_damage=4,
                            skills={'grappling':30})

def slime(new_map, pos, player):
    return _hostile_monster(new_map, pos, player,
                            ',', 'slime', libtcod.white, unarmed_damage=3,
                            on_strike=_slime_strike,
                            skills={'grappling':30})

def _slime_strike(attacker_ftr, target_obj, damage):
    d_armor_eq = actions.get_equipped_in_slot(target_obj, 'robes')
    if not d_armor_eq:
        d_armor_eq = actions.get_equipped_in_slot(target_obj, 'armor')
    if not d_armor_eq:
        d_armor_eq = actions.get_equipped_in_slot(target_obj, 'underclothes')
    if d_armor_eq and libtcod.random_get_int(0, 1, 20) <= damage + 2 * d_armor_eq.defense_bonus:
        d_armor_eq.defense_bonus -= 1
        if d_armor_eq.defense_bonus <= 0:
            log.message('Acid destroys the ' + d_armor_eq.owner.name + ' worn by ' + target_obj.name)
            target_obj.inventory.remove(d_armor_eq.owner)
        else:
            log.message('Acid weakens the ' + d_armor_eq.owner.name + ' worn by ' + target_obj.name)


def jelly(new_map, pos, player):
    return _hostile_monster(new_map, pos, player,
                            'j', 'jelly', libtcod.white, hp=24, unarmed_damage=4,
                            on_strike=_slime_strike,
                            skills={'grappling':30})

def worm(new_map, pos, player):
    return _hostile_monster(new_map, pos, player,
                            'w', 'seething mass of worms', libtcod.white, unarmed_damage=6)

def swamp_goblin(new_map, pos, player):
    return _hostile_monster(new_map, pos, player,
                            'g', 'swamp blight', libtcod.light_blue, hp=16, unarmed_damage=3,
                            skills={'grappling':20})

def vodanyoi(new_map, pos, player):
    return _add_inventory(
        _hostile_monster(new_map, pos, player,
                         'k', 'vodanyoi', libtcod.dark_han, hp=10, unarmed_damage=3,
                         skills={'grappling':20}))

def vodanyoi_warrior(new_map, pos, player):
    return _add_inventory(
        _hostile_monster(new_map, pos, player,
                         'k', 'vodanyoi warrior', libtcod.violet, hp=16, unarmed_damage=3,
                         skills={'grappling':20, 'spear':30}))

def rusalka(new_map, pos, player):
    return _add_inventory(
        _ignoring_monster(new_map, pos, player,
                             'h', 'rusalka', libtcod.darker_sea, hp=24,
                             on_idle=_idle_rusalka))

def _idle_rusalka(player):
    action = libtcod.random_get_int(0, 1, 3)
    if action == 1:
        log.message('The rusalka sings a plaintive song of longing and loss.', libtcod.dark_fuchsia)
        player.fighter.inebriation += 30
        if player.fighter.inebriation > 300:
            log.message("You want nothing more than to sit down and listen.", libtcod.dark_fuchsia)
        elif player.fighter.inebriation > 150:
            log.message("Something about the song tugs at your heartstrings.", libtcod.dark_fuchsia)
        
        return True
    elif action == 2:
        log.message('The rusalka combs her hair.')
    return False

def bear(new_map, pos, player):
    _insert(miscellany.honey_tree(pos), new_map)
    return _territorial_monster(new_map, pos, player, 'U', 'bear',
                                libtcod.darker_orange, hp=40, unarmed_damage=8,
                                skills={'grappling':25})

def wolf(new_map, pos, player):
    return _hostile_monster(new_map, pos, player, 'C', 'wolf',
                            libtcod.darker_orange, hp=16, unarmed_damage=4,
                            skills={'grappling':30})

def wolf_pair(new_map, pos, player):
    return (_hostile_monster(new_map, pos, player, 'C', 'wolf',
                            libtcod.darker_orange, hp=16, unarmed_damage=4,
                            skills={'grappling':30}),
        _hostile_monster(new_map, pos + actions.random_direction(), player, 'C', 'wolf',
                                    libtcod.darker_orange, hp=16, unarmed_damage=4,
                                    skills={'grappling':30}))

def hyena(new_map, pos, player):
    return _hostile_monster(new_map, pos, player, 'C', 'hyena',
                            libtcod.amber, hp=12, unarmed_damage=3,
                            skills={'grappling':20})

def hyena_pair(new_map, pos, player):
    return (_hostile_monster(new_map, pos, player, 'C', 'hyena',
                            libtcod.amber, hp=12, unarmed_damage=3,
                            skills={'grappling':20}),
        _hostile_monster(new_map, pos + actions.random_direction(), player, 'C', 'hyena',
                            libtcod.amber, hp=12, unarmed_damage=3,
                            skills={'grappling':20}))

def snow_leopard(new_map, pos, player):
    return _hostile_monster(new_map, pos, player, 'f', 'snow leopard',
                            libtcod.white, hp=30, unarmed_damage=6,
                            skills={'grappling':45})

def deer(new_map, pos, player):
    return _ignoring_monster(new_map, pos, player, 'q', 'deer',
                             libtcod.darker_yellow, hp=16)

def gazelle(new_map, pos, player):
    return _ignoring_monster(new_map, pos, player, 'q', 'gazelle',
                             libtcod.amber, hp=12)

def dvergr(new_map, pos, player):
    return _add_inventory(
        _hostile_monster(new_map, pos, player, 'h', 'dvergr',
                            libtcod.dark_magenta, hp=24,
                            skills={'grappling':30, 'axe':30, 'shield':30}))

def tepegoz(new_map, pos, player):
    return _add_inventory(
        _hostile_monster(new_map, pos, player, 'P', 'Tepegoz',
                            libtcod.peach, hp=80, unarmed_damage=8,
                            skills={'grappling':60, 'spear':60, 'shield':30}))

# UNUSED
def steppe_pony(new_map, pos, player):
    return _ignoring_monster(new_map, pos, player, 'q', 'steppe pony',
                             libtcod.darker_flame, hp=34, unarmed_damage=6,
                            skills={'grappling':15})

# deserves poison? or just model that as automatic bleeding?
# def snake(new_map, pos, player):

# def beastman aka broo
