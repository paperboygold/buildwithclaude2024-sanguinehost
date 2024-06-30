import logging
import traceback
from utils.logging import setup_logging
from world import World
from game import Game
from entities.Player import Player
from entities.Actor import Actor

def main():
    setup_logging()
    logger = logging.getLogger(__name__)
    try:
        game = Game(None)  # Create Game instance with None as world
        world = World(80, 38, game)  # Pass game to World
        game.setup_world(world)  # Set up the world and initialize the render system

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

        world.actor_knowledge_system.generate_initial_relationships(world.entities)

        game.run()
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        logger.debug(traceback.format_exc())
        print(f"A critical error occurred. Please check the game.log file for details.")

if __name__ == "__main__":
    main()
