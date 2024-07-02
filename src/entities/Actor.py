from ecs.ecs import Entity
from components.ActorComponent import ActorComponent, ActorState
from components.KnowledgeComponent import KnowledgeComponent
from components.PositionComponent import PositionComponent
from components.RenderComponent import RenderComponent
from utils.dijkstra_map import DijkstraMap
from data.character_cards import character_cards
import random
import time
from components.FighterComponent import FighterComponent
from systems.MessageSystem import MessageChannel
from entities.Player import Player
import logging
import numpy as np
import tcod

def get_character_card(character_card_key, default=None):
    return character_cards.get(character_card_key, default)

class Actor(Entity):
    def __init__(self, x, y, name, character_card_key):
        super().__init__()
        self.character_card = get_character_card(character_card_key)
        if not self.character_card:
            raise ValueError(f"No character card found for key: {character_card_key}")
        
        self.add_component(PositionComponent(x, y))
        self.add_component(RenderComponent('N', name))
        self.add_component(ActorComponent(name, self.character_card))
        self.add_component(KnowledgeComponent())
        self.add_component(FighterComponent(
            self.character_card['health'],
            self.character_card['defense'],
            self.character_card['power']
        ))
        self.color = (random.randint(100, 255), random.randint(100, 255), random.randint(100, 255))
        self.aggression_type = self.character_card['aggression_type']
        self.target_preference = self.character_card['target_preference']
        self.logger = logging.getLogger(__name__)

    @property
    def x(self):
        return self.get_component(PositionComponent).x

    @x.setter
    def x(self, value):
        self.get_component(PositionComponent).x = value

    @property
    def y(self):
        return self.get_component(PositionComponent).y

    @y.setter
    def y(self, value):
        self.get_component(PositionComponent).y = value

    @property
    def char(self):
        return self.get_component(RenderComponent).char

    @char.setter
    def char(self, value):
        self.get_component(RenderComponent).char = value

    @property
    def name(self):
        return self.get_component(RenderComponent).name

    @name.setter
    def name(self, value):
        self.get_component(RenderComponent).name = value

    @property
    def state(self):
        return self.get_component(ActorComponent).state

    @state.setter
    def state(self, value):
        self.get_component(ActorComponent).state = value

    @property
    def knowledge(self):
        return self.get_component(KnowledgeComponent)

    def become_hostile(self, target, game):
        actor_component = self.get_component(ActorComponent)
        if target not in actor_component.hostile_towards:
            actor_component.aggression_type = "hostile"
            actor_component.state = ActorState.AGGRESSIVE
            actor_component.aggressive_targets.add(target)
            actor_component.hostile_towards.add(target)
            self.logger.info(f"{self.name} has become hostile towards {target.name}")
            game.show_message(f"{self.name} becomes hostile towards {target.name}!", MessageChannel.COMBAT)

    def reassess_hostility(self, game, target=None):
        actor_component = self.get_component(ActorComponent)
        if target:
            actor_component.aggressive_targets.discard(target)
        
        if not actor_component.aggressive_targets:
            actor_component.aggression_type = self.character_card['aggression_type']
            actor_component.state = ActorState.IDLE
            actor_component.target = None
            game.show_message(f"{self.name} returns to their normal state.", MessageChannel.COMBAT)

    def update(self, game_map, player, game):
        actor_component = self.get_component(ActorComponent)
        current_time = time.time()
        if current_time - actor_component.last_move_time < actor_component.move_delay:
            return

        if self.aggression_type == "hostile" or actor_component.state == ActorState.AGGRESSIVE:
            # Check if the aggressive actor has a target
            self.find_nearest_target_in_sight(game)
            if actor_component.target:
                self.update_aggressive_behavior(game_map, player, game, current_time)
            else:
                # If no target, use Dijkstra map for movement
                self.move_using_dijkstra(game_map, game, current_time)
        else:
            self.update_non_aggressive_behavior(game_map, current_time, game.world.entities)

    def update_aggressive_behavior(self, game_map, player, game, current_time):
        actor_component = self.get_component(ActorComponent)
        
        # Find the nearest target in line of sight
        self.find_nearest_target_in_sight(game)
        
        if actor_component.target:
            # Check if the target has an aggressor
            aggressor = game.combat_system.get_aggressor(actor_component.target)
            if aggressor and aggressor != self:
                # If there's an aggressor and it's not this actor, target the aggressor instead
                actor_component.target = aggressor

            path = self.find_path_to_target_astar(game_map, actor_component.target)
            if path and len(path) > 1:
                next_step = path[1]  # First step is current position
                if game_map.is_walkable(next_step[0], next_step[1]):
                    entity_at_next_step = game.world.get_entity_at(next_step[0], next_step[1])
                    if not entity_at_next_step:
                        self.x, self.y = next_step
                        actor_component.last_move_time = current_time
                        game.logger.debug(f"{self.name} moved to {next_step} using A*")
                    elif entity_at_next_step == actor_component.target:
                        if self.is_valid_target(actor_component.target):
                            game.combat_system.attack(self, actor_component.target)
                            if actor_component.target:  # Check if target still exists after attack
                                game.logger.debug(f"{self.name} attacked {actor_component.target.name}")
                            else:
                                game.logger.debug(f"{self.name} defeated their target")
                                actor_component.target = None
                        else:
                            actor_component.target = None
                            game.logger.debug(f"{self.name}'s target is no longer valid")
                    else:
                        game.logger.debug(f"{self.name} is blocked by another entity at {next_step}")
            elif path and len(path) == 1:  # Actor is adjacent to the target
                if self.is_valid_target(actor_component.target):
                    game.combat_system.attack(self, actor_component.target)
                    if actor_component.target:  # Check if target still exists after attack
                        game.logger.debug(f"{self.name} attacked adjacent {actor_component.target.name}")
                    else:
                        game.logger.debug(f"{self.name} defeated their adjacent target")
                        actor_component.target = None
            else:
                game.logger.debug(f"{self.name} couldn't find a path to the target")
                actor_component.target = None  # Clear the target if no path is found
        else:
            # If no target, use Dijkstra map for movement
            self.move_using_dijkstra(game_map, game, current_time)

    def move_using_dijkstra(self, game_map, game, current_time):
        actor_component = self.get_component(ActorComponent)
        if not actor_component.dijkstra_map:
            actor_component.dijkstra_map = DijkstraMap(game_map.width, game_map.height)
            # Use player position as the goal for the Dijkstra map
            actor_component.dijkstra_map.compute([(game.world.player.x, game.world.player.y)], game_map.is_walkable)
        
        direction = actor_component.dijkstra_map.get_direction(int(self.x), int(self.y))
        if direction:
            new_x, new_y = self.x + direction[0], self.y + direction[1]
            if game_map.is_walkable(int(new_x), int(new_y)) and not game.world.get_entity_at(new_x, new_y):
                self.x, self.y = new_x, new_y
                actor_component.last_move_time = current_time
                game.logger.debug(f"{self.name} moved to ({new_x}, {new_y}) using Dijkstra map")
            else:
                game.logger.debug(f"{self.name} couldn't find a direction to move using Dijkstra map")
        else:
            game.logger.debug(f"{self.name} couldn't find a direction to move using Dijkstra map")

    def find_nearest_target_in_sight(self, game):
        actor_component = self.get_component(ActorComponent)
        
        potential_targets = [game.world.player] + [
            entity for entity in game.world.entities 
            if isinstance(entity, Actor) and entity != self
        ]
        
        visible_targets = [
            target for target in potential_targets
            if game.world.game_map.is_in_fov(int(self.x), int(self.y)) and
            game.world.game_map.is_in_fov(int(target.x), int(target.y))
        ]
        
        if visible_targets:
            actor_component.target = min(
                visible_targets, 
                key=lambda t: ((t.x - self.x)**2 + (t.y - self.y)**2)**0.5
            )
        else:
            actor_component.target = None

    def is_valid_target(self, entity):
        return (entity is not None and 
                (isinstance(entity, Actor) or isinstance(entity, Player)) and 
                entity != self and 
                not entity.get_component(FighterComponent).is_dead())

    def find_path_to_target_astar(self, game_map, target):
        # Create a cost array where 1 is walkable and 0 is blocked
        cost = np.ones((game_map.height, game_map.width), dtype=np.int8)
        for y in range(game_map.height):
            for x in range(game_map.width):
                if not game_map.is_walkable(x, y):
                    cost[y, x] = 0

        # Create a graph from the cost array
        graph = tcod.path.SimpleGraph(cost=cost, cardinal=2, diagonal=3)

        # Create a pathfinder
        pathfinder = tcod.path.Pathfinder(graph)

        # Set the start position
        pathfinder.add_root((int(self.y), int(self.x)))

        # Compute the path to the target
        path = pathfinder.path_to((int(target.y), int(target.x))).tolist()

        # Convert the path from (y, x) to (x, y) format
        return [(x, y) for y, x in path]

    def update_non_aggressive_behavior(self, game_map, current_time, entities):
        actor_component = self.get_component(ActorComponent)
        if actor_component.state == ActorState.IDLE:
            if random.random() < 0.1:
                actor_component.state = ActorState.PATROL
                actor_component.target = game_map.get_random_walkable_position()
                actor_component.dijkstra_map = DijkstraMap(game_map.width, game_map.height)
                actor_component.dijkstra_map.compute([actor_component.target], game_map.is_walkable)
        elif actor_component.state == ActorState.PATROL:
            if actor_component.target:
                direction = actor_component.dijkstra_map.get_direction(int(self.x), int(self.y))
                if direction:
                    new_x = self.x + direction[0]
                    new_y = self.y + direction[1]
                    if game_map.is_walkable(int(new_x), int(new_y)) and not any(entity.x == new_x and entity.y == new_y for entity in entities):
                        self.x = new_x
                        self.y = new_y
                        actor_component.last_move_time = current_time

                if (int(self.x), int(self.y)) == actor_component.target:
                    actor_component.state = ActorState.IDLE
                    actor_component.target = None
                    actor_component.dijkstra_map = None
            else:
                actor_component.state = ActorState.IDLE

    def witness_attack(self, attacker, victim, game):
        actor_component = self.get_component(ActorComponent)
        if attacker not in actor_component.hostile_towards:
            if self.aggression_type == "peaceful":
                self.become_hostile(attacker, game)
                self.logger.info(f"{self.name} is outraged by {attacker.name}'s attack on {victim.name}")
                game.show_message(f"{self.name} is outraged by {attacker.name}'s attack on {victim.name}!", MessageChannel.COMBAT)
            elif self.aggression_type == "neutral":
                if victim.aggression_type == "peaceful" or random.random() < 0.5:
                    self.become_hostile(attacker, game)
                    self.logger.info(f"{self.name} decides to intervene against {attacker.name}")
                    game.show_message(f"{self.name} decides to intervene against {attacker.name}!", MessageChannel.COMBAT)
                
            # Set the attacker as the target for this actor
            actor_component.target = attacker
