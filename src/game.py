import anthropic
import logging
import traceback
from utils.load_api_key import load_api_key
from systems.GameInitializationSystem import GameInitializationSystem
from systems.GameLoopSystem import GameLoopSystem
from systems.MessageSystem import MessageChannel
from entities.Actor import Actor
import os
from systems.MainMenuSystem import MainMenuSystem
from utils.mapgen import MapType
from world import World
from entities.Player import Player
import shelve
import tcod
from systems.CombatSystem import CombatSystem
from systems.PlayerSystem import PlayerSystem
from systems.DialogueSystem import DialogueSystem
from systems.InputSystem import InputSystem
from data.character_cards import get_character_card

class Game:
    def __init__(self, world):
        self.logger = logging.getLogger(__name__)
        try:
            self.world = world
            if self.world:
                self.world.game = self
            api_key = load_api_key()
            if not api_key:
                raise ValueError("No API key provided")
            self.anthropic_client = anthropic.Anthropic(api_key=api_key)
            
            self.init_system = GameInitializationSystem(self)
            self.init_system.initialize_all()
            self.render_system = self.init_system.game.render_system  # Set render_system after initializing all systems
            
            self.loop_system = GameLoopSystem(self)
            self.main_menu_system = MainMenuSystem(self)
            self.combat_system = CombatSystem(self)
            self.game_over = False
            self.disable_actor_dialogue = False  # For toggling dialogue in-game
            self.disable_dialogue_system = False  # For disabling dialogue system at game start

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

    def new_game(self, single_room=True):
        # Create a new world
        self.world = World(80, 38, self, MapType.DUNGEON, single_room=single_room)
        self.setup_world(self.world)
        
        # Create and add the player
        player_x, player_y = self.world.game_map.get_random_walkable_position()
        self.world.player = Player(player_x, player_y)
        self.world.add_entity(self.world.player)
        
        # Disable dialogue system at game start
        self.disable_dialogue_system = False
        
        # Add NPCs and generate relationships
        self.add_npcs()
        
        self.init_system.initialize_all()
        self.render_system = self.init_system.game.render_system
        self.fov_recompute = True
        
        self.show_message("Welcome to Sanguine Host!", MessageChannel.SYSTEM)
        self.game_over = False

    @staticmethod
    def get_unique_walkable_positions(world, count):
        positions = set()
        while len(positions) < count:
            x, y = world.game_map.get_random_walkable_position()
            if (x, y) not in positions:
                positions.add((x, y))
        return list(positions)

    def add_npcs(self):
        npc_types = ['wise_old_man', 'mysterious_stranger', 'aggressive_monster']
        positions = self.get_unique_walkable_positions(self.world, len(npc_types))
        for i, npc_type in enumerate(npc_types):
            x, y = positions[i]
            character_card = get_character_card(npc_type)
            name = character_card['name']
            npc = Actor(x, y, name, npc_type)
            self.world.entities.append(npc)

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

    def reset_game_state(self):
        self.game_over = False
        self.world = None
        self.fov_recompute = True
        
        # Reset systems
        self.init_system = GameInitializationSystem(self)
        self.init_system.initialize_all()
        self.render_system = self.init_system.game.render_system
        self.message_system.clear_messages()
        self.combat_system = CombatSystem(self)
        self.loop_system = GameLoopSystem(self)
        self.player_system = PlayerSystem(self)
        self.dialogue_system = DialogueSystem(self)
        self.input_system = InputSystem(self)
        
        # Reset game dimensions and consoles
        self.init_system.initialize_game_dimensions()
        self.init_system.initialize_consoles()
        
        # Reset camera and FOV
        self.camera_x = 0
        self.camera_y = 0
        self.fov_radius = 10
        
        # Clear any existing entities
        if hasattr(self, 'world') and self.world:
            self.world.entities.clear()
        
        self.show_message("Game reset. Returning to main menu.", MessageChannel.SYSTEM)

    def initialize_game_dimensions(self):
        self.width = 80
        self.height = 50
        self.tile_size = 16
        self.pixel_width = self.width * self.tile_size
        self.pixel_height = self.height * self.tile_size
        self.game_area_height = 38
        self.dialogue_height = 12

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

    def is_game_over(self):
        return self.game_over

