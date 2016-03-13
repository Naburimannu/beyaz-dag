"""
Implementation of actions.

Includes those which might be used by the AI (movement and combat)
and those which are currently only offered to the player.
Magical effects and targeting (spells.py) could also live here.

Conditionals and interfaces for the player sit up top in roguelike.py.
"""
# Copyright 2016 Thomas C. Hudson
# Governed by the license described in LICENSE.txt
import copy
import libtcodpy as libtcod

import log
import algebra
from components import *
import map


# Every 100 pts of exhaustion = -1 to all skills
#   (equivalent to 1 wound point)
ATTACK_EXHAUSTION = 10
CLIMB_EXHAUSTION = 9
MOVE_EXHAUSTION = 1

# CLIMB_EXHAUSTION is additive with MOVE_EXHAUSTION
# BUG: AI doesn't suffer climb_exhaustion because of coding awkwardness
#   (actions.move() doesn't know about elevation changes, only
#    roguelike.player_move_or_attack())


def random_direction():
    return algebra.directions[libtcod.random_get_int(0, 0, 7)]


def add_to_map(new_map, pos, obj):
    obj.pos = pos
    obj.current_map = new_map # not necessarily necessary?
    new_map.objects.insert(0, obj)


def move(obj, direction):
    """
    Moves object by (dx, dy).
    Returns true if move succeeded.
    """
    goal = obj.pos + direction
    if (goal.x < 0 or goal.y < 0 or
            goal.x >= obj.current_map.width or
            goal.y >= obj.current_map.height):
        # try_ catches this for the player, but need to
        # check here for NPCs
        return False
    if not obj.current_map.is_blocked_from(obj.pos, goal):
        obj.pos = goal
        if obj.fighter:
            obj.fighter.exhaustion += MOVE_EXHAUSTION
        return True
    return False


def move_towards(obj, target_pos):
    """
    Moves object one step towards target location.
    Returns true if move succeeded.
    """
    d = algebra.Direction(target_pos.x - obj.x, target_pos.y - obj.y)
    d.normalize()
    return move(obj, d)


def move_away_from(obj, target_pos):
    """
    Moves object one step away from target location.
    Returns true if move succeeded.
    """
    d = algebra.Direction(obj.x - target_pos.x, obj.y - target_pos.y)
    d.normalize()
    return move(obj, d)


def _assign_damage(fighter, attack_skill, target, defense_skill, quantity, method, report=True):
    if quantity > 0:
        if report:
            log.message(
                fighter.name.capitalize() + ' (' + str(attack_skill) + ') ' +
                method + ' ' + target.name + ' (' + str(defense_skill) + ')' +
                ' for ' + str(quantity) + ' wounds.')
        inflict_damage(fighter, target.fighter, quantity)
    elif report:
        log.message(
            fighter.name.capitalize() + ' (' + str(attack_skill) + ') ' +
            method + ' ' + target.name + ' (' + str(defense_skill) + ')' +
            ' but it has no effect!')


def _drop_ammo_on_hit(target, ammo):
    """
    If a shot hits, ammo is 33% reusable, found in same square
    """
    if libtcod.random_get_int(0, 1, 6) > 2:
        return
    new_ammo = copy.deepcopy(ammo)
    new_ammo.item.count = 1
    add_to_map(target.current_map, target.pos, new_ammo)


def _drop_ammo_on_miss(target, ammo):
    """
    If a shot misses, ammo goes into an adjacent square,
    reusable if that square is not blocked.
    """
    site = target.pos + random_direction()
    if target.current_map.is_blocked_at(site):
        return
    new_ammo = copy.deepcopy(ammo)
    new_ammo.item.count = 1
    add_to_map(target.current_map, site, new_ammo)


def _base_combat_skill(who_ftr):
    skill = who_ftr.skills.get('grappling', 10)
    # print(who_ftr.owner.name.capitalize() + ' grappling is ' + str(a_weapon_skill))
    eqp = get_equipped_in_slot(who_ftr.owner, 'right hand')
    if eqp:
        # print(who_ftr.owner.name.capitalize() + ' is wielding ' + a_weapon.owner.name)
        skill = (who_ftr.skills.get(eqp.owner.melee_weapon.skill, 10) +
                          eqp.owner.melee_weapon.skill_bonus)
        # print(who_ftr.owner.name.capitalize() + ' ' + a_weapon.owner.melee_weapon.skill + ' is ' + str(a_weapon_skill))
    return skill, eqp


def attack(attacker_ftr, target_obj, report=True):
    """
    Melee offence: attacker's weapon skill.
    Melee defense: half defender's weapon skill, plus defender's shield skill.
    Melee impact: attacker's weapon damage.
    Melee absorption: defender's armor soak.
    """
    target_obj.fighter.last_attacker = attacker_ftr.owner
    attacker_ftr.exhaustion += ATTACK_EXHAUSTION

    a_weapon_skill, a_weapon_eq = _base_combat_skill(attacker_ftr)
    d_weapon_skill, d_weapon_eq = _base_combat_skill(target_obj.fighter)

    # if a left-hand item has a defense bonus, use it as a shield
    d_shield_eq = get_equipped_in_slot(target_obj, 'left hand')
    shield_skill = 0
    if d_shield_eq and d_shield_eq.defense_bonus > 0:
        shield_skill = target_obj.fighter.skills.get('shield', 10)
    total_defense_skill = shield_skill + d_weapon_skill / 2

    # print('Attacker action penalty is ' + str(fighter.action_penalty))
    effective_attack_skill = max(a_weapon_skill - attacker_ftr.action_penalty, 10)
    effective_defense_skill = max(total_defense_skill - target_obj.fighter.action_penalty, 10)
    attack_roll = libtcod.random_get_int(0, 1, effective_attack_skill)
    defense_roll = libtcod.random_get_int(0, 1, effective_defense_skill)

    if defense_roll > attack_roll:
        if report:
            log.message(attacker_ftr.owner.name.capitalize() + ' (' + str(effective_attack_skill) + ')' +
                        ' attacks ' + target_obj.name + ' (' + str(effective_defense_skill) + ')' +
                        ' but misses.')
        return

    impact = attacker_ftr.unarmed_damage
    if a_weapon_eq:
        impact = a_weapon_eq.owner.melee_weapon.damage

    damage = impact - target_obj.fighter.defense

    _assign_damage(attacker_ftr.owner, effective_attack_skill,
                   target_obj, effective_defense_skill,
                   damage, 'attacks', report)

    if damage > 0:
        if a_weapon_eq:
            strike_fn = a_weapon_eq.owner.melee_weapon.on_strike
        else:
            strike_fn = attacker_ftr.on_unarmed_strike
        if strike_fn:
            strike_fn(attacker_ftr, target_obj, damage)


def draw(actor_obj, weapon_obj, report=True):
    if report:
        log.message(actor_obj.name.capitalize() + ' readies a ' + weapon_obj.name)
    actor_obj.game_state = 'shooting'


def fire(actor_obj, weapon_eq, ammo_eq, target_obj, report=True):
    ammo_eq.owner.item.count -= 1
    if ammo_eq.owner.item.count == 0:
        unequip(actor_obj, ammo_eq, False)
        actor_obj.inventory.remove(ammo_eq.owner)
    target_obj.fighter.last_attacker = actor_obj
    actor_obj.fighter.exhaustion += ATTACK_EXHAUSTION

    a_weapon_skill = actor_obj.fighter.skills.get(weapon_eq.owner.missile_weapon.skill, 10)
    effective_attack_skill = max(a_weapon_skill - actor_obj.fighter.action_penalty, 10)

    d_shield_eq = get_equipped_in_slot(target_obj, 'left hand')
    effective_shield_skill = 0
    if d_shield_eq and d_shield_eq.defense_bonus > 0:
        shield_skill = target_obj.fighter.skills.get('shield', 10)
        effective_shield_skill = max(shield_skill - target_obj.fighter.action_penalty, 0) / 2

    vector = target_obj.pos - actor_obj.pos
    distance = math.sqrt(vector.x ** 2 + vector.y **  2)
    effective_defense_skill = 5 + 5 * int(distance) + effective_shield_skill
    attack_roll = libtcod.random_get_int(0, 1, effective_attack_skill)
    defense_roll = libtcod.random_get_int(0, 1, effective_defense_skill)

    if defense_roll > attack_roll:
        if report:
            log.message(actor_obj.name.capitalize() + ' (' + str(effective_attack_skill) + ')' +
                        ' shoots at ' + target_obj.name + ' (' + str(effective_defense_skill) + ')' +
                        ' but misses.')
        _drop_ammo_on_miss(target_obj, ammo_eq.owner)
        return

    damage = weapon_eq.owner.missile_weapon.damage - target_obj.fighter.defense
    _assign_damage(actor_obj, effective_attack_skill,
                   target_obj, effective_defense_skill,
                   damage, 'shoots', report)
    _drop_ammo_on_hit(target_obj, ammo_eq.owner)


def inflict_damage(actor_obj, target_ftr, damage):
    """
    Apply damage.
    """
    if damage > 0:
        target_ftr.wounds += damage
        # for now flat 50% chance of inflicting bleeding
        # TODO: base on weapon type?
        if libtcod.random_get_int(0, 0, 1):
            inflict_bleeding(actor_obj, target_ftr, damage / 2)

        if target_ftr.wounds >= target_ftr.max_hp:
            # combat model says we just fall unconscious
            # but in a single-player game is that really
            # worth simulating?
            function = target_ftr.death_function
            if function is not None:
                function(target_ftr.owner)


def inflict_bleeding(actor_obj, target_ftr, bloodloss):
    """
    Apply bleeding.
    """
    bloodloss -= target_ftr.bleeding_defense
    if bloodloss > 0:
        target_ftr.bleeding += bloodloss
        log.message(target_ftr.owner.name.capitalize() + ' bleeds!', libtcod.red)


def bleed(actor_obj):
    # go into floats here so that we can model bleeding continuously
    # instead of assessing it every 10 turns
    actor_obj.fighter.hp -= actor_obj.fighter.bleeding / 10.
    if actor_obj.fighter.hp <= 0:
        function = actor_obj.fighter.death_function
        if function is not None:
            function(actor_obj)
        

def heal(target_ftr, amount):
    """
    Heal by the given amount, without going over the maximum.
    """
    target_ftr.hp += amount
    if target_ftr.hp > target_ftr.max_hp:
        target_ftr.hp = target_ftr.max_hp


def pick_up(actor, obj, report=True):
    """
    Add an Object to the actor's inventory and remove from the map.
    """
    for match in actor.inventory:
        if obj.item.can_combine(match):
            match.item.count += obj.item.count
            actor.current_map.objects.remove(obj)
            if report:
                log.message(actor.name.capitalize() + ' picked up a ' + obj.name + '!', libtcod.green)
            return True

    if len(actor.inventory) >= 22:
        if report:
            log.message(actor.name.capitalize() + ' inventory is full, cannot pick up ' +
                        obj.name + '.', libtcod.red)
        return False
    else:
        actor.inventory.append(obj)
        actor.current_map.objects.remove(obj)
        if report:
            if obj.item.count > 1:
                log.message(actor.name.capitalize() + ' picked up ' + str(obj.item.count) +
                            'x ' + obj.name + '!', libtcod.green)
            else:
                log.message(actor.name.capitalize() + ' picked up a ' + obj.name + '!', libtcod.green)

        # Special case: automatically equip if the corresponding equipment slot is unused.
        equipment = obj.equipment
        if equipment and get_equipped_in_slot(actor, equipment.slot) is None:
            equip(actor, equipment, report)
        return True


def drop(actor, obj, report=True, drop_all=False):
    """
    Remove an Object from the actor's inventory and add it to the map
    at the player's coordinates.
    If it's equipment, unequip before dropping.
    """
    must_split = False
    if obj.item.count > 1 and not drop_all:
        obj.item.count -= 1
        must_split = True
    else:
        if obj.equipment:
            unequip(actor, obj.equipment, report)
        actor.inventory.remove(obj)

    combined = False
    for match in actor.current_map.objects:
        if match.pos == actor.pos and obj.item.can_combine(match):
            if drop_all:
                match.item.count += obj.item.count
            else:
                match.item.count += 1
            combined = True
            break

    if not combined:
        new_o = obj
        if must_split:
            new_o = copy.deepcopy(obj)
        if drop_all:
            new_o.item.count = obj.item.count
        else:
            new_o.item.count = 1
        add_to_map(actor.current_map, actor.pos, new_o)

    if report:
        if drop_all:
            log.message(actor.name.capitalize() + ' dropped ' + str(obj.item.count) + 'x ' + obj.name + '.', libtcod.yellow)
        else:
            log.message(actor.name.capitalize() + ' dropped a ' + obj.name + '.', libtcod.yellow)


def use(actor, obj, report=True):
    """
    If the object has the Equipment component, toggle equip/unequip.
    Otherwise invoke its use_function and (if not cancelled) destroy it.
    """
    if obj.equipment:
        _toggle_equip(actor, obj.equipment, report)
        return

    if obj.item.use_function is None:
        if report:
            log.message('The ' + obj.name + ' cannot be used.')
    else:
        if obj.item.use_function(actor) != 'cancelled':
            if obj.item.count > 1:
                obj.item.count -= 1
            else:
                actor.inventory.remove(obj)


def _toggle_equip(actor, eqp, report=True):
    if eqp.is_equipped:
        unequip(actor, eqp, report)
    else:
        equip(actor, eqp, report)


def equip(actor, eqp, report=True):
    """
    Equip the object (and log unless report=False).
    Ensure only one object per slot.
    """
    old_equipment = get_equipped_in_slot(actor, eqp.slot)
    if old_equipment is not None:
        unequip(actor, old_equipment, report)

    eqp.is_equipped = True
    if report:
        log.message('Equipped ' + eqp.owner.name + ' on ' + eqp.slot + '.', libtcod.light_green)


def unequip(actor, eqp, report=True):
    """
    Unequip the object (and log).
    """
    if not eqp.is_equipped:
        return
    eqp.is_equipped = False
    if report:
        log.message('Unequipped ' + eqp.owner.name + ' from ' + eqp.slot + '.', libtcod.light_yellow)


def get_equipped_in_slot(actor, slot):
    """
    Returns Equipment in a slot, or None.
    """
    if hasattr(actor, 'inventory'):
        for obj in actor.inventory:
            if obj.equipment and obj.equipment.slot == slot and obj.equipment.is_equipped:
                return obj.equipment
    return None


class _MockMap(object):
    def is_blocked_at(self, pos):
        return False


def _test_move():
    obj = Object(algebra.Location(0, 0), 'o', 'test object', libtcod.white)
    obj.current_map = _MockMap()
    assert obj.pos == algebra.Location(0, 0)
    move(obj, algebra.south)
    assert obj.pos == algebra.Location(0, 1)
    move(obj, algebra.southeast)
    assert obj.pos == algebra.Location(1, 2)


def _test_move_towards():
    obj = Object(algebra.Location(0, 0), 'o', 'test object', libtcod.white)
    obj.current_map = _MockMap()
    assert obj.pos == algebra.Location(0, 0)
    move_towards(obj, algebra.Location(10, 10))
    assert obj.pos == algebra.Location(1, 1)
    move_towards(obj, algebra.Location(10, 10))
    assert obj.pos == algebra.Location(2, 2)
    move_towards(obj, algebra.Location(-10, 2))
    assert obj.pos == algebra.Location(1, 2)
    move_towards(obj, obj.pos)
    assert obj.pos == algebra.Location(1, 2)


def _test_attack():
    af = Fighter(100)
    df = Fighter(100)
    a = Object(algebra.Location(0, 0), 'a', 'test attacker', libtcod.white, fighter=af)
    d = Object(algebra.Location(1, 1), 'd', 'test defender', libtcod.white, fighter=df)

    assert af.hp == 100
    assert df.hp == 100
    # if defense == 0, full damage is done
    attack(af, d, False)
    assert df.hp == 90
    df.base_defense = 5
    attack(af, d, False)
    assert df.hp == 85
    # if defense > attack, no damage is done
    df.base_defense = 15
    attack(af, d, False)
    assert df.hp == 85


def _test_actions():
    _test_move()
    _test_move_towards()
    _test_attack()


if __name__ == '__main__':
    _test_actions()
    print('Action tests complete.')
