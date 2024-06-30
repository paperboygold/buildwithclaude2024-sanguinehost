import tcod
import textwrap
from ecs.ecs import System
from utils.mapgen import TileType

class RenderSystem(System):
    def __init__(self, game, world, message_system, root_console, game_console, dialogue_console, context):
        self.game = game
        self.world = world
        self.message_system = message_system
        self.root_console = root_console
        self.game_console = game_console
        self.dialogue_console = dialogue_console
        self.context = context
        self.width = game.width
        self.height = game.height
        self.game_area_height = game.game_area_height
        self.dialogue_height = game.dialogue_height
        self.camera_x = 0
        self.camera_y = 0

    def update_camera(self):
        self.camera_x = int(self.world.player.x - self.width // 2)
        self.camera_y = int(self.world.player.y - self.game_area_height // 2)

    def render_message_log(self):
        self.dialogue_console.clear()
        self.dialogue_console.draw_frame(0, 0, self.width, self.dialogue_height, ' ')

        y = self.dialogue_height - 2
        for message in self.message_system.get_visible_messages():
            wrapped_text = textwrap.wrap(message.text, self.width - 2)
            for line in reversed(wrapped_text):
                if y < 1:
                    break
                self.dialogue_console.print(1, y, line, message.color)
                y -= 1
            if y < 1:
                break

    def render(self):
        if self.game.fov_recompute:
            self.world.game_map.compute_fov(
                int(self.world.player.x),
                int(self.world.player.y),
                self.game.fov_radius
            )
            self.game.fov_recompute = False

        self.update_camera()
        self.game_console.clear()
        self.dialogue_console.clear()
        
        # Render game area
        self.game_console.draw_frame(0, 0, self.width, self.game_area_height, ' ')
        self.game_console.draw_rect(1, 0, self.width - 2, 1, ord('─'))
        self.game_console.put_char(self.width - 1, 0, ord('┐'))
        
        # Render map
        self.render_map()
        
        # Render entities
        self.render_entities()
        
        # Render dialogue area
        self.render_message_log()
        self.dialogue_console.draw_rect(1, 0, self.width - 2, 1, ord('─'))
        self.dialogue_console.put_char(self.width - 1, 0, ord('┐'))
        
        # Blit game and dialogue consoles to root console
        self.game_console.blit(self.root_console, 0, 0)
        self.dialogue_console.blit(self.root_console, 0, self.game_area_height)
        
        self.context.present(self.root_console)

    def render_map(self):
        for y in range(self.game_area_height - 2):
            for x in range(self.width - 2):
                map_x = x + self.camera_x
                map_y = y + self.camera_y
                if 0 <= map_x < self.world.width and 0 <= map_y < self.world.height:
                    tile = self.world.game_map.tiles[map_y][map_x]
                    visible = self.world.game_map.is_in_fov(map_x, map_y)
                    if visible:
                        tile.explored = True
                        if tile.tile_type == TileType.WALL:
                            color = (130, 110, 50)
                        elif tile.tile_type == TileType.FLOOR:
                            color = (200, 180, 50)
                        else:  # Door
                            color = (0, 255, 255)
                    elif tile.explored:
                        if tile.tile_type == TileType.WALL:
                            color = (0, 0, 100)
                        elif tile.tile_type == TileType.FLOOR:
                            color = (50, 50, 150)
                        else:  # Door
                            color = (0, 100, 100)
                    else:
                        color = (0, 0, 0)  # Unexplored and not visible
                    if tile.tile_type == TileType.DOOR:
                        if tile.is_open:
                            char = '/'
                        else:
                            char = '+'
                        self.game_console.print(x + 1, y + 1, char, color)
                    else:
                        self.game_console.print(x + 1, y + 1, tile.tile_type.value, color)

    def render_entities(self):
        for entity in self.world.entities:
            if self.world.game_map.is_in_fov(int(entity.x), int(entity.y)):
                x = int(entity.x) - self.camera_x
                y = int(entity.y) - self.camera_y
                if 0 <= x < self.width - 2 and 0 <= y < self.game_area_height - 2:
                    self.game_console.print(x + 1, y + 1, entity.char)