import random
import tcod
from components.ActorComponent import ActorComponent
from systems.MessageSystem import MessageChannel
from entities.Actor import Actor

class GameLoopSystem:
    def __init__(self, game):
        self.game = game

    def run(self):
        self.game.logger.info("Starting game loop")
        while True:
            self.game.render_system.render()
            
            if self.game.game_over:
                self.handle_game_over()
                break
            
            action_taken = self.game.input_system.handle_input()
            
            if action_taken:
                self.update_game_state()
                self.handle_actor_interactions()
            
            self.game.logger.debug("Game loop iteration completed")

    def handle_game_over(self):
        self.game.show_message("Game Over. Press any key to return to main menu.", MessageChannel.SYSTEM)
        self.game.render_system.render()  # Ensure the message is displayed
        while True:
            for event in tcod.event.wait():
                if event.type == "QUIT":
                    raise SystemExit()
                elif event.type == "KEYDOWN":
                    self.game.main_menu_system.handle_main_menu()
                    return

    def update_game_state(self):
        self.game.logger.debug("Updating actor knowledge and positions")
        self.game.world.actor_knowledge_system.update(self.game.world.entities, self.game.world.game_map)
        self.game.world.update_actors()

    def handle_actor_interactions(self):
        self.game.logger.debug("Checking for potential actor interactions")
        potential_interactions = self.game.world.get_potential_actor_interactions()
        for actor1, actor2 in potential_interactions:
            if not self.game.disable_actor_dialogue:  # Add this condition
                if not actor1.get_component(ActorComponent).current_conversation and random.random() < 0.05:
                    self.game.dialogue_system.start_actor_dialogue(actor1, actor2)
        
        for actor1, actor2 in potential_interactions:
            if not self.game.disable_actor_dialogue:  # Add this condition
                if actor1.get_component(ActorComponent).current_conversation and actor1.get_component(ActorComponent).conversation_turns < 3:
                    self.game.dialogue_system.continue_actor_dialogue(actor1, actor2)
                    break
