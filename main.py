import os
import anthropic
import tcod
import textwrap
from tcod.event import KeySym
from dotenv import load_dotenv
from enum import Enum, auto
import logging
import traceback
from typing import Optional

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        filename='game.log',
        filemode='w'
    )
    console = logging.StreamHandler()
    console.setLevel(logging.WARNING)
    formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
    console.setFormatter(formatter)
    logging.getLogger('').addHandler(console)

def load_api_key() -> Optional[str]:
    load_dotenv()
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logging.warning("ANTHROPIC_API_KEY not found in .env file.")
        print("Please enter your Anthropic API key manually:")
        api_key = input().strip()
    return api_key

class Entity:
    def __init__(self, x, y, char, name):
        self.x = float(x)
        self.y = float(y)
        self.char = char
        self.name = name

class Player(Entity):
    def __init__(self, x, y):
        super().__init__(x, y, '@', 'Player')

class NPC(Entity):
    def __init__(self, x, y, name):
        super().__init__(x, y, 'N', name)
        self.dialogue_history = []

class World:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.entities = []
        self.player = None

    def add_entity(self, entity):
        if isinstance(entity, Player):
            self.player = entity
        self.entities.append(entity)

    def get_entity_at(self, x, y):
        return next((e for e in self.entities if int(e.x) == int(x) and int(e.y) == int(y)), None)

class MessageChannel(Enum):
    COMBAT = auto()
    DIALOGUE = auto()
    SYSTEM = auto()
    IMPORTANT = auto()
    MOVEMENT = auto()

class Message:
    def __init__(self, text, channel, color):
        self.text = text
        self.channel = channel
        self.color = color

class Game:
    def __init__(self, world):
        self.logger = logging.getLogger(__name__)
        try:
            self.world = world
            api_key = load_api_key()
            if not api_key:
                raise ValueError("No API key provided")
            self.anthropic_client = anthropic.Anthropic(api_key=api_key)
            
            self.width = 80  # Characters wide
            self.height = 50  # Characters high
            self.tile_size = 16  # Pixels per character
            self.pixel_width = self.width * self.tile_size
            self.pixel_height = self.height * self.tile_size
            self.game_area_height = 38  # Characters high
            self.dialogue_height = 12  # Characters high
            
            self.message_log = []
            self.max_log_messages = 100
            self.visible_log_lines = 10
            self.visible_channels = set(MessageChannel) - {MessageChannel.MOVEMENT}
            
            self.context = tcod.context.new_terminal(
                self.width,
                self.height,
                title="Roguelike Game",
                vsync=True,
                tileset=tcod.tileset.load_tilesheet(
                    "assets/tiles/terminal16x16_gs_ro.png", 16, 16, tcod.tileset.CHARMAP_CP437
                )
            )
            self.root_console = tcod.console.Console(self.width, self.height)
            self.game_console = tcod.console.Console(self.width, self.game_area_height)
            self.dialogue_console = tcod.console.Console(self.width, self.dialogue_height)
            
            self.camera_x = 0
            self.camera_y = 0

        except Exception as e:
            self.logger.error(f"Error initializing game: {str(e)}")
            self.logger.debug(traceback.format_exc())
            raise

    def update_camera(self):
        # Center the camera on the player
        self.camera_x = int(self.world.player.x - self.width // 2)
        self.camera_y = int(self.world.player.y - self.game_area_height // 2)

    def add_message(self, text, channel=MessageChannel.SYSTEM, color=(255, 255, 255)):
        if channel in self.visible_channels:
            message = Message(text, channel, color)
            self.message_log.append(message)
            if len(self.message_log) > self.max_log_messages:
                self.message_log.pop(0)

    def render_message_log(self):
        self.dialogue_console.clear()
        self.dialogue_console.draw_frame(0, 0, self.width, self.dialogue_height, ' ')

        y = self.dialogue_height - 2
        for message in reversed(self.message_log[-self.visible_log_lines:]):
            wrapped_text = textwrap.wrap(message.text, self.width - 2)
            for line in reversed(wrapped_text):
                if y < 1:
                    break
                self.dialogue_console.print(1, y, line, message.color)
                y -= 1
            if y < 1:
                break

    def render(self):
        self.update_camera()
        self.game_console.clear()
        self.dialogue_console.clear()
        
        # Render game area
        self.game_console.draw_frame(0, 0, self.width, self.game_area_height, ' ')
        self.game_console.draw_rect(1, 0, self.width - 2, 1, ord('─'))
        self.game_console.put_char(self.width - 1, 0, ord('┐'))
        
        for entity in self.world.entities:
            x = int(entity.x) - self.camera_x
            y = int(entity.y) - self.camera_y
            # Only draw entities within the inner area of the game window
            if 1 <= x < self.width - 1 and 1 <= y < self.game_area_height - 1:
                self.game_console.print(x, y, entity.char)
        
        # Render dialogue area
        self.render_message_log()
        # Draw the missing top horizontal line for the dialogue console
        self.dialogue_console.draw_rect(1, 0, self.width - 2, 1, ord('─'))
        # Fix the top-right corner for the dialogue console
        self.dialogue_console.put_char(self.width - 1, 0, ord('┐'))
        
        # Blit game and dialogue consoles to root console
        self.game_console.blit(self.root_console, 0, 0)
        self.dialogue_console.blit(self.root_console, 0, self.game_area_height)
        
        self.context.present(self.root_console)

    def show_message(self, text, channel=MessageChannel.SYSTEM, color=(255, 255, 255)):
        self.add_message(text, channel, color)
        self.render()

    def get_user_input(self, prompt):
        user_input = ""
        max_input_length = self.width * 3  # Allow for multiple lines
        input_lines = []
        cursor_pos = 0

        while True:
            # Wrap the current input
            wrapped_lines = textwrap.wrap(prompt + user_input, width=self.width - 2)
            
            # Update the message log with the wrapped input
            self.message_log = self.message_log[:-len(input_lines)] if input_lines else self.message_log
            input_lines = [Message(line, MessageChannel.SYSTEM, (255, 255, 255)) for line in wrapped_lines]
            self.message_log.extend(input_lines)

            # Ensure we don't exceed the visible log lines
            while len(self.message_log) > self.visible_log_lines:
                self.message_log.pop(0)

            self.render()  # Render the game state

            for event in tcod.event.wait():
                if event.type == "QUIT":
                    raise SystemExit()
                elif event.type == "KEYDOWN":
                    if event.sym == KeySym.RETURN and user_input:
                        # Remove temporary input lines
                        self.message_log = self.message_log[:-len(input_lines)]
                        # Add the final input as a single message
                        self.add_message(prompt + user_input, MessageChannel.DIALOGUE, (0, 255, 255))
                        return user_input
                    elif event.sym == KeySym.BACKSPACE:
                        if user_input:
                            user_input = user_input[:cursor_pos-1] + user_input[cursor_pos:]
                            cursor_pos = max(0, cursor_pos - 1)
                    elif event.sym == KeySym.ESCAPE:
                        self.message_log = self.message_log[:-len(input_lines)]
                        return None
                elif event.type == "TEXTINPUT":
                    if len(user_input) < max_input_length:
                        user_input = user_input[:cursor_pos] + event.text + user_input[cursor_pos:]
                        cursor_pos += len(event.text)

            # Add cursor to the end of the last line
            if input_lines:
                last_line = input_lines[-1].text
                cursor_line = last_line[:cursor_pos] + "_" + last_line[cursor_pos:]
                self.message_log[-1] = Message(cursor_line, MessageChannel.SYSTEM, (255, 255, 255))

    def start_dialogue(self, npc):
        try:
            self.show_message(f"You are now talking to {npc.name}", MessageChannel.DIALOGUE, (0, 255, 255))
            
            while True:
                user_input = self.get_user_input("You: ")
                if user_input is None:  # User pressed Escape
                    self.show_message("Dialogue ended.", MessageChannel.DIALOGUE, (0, 255, 255))
                    break
                
                npc.dialogue_history.append({"role": "user", "content": user_input})
                
                try:
                    response = self.anthropic_client.messages.create(
                        model="claude-3-5-sonnet-20240620",
                        max_tokens=150,
                        system=f"You are {npc.name}, an NPC in a roguelike game. Respond in character, but keep your responses brief, natural, and to the point. Avoid overly flowery or theatrical language.",
                        messages=npc.dialogue_history
                    )
                    
                    npc_response = response.content[0].text if response.content else ""
                    npc.dialogue_history.append({"role": "assistant", "content": npc_response})
                    
                    self.show_message(f"{npc.name}: {npc_response}", MessageChannel.DIALOGUE, (0, 255, 255))
                except Exception as e:
                    self.logger.error(f"Error in AI response: {str(e)}")
                    self.show_message(f"Error: Unable to get NPC response", MessageChannel.SYSTEM, (255, 0, 0))
        except Exception as e:
            self.logger.error(f"Error in dialogue: {str(e)}")
            self.logger.debug(traceback.format_exc())
            self.show_message(f"An error occurred during dialogue", MessageChannel.SYSTEM, (255, 0, 0))

    def interact(self):
        player_x, player_y = int(self.world.player.x), int(self.world.player.y)
        for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:  # Check adjacent tiles
            entity = self.world.get_entity_at(player_x + dx, player_y + dy)
            if isinstance(entity, NPC):
                self.start_dialogue(entity)
                return
        self.show_message("There's no one to interact with.", MessageChannel.SYSTEM, (255, 255, 0))

    def move_player(self, dx, dy):
        new_x = self.world.player.x + dx
        new_y = self.world.player.y + dy
        if 0 <= new_x < self.world.width and 0 <= new_y < self.world.height:
            self.world.player.x = new_x
            self.world.player.y = new_y
            self.add_message(f"You move to ({new_x}, {new_y})", MessageChannel.MOVEMENT, (200, 200, 200))
        self.update_camera()  # Update camera position after moving

    def run(self):
        try:
            while True:
                self.render()
                for event in tcod.event.wait():
                    if event.type == "QUIT":
                        raise SystemExit()
                    elif event.type == "KEYDOWN":
                        if event.sym == KeySym.UP:
                            self.move_player(0, -1)
                        elif event.sym == KeySym.DOWN:
                            self.move_player(0, 1)
                        elif event.sym == KeySym.LEFT:
                            self.move_player(-1, 0)
                        elif event.sym == KeySym.RIGHT:
                            self.move_player(1, 0)
                        elif event.sym == KeySym.i:
                            self.interact()
                        elif event.sym == KeySym.q:
                            raise SystemExit()
                    self.render()
        except Exception as e:
            self.logger.error(f"Error in game loop: {str(e)}")
            self.logger.debug(traceback.format_exc())
            self.show_message(f"An error occurred: {str(e)}", MessageChannel.SYSTEM, (255, 0, 0))

def main():
    setup_logging()
    logger = logging.getLogger(__name__)
    try:
        world = World(80, 38)  # Match the game area size
        player = Player(40, 19)
        npc = NPC(42, 19, "Wise Old Man")
        world.add_entity(player)
        world.add_entity(npc)

        game = Game(world)
        game.run()
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        logger.debug(traceback.format_exc())
        print(f"A critical error occurred. Please check the game.log file for details.")

if __name__ == "__main__":
    main()
