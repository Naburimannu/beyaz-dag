"""
Simple entity system: any renderable Object can have
a number of Components attached.
"""
# Copyright 2016 Thomas C. Hudson
# Governed by the license described in LICENSE.txt
import math
import algebra


class Object:
    """
    This is a generic object: the player, a monster, an item, the stairs...
    It's always represented by a character on screen.
    """
    def __init__(self, pos, char, name, color,
                 blocks=False, blocks_sight=False,
                 always_visible=False,
                 interactable=None,
                 fighter=None, ai=None, item=None, equipment=None,
                 melee=None, missile=None):
        self.pos = pos
        self.char = char
        self.name = name
        self.color = color
        self.blocks = blocks
        self.blocks_sight = blocks_sight
        self.always_visible = always_visible

        self.interactable = interactable
        self._ensure_ownership(interactable)
        self.fighter = fighter
        self._ensure_ownership(fighter)
        self.ai = ai
        self._ensure_ownership(ai)
        self.item = item
        self._ensure_ownership(item)
        self.equipment = equipment
        self._ensure_ownership(equipment)

        self.melee_weapon = melee
        self._ensure_ownership(melee)
        self.missile_weapon = missile
        self._ensure_ownership(missile)

    @property
    def x(self):
        return self.pos.x

    @property
    def y(self):
        return self.pos.y

    def _ensure_ownership(self, component):
        if (component):
            component.set_owner(self)

    def distance_to_obj(self, other):
        """
        Return the distance to another object.
        """
        return self.pos.distance(other.pos)

    def distance(self, pos):
        """
        Return the distance to some coordinates.
        """
        return self.pos.distance(pos)

class Component:
    """
    Base class for components to minimize boilerplate.
    """
    def set_owner(self, entity):
        self.owner = entity


class Fighter(Component):
    """
    Combat-related properties and methods (monster, player, NPC).
    """
    def __init__(self, hp, unarmed_damage=2, death_function=None, skills={}):
        self.max_hp = hp
        self.hp = hp
        self.unarmed_damage = unarmed_damage
        self.death_function = death_function
        self.skills = skills
        self.wounds = 0
        self.bleeding = 0
        self.exhaustion = 0
        self.inebriation = 0
        self.last_attacker = None

        self.on_unarmed_strike = None

    @property
    def action_penalty(self):
        return (self.wounds / 2 + self.bleeding +
                self.exhaustion / 100 + self.inebriation / 100)

    @property
    def defense(self):
        bonus = sum(equipment.defense_bonus for equipment
                    in _get_all_equipped(self.owner))
        return bonus

    @property
    def bleeding_defense(self):
        bonus = sum(equipment.bleeding_defense for equipment
                    in _get_all_equipped(self.owner))
        return bonus


class Interactable(Component):
    """
    An object in the world that can be used (but not picked up),
    presumably by bumping?
    """
    def __init__(self, description=None, use_function=None):
        self.description = description
        self.use_function = use_function


class Item(Component):
    """
    An item that can be picked up and used.
    """
    def __init__(self, description=None, count=1, stackable=False, use_function=None):
        self.description = description
        self.count = count
        self.stackable = stackable
        self.use_function = use_function

    def can_combine(self, other_obj):
        """
        Returns true if other can stack with self.
        Terribly simple for now.
        """
        return self.stackable and other_obj and other_obj.item and other_obj.name == self.owner.name


class Equipment(Component):
    """
    An object that can be equipped, yielding bonuses.
    Requires an Item component.
    """
    def __init__(self, slot, defense_bonus=0, bleeding_defense=0):
        self.defense_bonus = defense_bonus
        self.bleeding_defense = bleeding_defense

        self.slot = slot
        self.is_equipped = False

    def set_owner(self, entity):
        Component.set_owner(self, entity)

        # There must be an Item component for the Equipment
        # component to work properly.
        if entity.item is None:
            entity.item = Item()
            entity.item.set_owner(entity)


class MeleeWeapon(Component):
    def __init__(self, skill, damage, skill_bonus=0, on_strike=None):
        self.skill = skill
        self.damage = damage
        self.skill_bonus = skill_bonus

        self.on_strike = on_strike

    def set_owner(self, entity):
        Component.set_owner(self, entity)
        if entity.equipment is None:
            entity.equipment = Equipment('right hand')
            entity.equipment.set_owner(entity)


class MissileWeapon(Component):
    def __init__(self, skill, damage, ammo, max_range=8):
        self.skill = skill
        self.damage = damage
        self.ammo = ammo
        self.max_range = max_range

    def set_owner(self, entity):
        Component.set_owner(self, entity)
        if entity.equipment is None:
            entity.equipment = Equipment('left hand')
            entity.equipment.set_owner(entity)


class AI(Component):
    def __init__(self, take_turn, metadata=None):
        self._turn_function = take_turn
        self._metadata = metadata

    def take_turn(self, player):
        self._turn_function(self.owner, player, self._metadata)


def _get_all_equipped(obj):
    """
    Returns a list of all equipped items.
    """
    if hasattr(obj, 'inventory'):
        equipped_list = []
        for item in obj.inventory:
            if item.equipment and item.equipment.is_equipped:
                equipped_list.append(item.equipment)
        return equipped_list
    else:
        return []
