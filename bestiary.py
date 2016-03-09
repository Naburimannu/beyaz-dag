import libtcodpy as libtcod

import algebra
from components import *
import ai


def _insert(creature, new_map):
    new_map.objects.append(creature)
    creature.current_map = new_map    


def bandit(new_map, pos, player):
    creature = Object(pos, 'U', 'bandit', libtcod.white, blocks=True,
        fighter = Fighter(hp=16, death_function=ai.monster_death),
        ai = AI(ai.hostile_monster, ai.hostile_monster_metadata(player)))
    creature.inventory = []
    _insert(creature, new_map)
    return creature


def ghul(new_map, pos, player):
    creature = Object(pos, 'U', 'ghul', libtcod.white, blocks=True,
        fighter = Fighter(hp=20, unarmed_damage=4, death_function=ai.monster_death),
        ai = AI(ai.hostile_monster, ai.hostile_monster_metadata(player)))
    _insert(creature, new_map)
    return creature


def swamp_goblin(new_map, pos, player):
    creature = Object(pos, 'g', 'swamp goblin', libtcod.red, blocks=True,
        fighter=Fighter(hp=12, death_function=ai.monster_death),
        ai=AI(ai.hostile_monster, ai.hostile_monster_metadata(player)))
    _insert(creature, new_map)
    return creature