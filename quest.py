import libtcodpy as libtcod

import config
import log
import renderer
import actions


TEXT_WIDTH = config.SCREEN_WIDTH - 20


def goddess_charge(player, goddess):
    libtcod.console_clear(0)

    line = 4
    libtcod.console_print_ex(
        0, config.SCREEN_WIDTH/2, line, libtcod.BKGND_NONE,
        libtcod.CENTER, 'The goddess speaks from behind her veil, in a voice as cold as the icy hells:')
    line += 2

    libtcod.console_set_default_foreground(0, libtcod.light_blue)
    line += libtcod.console_print_rect(0, 10, line, TEXT_WIDTH, 0,
        'If you wish me to heal your people, you will have to right a offense against me. Bring me the Amulet of Golden Desires, which is worn by the cyclops Tepegoz. If you would slay him to gain it, I cannot tell you how; there is a nymph who lives in a grotto on the lakeshore who holds that knowledge to herself.')
    line += 1

    renderer.finish_welcome()
    goddess.wait_count = 0
    goddess.interactable.use_function = goddess_waiting


def goddess_waiting(player, goddess):
    for obj in player.inventory:
        # if it's the maguffin, win the game
        pass

    goddess.wait_count += 1
    log.message('I await the amulet; until then I have nothing further for you.', color=libtcod.light_blue)
    if goddess.wait_count > 2:
        log.message('Do not try my patience!', color=libtcod.light_blue)
        actions.inflict_bleeding(goddess, player.fighter, goddess.wait_count + player.fighter.bleeding_defense)


def display_welcome():
    libtcod.console_clear(0)

    libtcod.console_set_default_foreground(0, libtcod.light_yellow)
    line = 4
    libtcod.console_print_ex(
        0, config.SCREEN_WIDTH/2, line, libtcod.BKGND_NONE,
        libtcod.CENTER, 'BEYAZ DAG')
    line += 2

    libtcod.console_set_default_foreground(0, libtcod.white)
    line += libtcod.console_print_rect(0, 10, line, TEXT_WIDTH, 0,
        'It is not far from Navekat and Suyab to the lake they call the Eye of the World. But the visions you sought there carried you much farther, across mountains, deserts, marshes, across the Mother River to the lonely Mount Beyaz. Here, perhaps, you can convince the merciful goddess who lives above the clouds to save your people from the plague.')
    line += 1

    line += libtcod.console_print_rect(0, 10, line, TEXT_WIDTH, 0,
        "Beyaz Dag towers solitary above the deserts. No rival peak dares rear itself nearby, though a desultory range of hills stretches southwards. The mountain's western slopes fall off steeply into a deep blue lake; north lie the marshes that fringe the Mother River.")
    line += 1

    line += libtcod.console_print_rect(0, 10, line, TEXT_WIDTH, 0,
        'You never mastered sword and lance, like your brothers, but can shoot, ride, and wrestle as well as any of them.')
    line += 1

    libtcod.console_set_default_foreground(0, libtcod.darker_yellow)
    libtcod.console_print_ex(
        0, config.SCREEN_WIDTH/2, config.SCREEN_HEIGHT-4, libtcod.BKGND_NONE,
        libtcod.CENTER, 'Generating the map...')

    libtcod.console_flush()



    