import libtcodpy as libtcod

import algebra
from components import *
import ai
import actions
import miscellany


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


def _territorial_monster(new_map, pos, player, glyph, name, color, hp=12, unarmed_damage=2, skills={}, radius=3):
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
                            skills={'grappling':30})

def jelly(new_map, pos, player):
    return _hostile_monster(new_map, pos, player,
                            'j', 'jelly', libtcod.white, hp=24, unarmed_damage=4,
                            skills={'grappling':30})

def worm(new_map, pos, player):
    return _hostile_monster(new_map, pos, player,
                            'w', 'seething worm', libtcod.white, unarmed_damage=6)

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
    return _ignoring_monster(new_map, pos, player,
                             'h', 'rusalka', libtcod.darker_sea, hp=24)

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

def tepegoz(new_map, pos, player):
    return _hostile_monster(new_map, pos, player, 'P', 'Tepegoz',
                            libtcod.peach, hp=80, unarmed_damage=8,
                            skills={'grappling':50, 'spear':50})

# UNUSED
def steppe_pony(new_map, pos, player):
    return _ignoring_monster(new_map, pos, player, 'q', 'steppe pony',
                             libtcod.darker_flame, hp=34, unarmed_damage=6,
                            skills={'grappling':15})

# deserves poison? or just model that as automatic bleeding?
# def snake(new_map, pos, player):

# def beastman aka broo
