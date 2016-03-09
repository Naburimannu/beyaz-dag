import libtcodpy as libtcod

import algebra
from components import *
import ai


def _insert(creature, new_map):
    new_map.objects.append(creature)
    creature.current_map = new_map


def _hostile_monster(new_map, pos, player, glyph, name, color, hp=12, unarmed_damage=2):
    creature = Object(pos, glyph, name, color, blocks=True,
        fighter=Fighter(hp=hp, unarmed_damage=unarmed_damage, death_function=ai.monster_death),
        ai=AI(ai.hostile_monster, ai.hostile_monster_metadata(player)))
    _insert(creature, new_map)
    return creature


def _add_inventory(creature):
    creature.inventory = []
    return creature


def bandit(new_map, pos, player):
    return _add_inventory(_hostile_monster(new_map, pos, player, 'p', 'bandit', libtcod.blue, hp=16))


def ghul(new_map, pos, player):
    return _hostile_monster(new_map, pos, player, 'z', 'ghul', libtcod.dark_orange, hp=20, unarmed_damage=4)


def swamp_goblin(new_map, pos, player):
    return _hostile_monster(new_map, pos, player, 'g', 'swamp goblin', libtcod.light_blue, hp=12)


def bear(new_map, pos, player):
    return _hostile_monster(new_map, pos, player, 'q', 'bear', libtcod.darker_orange, hp=40, unarmed_damage=6)


def wolf(new_map, pos, player):
    return _hostile_monster(new_map, pos, player, 'C', 'wolf', libtcod.darker_orange, hp=16, unarmed_damage=4)


def snow_leopard(new_map, pos, player):
    return _hostile_monster(new_map, pos, player, 'f', 'snow leopard',
                            libtcod.white, hp=30, unarmed_damage=6)
