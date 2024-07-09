import tcod
from tcod.event import KeySym
from ecs.ecs import System
from systems.MessageSystem import MessageChannel
from utils.mapgen import TileType

class InputSystem(System):
    def __init__(self, game):
        self.game = game
        self.pressed_keys = set()

    def handle_input(self):
        for event in tcod.event.wait():
            if event.type == "QUIT":
                raise SystemExit()
            elif event.type == "KEYDOWN":
                self.pressed_keys.add(event.sym)
                return self.handle_keydown(event)
            elif event.type == "KEYUP":
                self.pressed_keys.discard(event.sym)
        return False

    def handle_keydown(self, event):
        action_taken = False
        move_map = {
            # Arrow keys
            KeySym.UP: (0, -1),
            KeySym.DOWN: (0, 1),
            KeySym.LEFT: (-1, 0),
            KeySym.RIGHT: (1, 0),
            # Numpad
            KeySym.KP_8: (0, -1),
            KeySym.KP_2: (0, 1),
            KeySym.KP_4: (-1, 0),
            KeySym.KP_6: (1, 0),
            # Diagonal movement
            KeySym.KP_7: (-1, -1),
            KeySym.KP_9: (1, -1),
            KeySym.KP_1: (-1, 1),
            KeySym.KP_3: (1, 1),
            # Optional: Add support for diagonal movement with arrow keys + modifiers
            (KeySym.UP, KeySym.LEFT): (-1, -1),
            (KeySym.UP, KeySym.RIGHT): (1, -1),
            (KeySym.DOWN, KeySym.LEFT): (-1, 1),
            (KeySym.DOWN, KeySym.RIGHT): (1, 1),
        }

        if event.sym in move_map:
            dx, dy = move_map[event.sym]
            self.game.move_player(dx, dy)
            action_taken = True
        elif isinstance(event.sym, tuple) and event.sym in move_map:
            dx, dy = move_map[event.sym]
            self.game.move_player(dx, dy)
            action_taken = True
        elif event.sym in (KeySym.PERIOD, KeySym.KP_5):
            self.game.message_system.add_message("You wait for a moment.", MessageChannel.SYSTEM)
            action_taken = True
        elif event.sym == KeySym.i:
            self.game.interact()
        elif event.sym == KeySym.o:
            action_taken = self.handle_open_door()
        elif event.sym == KeySym.c:
            action_taken = self.handle_close_door()
        elif event.sym == KeySym.q:
            raise SystemExit()
        elif event.sym == KeySym.s:
            self.game.save_game()
        elif event.sym == KeySym.d and (event.mod & tcod.event.KMOD_CTRL):
            self.game.disable_actor_dialogue = not self.game.disable_actor_dialogue
            status = "disabled" if self.game.disable_actor_dialogue else "enabled"
            self.game.message_system.add_message(f"Actor-to-actor dialogue {status}", MessageChannel.SYSTEM)
            action_taken = True

        # Check for diagonal movement with arrow keys
        if KeySym.UP in self.pressed_keys and KeySym.LEFT in self.pressed_keys:
            self.game.move_player(-1, -1)
            action_taken = True
        elif KeySym.UP in self.pressed_keys and KeySym.RIGHT in self.pressed_keys:
            self.game.move_player(1, -1)
            action_taken = True
        elif KeySym.DOWN in self.pressed_keys and KeySym.LEFT in self.pressed_keys:
            self.game.move_player(-1, 1)
            action_taken = True
        elif KeySym.DOWN in self.pressed_keys and KeySym.RIGHT in self.pressed_keys:
            self.game.move_player(1, 1)
            action_taken = True

        return action_taken

    def handle_door(self, action):
        player = self.game.world.player
        for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
            x, y = int(player.x + dx), int(player.y + dy)
            if self.game.world.game_map.tiles[y][x].tile_type == TileType.DOOR:
                tile = self.game.world.game_map.tiles[y][x]
                if (action == 'open' and not tile.is_open) or (action == 'close' and tile.is_open):
                    tile.toggle_door()
                    self.game.world.game_map.initialize_fov()
                    self.game.fov_recompute = True
                    self.game.message_system.add_message(f"You {action} the door.", MessageChannel.SYSTEM)
                    return True
        self.game.message_system.add_message(f"There is no {'door to open' if action == 'open' else 'open door to close'}.", MessageChannel.SYSTEM)
        return False

    def handle_open_door(self):
        return self.handle_door('open')

    def handle_close_door(self):
        return self.handle_door('close')