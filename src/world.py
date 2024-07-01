from utils.mapgen import generate_map, MapType
from entities.Player import Player
from entities.Actor import Actor
from systems.ActorKnowledgeSystem import ActorKnowledgeSystem

class World:
    def __init__(self, width, height, game, map_type=MapType.DUNGEON, single_room=False):
        self.width = width
        self.height = height
        self.game_map = generate_map(width, height, num_rooms=3, map_type=map_type, single_room=single_room)
        self.entities = []
        self.player = None
        self.game = game
        self.actor_knowledge_system = ActorKnowledgeSystem(game)
        self.map_type = map_type

    def add_entity(self, entity):
        if isinstance(entity, Player):
            self.player = entity
        self.entities.append(entity)

    def get_entity_at(self, x, y):
        return next((e for e in self.entities if int(e.x) == int(x) and int(e.y) == int(y)), None)

    def is_walkable(self, x, y):
        return self.game_map.is_walkable(x, y)

    def update_actors(self):
        for entity in self.entities:
            if isinstance(entity, Actor):
                entity.update(self.game_map, self.player, self.game)

    def get_potential_actor_interactions(self):
        actor_entities = [entity for entity in self.entities if isinstance(entity, Actor)]
        potential_interactions = []
        for actor1 in actor_entities:
            for actor2 in actor_entities:
                if actor1 != actor2 and self.game_map.is_in_fov(int(actor1.x), int(actor1.y)) and self.game_map.is_in_fov(int(actor2.x), int(actor2.y)):
                    potential_interactions.append((actor1, actor2))
        return potential_interactions

    def to_picklable(self):
        picklable_world = World(self.width, self.height, None, self.map_type)
        picklable_world.game_map = self.game_map
        picklable_world.entities = [entity for entity in self.entities if not isinstance(entity, Player)]
        picklable_world.player = self.player
        return picklable_world
