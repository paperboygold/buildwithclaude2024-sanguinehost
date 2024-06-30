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
import json
from utils.mapgen import generate_map, TileType
import random
from utils.dijkstra_map import DijkstraMap
import time
from ecs.ecs import Entity, Component
from components.ActorComponent import ActorComponent, ActorState
from components.KnowledgeComponent import KnowledgeComponent

def setup_logging():
    logging.basicConfig(
        level=logging.DEBUG,  # Change to DEBUG for more verbose logging
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        filename='game.log',
        filemode='w'
    )
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)  # Change to INFO to see more output in console
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

class PositionComponent(Component):
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y

class RenderComponent(Component):
    def __init__(self, char: str, name: str):
        self.char = char
        self.name = name

class GameEntity(Entity):
    def __init__(self, x: float, y: float, char: str, name: str):
        super().__init__()
        self.add_component(PositionComponent(x, y))
        self.add_component(RenderComponent(char, name))

    @property
    def x(self):
        return self.get_component(PositionComponent).x

    @x.setter
    def x(self, value):
        self.get_component(PositionComponent).x = value

    @property
    def y(self):
        return self.get_component(PositionComponent).y

    @y.setter
    def y(self, value):
        self.get_component(PositionComponent).y = value

    @property
    def char(self):
        return self.get_component(RenderComponent).char

    @property
    def name(self):
        return self.get_component(RenderComponent).name

class Player(GameEntity):
    def __init__(self, x, y):
        super().__init__(x, y, '@', 'Player')

class Actor(GameEntity):
    def __init__(self, x, y, name, character_card_key):
        super().__init__(x, y, 'N', name)
        self.add_component(ActorComponent(name, character_card_key))
        self.add_component(KnowledgeComponent())
        self.color = (random.randint(100, 255), random.randint(100, 255), random.randint(100, 255))

    @property
    def state(self):
        return self.get_component(ActorComponent).state

    @state.setter
    def state(self, value):
        self.get_component(ActorComponent).state = value

    @property
    def knowledge(self):
        return self.get_component(KnowledgeComponent)

    def update(self, game_map):
        actor_component = self.get_component(ActorComponent)
        current_time = time.time()
        if current_time - actor_component.last_move_time < actor_component.move_delay:
            return

        if actor_component.state == ActorState.IDLE:
            if random.random() < 0.1:
                actor_component.state = ActorState.PATROL
                actor_component.target = game_map.get_random_walkable_position()
                actor_component.dijkstra_map = DijkstraMap(game_map.width, game_map.height)
                actor_component.dijkstra_map.compute([actor_component.target], game_map.is_walkable)
        elif actor_component.state == ActorState.PATROL:
            if actor_component.target:
                direction = actor_component.dijkstra_map.get_direction(int(self.x), int(self.y))
                if direction:
                    new_x = self.x + direction[0]
                    new_y = self.y + direction[1]
                    if game_map.is_walkable(int(new_x), int(new_y)):
                        self.x = new_x
                        self.y = new_y
                        actor_component.last_move_time = current_time

                if (int(self.x), int(self.y)) == actor_component.target:
                    actor_component.state = ActorState.IDLE
                    actor_component.target = None
                    actor_component.dijkstra_map = None
            else:
                actor_component.state = ActorState.IDLE

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

class WorldState:
    def __init__(self):
        self.player_actions = []
        self.discovered_areas = set()
        self.defeated_enemies = []
        self.acquired_items = []

    def update(self, action, data):
        if action == "move":
            self.player_actions.append(f"Moved to {data}")
        elif action == "discover":
            self.discovered_areas.add(data)
        elif action == "defeat":
            self.defeated_enemies.append(data)
        elif action == "acquire":
            self.acquired_items.append(data)

    def get_summary(self):
        return f"""
Player Actions: {', '.join(self.player_actions[-5:])}
Discovered Areas: {', '.join(self.discovered_areas)}
Defeated Enemies: {', '.join(self.defeated_enemies[-5:])}
Acquired Items: {', '.join(self.acquired_items[-5:])}
"""

class World:
    def __init__(self, width, height, game):
        self.width = width
        self.height = height
        self.game_map = generate_map(width, height, num_rooms=1)
        self.entities = []
        self.player = None
        self.game = game

    def add_entity(self, entity):
        if isinstance(entity, Player):
            self.player = entity
        self.entities.append(entity)

    def get_entity_at(self, x, y):
        return next((e for e in self.entities if int(e.x) == int(x) and int(e.y) == int(y)), None)

    def is_walkable(self, x, y):
        return self.game_map.is_walkable(x, y)

    def update_actor_knowledge(self):
        for actor in [entity for entity in self.entities if isinstance(entity, Actor)]:
            for other_actor in [e for e in self.entities if isinstance(e, Actor) and e != actor]:
                if self.game_map.is_in_fov(int(actor.x), int(actor.y)) and self.game_map.is_in_fov(int(other_actor.x), int(other_actor.y)):
                    actor.knowledge.add_actor(other_actor.name)
            
            current_room = next((room for room in self.game_map.rooms if room.x <= actor.x < room.x + room.width and room.y <= actor.y < room.y + room.height), None)
            if current_room:
                actor.knowledge.add_location(f"Room at ({current_room.x}, {current_room.y})")

    def update_actors(self):
        for entity in self.entities:
            if isinstance(entity, Actor):
                entity.update(self.game_map)

    def generate_actor_relationships(self):
        actor_entities = [entity for entity in self.entities if isinstance(entity, Actor)]
        for i, actor1 in enumerate(actor_entities):
            for actor2 in actor_entities[i+1:]:
                relationship_type = "stranger"
                if random.random() < 0.5:  # 50% chance of a non-stranger relationship
                    relationship_type = random.choice([
                        "friend", "rival", "mentor", "student", "ally", "enemy",
                        "acquaintance", "family", "colleague"
                    ])
                relationship_story = self.generate_relationship_story(actor1, actor2, relationship_type)
                actor1.knowledge.add_actor(actor2.name, relationship_type, relationship_story)
                actor2.knowledge.add_actor(actor1.name, relationship_type, relationship_story)

    def generate_relationship_story(self, actor1, actor2, relationship_type):
        actor1_component = actor1.get_component(ActorComponent)
        actor2_component = actor2.get_component(ActorComponent)
        prompt = f"Generate a very brief story (1-2 sentences) about the {relationship_type} relationship between {actor1.name} and {actor2.name}. {actor1.name}'s character: {actor1_component.character_card}. {actor2.name}'s character: {actor2_component.character_card}."
        
        self.game.logger.info(f"Generating relationship story for {actor1.name} and {actor2.name}")
        self.game.logger.debug(f"Relationship story prompt: {prompt}")
        
        try:
            response = self.game.anthropic_client.messages.create(
                model="claude-3-5-sonnet-20240620",
                max_tokens=100,  # Increased from 50 to 100
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            story = response.content[0].text.strip()
            self.game.logger.info(f"Generated relationship story: {story}")
            return story
        except Exception as e:
            self.game.logger.error(f"Error generating relationship story: {str(e)}")
            self.game.logger.debug(traceback.format_exc())
            return f"{actor1.name} and {actor2.name} have a {relationship_type} relationship."

    def get_potential_actor_interactions(self):
        actor_entities = [entity for entity in self.entities if isinstance(entity, Actor)]
        potential_interactions = []
        for actor1 in actor_entities:
            for actor2 in actor_entities:
                if actor1 != actor2 and self.game_map.is_in_fov(int(actor1.x), int(actor1.y)) and self.game_map.is_in_fov(int(actor2.x), int(actor2.y)):
                    potential_interactions.append((actor1, actor2))
        return potential_interactions

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
                title="Sanguine Host",
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
            self.fov_radius = 10
            self.fov_recompute = True

        except Exception as e:
            self.logger.error(f"Error initializing game: {str(e)}")
            self.logger.debug(traceback.format_exc())
            raise

    def update_camera(self):
        # Center the camera on the player
        self.camera_x = int(self.world.player.x - self.width // 2)
        self.camera_y = int(self.world.player.y - self.game_area_height // 2)
        self.logger.debug(f"Updating camera position to ({self.camera_x}, {self.camera_y})")

    def add_message(self, text, channel=MessageChannel.SYSTEM, color=(255, 255, 255)):
        if channel in self.visible_channels:
            message = Message(text, channel, color)
            self.message_log.append(message)
            if len(self.message_log) > self.max_log_messages:
                self.message_log.pop(0)
        self.logger.debug(f"Adding message: {text} (Channel: {channel}, Color: {color})")

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
        if self.fov_recompute:
            self.world.game_map.compute_fov(
                int(self.world.player.x),
                int(self.world.player.y),
                self.fov_radius
            )
            self.fov_recompute = False

        self.update_camera()
        self.game_console.clear()
        self.dialogue_console.clear()
        
        # Render game area
        self.game_console.draw_frame(0, 0, self.width, self.game_area_height, ' ')
        self.game_console.draw_rect(1, 0, self.width - 2, 1, ord('─'))
        self.game_console.put_char(self.width - 1, 0, ord('┐'))
        
        # Render map
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
                    self.game_console.print(x + 1, y + 1, tile.tile_type.value, color)
        
        # Render entities
        for entity in self.world.entities:
            if self.world.game_map.is_in_fov(int(entity.x), int(entity.y)):
                x = int(entity.x) - self.camera_x
                y = int(entity.y) - self.camera_y
                if 0 <= x < self.width - 2 and 0 <= y < self.game_area_height - 2:
                    self.game_console.print(x + 1, y + 1, entity.char)
        
        # Render dialogue area
        self.render_message_log()
        self.dialogue_console.draw_rect(1, 0, self.width - 2, 1, ord('─'))
        self.dialogue_console.put_char(self.width - 1, 0, ord('┐'))
        
        # Blit game and dialogue consoles to root console
        self.game_console.blit(self.root_console, 0, 0)
        self.dialogue_console.blit(self.root_console, 0, self.game_area_height)
        
        self.context.present(self.root_console)

    def show_message(self, text, channel=MessageChannel.SYSTEM, color=None, sender=None):
        if sender and isinstance(sender, Actor):
            color = sender.color
        elif channel == MessageChannel.DIALOGUE and not color:
            color = (0, 255, 255)  # Default dialogue color if no sender specified
        elif not color:
            color = (255, 255, 255)  # Default white color for other messages
        self.add_message(text, channel, color)
        self.render()

    def get_user_input(self, prompt):
        user_input = ""
        max_input_length = self.width * 3  # Allow for multiple lines
        input_lines = []
        cursor_pos = 0
        ignore_next_i = True  # Add this flag

        while True:
            # Wrap the current input
            wrapped_lines = textwrap.wrap(prompt + user_input, width=self.width - 2)
            
            # Update the message log with the wrapped input
            self.message_log = self.message_log[:-len(input_lines)] if input_lines else self.message_log
            input_lines = [Message(line, MessageChannel.SYSTEM, (0, 255, 0)) for line in wrapped_lines]  # Change color to green
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
                        # Don't add the final input as a message here
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
                        if ignore_next_i and event.text == 'i':
                            ignore_next_i = False  # Reset the flag
                        else:
                            user_input = user_input[:cursor_pos] + event.text + user_input[cursor_pos:]
                            cursor_pos += len(event.text)

            # Add cursor to the end of the last line
            if input_lines:
                last_line = input_lines[-1].text
                cursor_line = last_line[:cursor_pos] + "_" + last_line[cursor_pos:]
                self.message_log[-1] = Message(cursor_line, MessageChannel.SYSTEM, (0, 255, 0))  # Change color to green

    def start_dialogue(self, actor):
        try:
            actor_component = actor.get_component(ActorComponent)
            self.logger.info(f"Starting dialogue with {actor.name}")
            self.logger.debug(f"Actor {actor.name} character card: {actor_component.character_card}")
            self.logger.debug(f"Actor {actor.name} knowledge: {actor.knowledge.get_summary()}")
            self.show_message(f"You are now talking to {actor.name}", MessageChannel.DIALOGUE, sender=actor)
            
            while True:
                user_input = self.get_user_input("You: ")
                if user_input is None:  # User pressed Escape
                    self.logger.info(f"Dialogue with {actor.name} ended by user")
                    self.show_message("Dialogue ended.", MessageChannel.DIALOGUE, (0, 255, 255))
                    break
            
                self.logger.debug(f"Processing user input: {user_input}")
                self.show_message(f"You: {user_input}", MessageChannel.DIALOGUE, (0, 255, 0))
            
                actor_component.dialogue_history.append({"role": "user", "content": user_input})
                
                try:
                    relationship_info = ""
                    if actor.knowledge.known_actors:
                        other_actor_name, relationship_data = next(iter(actor.knowledge.known_actors.items()))
                        relationship = relationship_data["relationship"]
                        relationship_story = relationship_data["story"]
                        relationship_info = f"You have a {relationship} relationship with {other_actor_name}. {relationship_story} "

                    system_prompt = f"""You are {actor.name}, an NPC in a roguelike game. Character: {actor_component.character_card}
Environmental knowledge: {actor.knowledge.get_summary()}
{relationship_info}Respond in character with extremely brief responses, typically 1-2 short sentences or 10 words or less. Be concise and direct.
Important: Speak only in dialogue. Do not describe actions, appearances, use asterisks or quotation marks. Simply respond with what your character would say."""
                    
                    self.logger.info(f"API Request for {actor.name}:")
                    self.logger.info(f"System Prompt: {system_prompt}")
                    self.logger.debug(f"Dialogue history: {json.dumps(actor_component.dialogue_history, indent=2)}")
                    
                    request_body = {
                        "model": "claude-3-5-sonnet-20240620",
                        "max_tokens": 50,
                        "messages": actor_component.dialogue_history,
                        "system": system_prompt,
                        "temperature": 0.7,
                        "top_p": 1,
                        "stream": False,
                        "stop_sequences": ["\n\nHuman:", "\n\nSystem:", "\n\nAssistant:"]
                    }
                    
                    response = self.anthropic_client.messages.create(**request_body)
                    
                    self.logger.info(f"API Response for {actor.name}:")
                    self.logger.info(f"Response: {json.dumps(response.model_dump(), indent=2)}")
                    
                    actor_response = response.content[0].text if response.content else ""
                    actor_component.dialogue_history.append({"role": "assistant", "content": actor_response})
                    
                    self.show_message(f"{actor.name}: {actor_response}", MessageChannel.DIALOGUE, sender=actor)
                except Exception as e:
                    self.logger.error(f"Error in AI response: {str(e)}")
                    self.logger.debug(traceback.format_exc())
                    self.show_message(f"Error: Unable to get NPC response", MessageChannel.SYSTEM, (255, 0, 0))
        except Exception as e:
            self.logger.error(f"Error in dialogue: {str(e)}")
            self.logger.debug(traceback.format_exc())
            self.show_message(f"An error occurred during dialogue", MessageChannel.SYSTEM, (255, 0, 0))

    def start_actor_dialogue(self, actor1, actor2):
        try:
            actor1_component = actor1.get_component(ActorComponent)
            actor2_component = actor2.get_component(ActorComponent)
            current_time = time.time()
            if current_time - actor1_component.last_conversation_time < actor1_component.conversation_cooldown or \
               current_time - actor2_component.last_conversation_time < actor2_component.conversation_cooldown:
                return  # Skip if either actor is on cooldown

            actor1_component.last_conversation_time = current_time
            actor2_component.last_conversation_time = current_time

            player_can_see = self.world.game_map.is_in_fov(int(self.world.player.x), int(self.world.player.y)) and \
                             (self.world.game_map.is_in_fov(int(actor1.x), int(actor1.y)) or 
                              self.world.game_map.is_in_fov(int(actor2.x), int(actor2.y)))

            if player_can_see:
                self.show_message(f"{actor1.name} and {actor2.name} have started a conversation.", MessageChannel.DIALOGUE, sender=actor1)

            relationship_info = actor1.knowledge.get_relationship_story(actor2.name) or ""
             
            system_prompt = f"""You are simulating a conversation between {actor1.name} and {actor2.name} in a dungeon setting.
{actor1.name}'s character: {actor1_component.character_card}
{actor2.name}'s character: {actor2_component.character_card}
Their relationship: {relationship_info}
Environmental knowledge: {actor1.knowledge.get_summary()}
Keep responses brief and in character, typically 1-2 short sentences or 10-15 words. Be concise and direct.
Important: Speak only in dialogue. Do not describe actions, appearances, use asterisks or quotation marks. Simply respond with what the character would say."""

            # Define the initial prompt
            actor_prompt = f"You are {actor1.name}. Start a conversation with {actor2.name} in character, briefly and naturally."
            
            self.logger.info(f"Starting actor dialogue between {actor1.name} and {actor2.name}")
            self.logger.debug(f"Actor1 {actor1.name} character card: {actor1_component.character_card}")
            self.logger.debug(f"Actor2 {actor2.name} character card: {actor2_component.character_card}")
            self.logger.debug(f"Relationship info: {relationship_info}")
            self.logger.info(f"API Request for {actor1.name}:")
            self.logger.info(f"System Prompt: {system_prompt}")
            self.logger.info(f"Actor Prompt: {actor_prompt}")
            
            request_body = {
                "model": "claude-3-5-sonnet-20240620",
                "max_tokens": 100,
                "messages": [{"role": "user", "content": actor_prompt}],
                "system": system_prompt,
                "temperature": 0.7
            }
            
            response = self.anthropic_client.messages.create(**request_body)
            
            self.logger.info(f"API Response for {actor1.name}:")
            self.logger.info(f"Response: {json.dumps(response.model_dump(), indent=2)}")
            
            actor_response = response.content[0].text if response.content else ""

            # Start a new conversation
            conversation = [
                {"role": "user", "content": actor_prompt},
                {"role": "assistant", "content": actor_response}
            ]
            
            if player_can_see:
                self.show_message(f"{actor1.name}: {actor_response}", MessageChannel.DIALOGUE, sender=actor1)

            # Store the conversation for future reference
            actor1_component.current_conversation = conversation
            actor2_component.current_conversation = conversation
            actor1_component.conversation_partner = actor2
            actor2_component.conversation_partner = actor1
            actor1_component.conversation_turns = 1
            actor2_component.conversation_turns = 0

            self.logger.info(f"Conversation started. Turn counts: {actor1.name} = 1, {actor2.name} = 0")

        except Exception as e:
            self.logger.error(f"Error in actor dialogue: {str(e)}")
            self.logger.debug(traceback.format_exc())
            if player_can_see:
                self.show_message(f"An error occurred during actor dialogue", MessageChannel.SYSTEM, (255, 0, 0))

    def continue_actor_dialogue(self, actor1, actor2):
        try:
            actor1_component = actor1.get_component(ActorComponent)
            actor2_component = actor2.get_component(ActorComponent)
            player_can_see = self.world.game_map.is_in_fov(int(self.world.player.x), int(self.world.player.y)) and \
                             (self.world.game_map.is_in_fov(int(actor1.x), int(actor1.y)) or 
                              self.world.game_map.is_in_fov(int(actor2.x), int(actor2.y)))

            conversation = actor1_component.current_conversation
            self.logger.info(f"Continuing actor dialogue between {actor1.name} and {actor2.name}")
            self.logger.debug(f"Current conversation state: {json.dumps(conversation, indent=2)}")

            # Determine which actor should speak next
            current_actor = actor2 if actor1_component.conversation_turns > actor2_component.conversation_turns else actor1
            other_actor = actor1 if current_actor == actor2 else actor2

            self.logger.debug(f"Current speaker: {current_actor.name}, Responding to: {other_actor.name}")
            self.logger.debug(f"Conversation turns - {actor1.name}: {actor1_component.conversation_turns}, {actor2.name}: {actor2_component.conversation_turns}")

            # Check the role of the last message and set the next role accordingly
            last_role = conversation[-1]["role"] if conversation else "assistant"
            next_role = "user" if last_role == "assistant" else "assistant"

            # Add the prompt for the current actor to speak next
            if next_role == "user":
                conversation.append({
                    "role": "user",
                    "content": f"{current_actor.name}, respond to {other_actor.name}'s last statement."
                })

            system_prompt = f"""You are {current_actor.name} in a conversation with {other_actor.name} in a dungeon setting.
{current_actor.name}'s character: {current_actor.get_component(ActorComponent).character_card}
Keep responses brief and in character, typically 1-2 short sentences or 10-15 words. Be concise and direct.
Important: Speak only in dialogue. Do not describe actions, appearances, use asterisks or quotation marks. Simply respond with what the character would say."""

            self.logger.info(f"API Request for {current_actor.name}:")
            self.logger.info(f"System Prompt: {system_prompt}")
            self.logger.info(f"Messages: {json.dumps(conversation, indent=2)}")
            
            request_body = {
                "model": "claude-3-5-sonnet-20240620",
                "max_tokens": 100,
                "messages": conversation,
                "system": system_prompt,
                "temperature": 0.7
            }
            
            response = self.anthropic_client.messages.create(**request_body)
            
            self.logger.info(f"API Response for {current_actor.name}:")
            self.logger.info(f"Response: {json.dumps(response.model_dump(), indent=2)}")
            
            actor_response = response.content[0].text if response.content else ""
            
            if actor_response.strip():  # Only add non-empty responses
                conversation.append({"role": "assistant", "content": actor_response})
                
                if player_can_see:
                    self.show_message(f"{current_actor.name}: {actor_response}", MessageChannel.DIALOGUE, sender=current_actor)

                # Update the conversation for both actors
                actor1_component.current_conversation = conversation
                actor2_component.current_conversation = conversation

                # Increment the conversation turn counter for the current actor
                current_actor.get_component(ActorComponent).conversation_turns += 1

                self.logger.info(f"Updated turn counts: {actor1.name} = {actor1_component.conversation_turns}, {actor2.name} = {actor2_component.conversation_turns}")
                self.logger.info(f"Updated conversation state: {json.dumps(conversation, indent=2)}")
            else:
                self.logger.warning(f"Empty response received for {current_actor.name}. Ending conversation.")
                self.end_actor_conversation(actor1, actor2)

        except Exception as e:
            self.logger.error(f"Error in continuing actor dialogue: {str(e)}")
            self.logger.debug(traceback.format_exc())
            if player_can_see:
                self.show_message(f"An error occurred during actor dialogue", MessageChannel.SYSTEM, (255, 0, 0))
            self.end_actor_conversation(actor1, actor2)

    def end_actor_conversation(self, actor1, actor2):
        actor1_component = actor1.get_component(ActorComponent)
        actor2_component = actor2.get_component(ActorComponent)
        actor1_component.current_conversation = None
        actor2_component.current_conversation = None
        actor1_component.conversation_partner = None
        actor2_component.conversation_partner = None
        actor1_component.conversation_turns = 0
        actor2_component.conversation_turns = 0
        self.logger.info(f"Conversation between {actor1.name} and {actor2.name} has ended.")
 
    def interact(self):
        player_x, player_y = int(self.world.player.x), int(self.world.player.y)
        self.logger.debug(f"Player attempting to interact at position ({player_x}, {player_y})")
        for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:  # Check adjacent tiles
            entity = self.world.get_entity_at(player_x + dx, player_y + dy)
            if isinstance(entity, Actor):
                self.start_dialogue(entity)
                return
        self.show_message("There's no one to interact with.", MessageChannel.SYSTEM, (255, 255, 0))

    def move_player(self, dx, dy):
        new_x = int(self.world.player.x + dx)
        new_y = int(self.world.player.y + dy)
        self.logger.debug(f"Attempting to move player to ({new_x}, {new_y})")
        if self.world.game_map.is_walkable(new_x, new_y):
            self.world.player.x = new_x
            self.world.player.y = new_y
            self.add_message(f"You move to ({new_x}, {new_y})", MessageChannel.MOVEMENT, (200, 200, 200))
            self.fov_recompute = True
            self.logger.debug(f"Player moved to ({new_x}, {new_y})")
        else:
            self.logger.debug(f"Movement to ({new_x}, {new_y}) blocked")
        self.update_camera()  # Update camera position after moving

    def run(self):
        try:
            self.logger.info("Starting game loop")
            while True:
                self.world.update_actor_knowledge()
                self.world.update_actors()
                self.render()
                
                for event in tcod.event.wait():
                    if event.type == "QUIT":
                        raise SystemExit()
                    elif event.type == "KEYDOWN":
                        action_taken = False
                        if event.sym == tcod.event.KeySym.UP:
                            self.move_player(0, -1)
                            action_taken = True
                        elif event.sym == tcod.event.KeySym.DOWN:
                            self.move_player(0, 1)
                            action_taken = True
                        elif event.sym == tcod.event.KeySym.LEFT:
                            self.move_player(-1, 0)
                            action_taken = True
                        elif event.sym == tcod.event.KeySym.RIGHT:
                            self.move_player(1, 0)
                            action_taken = True
                        elif event.sym == tcod.event.KeySym.PERIOD:
                            self.add_message("You wait for a moment.", MessageChannel.SYSTEM)
                            action_taken = True
                        elif event.sym == tcod.event.KeySym.i:
                            self.interact()
                        elif event.sym == tcod.event.KeySym.q:
                            raise SystemExit()
                        
                        if action_taken:
                            self.logger.debug("Updating actor knowledge and positions")
                            self.world.update_actor_knowledge()
                            self.world.update_actors()
                            
                            self.logger.debug("Checking for potential actor interactions")
                            potential_interactions = self.world.get_potential_actor_interactions()
                            for actor1, actor2 in potential_interactions:
                                if not actor1.get_component(ActorComponent).current_conversation and random.random() < 0.3:  # 30% chance to start a conversation
                                    self.start_actor_dialogue(actor1, actor2)
                            
                            # Continue actor dialogues after player action
                            for actor1, actor2 in potential_interactions:
                                if actor1.get_component(ActorComponent).current_conversation and actor1.get_component(ActorComponent).conversation_turns < 3:
                                    self.continue_actor_dialogue(actor1, actor2)
                                    break  # Only continue one conversation per turn
                        self.logger.debug("Game loop iteration completed")
        except Exception as e:
            self.logger.error(f"Error in game loop: {str(e)}")
            self.logger.debug(traceback.format_exc())
            self.show_message(f"An error occurred: {str(e)}", MessageChannel.SYSTEM, (255, 0, 0))

def main():
    setup_logging()
    logger = logging.getLogger(__name__)
    try:
        game = Game(None)  # Create Game instance with None as world
        world = World(80, 38, game)  # Pass game to World
        game.world = world  # Set the world for the game

        # Find a valid starting position for the player
        player_x, player_y = world.game_map.get_random_walkable_position()
        player = Player(player_x, player_y)
        world.add_entity(player)
        
        # Place actors in random positions
        for i in range(2):  # Place 2 actors
            actor_x, actor_y = world.game_map.get_random_walkable_position()
            if i == 0:
                actor = Actor(actor_x, actor_y, "Wise Old Man", "wise_old_man")
            else:
                actor = Actor(actor_x, actor_y, "Mysterious Stranger", "mysterious_stranger")
            world.add_entity(actor)

        world.generate_actor_relationships()

        game.run()
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        logger.debug(traceback.format_exc())
        print(f"A critical error occurred. Please check the game.log file for details.")

if __name__ == "__main__":
    main()
