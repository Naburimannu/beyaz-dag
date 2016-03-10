import libtcodpy as libtcod

import algebra
from components import *
import ai


def _insert(creature, new_map):
    new_map.objects.append(creature)
    creature.current_map = new_map


def _ignoring_monster(new_map, pos, player, glyph, name, color, hp=12, unarmed_damage=2):
    creature = Object(pos, glyph, name, color, blocks=True,
        fighter=Fighter(hp=hp, unarmed_damage=unarmed_damage, death_function=ai.monster_death),
        ai=AI(ai.ignoring_monster, None))
    _insert(creature, new_map)
    return creature


def _hostile_monster(new_map, pos, player, glyph, name, color, hp=12, unarmed_damage=2, skills={}):
    creature = Object(pos, glyph, name, color, blocks=True,
        fighter=Fighter(hp=hp, unarmed_damage=unarmed_damage, death_function=ai.monster_death,
                        skills=skills),
        ai=AI(ai.hostile_monster, ai.hostile_monster_metadata(player)))
    _insert(creature, new_map)
    return creature


def _add_inventory(creature):
    creature.inventory = []
    return creature


def bandit(new_map, pos, player):
    return _add_inventory(
        _hostile_monster(new_map, pos, player,
                         'p', 'bandit', libtcod.blue, hp=24,
                         skills={'grappling':30, 'sword':30, 'spear':30, 'bow':30}))


def ghul(new_map, pos, player):
    return _hostile_monster(new_map, pos, player,
                            'z', 'ghul', libtcod.dark_orange, hp=30, unarmed_damage=4,
                            skills={'grappling':30})


def swamp_goblin(new_map, pos, player):
    return _hostile_monster(new_map, pos, player,
                            'g', 'swamp goblin', libtcod.light_blue, hp=16)


def bear(new_map, pos, player):
    return _hostile_monster(new_map, pos, player, 'q', 'bear',
                            libtcod.darker_orange, hp=40, unarmed_damage=6)


def wolf(new_map, pos, player):
    return _hostile_monster(new_map, pos, player, 'C', 'wolf',
                            libtcod.darker_orange, hp=16, unarmed_damage=4)

def hyena(new_map, pos, player):
    return _hostile_monster(new_map, pos, player, 'C', 'hyena',
                            libtcod.amber, hp=12, unarmed_damage=3)

def snow_leopard(new_map, pos, player):
    return _hostile_monster(new_map, pos, player, 'f', 'snow leopard',
                            libtcod.white, hp=30, unarmed_damage=6)

def deer(new_map, pos, player):
    return _ignoring_monster(new_map, pos, player, 'q', 'deer',
                             libtcod.darker_yellow, hp=16)

def gazelle(new_map, pos, player):
    return _ignoring_monster(new_map, pos, player, 'q', 'gazelle',
                             libtcod.amber, hp=12)

def steppe_pony(new_map, pos, player):
    return _ignoring_monster(new_map, pos, player, 'q', 'steppe pony',
                             libtcod.darker_flame, hp=34, unarmed_damage=6)

# deserves poison? or just model that as automatic bleeding?
# def snake(new_map, pos, player):

# def beastman aka broo
