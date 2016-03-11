import libtcodpy as libtcod

import log
import algebra
from components import *
import spells  # nasty levelization violation?!


######################


def closed_door(pos):
    return Object(pos, '+', 'closed door', libtcod.white, blocks=True,
            blocks_sight=True,
            interactable=Interactable(use_function=_do_open_door))

def open_door(pos):
    return Object(pos, "'", 'open door', libtcod.white, blocks=False)

def _do_open_door(actor, target):
    replacement = open_door(target.pos)
    actor.current_map.objects.append(replacement)
    actor.current_map.objects.remove(target)
    actor.current_map.fov_needs_recompute = True
    actor.current_map.fov_elevation_changed = True
    log.message(actor.name.capitalize() + ' opens a door.')


######################


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

def bandage(count):
    return Object(None, '~', 'bandage', libtcod.dark_sky,
            item=Item(description='A clean-enough length of cloth for binding wounds, and a bit of herbs for a poultice.',
                    count=count, use_function=spells.use_bandage))

def maguffin():
    return Object(None, '"', "Yen d'Or", libtcod.gold,
            item=Item(description="You've never seen anything like it. You can't imagine how you ever managed to live without it. It's so ineffably precious."),
            equipment=Equipment(slot='amulet'))