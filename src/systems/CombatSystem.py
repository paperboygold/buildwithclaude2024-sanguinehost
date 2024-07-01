import logging

from ecs.ecs import System
from components.FighterComponent import FighterComponent
from systems.MessageSystem import MessageChannel
from entities.Actor import Actor
from components.ActorComponent import ActorComponent, ActorState

class CombatSystem(System):
    def __init__(self, game):
        self.game = game
        self.logger = logging.getLogger(__name__)

    def attack(self, attacker, target):
        attacker_fighter = attacker.get_component(FighterComponent)
        target_fighter = target.get_component(FighterComponent)

        damage = attacker_fighter.power - target_fighter.defense

        if damage > 0:
            target_fighter.hp -= damage
            self.logger.info(f"{attacker.name} attacks {target.name} for {damage} hit points")
            self.game.show_message(
                f"{attacker.name.capitalize()} attacks {target.name} for {damage} hit points.",
                MessageChannel.COMBAT
            )
            
            # Handle target's response
            if isinstance(target, Actor):
                target.become_hostile(attacker, self.game)
            
            # Handle witnesses
            self.handle_attack_witnesses(attacker, target)

            if target_fighter.hp <= 0:
                self.kill(target)
                return True  # Return True if the target was killed
        else:
            self.logger.info(f"{attacker.name} attacks {target.name} but does no damage")
            self.game.show_message(
                f"{attacker.name.capitalize()} attacks {target.name} but does no damage.",
                MessageChannel.COMBAT
            )
        return False  # Return False if the target survived

    def handle_attack_witnesses(self, attacker, target):
        for entity in self.game.world.entities:
            if isinstance(entity, Actor) and entity != attacker and entity != target:
                if self.game.world.game_map.is_in_fov(int(entity.x), int(entity.y)) and \
                   (self.game.world.game_map.is_in_fov(int(attacker.x), int(attacker.y)) or 
                    self.game.world.game_map.is_in_fov(int(target.x), int(target.y))):
                    if entity.aggression_type != "hostile" and target.aggression_type != "hostile":
                        self.logger.info(f"{entity.name} witnesses attack from {attacker.name} on {target.name}")
                        entity.witness_attack(attacker, target, self.game)

    def kill(self, target):
        self.logger.info(f"{target.name} is defeated")
        self.game.show_message(f"{target.name.capitalize()} is defeated!", MessageChannel.COMBAT)
        if target == self.game.world.player:
            self.logger.info("Game Over")
            self.game.show_message("Game Over! Press any key to return to the main menu.", MessageChannel.SYSTEM)
            self.game.game_over = True
        else:
            self.game.world.entities.remove(target)
            # Only call calm_down for non-aggressive actors
            if isinstance(target, Actor) and target.aggression_type != "hostile":
                for entity in self.game.world.entities:
                    if isinstance(entity, Actor) and entity.aggression_type == "hostile":
                        entity.reassess_hostility(self.game, target)
