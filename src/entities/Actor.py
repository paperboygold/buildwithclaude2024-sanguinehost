from ecs.ecs import Entity
from components.ActorComponent import ActorComponent, ActorState
from components.KnowledgeComponent import KnowledgeComponent
from components.PositionComponent import PositionComponent
from components.RenderComponent import RenderComponent
from utils.dijkstra_map import DijkstraMap
import random
import time
import math

class Actor(Entity):
    def __init__(self, x, y, name, character_card_key, aggressive=False):
        super().__init__()
        self.add_component(PositionComponent(x, y))
        self.add_component(RenderComponent('N', name))
        self.add_component(ActorComponent(name, character_card_key))
        self.add_component(KnowledgeComponent())
        self.color = (random.randint(100, 255), random.randint(100, 255), random.randint(100, 255))
        self.aggressive = aggressive

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

    def update(self, game_map, player):
        actor_component = self.get_component(ActorComponent)
        current_time = time.time()
        if current_time - actor_component.last_move_time < actor_component.move_delay:
            return

        if self.aggressive:
            actor_component.state = ActorState.AGGRESSIVE
            dx = player.x - self.x
            dy = player.y - self.y
            distance = math.sqrt(dx**2 + dy**2)
            
            if distance > 1:  # If not adjacent to the player
                move_x = int(round(dx / distance))
                move_y = int(round(dy / distance))
                new_x = int(self.x + move_x)
                new_y = int(self.y + move_y)
                if game_map.is_walkable(new_x, new_y):
                    self.x = new_x
                    self.y = new_y
                    actor_component.last_move_time = current_time
        else:
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
                        if game_map.is_walkable(int(new_x), int(new_y)):
                            self.x = new_x
                            self.y = new_y
                            actor_component.last_move_time = current_time

                    if (int(self.x), int(self.y)) == actor_component.target:
                        actor_component.state = ActorState.IDLE
                        actor_component.target = None
                        actor_component.dijkstra_map = None
                else:
                    actor_component.state = ActorState.IDLE
