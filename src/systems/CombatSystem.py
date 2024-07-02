import logging
import random
from ecs.ecs import System
from components.FighterComponent import FighterComponent
from systems.MessageSystem import MessageChannel
from entities.Actor import Actor
from components.ActorComponent import ActorComponent, ActorState

class CombatSystem(System):
    def __init__(self, game):
        self.game = game
        self.logger = logging.getLogger(__name__)
        self.aggressors = {}  # Dictionary to keep track of aggressors
        self.combat_participants = set()  # Set to keep track of actors in combat

    def attack(self, attacker, target):
        attacker_fighter = attacker.get_component(FighterComponent)
        target_fighter = target.get_component(FighterComponent)

        damage = max(0, attacker_fighter.power - target_fighter.defense)

        if damage > 0:
            target_fighter.hp -= damage
            self.logger.info(f"{attacker.name} attacks {target.name} for {damage} damage")
            self.game.show_message(f"{attacker.name} attacks {target.name} for {damage} damage!", MessageChannel.COMBAT)
            
            # Record the attacker as the aggressor for this target
            self.aggressors[target] = attacker
            self.logger.debug(f"Aggressor recorded: {attacker.name} is now the aggressor for {target.name}")

            # Handle target's response
            if isinstance(target, Actor) and attacker not in target.get_component(ActorComponent).hostile_towards:
                # Check if the attacker is already hostile towards the target
                if target not in attacker.get_component(ActorComponent).hostile_towards:
                    self.logger.info(f"Combat response: {target.name} is becoming hostile towards {attacker.name}")
                    target.become_hostile(attacker, self.game)
            
            # Add both attacker and target to combat participants
            self.combat_participants.add(attacker)
            self.combat_participants.add(target)

            # Handle witnesses only for the first attack
            if len(self.combat_participants) == 2:
                self.handle_attack_witnesses(attacker, target)

            if target_fighter.hp <= 0:
                self.kill(target)
                return True  # Return True if the target was killed
        else:
            self.logger.info(f"{attacker.name}'s attack on {target.name} was ineffective")
            self.game.show_message(f"{attacker.name}'s attack on {target.name} is ineffective!", MessageChannel.COMBAT)
        return False  # Return False if the target survived

    def handle_attack_witnesses(self, attacker, target):
        self.logger.info(f"Checking for witnesses to the attack between {attacker.name} and {target.name}")
        for entity in self.game.world.entities:
            if (isinstance(entity, Actor) and 
                entity != attacker and 
                entity != target and
                attacker not in entity.get_component(ActorComponent).hostile_towards and
                self.game.world.game_map.is_in_fov(int(entity.x), int(entity.y)) and 
                (self.game.world.game_map.is_in_fov(int(attacker.x), int(attacker.y)) or 
                 self.game.world.game_map.is_in_fov(int(target.x), int(target.y)))):
                self.handle_witness_reaction(entity, attacker, target)

    def handle_witness_reaction(self, witness, attacker, target):
        if attacker not in witness.get_component(ActorComponent).hostile_towards:
            # Check if the attacker is attacking an enemy of the witness
            if target in witness.get_component(ActorComponent).hostile_towards:
                self.witness_decides_to_intervene(witness, attacker, target, help_target=False)
            elif witness.aggression_type == "peaceful":
                self.witness_decides_to_intervene(witness, attacker, target, help_target=True)
            elif witness.aggression_type == "neutral" and (target.aggression_type == "peaceful" or random.random() < 0.5):
                self.witness_decides_to_intervene(witness, attacker, target, help_target=True)
            else:
                self.game.logger.info(f"{witness.name} witnesses the attack but chooses not to intervene")

    def witness_decides_to_intervene(self, witness, attacker, target, help_target):
        if help_target:
            witness.become_hostile(attacker, self.game)
            witness.get_component(ActorComponent).target = attacker  # Set the target explicitly
            self.game.logger.info(f"{witness.name} decides to intervene against {attacker.name}")
            self.game.show_message(f"{witness.name} decides to intervene against {attacker.name}", MessageChannel.COMBAT)
        else:
            witness.become_hostile(target, self.game)
            witness.get_component(ActorComponent).target = target  # Set the target explicitly
            self.game.logger.info(f"{witness.name} decides to help {attacker.name} against {target.name}")
            self.game.show_message(f"{witness.name} decides to help {attacker.name} against {target.name}", MessageChannel.COMBAT)
        self.combat_participants.add(witness)

    def get_aggressor(self, target):
        return self.aggressors.get(target)

    def clear_aggressor(self, target):
        if target in self.aggressors:
            del self.aggressors[target]

    def kill(self, target):
        self.logger.info(f"Combat result: {target.name} is defeated")
        self.game.show_message(f"{target.name.capitalize()} is defeated!", MessageChannel.COMBAT)
        if target == self.game.world.player:
            self.logger.info("Game Over: Player has been defeated")
            self.game.show_message("Game Over! Press any key to return to the main menu.", MessageChannel.SYSTEM)
            self.game.game_over = True
        else:
            self.logger.info(f"Removing defeated entity: {target.name}")
            self.game.world.entities.remove(target)
            # Only call calm_down for non-aggressive actors
            if isinstance(target, Actor) and target.aggression_type != "hostile":
                self.logger.info(f"Reassessing hostility for other actors due to defeat of {target.name}")
                for entity in self.game.world.entities:
                    if isinstance(entity, Actor) and entity.aggression_type == "hostile":
                        self.logger.debug(f"{entity.name} is reassessing hostility after defeat of {target.name}")
                        entity.reassess_hostility(self.game, target)
        self.clear_aggressor(target)
        self.logger.debug(f"Aggressor cleared for defeated entity: {target.name}")
        self.end_combat(target)

    def end_combat(self, defeated_entity):
        self.combat_participants.remove(defeated_entity)
        if len(self.combat_participants) <= 1:
            self.game.logger.info("Combat has ended")
            self.game.show_message("The fighting has stopped.", MessageChannel.COMBAT)
            self.reset_hostility()
            self.combat_participants.clear()

    def reset_hostility(self):
        for entity in self.combat_participants:
            if isinstance(entity, Actor):
                entity.reset_hostility(self.game)