import anthropic
import tcod
import logging
import traceback
import random
from systems.MessageSystem import MessageChannel, MessageSystem
from systems.RenderSystem import RenderSystem
from systems.InputSystem import InputSystem
from systems.DialogueSystem import DialogueSystem
from utils.load_api_key import load_api_key
from components.ActorComponent import ActorComponent
from entities.Actor import Actor
from systems.PlayerSystem import PlayerSystem

class Game:
    def __init__(self, world):
        self.logger = logging.getLogger(__name__)
        try:
            self.world = world
            api_key = load_api_key()
            if not api_key:
                raise ValueError("No API key provided")
            self.anthropic_client = anthropic.Anthropic(api_key=api_key)
            
            # Initialize game dimensions and consoles
            self.initialize_game_dimensions()
            self.initialize_consoles()
            
            # Initialize message system
            self.initialize_message_system()
            
            # Initialize camera and FOV
            self.initialize_camera_and_fov()

            # Initialize input system
            self.input_system = InputSystem(self)

            # Initialize dialogue system
            self.dialogue_system = DialogueSystem(self)

            # Initialize player system
            self.player_system = PlayerSystem(self)

        except Exception as e:
            self.logger.error(f"Error initializing game: {str(e)}")
            self.logger.debug(traceback.format_exc())
            raise

    def initialize_game_dimensions(self):
        self.width = 80  # Characters wide
        self.height = 50  # Characters high
        self.tile_size = 16  # Pixels per character
        self.pixel_width = self.width * self.tile_size
        self.pixel_height = self.height * self.tile_size
        self.game_area_height = 38  # Characters high
        self.dialogue_height = 12  # Characters high

    def initialize_consoles(self):
        self.context = tcod.context.new_terminal(
            self.width,
            self.height,
            title="Sanguine Host",
            vsync=True,
            tileset=tcod.tileset.load_tilesheet(
                "assets/tiles/terminal16x16_gs_ro.png", 16, 16, tcod.tileset.CHARMAP_CP437
            )
        )
        self.root_console = tcod.console.Console(self.width, self.height)
        self.game_console = tcod.console.Console(self.width, self.game_area_height)
        self.dialogue_console = tcod.console.Console(self.width, self.dialogue_height)

    def initialize_message_system(self):
        self.message_system = MessageSystem()
        self.max_log_messages = 100
        self.visible_log_lines = 10
        self.visible_channels = set(MessageChannel) - {MessageChannel.MOVEMENT}

    def initialize_camera_and_fov(self):
        self.camera_x = 0
        self.camera_y = 0
        self.fov_radius = 10
        self.fov_recompute = True

    def initialize_render_system(self):
        self.render_system = RenderSystem(
            self,
            self.world,
            self.message_system,
            self.root_console,
            self.game_console,
            self.dialogue_console,
            self.context
        )

    def setup_world(self, world):
        self.world = world
        self.initialize_render_system()

    def show_message(self, text, channel=MessageChannel.SYSTEM, color=None, sender=None):
        if sender and isinstance(sender, Actor):
            color = sender.color
        elif channel == MessageChannel.DIALOGUE and not color:
            color = (0, 255, 255)  # Default dialogue color if no sender specified
        elif not color:
            color = (255, 255, 255)  # Default white color for other messages
        self.message_system.add_message(text, channel, color)
        self.render_system.render()

    def interact(self):
        return self.player_system.interact()

    def move_player(self, dx, dy):
        return self.player_system.move_player(dx, dy)

    def run(self):
        try:
            self.logger.info("Starting game loop")
            while True:
                self.render_system.render()
                action_taken = self.input_system.handle_input()
                
                if action_taken:
                    self.logger.debug("Updating actor knowledge and positions")
                    self.world.actor_knowledge_system.update(self.world.entities)
                    self.world.update_actors()
                    
                    self.logger.debug("Checking for potential actor interactions")
                    potential_interactions = self.world.get_potential_actor_interactions()
                    for actor1, actor2 in potential_interactions:
                        if not actor1.get_component(ActorComponent).current_conversation and random.random() < 0.3:  # 30% chance to start a conversation
                            self.dialogue_system.start_actor_dialogue(actor1, actor2)
                    
                    # Continue actor dialogues after player action
                    for actor1, actor2 in potential_interactions:
                        if actor1.get_component(ActorComponent).current_conversation and actor1.get_component(ActorComponent).conversation_turns < 3:
                            self.dialogue_system.continue_actor_dialogue(actor1, actor2)
                            break  # Only continue one conversation per turn
                self.logger.debug("Game loop iteration completed")
        except Exception as e:
            self.logger.error(f"Error in game loop: {str(e)}")
            self.logger.debug(traceback.format_exc())
            self.show_message(f"An error occurred: {str(e)}", MessageChannel.SYSTEM, (255, 0, 0))