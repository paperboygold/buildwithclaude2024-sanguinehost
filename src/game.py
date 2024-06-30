import anthropic
import logging
import traceback
from utils.load_api_key import load_api_key
from systems.GameInitializationSystem import GameInitializationSystem
from systems.GameLoopSystem import GameLoopSystem
from systems.MessageSystem import MessageChannel
from entities.Actor import Actor

class Game:
    def __init__(self, world):
        self.logger = logging.getLogger(__name__)
        try:
            self.world = world
            api_key = load_api_key()
            if not api_key:
                raise ValueError("No API key provided")
            self.anthropic_client = anthropic.Anthropic(api_key=api_key)
            
            self.init_system = GameInitializationSystem(self)
            self.init_system.initialize_all()
            
            self.loop_system = GameLoopSystem(self)

        except Exception as e:
            self.logger.error(f"Error initializing game: {str(e)}")
            self.logger.debug(traceback.format_exc())
            raise

    def setup_world(self, world):
        self.world = world
        self.init_system.initialize_render_system()

    def show_message(self, text, channel=MessageChannel.SYSTEM, color=None, sender=None):
        if sender and isinstance(sender, Actor):
            color = sender.color
        elif channel == MessageChannel.DIALOGUE and not color:
            color = (0, 255, 255)
        elif not color:
            color = (255, 255, 255)
        self.message_system.add_message(text, channel, color)
        self.render_system.render()

    def interact(self):
        return self.player_system.interact()

    def move_player(self, dx, dy):
        return self.player_system.move_player(dx, dy)

    def run(self):
        try:
            self.loop_system.run()
        except Exception as e:
            self.logger.error(f"Error in game loop: {str(e)}")
            self.logger.debug(traceback.format_exc())
            self.show_message(f"An error occurred: {str(e)}", MessageChannel.SYSTEM, (255, 0, 0))
