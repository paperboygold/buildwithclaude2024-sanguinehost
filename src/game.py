import anthropic
import logging
import traceback
from utils.load_api_key import load_api_key
from systems.GameInitializationSystem import GameInitializationSystem
from systems.GameLoopSystem import GameLoopSystem
from systems.MessageSystem import MessageChannel
from entities.Actor import Actor
import pickle
import os
from systems.MainMenuSystem import MainMenuSystem
from utils.mapgen import MapType
from world import World
from entities.Player import Player
import shelve


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
            self.render_system = self.init_system.game.render_system  # Set render_system after initializing all systems
            
            self.loop_system = GameLoopSystem(self)
            self.main_menu_system = MainMenuSystem(self)

        except Exception as e:
            self.logger.error(f"Error initializing game: {str(e)}")
            self.logger.debug(traceback.format_exc())
            raise

    def setup_world(self, world):
        self.world = world
        self.init_system.initialize_render_system()
        self.fov_recompute = True

    def show_message(self, text, channel=MessageChannel.SYSTEM, color=None, sender=None):
        if sender and isinstance(sender, Actor):
            color = sender.color
        elif channel == MessageChannel.DIALOGUE and not color:
            color = (0, 255, 255)
        elif not color:
            color = (255, 255, 255)
        self.message_system.add_message(text, channel, color)
        if hasattr(self, 'render_system') and self.render_system and self.world and self.world.game_map:
            self.render_system.render()
        else:
            self.logger.warning(f"Unable to render message: {text}")

    def interact(self):
        return self.player_system.interact()

    def move_player(self, dx, dy):
        return self.player_system.move_player(dx, dy)

    def new_game(self):
        # Reset the game state for a new game
        self.world = World(80, 38, self, MapType.CAVE)
        self.setup_world(self.world)
        
        # Create and add the player
        player_x, player_y = self.world.game_map.get_random_walkable_position()
        self.world.player = Player(player_x, player_y)
        self.world.add_entity(self.world.player)
        
        # Add some NPCs
        self.add_npcs()
        
        self.show_message("Welcome to Sanguine Host!", MessageChannel.SYSTEM)

    def add_npcs(self):
        from data.character_cards import get_character_card
        
        npc_types = ["wise_old_man", "mysterious_stranger", "aggressive_monster"]
        for npc_type in npc_types:
            x, y = self.world.game_map.get_random_walkable_position()
            name = get_character_card(npc_type).split('\n')[1].split(': ')[1]  # Extract name from character card
            aggressive = npc_type == "aggressive_monster"
            npc = Actor(x, y, name, npc_type, aggressive=aggressive)
            self.world.add_entity(npc)

        # Generate initial relationships between NPCs
        self.world.actor_knowledge_system.generate_initial_relationships(self.world.entities)

    def save_game(self):
        with shelve.open('savegame', 'n') as file:
            file['world'] = self.world.to_picklable()
            file['player_index'] = self.world.entities.index(self.world.player)
        self.show_message("Game saved.", MessageChannel.SYSTEM)

    def load_game(self):
        if os.path.exists('savegame') or os.path.exists('savegame.db'):
            with shelve.open('savegame', 'r') as file:
                loaded_world = file['world']
                player_index = file['player_index']
                self.world = World(loaded_world.width, loaded_world.height, self, loaded_world.map_type)
                self.world.game_map = loaded_world.game_map
                self.world.entities = loaded_world.entities
                self.world.player = loaded_world.player
                self.world.entities.insert(player_index, self.world.player)
            self.setup_world(self.world)
            self.show_message("Game loaded.", MessageChannel.SYSTEM)
        else:
            self.new_game()  # Start a new game if no saved game is found
            self.show_message("No saved game found. Starting a new game.", MessageChannel.SYSTEM)

    def run(self):
        try:
            self.main_menu_system.handle_main_menu()
            self.loop_system.run()
        except Exception as e:
            self.logger.error(f"Error in game loop: {str(e)}")
            self.logger.debug(traceback.format_exc())
            print(f"An error occurred: {str(e)}. Please check the game.log file for details.")
