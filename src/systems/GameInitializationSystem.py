import tcod
from systems.MessageSystem import MessageSystem
from systems.RenderSystem import RenderSystem
from systems.InputSystem import InputSystem
from systems.DialogueSystem import DialogueSystem
from systems.PlayerSystem import PlayerSystem
from systems.MessageSystem import MessageChannel

class GameInitializationSystem:
    def __init__(self, game):
        self.game = game

    def initialize_game_dimensions(self):
        self.game.width = 80
        self.game.height = 50
        self.game.tile_size = 16
        self.game.pixel_width = self.game.width * self.game.tile_size
        self.game.pixel_height = self.game.height * self.game.tile_size
        self.game.game_area_height = 38
        self.game.dialogue_height = 12

    def initialize_consoles(self):
        self.game.context = tcod.context.new_terminal(
            self.game.width,
            self.game.height,
            title="Sanguine Host",
            vsync=True,
            tileset=tcod.tileset.load_tilesheet(
                "assets/tiles/terminal16x16_gs_ro.png", 16, 16, tcod.tileset.CHARMAP_CP437
            )
        )
        self.game.root_console = tcod.console.Console(self.game.width, self.game.height)
        self.game.game_console = tcod.console.Console(self.game.width, self.game.game_area_height)
        self.game.dialogue_console = tcod.console.Console(self.game.width, self.game.dialogue_height)

    def initialize_message_system(self):
        self.game.message_system = MessageSystem()
        self.game.max_log_messages = 100
        self.game.visible_log_lines = 10
        self.game.visible_channels = set(MessageChannel) - {MessageChannel.MOVEMENT}

    def initialize_camera_and_fov(self):
        self.game.camera_x = 0
        self.game.camera_y = 0
        self.game.fov_radius = 10
        self.game.fov_recompute = True

    def initialize_systems(self):
        self.game.input_system = InputSystem(self.game)
        self.game.dialogue_system = DialogueSystem(self.game)
        self.game.player_system = PlayerSystem(self.game)

    def initialize_render_system(self):
        self.game.render_system = RenderSystem(
            self.game,
            self.game.world,
            self.game.message_system,
            self.game.root_console,
            self.game.game_console,
            self.game.dialogue_console,
            self.game.context
        )

    def initialize_all(self):
        self.initialize_game_dimensions()
        self.initialize_consoles()
        self.initialize_message_system()
        self.initialize_camera_and_fov()
        self.initialize_systems()
        self.initialize_render_system()