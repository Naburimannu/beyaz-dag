"""
Simple entity system: any renderable Object can have
a number of Components attached.
"""
import math
import algebra


class Object:
    """
    This is a generic object: the player, a monster, an item, the stairs...
    It's always represented by a character on screen.
    """
    def __init__(self, pos, char, name, color,
                 blocks=False, always_visible=False,
                 fighter=None, ai=None, item=None, equipment=None,
                 melee=None):
        self.pos = pos
        self.char = char
        self.name = name
        self.color = color
        self.blocks = blocks
        self.always_visible = always_visible

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

    @property
    def x(self):
        return self.pos.x

    @property
    def y(self):
        return self.pos.y

    def _ensure_ownership(self, component):
        if (component):
            component.set_owner(self)

    def distance_to(self, other):
        """
        Return the distance to another object.
        """
        dx = other.x - self.x
        dy = other.y - self.y
        return math.sqrt(dx ** 2 + dy ** 2)

    def distance(self, x, y):
        """
        Return the distance to some coordinates.
        """
        return math.sqrt((x - self.x) ** 2 + (y - self.y) ** 2)

    def distance(self, pos):
        """
        Return the distance to some coordinates.
        """
        return math.sqrt((pos.x - self.x) ** 2 + (pos.y - self.y) ** 2)


class Component:
    """
    Base class for components to minimize boilerplate.
    """
    def set_owner(self, entity):
        self.owner = entity


skill_list = [
    'bow',
    'climb',
    'first aid',
    'grappling',
    'spear',
    'sword'
]


class Fighter(Component):
    """
    Combat-related properties and methods (monster, player, NPC).
    """
    def __init__(self, hp, death_function=None):
        self.max_hp = hp
        self.hp = hp
        self.death_function = death_function
        self.skills = { }
        self.wounds = 0
        self.bleeding = 0
        self.exhaustion = 0

    @property
    def action_penalty(self):
        return self.wounds + self.exhaustion / 100

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


class Item(Component):
    """
    An item that can be picked up and used.
    """
    def __init__(self, description=None, count=1, use_function=None):
        self.description = description
        self.use_function = use_function
        self.count = count

    def can_combine(self, other):
        """
        Returns true if other can stack with self.
        Terribly simple for now.
        """
        return other.item and other.name == self.owner.name


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
    def __init__(self, skill, damage):
        self.skill = skill
        self.damage = damage

    def set_owner(self, entity):
        Component.set_owner(self, entity)

        # There must be an Equipment component for the MeleeWeapon
        # component to work properly.
        if entity.equipment is None:
            entity.equipment = Equipment('right hand')
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
