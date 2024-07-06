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
            self.game.context
        )

    def initialize_all(self):
        self.initialize_message_system()
        self.initialize_camera_and_fov()
        self.initialize_systems()
        self.initialize_render_system()