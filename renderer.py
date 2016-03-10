import libtcodpy as libtcod
import time

import config
import log
import algebra
import map


FOV_ALGO = 0
FOV_LIGHT_WALLS = True
TORCH_RADIUS = 10

PANEL_Y = config.SCREEN_HEIGHT - config.PANEL_HEIGHT
MSG_X = config.BAR_WIDTH + 2

LIMIT_FPS = 20

_frame_index = 0
_twenty_frame_estimate = 1000
_last_frame_time = None


_con = None
""" main console window for drawing the map and objects """
_overlay = None
""" buffer overlaid over the main console window for effects,
labels, and other metadata.
"""
_panel = None
""" UI text data """




_console_center = algebra.Location(config.MAP_PANEL_WIDTH / 2,
                                   config.MAP_PANEL_HEIGHT / 2)


def block_for_key():
    """
    Approximately replacing libtcod.console_wait_for_keypress(),
    returns a libtcod.Key object.
    """
    key = libtcod.Key()
    mouse = libtcod.Mouse()
    while True:
        libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS, key, mouse)
        if (key.vk == libtcod.KEY_NONE):
            continue

        if (key.vk == libtcod.KEY_ALT or
                key.vk == libtcod.KEY_SHIFT or
                key.vk == libtcod.KEY_CONTROL):
            continue

        break
    return key


class ScreenCoords(tuple):
    @staticmethod
    def fromWorldCoords(camera_coords, world_coords):
        """
        Returns (None, None) if the specified world coordinates would be off-screen.
        """
        x = world_coords.x - camera_coords.x
        y = world_coords.y - camera_coords.y
        if (x < 0 or y < 0 or x >= config.MAP_PANEL_WIDTH or y >= config.MAP_PANEL_HEIGHT):
            return ScreenCoords((None, None))
        return ScreenCoords((x, y))

    @staticmethod
    def toWorldCoords(camera_coords, screen_coords):
        x = screen_coords[0] + camera_coords.x
        y = screen_coords[1] + camera_coords.y
        return algebra.Location(x, y)


def renderer_init():
    """
    Initialize libtcod and set up our basic consoles to draw into.
    """
    global _con, _panel, _overlay, _last_frame_time
    libtcod.console_set_custom_font('arial12x12.png', libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_TCOD)
    # Map the dead space in the TCOD layout to [128...164]
    # libtcod.console_map_ascii_codes_to_font(256, 21, 11, 1)
    # libtcod.console_map_ascii_codes_to_font(277, 25, 0, 2)
    libtcod.console_map_ascii_code_to_font(129, 12, 1)
    libtcod.console_init_root(config.SCREEN_WIDTH, config.SCREEN_HEIGHT, 'Beyaz Dag', False)
    libtcod.sys_set_fps(LIMIT_FPS)
    _con = libtcod.console_new(config.MAP_PANEL_WIDTH, config.MAP_PANEL_HEIGHT)
    _overlay = libtcod.console_new(config.MAP_PANEL_WIDTH, config.MAP_PANEL_HEIGHT)
    _panel = libtcod.console_new(config.SCREEN_WIDTH, config.PANEL_HEIGHT)
    _last_frame_time = time.time() * 1000


def parse_move(key):
    """
    Returns (bool, direction, bool).
    First value is True if a direction key was pressed, False otherwise.
    Direction will be None if first value is False or the '.' or numpad 5 were pressed.
    Last value is True if shift was held (run / page-scroll), False otherwise.
    """
    key_char = chr(key.c)
    if (key.vk == libtcod.KEY_UP or key.vk == libtcod.KEY_KP8 or
            key_char == 'k' or key_char == 'K'):
        return (True, algebra.north, key.shift)
    elif (key.vk == libtcod.KEY_DOWN or key.vk == libtcod.KEY_KP2 or
            key_char == 'j' or key_char == 'J'):
        return (True, algebra.south, key.shift)
    elif (key.vk == libtcod.KEY_LEFT or key.vk == libtcod.KEY_KP4 or
            key_char == 'h' or key_char == 'H'):
        return (True, algebra.west, key.shift)
    elif (key.vk == libtcod.KEY_RIGHT or key.vk == libtcod.KEY_KP6 or
            key_char == 'l' or key_char == 'L'):
        return (True, algebra.east, key.shift)
    elif (key.vk == libtcod.KEY_HOME or key.vk == libtcod.KEY_KP7 or
            key_char == 'y' or key_char == 'Y'):
        return (True, algebra.northwest, key.shift)
    elif (key.vk == libtcod.KEY_PAGEUP or key.vk == libtcod.KEY_KP9 or
            key_char == 'u' or key_char == 'U'):
        return (True, algebra.northeast, key.shift)
    elif (key.vk == libtcod.KEY_END or key.vk == libtcod.KEY_KP1 or
            key_char == 'b' or key_char == 'B'):
        return (True, algebra.southwest, key.shift)
    elif (key.vk == libtcod.KEY_PAGEDOWN or key.vk == libtcod.KEY_KP3 or
            key_char == 'n' or key_char == 'N'):
        return (True, algebra.southeast, key.shift)
    elif (key.vk == libtcod.KEY_KP5 or key_char == '.'):
        # do nothing but note that a relevant key was pressed
        return (True, None, False)
    return (False, None, False)


def msgbox(text, width=50):
    """
    Display a message, wait for any keypress.
    """
    menu(text, [], width)


def write_log(messages, window, x, initial_y):
    y = initial_y
    for m in messages:
        libtcod.console_set_default_foreground(window, m.color)
        line = m.message
        if m.count > 1:
            line += ' (x' + str(m.count) + ')'
        libtcod.console_print_ex(window, x, y, libtcod.BKGND_NONE,
                                 libtcod.LEFT, line)
        y += 1


def main_menu(new_game, play_game, load_game):
    """
    Prompt the player to start a new game, continue playing the last game,
    or exit.
    """
    img = libtcod.image_load('menu_background.png')

    while not libtcod.console_is_window_closed():
        # Show the background image, at twice the regular console resolution.
        libtcod.image_blit_2x(img, 0, 0, 0)

        libtcod.console_set_default_foreground(0, libtcod.light_yellow)
        libtcod.console_print_ex(
            0, config.SCREEN_WIDTH/2, config.SCREEN_HEIGHT/2-4, libtcod.BKGND_NONE,
            libtcod.CENTER, 'BEYAZ DAG')
        libtcod.console_print_ex(
            0, config.SCREEN_WIDTH/2, config.SCREEN_HEIGHT-2, libtcod.BKGND_NONE,
            libtcod.CENTER, 'By Naburimanu')

        (char, choice) = menu('', ['Play a new game', 'Continue last game', 'Quit'], 24)

        if choice == 0:
            play_game(new_game())
        if choice == 1:
            try:
                player = load_game()
            except:
                msgbox('\n No saved game to load.\n', 24)
                continue
            play_game(player)
        elif choice == 2:
            break


def display_welcome():
    libtcod.console_clear(0)

    libtcod.console_set_default_foreground(0, libtcod.light_yellow)
    line = 4
    libtcod.console_print_ex(
        0, config.SCREEN_WIDTH/2, line, libtcod.BKGND_NONE,
        libtcod.CENTER, 'BEYAZ DAG')
    line += 2

    welcome_width = config.SCREEN_WIDTH - 20
    libtcod.console_set_default_foreground(0, libtcod.white)
    line += libtcod.console_print_rect(0, 10, line, welcome_width, 0,
        'It is not far from Navekat and Suyab to the lake they call the Eye of the World. But the visions you sought there carried you much farther, across mountains, deserts, marshes, across the Mother River to the lonely Mount Beyaz. Here, perhaps, you can convince the merciful goddess who lives above the clouds to save your people from the plague.')
    line += 1

    line += libtcod.console_print_rect(0, 10, line, welcome_width, 0,
        "Beyaz Dag towers solitary above the deserts. No rival peak dares rear itself nearby, though a desultory range of hills stretches southwards. The mountain's western slopes fall off steeply into a deep blue lake; north lie the marshes that fringe the Mother River.")
    line += 1

    line += libtcod.console_print_rect(0, 10, line, welcome_width, 0,
        'You never mastered sword and lance, like your brothers, but can shoot, ride, and wrestle as well as any of them.')
    line += 1

    libtcod.console_set_default_foreground(0, libtcod.darker_yellow)
    libtcod.console_print_ex(
        0, config.SCREEN_WIDTH/2, config.SCREEN_HEIGHT-4, libtcod.BKGND_NONE,
        libtcod.CENTER, 'Generating the map...')

    libtcod.console_flush()


def finish_welcome():
    libtcod.console_set_default_foreground(0, libtcod.darker_yellow)
    libtcod.console_print_ex(
        0, config.SCREEN_WIDTH/2, config.SCREEN_HEIGHT-4, libtcod.BKGND_NONE,
        libtcod.CENTER, 'Press any key to continue...')
    libtcod.console_flush()
    block_for_key()

def clear_console():
    global _con
    libtcod.console_clear(_con)


def _render_bar(x, y, total_width, name, value, maximum, bar_color, back_color):
    bar_width = int(float(value) / maximum * total_width)

    libtcod.console_set_default_background(_panel, back_color)
    libtcod.console_rect(_panel, x, y, total_width, 1, False, libtcod.BKGND_SCREEN)

    libtcod.console_set_default_background(_panel, bar_color)
    if bar_width > 0:
        libtcod.console_rect(_panel, x, y, bar_width, 1, False, libtcod.BKGND_SCREEN)

    libtcod.console_set_default_foreground(_panel, libtcod.white)
    libtcod.console_print_ex(
        _panel, x + total_width / 2, y, libtcod.BKGND_NONE, libtcod.CENTER,
        name + ': ' + str(value) + '/' + str(maximum))


def _describe_obj(obj):
    """
    Prints the name of the object, and any qualifiers.
    - if an item with count > 1, appends the count
    """
    if obj.item and obj.item.count > 1:
        return obj.name + ' (x' + str(obj.item.count) + ')'
    else:
        return obj.name


def _get_names_under_mouse(player, (sx, sy)):
    if (sx < 0 or sy < 0 or
            sx >= config.MAP_PANEL_WIDTH or
            sy >= config.MAP_PANEL_HEIGHT):
        return ''

    objects = player.current_map.objects
    fov_map = player.current_map.fov_map
    pos = ScreenCoords.toWorldCoords(player.camera_position,
                                     (sx, sy))
    if (pos.x >= player.current_map.width or
            pos.y >= player.current_map.height):
        return ''

    names = [_describe_obj(obj) for obj in objects
             if obj.pos == pos and
             libtcod.map_is_in_fov(fov_map, obj.x, obj.y)]

    names = ', '.join(names)
    names = names.capitalize()

    if player.current_map.terrain_at(pos).display_name:
        if names == '':
            names = player.current_map.terrain_at(pos).display_name
        else:
            names = ', '.join([names, player.current_map.terrain_at(pos).display_name])

    if player.current_map.is_outdoors:
        player_elevation = player.current_map.region_elevations[player.current_map.region[player.pos.x][player.pos.y]]
        viewed_elevation = player.current_map.region_elevations[player.current_map.region[pos.x][pos.y]]
        if viewed_elevation < player_elevation:
            names += ' below you'
        elif viewed_elevation > player_elevation:
            names += ' above you'

    # DEBUG
    names += '  [' + str(pos.x) + ' ' + str(pos.y) + ']'

    return names


def _draw_object(player, o):
    global _con
    libtcod.console_set_default_foreground(_con, o.color)
    (x, y) = ScreenCoords.fromWorldCoords(player.camera_position, o.pos)
    libtcod.console_put_char(_con, x, y, o.char, libtcod.BKGND_NONE)
 

def clear_object(player, o):
    """
    Erase the character that represents this object.
    """
    global _con
    (x, y) = ScreenCoords.fromWorldCoords(player.camera_position, o.pos)
    char = ' '
    # qv _draw_fov_using_terrain(); doing this right may be ugly.
    if player.current_map.is_outdoors:
        if (player.current_map.elevation(o.pos.x, o.pos.y) <
                player.current_map.elevation(player.pos.x, player.pos.y) - 1):
            char = '#'
    libtcod.console_put_char(_con, x, y, char, libtcod.BKGND_NONE)


def menu(header, options, width):
    """
    Display a menu of options headed by letters; return (the key pressed, the index [0, 25] of the selection, or None).
    """
    global _con
    if len(options) > 26:
        raise ValueError('Cannot have a menu with more than 26 options.')

    # Calculate total height for the header (after auto-wrap) and one line per option.
    header_height = libtcod.console_get_height_rect(_con, 0, 0, width, config.SCREEN_HEIGHT, header)
    if header == '':
        header_height = 0
    height = len(options) + header_height

    # Create an off-screen console that represents the menu's window.
    window = libtcod.console_new(width, height)

    libtcod.console_set_default_foreground(window, libtcod.white)
    libtcod.console_print_rect_ex(window, 0, 0, width, height, libtcod.BKGND_NONE, libtcod.LEFT, header)

    y = header_height
    letter_index = ord('a')
    for option_text in options:
        text = '(' + chr(letter_index) + ') ' + option_text
        libtcod.console_print_ex(window, 0, y, libtcod.BKGND_NONE, libtcod.LEFT, text)
        y += 1
        letter_index += 1

    x = config.SCREEN_WIDTH/2 - width/2
    y = config.SCREEN_HEIGHT/2 - height/2
    libtcod.console_blit(window, 0, 0, width, height, 0, x, y, 1.0, 0.7)

    libtcod.console_flush()
    while True:
        key = block_for_key()
        if not (key.vk == libtcod.KEY_ALT or key.vk == libtcod.KEY_CONTROL or
                key.vk == libtcod.KEY_SHIFT):
            break

    index = key.c - ord('a')
    if index >= 0 and index < len(options):
        return (key.c, index)
    return (key.c, None)


def _debug_region(current_map, screen_x, screen_y, pos):
    global _con
    libtcod.console_set_char(_con, screen_x, screen_y, chr(65 + (current_map.region[pos.x][pos.y] % 26)))


def _debug_elevation(current_map, screen_x, screen_y, pos):
    global _con
    libtcod.console_set_char(_con, screen_x, screen_y,
                             chr(48 + current_map.region_elevations[current_map.region[pos.x][pos.y]]))


def _draw_unseen(player, screen_x, screen_y, pos, terrain, icon):
    global _con
    current_map = player.current_map
    sc = terrain.unseen_color
    if not sc:
        sc = map.region_colors_unseen[current_map.region_terrain[current_map.region[pos.x][pos.y]]]
    libtcod.console_set_char_background(_con, screen_x, screen_y, sc, libtcod.BKGND_SET)
    # _debug_region(current_map, screen_x, screen_y, pos)
    if icon:
        libtcod.console_set_char_foreground(_con, screen_x, screen_y, terrain.icon_color)
        libtcod.console_set_char(_con, screen_x, screen_y, icon)
    # else:
    #     _debug_elevation(current_map, screen_x, screen_y, pos)


def _draw_outdoors(player):
    """
    Overly optimized: this code inlines Map.terrain_at(), Map.is_explored(),
    and ScreenCoords.toWorldCoords() in order to get a 2.5x speedup on
    large maps.
    """
    libtcod.console_clear(_con)
    current_map = player.current_map
    pos = algebra.Location(0, 0)
    player_elevation = current_map.region_elevations[current_map.region[player.pos.x][player.pos.y]]
    for screen_y in range(min(current_map.height, config.MAP_PANEL_HEIGHT)):
        pos.set(player.camera_position.x, player.camera_position.y + screen_y)
        for screen_x in range(min(current_map.width, config.MAP_PANEL_WIDTH)):
            visible = libtcod.map_is_in_fov(current_map.fov_map, pos.x, pos.y)
            terrain = map.terrain_types[current_map.terrain[pos.x][pos.y]]
            explored = current_map._explored[pos.x][pos.y]
            current_elevation = current_map.region_elevations[current_map.region[pos.x][pos.y]]
            icon = terrain.icon
            if icon:
                if terrain.name == 'slope' and current_elevation < player_elevation:
                    icon = 'v'
            # draw (player_elevation - 1) so that we can see up-slopes; lower than that just
            # gets a colored fill
            if (current_elevation + 1 < player_elevation):
                if visible or explored:
                    libtcod.console_put_char_ex(_con, screen_x, screen_y, '#',
                        map.region_colors_seen[current_map.region_terrain[current_map.region[pos.x][pos.y]]],
                        libtcod.black)
                if visible:
                    current_map.explore(pos)
            elif not visible:
                if explored:
                    _draw_unseen(player, screen_x, screen_y, pos, terrain, icon)
            else:
                if terrain.seen_color:
                    libtcod.console_set_char_background(_con, screen_x, screen_y, terrain.seen_color)
                else:
                    libtcod.console_put_char_ex(_con, screen_x, screen_y, icon, terrain.icon_color,
                            map.region_colors_seen[current_map.region_terrain[current_map.region[pos.x][pos.y]]])
                current_map.explore(pos)
            pos.x += 1


def _draw_indoors(player):
    """
    Overly optimized: this code inlines Map.terrain_at(), Map.is_explored(),
    and ScreenCoords.toWorldCoords() in order to get a 2.5x speedup on
    large maps.
    """
    libtcod.console_clear(_con)
    current_map = player.current_map
    pos = algebra.Location(0, 0)
    for screen_y in range(min(current_map.height, config.MAP_PANEL_HEIGHT)):
        pos.set(player.camera_position.x, player.camera_position.y + screen_y)
        for screen_x in range(min(current_map.width, config.MAP_PANEL_WIDTH)):
            # pos = ScreenCoords.toWorldCoords(player.camera_position, (screen_x, screen_y))
            visible = libtcod.map_is_in_fov(current_map.fov_map, pos.x, pos.y)
            # terrain = current_map.terrain_at(pos)
            terrain = map.terrain_types[current_map.terrain[pos.x][pos.y]]
            if not visible:
                # if current_map.is_explored(pos):
                if current_map._explored[pos.x][pos.y]:
                    libtcod.console_set_char_background(_con, screen_x, screen_y,
                                                        terrain.unseen_color, libtcod.BKGND_SET)
            else:
                libtcod.console_set_char_background(_con, screen_x, screen_y,
                                                    terrain.seen_color, libtcod.BKGND_SET)
                current_map.explore(pos)
            pos.x += 1


def update_camera(player):
    """
    Makes sure the player is roughly centered and that we're not trying to draw off screen.
    Basic implementation is stateless.
    """
    newPos = player.pos - _console_center

    # Make sure the camera doesn't see outside the map.
    newPos.bound(algebra.Rect(0, 0,
                 player.current_map.width - config.MAP_PANEL_WIDTH,
                 player.current_map.height - config.MAP_PANEL_HEIGHT))

    if newPos != player.camera_position:
        player.current_map.fov_needs_recompute = True
        player.camera_position = newPos


def _debug_positions(player, mouse):
    global _panel
    libtcod.console_print_ex(
        _panel, 15, 4, libtcod.BKGND_NONE,
        libtcod.RIGHT, '  @ ' + player.pos.to_string())
    libtcod.console_print_ex(
        _panel, 15, 5, libtcod.BKGND_NONE,
        libtcod.RIGHT, '  m ' + str(mouse[0]) + ', ' + str(mouse[1]))
    libtcod.console_print_ex(
        _panel, 15, 6, libtcod.BKGND_NONE,
        libtcod.RIGHT, 'cam ' + player.camera_position.to_string())


def _debug_room(player):
    global _panel
    room_index = -1
    for r in player.current_map.rooms:
        if r.contains(player.pos):
            room_index = player.current_map.rooms.index(r)
            break
    if (room_index != -1):
        libtcod.console_print_ex(
            _panel, 1, 4, libtcod.BKGND_NONE,
            libtcod.LEFT, 'Room ' + str(room_index + 1))


def _debug_danger(player):
    global _panel
    if player.endangered:
        libtcod.console_print_ex(
            _panel, 1, 2, libtcod.BKGND_NONE,
            libtcod.LEFT, 'DANGER')


def _debug_fps():
    global _panel, _twenty_frame_estimate
    libtcod.console_print_ex(_panel, 1, 2, libtcod.BKGND_NONE, libtcod.LEFT,
                             'FPS ' + str(20000. / _twenty_frame_estimate))


def draw_console(player):
    """
    Refreshes the map display and blits to the window.
    Sets or clears player.endangered.
    """
    global _con

    current_map = player.current_map

    if current_map.is_outdoors and current_map.fov_elevation_changed:
        current_map.set_fov_elevation(current_map.region_elevations[current_map.region[player.pos.x][player.pos.y]])
        current_map.fov_elevation_changed = False

    if current_map.fov_needs_recompute:
        # Recompute FOV if needed (the player moved or something in
        # the dungeon changed).
        libtcod.map_compute_fov(
            current_map.fov_map, player.x,
            player.y, TORCH_RADIUS, FOV_LIGHT_WALLS, FOV_ALGO)
        if current_map.is_outdoors:
            _draw_outdoors(player)
        else:
            _draw_indoors(player)

    # Draw all objects in the list, except the player. We want it to
    # always appear over all other objects, so it's drawn later.
    # (Could also achieve this by guaranteeing the player is always
    # the last object in current_map.objects.)
    for object in player.visible_objects:
        _draw_object(player, object)
    _draw_object(player, player)

    libtcod.console_blit(_con, 0, 0, config.MAP_PANEL_WIDTH,
                         config.MAP_PANEL_HEIGHT, 0, 0, 0)


def _pwrite(line, string, color=libtcod.white):
    global _panel
    libtcod.console_set_default_foreground(_panel, color)
    libtcod.console_print_ex(_panel, 1, line, libtcod.BKGND_NONE, libtcod.LEFT, string)


def draw_panel(player, pointer_location):
    """
    Refreshes the UI display and blits it to the window.
    """
    libtcod.console_set_default_background(_panel, libtcod.black)
    libtcod.console_clear(_panel)

    # Only display the (log.MSG_HEIGHT) most recent
    write_log(log.game_msgs[-log.MSG_HEIGHT:], _panel, MSG_X, 1)

    _render_bar(1, 1, config.BAR_WIDTH, 'HP', int(player.fighter.hp),
                player.fighter.max_hp,
                libtcod.light_red, libtcod.darker_red)
    #libtcod.console_print_ex(
    #    _panel, 1, 3, libtcod.BKGND_NONE,
    #    libtcod.LEFT, 'Dungeon level ' + str(player.current_map.dungeon_level))
    line = 2
    if player.fighter.bleeding > 0:
        _pwrite(line, 'Bleeding: ' + str(player.fighter.bleeding), libtcod.red)
        line += 1
    if player.fighter.wounds > 0:
        _pwrite(line, 'Wounds: ' + str(player.fighter.wounds))
        line += 1
    if player.fighter.exhaustion / 100 > 0:
        _pwrite(line, 'Exhaustion: ' + str(player.fighter.exhaustion / 100))
        line += 1
    if player.current_map.is_outdoors:
        _pwrite(line,
                'Elevation: ' +
                str(player.current_map.region_elevations[player.current_map.region[player.pos.x][player.pos.y]] * 500) +
                ' feet')
        line += 1
    elif hasattr(player.current_map, 'dungeon_level'):
        _pwrite(line, 'Dungeon level ' + str(player.current_map.dungeon_level))
        line += 1
    _pwrite(line, 'Turn ' + str(player.turn_count))
    line += 1

    # _debug_positions(player, pointer_location)
    # _debug_room(player)
    # _debug_danger(player)
    # _debug_fps()

    libtcod.console_set_default_foreground(_panel, libtcod.light_gray)
    libtcod.console_print_ex(
        _panel, 1, 0, libtcod.BKGND_NONE, libtcod.LEFT,
        _get_names_under_mouse(player, pointer_location))

    # Done with "_panel", blit it to the root console.
    libtcod.console_blit(_panel, 0, 0, config.SCREEN_WIDTH, config.PANEL_HEIGHT,
                         0, 0, PANEL_Y)


def blit_overlay():
    global _overlay
    libtcod.console_set_key_color(_overlay, libtcod.black)
    libtcod.console_blit(_overlay, 0, 0, config.MAP_PANEL_WIDTH,
                         config.MAP_PANEL_HEIGHT, 0, 0, 0, 0.4, 1.0)


def render_all(player, pointer_location):
    global _frame_index, _twenty_frame_estimate, _last_frame_time

    global _last_pointer
    if not pointer_location:
        pointer_location = _last_pointer
    _last_pointer = pointer_location

    update_camera(player)
    _frame_index = (_frame_index + 1) % 20
    if _frame_index == 0:
        now = time.time() * 1000
        _twenty_frame_estimate = (now - _last_frame_time) / 2 + (_twenty_frame_estimate / 2)
        _last_frame_time = now

    draw_console(player)
    draw_panel(player, pointer_location)
    blit_overlay()
