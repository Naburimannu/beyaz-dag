# Copyright 2016 Thomas C. Hudson
# Governed by the license described in LICENSE.txt
import libtcodpy as libtcod

import log
import algebra
from components import *
import map
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
    actor.current_map.objects.insert(0, replacement)
    actor.current_map.objects.remove(target)
    actor.current_map.fov_needs_recompute = True
    actor.current_map.fov_elevation_changed = True
    log.message(actor.name.capitalize() + ' opens a door.')


def honey_tree(pos):
    return Object(pos, 'T', 'honey tree', libtcod.gold, blocks=True,
            blocks_sight = True,
            interactable=Interactable(use_function=_do_harvest_honey))

def _do_harvest_honey(actor, target):
    if not actor.fighter:
        return
    log.message(actor.name.capitalize() + ' eats some refreshing honey.')
    actor.fighter.exhaustion = max(actor.fighter.exhaustion - 6, 0)
    actor.current_map.terrain[target.pos.x][target.pos.y] = 9
    actor.current_map.fov_needs_recompute = True
    actor.current_map.objects.remove(target)

######################


def dagger():
    return Object(None, '|', 'dagger', libtcod.dark_sky,
            item=Item(description='A leaf-shaped iron knife; inflicts 4 damage (using grappling skill).'),
            melee=MeleeWeapon(skill='grappling', damage=4))

def sword():
    return Object(None, '|', 'sword', libtcod.dark_sky,
            item=Item(description='A broad iron sword; inflicts 8 damage.'),
            melee=MeleeWeapon(skill='sword', damage=8))

def spear():
    return Object(None, '/', 'spear', libtcod.dark_sky,
            item=Item(description='An iron-headed spear; inflicts 8 damage.'),
            melee=MeleeWeapon(skill='spear', damage=8))

def roundshield():
    return Object(None, ')', 'roundshield', libtcod.dark_sky,
            item=Item(description='A large round wooden shield, edged with iron.'),
            equipment=Equipment('left hand', defense_bonus=1))

def horn_bow():
    return Object(None, '}', 'horn bow', libtcod.dark_sky,
            item=Item(description='A short, sharply-curved, horn-backed bow; inflicts 10 damage.'),
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

def the_black_sword():
    return Object(None, '|', 'black sword', libtcod.darkest_pink,
            item=Item(description='The utter darkness of the blade draws the eye, as if you could fall through it; inflicts 10 damage.'),
            melee=MeleeWeapon(skill='sword', damage=10))