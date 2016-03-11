"""
AI routines, AI data, and monster death.
"""
import libtcodpy as libtcod

import log
from components import *
import actions


# Might make sense to have this defined
# in spells.py instead, dropping the
# default argument?
CONFUSE_NUM_TURNS = 10


def fleeing_monster(monster, player, metadata):
    if libtcod.map_is_in_fov(monster.current_map.fov_map,
                             monster.x, monster.y):
        # No intelligent behavior at all here
        actions.move_away_from(monster, metadata.target.pos)


def ignoring_monster(monster, player, metadata):
    """
    A creature that moves randomly (q.v. confused_monster) and ignores
    the player unless hurt, in which case it becomes hostile or scared.
    """
    if libtcod.map_is_in_fov(monster.current_map.fov_map,
                             monster.x, monster.y):
        if monster.fighter.last_attacker:
            if monster.fighter.unarmed_damage > 2:
                monster.ai = AI(hostile_monster,
                                hostile_monster_metadata(monster.fighter.last_attacker))
            else:
                monster.ai = AI(fleeing_monster,
                                hostile_monster_metadata(monster.fighter.last_attacker))
            monster.ai.set_owner(monster)
            return monster.ai.take_turn(player)
        # TODO: this movement may fail, so the monster will appear to
        # move less when in constricted quarters.
        actions.move(monster, actions.random_direction())



class hostile_monster_metadata:
    def __init__(self, target):
        self.target = target


def hostile_monster(monster, player, metadata):
    """
    A basic monster takes its turn. if you can see it, it can see you.
    """
    if libtcod.map_is_in_fov(monster.current_map.fov_map,
                             monster.x, monster.y):
        if monster.distance_to(metadata.target) >= 2:
            actions.move_towards(monster, metadata.target.pos)
        elif metadata.target.fighter.hp > 0:
            if not monster.current_map.is_blocked_from(monster.pos, metadata.target.pos,
                                                       ignore=metadata.target):
                actions.attack(monster.fighter, metadata.target)


def hostile_archer(monster, player, metadata):
    if libtcod.map_is_in_fov(monster.current_map.fov_map,
                             monster.x, monster.y):
        weapon_eq = actions.get_equipped_in_slot(monster, 'missile weapon')
        ammo_eq = actions.get_equipped_in_slot(monster, 'quiver')
        if monster.game_state == 'shooting':
            # TODO: possibly cheats on range
            actions.fire(monster, weapon_eq, ammo_eq, metadata.target)
            monster.game_state = None
            return

        distance = monster.distance(metadata.target.pos)
        if (weapon_eq is not None and
                ammo_eq is not None and
                libtcod.random_get_int(0, 1, 2) == 1 and
                distance > 1 and
                distance < weapon_eq.owner.missile_weapon.max_range):
            actions.draw(monster, weapon_eq.owner)
        else:
            hostile_monster(monster, player, metadata)

class confused_monster_metadata:
    def __init__(self, old_ai, num_turns=CONFUSE_NUM_TURNS):
        self.old_ai = old_ai
        self.num_turns = num_turns


def confused_monster(monster, player, metadata):
    if metadata.num_turns > 0:
        actions.move(monster, actions.random_direction())
        metadata.num_turns -= 1
    else:
        # Restore the previous AI (this one will be deleted
        # because it's not referenced anymore)
        monster.ai = metadata.old_ai
        log.message(monster.name.capitalize() +
                    ' is no longer confused!', libtcod.red)


def monster_death(monster):
    # Transform it into a nasty corpse! it doesn't block, can't be
    # attacked, and doesn't move.
    log.message(
        'The ' + monster.name + ' is dead!', libtcod.orange)
    monster.char = '%'
    monster.color = libtcod.dark_red
    monster.blocks = False
    monster.fighter = None
    monster.ai = None

    if hasattr(monster, 'inventory'):
        while len(monster.inventory) > 0:
            # Might be nice to report what's dropped; even though we
            # have drop-all, we can't suppress unequip reporting while
            # still reporting dropping.
            actions.drop(monster, monster.inventory[0], report=False, drop_all=True)

    monster.name = 'remains of ' + monster.name
    monster.current_map.objects.remove(monster)
    monster.current_map.objects.insert(0, monster)


