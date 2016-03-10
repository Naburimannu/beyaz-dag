import libtcodpy as libtcod

import algebra
from components import *


def dagger():
    return Object(None, '|', 'dagger', libtcod.dark_sky,
            item=Item(description='A leaf-shaped iron knife; inflicts 4 damage'),
            melee=MeleeWeapon(skill='grappling', damage=4))

def sword():
    return Object(None, '|', 'sword', libtcod.dark_sky,
            item=Item(description='A broad iron sword; inflicts 8 damage.'),
            melee=MeleeWeapon(skill='sword', damage=8))

def spear():
    return Object(None, '/', 'spear', libtcod.dark_sky,
            item=Item(description='An iron-headed spear; inflicts 8 damage.'),
            melee=MeleeWeapon(skill='spear', damage=8))

def horn_bow():
    return Object(None, '}', 'horn bow', libtcod.dark_sky,
            item=Item(description='A short, sharply-curved, horn-backed bow.'),
            missile=MissileWeapon(skill='bow', damage=10, ammo='arrow'))

def arrow(count):
    return Object(None, '{', 'arrow', libtcod.dark_sky,
            item=Item(description='A gold-feathered beech arrow.', count=count),
            equipment=Equipment(slot='quiver'))
