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
        game = Game(None)
        game.run()
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        logger.debug(traceback.format_exc())
        print(f"A critical error occurred. Please check the game.log file for details.")

if __name__ == "__main__":
    main()
