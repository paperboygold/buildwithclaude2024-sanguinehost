import tcod
from tcod.event import KeySym
from ecs.ecs import System
from systems.MessageSystem import MessageChannel
from utils.mapgen import TileType

class InputSystem(System):
    def __init__(self, game):
        self.game = game

    def handle_input(self):
        for event in tcod.event.wait():
            if event.type == "QUIT":
                raise SystemExit()
            elif event.type == "KEYDOWN":
                return self.handle_keydown(event)
        return False

    def handle_keydown(self, event):
        action_taken = False
        if event.sym == KeySym.UP:
            self.game.move_player(0, -1)
            action_taken = True
        elif event.sym == KeySym.DOWN:
            self.game.move_player(0, 1)
            action_taken = True
        elif event.sym == KeySym.LEFT:
            self.game.move_player(-1, 0)
            action_taken = True
        elif event.sym == KeySym.RIGHT:
            self.game.move_player(1, 0)
            action_taken = True
        elif event.sym == KeySym.PERIOD:
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
        return action_taken

    def handle_open_door(self):
        player = self.game.world.player
        for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:  # Check adjacent tiles
            x, y = int(player.x + dx), int(player.y + dy)
            if self.game.world.game_map.tiles[y][x].tile_type == TileType.DOOR:
                tile = self.game.world.game_map.tiles[y][x]
                if not tile.is_open:
                    tile.is_open = True
                    tile.blocked = False
                    tile.walkable = True
                    tile.block_sight = False  # Update block_sight
                    self.game.message_system.add_message("You open the door.", MessageChannel.SYSTEM)
                    return True
        self.game.message_system.add_message("There is no door to open.", MessageChannel.SYSTEM)
        return False

    def handle_close_door(self):
        player = self.game.world.player
        for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:  # Check adjacent tiles
            x, y = int(player.x + dx), int(player.y + dy)
            if self.game.world.game_map.tiles[y][x].tile_type == TileType.DOOR:
                tile = self.game.world.game_map.tiles[y][x]
                if tile.is_open:
                    tile.is_open = False
                    tile.blocked = True
                    tile.walkable = False
                    tile.block_sight = True  # Update block_sight
                    self.game.message_system.add_message("You close the door.", MessageChannel.SYSTEM)
                    return True
        self.game.message_system.add_message("There is no open door to close.", MessageChannel.SYSTEM)
        return False