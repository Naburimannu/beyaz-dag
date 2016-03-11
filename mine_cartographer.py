import libtcodpy as libtcod

import config
import algebra
import map
from components import *
import actions
import miscellany
import bestiary
import quest
import ai
import spells

def make_map(player, dungeon_level):
    """
    Creates a new simple map at the given dungeon level.
    Sets player.current_map to the new map, and adds the player as the first
    object.
    """
    old_map = player.current_map

    new_map = map.Map(config.MAP_WIDTH, config.MAP_HEIGHT, dungeon_level)
    new_map.objects.append(player)
    player.current_map = new_map
    player.camera_position = algebra.Location(0, 0)
    new_map.random_seed = libtcod.random_save(0)

    oqs = old_map.quarry_stairs
    oqs[1].dest_position = algebra.Location(new_map.width / 2, new_map.height / 2)
    oqs[0].dest_position = oqs[1].dest_position + 3 * (oqs[1].pos - oqs[0].pos)
    oqs[2].dest_position = oqs[2].dest_position + 3 * (oqs[2].pos - oqs[0].pos)

    # TODO: build map with three entrances
    # TODO: add inhabitants

    new_map.initialize_fov()
    return new_map