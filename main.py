import os
import anthropic
import tcod
from tcod import console
import textwrap
from tcod.event import KeySym
from dotenv import load_dotenv
from enum import Enum, auto  # Add this line

def load_api_key():
    load_dotenv()  # This loads the .env file
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Warning: ANTHROPIC_API_KEY not found in .env file.")
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
    MOVEMENT = auto()  # Add this new channel

class Message:
    def __init__(self, text, channel, color):
        self.text = text
        self.channel = channel
        self.color = color

class Game:
    def __init__(self, world):
        self.world = world
        api_key = load_api_key()
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
        self.visible_channels = set(MessageChannel) - {MessageChannel.MOVEMENT}  # Filter out movement messages
        
        self.context = tcod.context.new_terminal(
            self.width,
            self.height,
            title="Roguelike Game",
            vsync=True,
            tileset=tcod.tileset.load_tilesheet(
                "tiles/terminal16x16_gs_ro.png", 16, 16, tcod.tileset.CHARMAP_CP437
            )
        )
        self.root_console = tcod.console.Console(self.width, self.height)
        self.game_console = tcod.console.Console(self.width, self.game_area_height)
        self.dialogue_console = tcod.console.Console(self.width, self.dialogue_height)

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
        self.game_console.clear()
        self.dialogue_console.clear()
        
        # Render game area
        self.game_console.draw_frame(0, 0, self.width, self.game_area_height, ' ')
        for entity in self.world.entities:
            x = int(entity.x)
            y = int(entity.y)
            self.game_console.print(x, y, entity.char)
        
        self.render_message_log()
        
        # Blit game and dialogue consoles to root console
        self.game_console.blit(self.root_console, 0, 0)
        self.dialogue_console.blit(self.root_console, 0, self.game_area_height)
        
        self.context.present(self.root_console)

    def show_message(self, text, channel=MessageChannel.SYSTEM, color=(255, 255, 255)):
        self.add_message(text, channel, color)
        self.render()

    def get_user_input(self, prompt):
        user_input = ""
        max_input_length = self.width - len(prompt) - 3
        input_message = f"{prompt}{user_input}_"
        
        # Add an initial empty input line to the log
        self.add_message(input_message, MessageChannel.SYSTEM, (255, 255, 255))
        
        while True:
            self.render()  # Render the game state
            
            for event in tcod.event.wait():
                if event.type == "QUIT":
                    raise SystemExit()
                elif event.type == "KEYDOWN":
                    if event.sym == KeySym.RETURN and user_input:
                        # Remove the input line from the log
                        self.message_log.pop()
                        return user_input
                    elif event.sym == KeySym.BACKSPACE:
                        user_input = user_input[:-1]
                    elif event.sym == KeySym.ESCAPE:
                        # Remove the input line from the log
                        self.message_log.pop()
                        return None
                elif event.type == "TEXTINPUT":
                    if len(user_input) < max_input_length:
                        user_input += event.text
                
                # Update the last message in the log with the current input
                input_message = f"{prompt}{user_input}_"
                self.message_log[-1] = Message(input_message, MessageChannel.SYSTEM, (255, 255, 255))
                self.render()  # Re-render to show the updated input

    def start_dialogue(self, npc):
        self.show_message(f"You are now talking to {npc.name}", MessageChannel.DIALOGUE, (0, 255, 255))
        
        while True:
            user_input = self.get_user_input("You: ")
            if user_input is None:  # User pressed Escape
                self.show_message("Dialogue ended.", MessageChannel.DIALOGUE, (0, 255, 255))
                break
            
            self.show_message(f"You: {user_input}", MessageChannel.DIALOGUE, (0, 255, 255))
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
                self.show_message(f"Error: {str(e)}", MessageChannel.SYSTEM, (255, 0, 0))
                break

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
        # Note: We're using add_message instead of show_message to avoid forcing a render

    def run(self):
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
                        self.interact()  # Call the new interact method
                    elif event.sym == KeySym.q:
                        raise SystemExit()
                self.render()

# Example usage
def main():
    world = World(80, 38)  # Match the game area size
    player = Player(40, 19)
    npc = NPC(42, 19, "Wise Old Man")
    world.add_entity(player)
    world.add_entity(npc)

    try:
        game = Game(world)
        game.run()
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()