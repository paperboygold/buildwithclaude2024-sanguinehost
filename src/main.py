import logging
import traceback
from utils.logging import setup_logging
from game import Game

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
        while True:
            game = Game(None)
            game.main_menu_system.handle_main_menu()
            
            while not game.is_game_over():
                game.loop_system.run()
            
            logger.info("Game over. Returning to main menu.")
            
            # Ask the player if they want to play again
            play_again = game.main_menu_system.show_play_again_menu()
            if not play_again:
                break
            
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        logger.debug(traceback.format_exc())
        print(f"A critical error occurred. Please check the game.log file for details.")

if __name__ == "__main__":
    main()
