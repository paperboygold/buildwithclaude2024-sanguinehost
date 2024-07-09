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

    def add_combat_memory(self, actor, memory):
        if isinstance(actor, Actor):
            actor.knowledge.add_combat_memory(memory)
            self.logger.info(f"Added combat memory for {actor.name}: {memory}")

    def attack(self, attacker, target):
        attacker_fighter = attacker.get_component(FighterComponent)
        target_fighter = target.get_component(FighterComponent)

        # Check if the target is actively hostile or attacking
        target_is_hostile = target.is_hostile(attacker) if isinstance(target, Actor) else False
        target_is_attacking = target == self.aggressors.get(attacker)

        # Check relationship before allowing attack
        relationship_value = attacker.knowledge.relationships.get(target.name, {"value": 0})["value"]
        
        # If the attacker is the player, prompt for confirmation only for non-hostile targets
        if attacker == self.game.world.player and not target_is_hostile:
            if not self.game.player_system.confirm_attack(target):
                self.logger.info(f"Player chose not to attack {target.name}.")
                return False
        elif isinstance(attacker, Actor):
            actor_component = attacker.get_component(ActorComponent)
            # Allow attack if the target is hostile, attacking, or if the attacker is hostile towards the target
            if not (target_is_hostile or target_is_attacking or target in actor_component.hostile_towards or attacker.aggression_type == "hostile"):
                if relationship_value > 0:
                    self.logger.info(f"{attacker.name} refuses to attack {target.name} due to positive relationship.")
                    self.game.show_message(f"{attacker.name} refuses to attack {target.name}!", MessageChannel.COMBAT)
                    return False
                elif attacker.aggression_type != "hostile" and attacker.aggression_type != "peaceful":
                    self.logger.info(f"{attacker.name} is not hostile and refuses to attack {target.name}.")
                    self.game.show_message(f"{attacker.name} refuses to attack {target.name}!", MessageChannel.COMBAT)
                    return False

        damage = max(0, attacker_fighter.power - target_fighter.defense)

        if damage > 0:
            target_fighter.hp -= damage
            self.logger.info(f"{attacker.name} attacks {target.name} for {damage} damage")
            self.game.show_message(f"{attacker.name} attacks {target.name} for {damage} damage!", MessageChannel.COMBAT)
            
            # Record the attacker as the aggressor for this target
            self.aggressors[target] = attacker
            self.logger.debug(f"Aggressor recorded: {attacker.name} is now the aggressor for {target.name}")

            # Handle target's response
            if isinstance(target, Actor):
                target_relationship = target.knowledge.relationships.get(attacker.name, {"value": 0})["value"]
                if target_relationship <= 0 or target.aggression_type != "peaceful":
                    if attacker not in target.get_component(ActorComponent).hostile_towards:
                        self.logger.info(f"Combat response: {target.name} is becoming hostile towards {attacker.name}")
                        target.become_hostile(attacker, self.game)
                    target.get_component(ActorComponent).target = attacker
                    target.get_component(ActorComponent).state = ActorState.AGGRESSIVE
            
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
        
        # Update relationships after combat
        if target_fighter.is_dead():
            self.game.dialogue_system.relationship_manager.update_relationship_after_combat(attacker, target, "victory")
        else:
            self.game.dialogue_system.relationship_manager.update_relationship_after_combat(attacker, target, "defeat")
        
        return False  # Return False if the target survived

    def handle_attack_witnesses(self, attacker, target):
        self.logger.info(f"Checking for witnesses to the attack between {attacker.name} and {target.name}")
        for entity in self.game.world.entities:
            if (isinstance(entity, Actor) and 
                entity != attacker and 
                entity != target and
                self.game.world.game_map.is_in_fov(int(entity.x), int(entity.y)) and 
                (self.game.world.game_map.is_in_fov(int(attacker.x), int(attacker.y)) or 
                 self.game.world.game_map.is_in_fov(int(target.x), int(target.y)))):
                self.handle_witness_reaction(entity, attacker, target)

    def handle_witness_reaction(self, witness, attacker, target):
        attacker_relationship = witness.knowledge.relationships.get(attacker.name, {"value": 0})["value"]
        target_relationship = witness.knowledge.relationships.get(target.name, {"value": 0})["value"]
        
        witness_aggression_type = witness.get_component(ActorComponent).character_card['aggression_type']
        
        if witness_aggression_type == "peaceful":
            # Peaceful types are more likely to intervene against aggressors
            if self.game.dialogue_system.relationship_manager.will_intervene_in_combat(witness, attacker, target):
                witness.become_hostile(attacker, self.game)
                witness.get_component(ActorComponent).target = attacker
                self.game.logger.info(f"{witness.name}, being peaceful, decides to intervene against {attacker.name}")
                self.game.show_message(f"{witness.name} decides to intervene against {attacker.name}", MessageChannel.COMBAT)
        elif target_relationship > 0 and attacker_relationship <= 0:
            # Other types intervene based on relationships
            if self.game.dialogue_system.relationship_manager.will_intervene_in_combat(witness, attacker, target):
                witness.become_hostile(attacker, self.game)
                witness.get_component(ActorComponent).target = attacker
                self.game.logger.info(f"{witness.name} decides to intervene against {attacker.name}")
                self.game.show_message(f"{witness.name} decides to intervene against {attacker.name}", MessageChannel.COMBAT)
        elif attacker_relationship > 0 and target_relationship <= 0:
            self.game.logger.info(f"{witness.name} supports {attacker.name}'s actions")
        else:
            self.game.logger.info(f"{witness.name} witnesses the attack but chooses not to intervene")
        
        self.combat_participants.add(witness)

    def get_aggressor(self, target):
        return self.aggressors.get(target)

    def clear_aggressor(self, target):
        if target in self.aggressors:
            del self.aggressors[target]

    def kill(self, target):
        self.logger.info(f"Combat result: {target.name} is defeated")
        self.game.show_message(f"{target.name.capitalize()} is defeated!", MessageChannel.COMBAT)
        
        # Add combat memory for all participants
        for participant in self.combat_participants:
            if participant != target:
                memory = f"Defeated {target.name} in combat"
                self.add_combat_memory(participant, memory)
        
        if target == self.game.world.player:
            self.logger.info("Game Over: Player has been defeated")
            self.game.show_message("Game Over! Press any key to return to the main menu.", MessageChannel.SYSTEM)
            self.game.game_over = True
        else:
            self.logger.info(f"Removing defeated entity: {target.name}")
            self.update_defeated_entity_position(target)
            self.game.world.entities.remove(target)
            self.clear_defeated_entity_as_target(target)
            
            # Add combat memory for the defeated entity
            memory = f"Was defeated in combat"
            self.add_combat_memory(target, memory)
            
            if isinstance(target, Actor) and target.aggression_type != "hostile":
                self.logger.info(f"Reassessing hostility for other actors due to defeat of {target.name}")
                for entity in self.game.world.entities:
                    if isinstance(entity, Actor) and entity.aggression_type == "hostile":
                        self.logger.debug(f"{entity.name} is reassessing hostility after defeat of {target.name}")
                        entity.reassess_hostility(self.game, target)
            
            # Update knowledge only for actors who can see the target
            for entity in self.game.world.entities:
                if isinstance(entity, Actor) and self.game.world.game_map.is_in_fov(int(entity.x), int(entity.y)) and self.game.world.game_map.is_in_fov(int(target.x), int(target.y)):
                    entity.knowledge.update_actor_info(
                        target.name,
                        is_dead=True,
                        last_seen_position=(target.x, target.y)
                    )
                    self.logger.debug(f"Updated {entity.name}'s knowledge about {target.name}'s defeat")
            
            self.clear_aggressor(target)
            self.logger.debug(f"Aggressor cleared for defeated entity: {target.name}")
            self.end_combat(target)
            # Reset state for all entities that were targeting the defeated entity
            for entity in self.game.world.entities:
                if isinstance(entity, Actor):
                    actor_component = entity.get_component(ActorComponent)
                    if actor_component.target == target:
                        actor_component.target = None
                        actor_component.state = ActorState.IDLE
                        self.logger.info(f"{entity.name} lost its target and returned to IDLE state")

    def clear_defeated_entity_as_target(self, defeated_entity):
        for entity in self.game.world.entities:
            if isinstance(entity, Actor):
                actor_component = entity.get_component(ActorComponent)
                if actor_component.target == defeated_entity:
                    actor_component.target = None
                    self.game.logger.debug(f"{entity.name} cleared their target as it was defeated")

    def end_combat(self, defeated_entity):
        self.combat_participants.remove(defeated_entity)
        if len(self.combat_participants) <= 1:
            self.game.logger.info("Combat has ended")
            self.game.show_message("The fighting has stopped.", MessageChannel.COMBAT)
            self.reset_hostility()
            self.combat_participants.clear()
            # Reset state for all remaining participants, except hostile actors
            for entity in self.combat_participants:
                if isinstance(entity, Actor):
                    actor_component = entity.get_component(ActorComponent)
                    if entity.aggression_type != "hostile":
                        actor_component.state = ActorState.IDLE
                    actor_component.target = None

    def reset_hostility(self):
        for entity in self.combat_participants:
            if isinstance(entity, Actor):
                actor_component = entity.get_component(ActorComponent)
                if entity.aggression_type != "hostile":
                    actor_component.hostile_towards.clear()
                    actor_component.state = ActorState.IDLE
                actor_component.target = None
                self.game.logger.info(f"{entity.name} has reset their hostility and returned to {'IDLE' if entity.aggression_type != 'hostile' else 'AGGRESSIVE'} state")

    def update_defeated_entity_position(self, entity):
        self.game.world.actor_knowledge_system.defeated_entity_positions[entity.name] = (entity.x, entity.y)