import logging
import traceback
from utils.logging import setup_logging
from world import World
from game import Game
from entities.Player import Player
from entities.Actor import Actor
from utils.mapgen import MapType

def get_unique_walkable_positions(world, count):
    positions = set()
    while len(positions) < count:
        x, y = world.game_map.get_random_walkable_position()
        if (x, y) not in positions:
            positions.add((x, y))
    return list(positions)

def main():
    setup_logging()
    logger = logging.getLogger(__name__)
    try:
        game = Game(None)  # Create Game instance with None as world
        

        
        map_type = MapType.BSP
        
        world = World(80, 38, game, map_type)  # Pass game and map_type to World
        game.setup_world(world)  # Set up the world and initialize the render system

        # Find a valid starting position for the player
        player_x, player_y = world.game_map.get_random_walkable_position()
        player = Player(player_x, player_y)
        world.add_entity(player)
        
        # Get unique positions for actors
        actor_positions = get_unique_walkable_positions(world, 2)  # Get 2 unique positions

        # Place actors in unique positions
        actors = [
            Actor(actor_positions[0][0], actor_positions[0][1], "Wise Old Man", "wise_old_man"),
            Actor(actor_positions[1][0], actor_positions[1][1], "Mysterious Stranger", "mysterious_stranger")
        ]
        for actor in actors:
            world.add_entity(actor)

        world.actor_knowledge_system.generate_initial_relationships(world.entities)

        game.run()
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        logger.debug(traceback.format_exc())
        print(f"A critical error occurred. Please check the game.log file for details.")

if __name__ == "__main__":
    main()
