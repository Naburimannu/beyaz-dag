"""
Implementation of actions.

Includes those which might be used by the AI (movement and combat)
and those which are currently only offered to the player.
Magical effects and targeting (spells.py) could also live here.

Conditionals and interfaces for the player sit up top in roguelike.py.
"""
import libtcodpy as libtcod
import copy

import log
import algebra
from components import *


def random_direction():
    return algebra.directions[libtcod.random_get_int(0, 0, 7)]


def add_to_map(new_map, pos, obj):
    obj.pos = pos
    obj.current_map = new_map # not necessarily necessary?
    new_map.objects.append(obj)


def move(o, direction):
    """
    Moves object by (dx, dy).
    Returns true if move succeeded.
    """
    goal = o.pos + direction
    if (goal.x < 0 or goal.y < 0 or
            goal.x >= o.current_map.width or
            goal.y >= o.current_map.height):
        # try_ catches this for the player, but need to
        # check here for NPCs
        return False
    if not o.current_map.is_blocked_from(o.pos, goal):
        o.pos = goal
        return True
    return False


def move_towards(o, target_pos):
    """
    Moves object one step towards target location.
    Returns true if move succeeded.
    """
    dir = algebra.Direction(target_pos.x - o.x, target_pos.y - o.y)
    dir.normalize()
    return move(o, dir)


def move_away_from(o, target_pos):
    """
    Moves object one step away from target location.
    Returns true if move succeeded.
    """
    dir = algebra.Direction(o.x - target_pos.x , o.y - target_pos.y)
    dir.normalize()
    return move(o, dir)


def _assign_damage(fighter, attack, target, defense, quantity, method, report=True):
    if quantity > 0:
        if report:
            log.message(
                fighter.name.capitalize() + ' (' + str(attack) + ') ' +
                method + ' ' + target.name + ' (' + str(defense) + ')' +
                ' for ' + str(quantity) + ' wounds.')
        inflict_damage(fighter, target.fighter, quantity)
    elif report:
        log.message(
            fighter.name.capitalize() + ' (' + str(attack) + ') ' +
            method + ' ' + target.name + ' (' + str(defense) + ')' +
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


def attack(attacker_ftr, target_obj, report=True):
    """
    Melee offence: attacker's weapon skill.
    Melee defense: half defender's weapon skill, plus defender's shield skill.
    Melee impact: attacker's weapon damage.
    Melee absorption: defender's armor soak.
    """
    target_obj.fighter.last_attacker = attacker_ftr.owner

    a_weapon_skill = attacker_ftr.skills.get('grappling', 10)
    # print('Attacker grappling is ' + str(a_weapon_skill))
    a_weapon_eq = get_equipped_in_slot(attacker_ftr.owner, 'right hand')
    if a_weapon_eq:
        # print('Attacker is wielding ' + a_weapon.owner.name)
        a_weapon_skill = attacker_ftr.skills.get(a_weapon_eq.owner.melee_weapon.skill, 10)
        # print('Attacker ' + a_weapon.owner.melee_weapon.skill + ' is ' + str(a_weapon_skill))

    d_weapon_skill = target_obj.fighter.skills.get('grappling', 10)
    d_weapon_eq = get_equipped_in_slot(target_obj, 'right hand')
    if d_weapon_eq:
        d_weapon_skill = target_obj.fighter.skills.get(d_weapon_eq.owner.melee_weapon.skill, 10)

    # TODO - no allowance for left-hand items other than shield
    d_shield_eq = get_equipped_in_slot(target_obj, 'left hand')
    shield_skill = 0
    if d_shield_eq:
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


def draw(actor_obj, weapon_obj, report=True):
    log.message(actor_obj.name.capitalize() + ' readies a ' + weapon_obj.name)
    actor_obj.game_state = 'shooting'


def fire(actor_obj, weapon_eq, ammo_eq, target_obj, report=True):
    ammo_eq.owner.item.count -= 1
    if ammo_eq.owner.item.count == 0:
        unequip(actor_obj, ammo_eq, False)
        actor_obj.inventory.remove(ammo_eq.owner)
    target_obj.fighter.last_attacker = actor_obj

    a_weapon_skill = actor_obj.fighter.skills.get(weapon_eq.owner.missile_weapon.skill, 10)
    effective_attack_skill = max(a_weapon_skill - actor_obj.fighter.action_penalty, 10)
    vector = target_obj.pos - actor_obj.pos
    distance = math.sqrt(vector.x ** 2 + vector.y **  2)
    effective_defense_skill = 10 + 5 * int(distance)
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


def pick_up(actor, o, report=True):
    """
    Add an Object to the actor's inventory and remove from the map.
    """
    for p in actor.inventory:
        if o.item.can_combine(p):
            p.item.count += o.item.count
            actor.current_map.objects.remove(o)
            if report:
                log.message(actor.name.capitalize() + ' picked up a ' + o.name + '!', libtcod.green)
            return True

    if len(actor.inventory) >= 22:
        if report:
            log.message(actor.name.capitalize() + ' inventory is full, cannot pick up ' +
                        o.name + '.', libtcod.red)
        return False
    else:
        actor.inventory.append(o)
        actor.current_map.objects.remove(o)
        if report:
            if o.item.count > 0:
                log.message(actor.name.capitalize() + ' picked up ' + str(o.item.count) + 'x ' + o.name + '!', libtcod.green)
            else:
                log.message(actor.name.capitalize() + ' picked up a ' + o.name + '!', libtcod.green)

        # Special case: automatically equip if the corresponding equipment slot is unused.
        equipment = o.equipment
        if equipment and get_equipped_in_slot(actor, equipment.slot) is None:
            equip(actor, equipment, report)
        return True


def drop(actor, o, report=True, all=False):
    """
    Remove an Object from the actor's inventory and add it to the map
    at the player's coordinates.
    If it's equipment, unequip before dropping.
    """
    must_split = False
    if o.item.count > 1 and not all:
        o.item.count -= 1
        must_split = True
    else:
        if o.equipment:
            unequip(actor, o.equipment, report)
        actor.inventory.remove(o)

    combined = False
    for p in actor.current_map.objects:
        if p.pos == actor.pos and o.item.can_combine(p):
            if all:
                p.item.count += o.item.count
            else:
                p.item.count += 1
            combined = True
            break

    if not combined:
        new_o = o
        if must_split:
            new_o = copy.deepcopy(o)
        if all:
            new_o.item.count = o.item.count
        else:
            new_o.item.count = 1
        add_to_map(actor.current_map, actor.pos, new_o)

    if report:
        if all:
            log.message(actor.name.capitalize() + ' dropped ' + str(o.item.count) + 'x ' + o.name + '.', libtcod.yellow)
        else:
            log.message(actor.name.capitalize() + ' dropped a ' + o.name + '.', libtcod.yellow)


def use(actor, o, report=True):
    """
    If the object has the Equipment component, toggle equip/unequip.
    Otherwise invoke its use_function and (if not cancelled) destroy it.
    """
    if o.equipment:
        _toggle_equip(actor, o.equipment, report)
        return

    if o.item.use_function is None:
        if report:
            log.message('The ' + o.name + ' cannot be used.')
    else:
        if o.item.use_function(actor) != 'cancelled':
            if o.item.count > 1:
                o.item.count -= 1
            else:
                actor.inventory.remove(o)


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
    o = Object(algebra.Location(0, 0), 'o', 'test object', libtcod.white)
    o.current_map = _MockMap()
    assert o.pos == algebra.Location(0, 0)
    move(o, algebra.south)
    assert o.pos == algebra.Location(0, 1)
    move(o, algebra.southeast)
    assert o.pos == algebra.Location(1, 2)


def _test_move_towards():
    o = Object(algebra.Location(0, 0), 'o', 'test object', libtcod.white)
    o.current_map = _MockMap()
    assert o.pos == algebra.Location(0, 0)
    move_towards(o, algebra.Location(10, 10))
    assert o.pos == algebra.Location(1, 1)
    move_towards(o, algebra.Location(10, 10))
    assert o.pos == algebra.Location(2, 2)
    move_towards(o, algebra.Location(-10, 2))
    assert o.pos == algebra.Location(1, 2)
    move_towards(o, o.pos)
    assert o.pos == algebra.Location(1, 2)


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
