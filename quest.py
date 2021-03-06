# Copyright 2016 Thomas C. Hudson
# Governed by the license described in LICENSE.txt
import sys

import libtcodpy as libtcod

import config
import log
import renderer
import actions


TEXT_WIDTH = config.SCREEN_WIDTH - 30
QUEST_SP = 6


def _grant_quest_sp(player):
    player.skill_points += QUEST_SP
    log.message('You gained ' + str(QUEST_SP) + ' skill points.')


class PageLayout(object):
    def __init__(self):
        libtcod.console_clear(0)
        self.line = 4

    def title(self, text):
        libtcod.console_print_ex(
            0, config.SCREEN_WIDTH/2, self.line, libtcod.BKGND_NONE,
            libtcod.CENTER, text)
        self.line += 4

    def color(self, color):
        libtcod.console_set_default_foreground(0, color)

    def paragraph(self, text):
        self.line += libtcod.console_print_rect(0, 10, self.line, TEXT_WIDTH, 0, text)
        self.line += 1


def goddess_charge(player, goddess):
    page = PageLayout()

    page.title('The goddess speaks from behind her veil, in a voice as cold as the icy hells:')
    page.color(libtcod.light_blue)
    page.paragraph(
        'If you wish me to heal your people, you will have to right an offense against me. Bring me the Amulet of Golden Desires, which is worn by the cyclops Tepegoz. He dwells in a cunning maze, carved into the heart of the mountain; many are the entraces, but few are the exits.')

    page.paragraph('If you would slay him to gain it, I cannot tell you how; there is a nymph who lives in a grotto on the lakeshore who holds that knowledge to herself.')

    renderer.finish_welcome()
    goddess.wait_count = 0
    goddess.interactable.use_function = goddess_waiting
    _grant_quest_sp(player)


def goddess_waiting(player, goddess):
    for obj in player.inventory:
        if obj.name == "Yen d'Or":
            page = PageLayout()
            page.title('The goddess speaks from behind her veil, her voice still as chill as death:')
            page.color(libtcod.light_blue)
            page.paragraph(
                "Ooh, isn't it precious?")
            page.paragraph(
                "Yes, yes, I'll do something about your homeland. Now if you'll just see yourself out...")
            libtcod.console_print_ex(
                0, config.SCREEN_WIDTH/2, page.line + 4, libtcod.BKGND_NONE,
                libtcod.CENTER, 'YOU HAVE WON!')
            renderer.finish_welcome()
            sys.exit()

    goddess.wait_count += 1
    log.message('I await the amulet; until then I have nothing further for you.', color=libtcod.light_blue)
    if goddess.wait_count > 2:
        log.message('Do not try my patience!', color=libtcod.light_blue)
        actions.inflict_bleeding(goddess, player.fighter, goddess.wait_count + player.fighter.bleeding_defense)


def nymph_info(player, nymph):
    page = PageLayout()

    page.title("The nymph's words roil around you, now loud, now soft, now rushing, now slow:")

    page.color(libtcod.azure)
    page.paragraph("You want to kill my son?")
    page.paragraph("It's about time.")
    page.paragraph("You'll need a spear to put his eye out - any spear will do.")
    page.paragraph("But then to kill him you'll need something special.")
    page.paragraph("A black sword was lost by a hero of another age in long-abandoned mines.")
    page.paragraph("They can be entered from a deep rocky quarry on the south slope of the mountain.")

    renderer.finish_welcome()
    nymph.interactable.use_function = nymph_unhappy
    _grant_quest_sp(player)


def nymph_unhappy(player, nymph):
    log.message("Indeed, it is fated - necessary, even - that Tepegoz be slain, but do not think I'm happy about it. Neither be certain that you are fated to be his slayer.", color=libtcod.azure)


def display_welcome():
    page = PageLayout()

    page.color(libtcod.light_yellow)
    page.title('BEYAZ DAG')

    page.color(libtcod.white)
    page.paragraph(
        'It is not far from Navekat and Suyab to the lake they call the Eye of the World. But the visions you sought there carried you much farther, across mountains, deserts, marshes, across the Mother River to the lonely Mount Beyaz. Here, perhaps, you can convince the merciful goddess who lives above the clouds to save your people from the plague.')
    page.paragraph(
        "Beyaz Dag towers solitary above the deserts. No rival peak dares rear itself nearby, though a desultory range of hills stretches southwards. The mountain's western slopes fall off steeply into a deep blue lake; north lie the marshes that fringe the Mother River.")
    page.paragraph(
        'You never mastered sword and lance, like your brothers, but can shoot, ride, and wrestle as well as any of them.')
    page.paragraph(
        'Beyaz Dag teems with life: hyenas and gazelles in the desert scrub, deer, wolves, bear in the forests. Travelers you met on the Northern Road tell of other, darker things here: ruins, abandoned quarries, sunken grottoes...')

    page.line += 2
    page.paragraph(
        "Now you're almost through the marshes; the mountain rises to the southwest.")

    libtcod.console_set_default_foreground(0, libtcod.darker_yellow)
    libtcod.console_print_ex(
        0, config.SCREEN_WIDTH/2, config.SCREEN_HEIGHT-6, libtcod.BKGND_NONE,
        libtcod.CENTER, 'Generating the map...')

    libtcod.console_flush()



    