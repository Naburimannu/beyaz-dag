"""
Shared configuration variables.
"""
# Copyright 2016 Thomas C. Hudson
# Governed by the license described in LICENSE.txt

# Total size of the game window.
SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50

# Size of the map panel in the window.
MAP_PANEL_WIDTH = 80
MAP_PANEL_HEIGHT = 43

# Size of the actual map; if larger than the map panel, the map panel will
# scroll as the player moves.
OUTDOOR_MAP_WIDTH = 200
OUTDOOR_MAP_HEIGHT = 200
MAP_WIDTH = 60
MAP_HEIGHT = 33

# Height of the HUD display (should be screen height - map display height)
PANEL_HEIGHT = 7
BAR_WIDTH = 20

# Experience and level-ups
REGION_EXPLORATION_SP = 1
ELEVATION_EXPLORATION_SP = 5
