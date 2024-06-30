from ecs.ecs import System
from components.PositionComponent import PositionComponent
from systems.MessageSystem import MessageChannel

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
            entity = self.game.world.get_entity_at(player_x + dx, player_y + dy)
            if hasattr(entity, 'interact'):
                entity.interact(self.game)
                return True
        self.game.show_message("There's nothing to interact with here.", MessageChannel.SYSTEM, (255, 255, 0))
        return False

    def update(self, entities):
        # This method can be used for any per-turn updates related to the player
        pass