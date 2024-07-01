from ecs.ecs import System
from components.PositionComponent import PositionComponent
from systems.MessageSystem import MessageChannel
from entities.Actor import Actor
from utils.mapgen import TileType

class PlayerSystem(System):
    def __init__(self, game):
        self.game = game
        self.logger = game.logger

    def move_player(self, dx, dy):
        player = self.game.world.player
        new_x = int(player.x + dx)
        new_y = int(player.y + dy)
        self.logger.debug(f"Attempting to move player to ({new_x}, {new_y})")
        if self.game.world.game_map.is_walkable(new_x, new_y):
            player.get_component(PositionComponent).x = new_x
            player.get_component(PositionComponent).y = new_y
            self.game.fov_recompute = True
            return True
        return False

    def interact(self):
        player = self.game.world.player
        player_x, player_y = int(player.x), int(player.y)
        self.logger.debug(f"Player attempting to interact at position ({player_x}, {player_y})")
        for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:  # Check adjacent tiles
            x, y = player_x + dx, player_y + dy
            tile = self.game.world.game_map.tiles[y][x]
            if tile.tile_type == TileType.DOOR:
                tile.toggle_door()
                action = "open" if tile.is_open else "close"
                self.game.show_message(f"You {action} the door.", MessageChannel.SYSTEM, (255, 255, 0))
                return True
            entity = self.game.world.get_entity_at(x, y)
            if isinstance(entity, Actor):
                self.game.dialogue_system.start_dialogue(entity)
                return True
        self.game.show_message("There's nothing to interact with here.", MessageChannel.SYSTEM, (255, 255, 0))
        return False

    def update(self, entities):
        # This method can be used for any per-turn updates related to the player
        pass