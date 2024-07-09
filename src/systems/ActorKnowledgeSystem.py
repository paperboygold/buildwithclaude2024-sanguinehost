from ecs.ecs import System
from components.ActorComponent import ActorComponent, ActorState
from components.FighterComponent import FighterComponent
from entities.Actor import Actor
import random
import logging
import traceback
import math
import asyncio
from anthropic import AsyncAnthropic
from entities.Player import Player

class ActorKnowledgeSystem(System):
    def __init__(self, game):
        self.game = game
        self.logger = logging.getLogger(__name__)
        self.relationships_generated = False
        self.async_client = AsyncAnthropic(api_key=game.anthropic_client.api_key)
        self.defeated_entity_positions = {}  # New attribute

    def initialize(self):
        self.initialize_relationships(self.game.world.entities)

    def initialize_relationships(self, entities):
        for entity in entities:
            if isinstance(entity, Actor):
                for other_entity in entities:
                    if isinstance(other_entity, Actor) and other_entity != entity:
                        if other_entity.name not in entity.knowledge.relationships:
                            entity.knowledge.relationships[other_entity.name] = {"type": "stranger", "value": 0}

    def update(self, entities, game_map):
        self.update_actor_knowledge(entities, game_map)
        
        for actor in entities:
            if isinstance(actor, Actor):
                self.logger.debug(f"Actor directions relative to {actor.name}:")
                for other_entity in entities:
                    if isinstance(other_entity, Actor) and other_entity != actor:
                        direction = self.get_direction(actor, other_entity)
                        self.logger.debug(f"{other_entity.name} is {direction} of {actor.name}")
                
                # Log directions of defeated entities
                for name, position in self.defeated_entity_positions.items():
                    direction = self.get_direction(actor, name)
                    self.logger.debug(f"{name} (defeated) is {direction} of {actor.name}")

    def generate_initial_relationships(self, entities):
        if not self.relationships_generated and not self.game.disable_dialogue_system:
            asyncio.run(self.generate_actor_relationships(entities))
            self.relationships_generated = True

    def update_actor_knowledge(self, entities, game_map):
        alive_actors = [entity for entity in entities if isinstance(entity, Actor)]
        
        for actor in alive_actors:
            for other_actor in entities:
                if isinstance(other_actor, Actor) and other_actor != actor:
                    self.update_actor_info(actor, other_actor, game_map)
            
            # Update knowledge about defeated entities
            for defeated_name, position in self.defeated_entity_positions.items():
                direction = self.get_direction(actor, defeated_name)
                actor.knowledge.update_actor_info(
                    defeated_name,
                    is_dead=True,
                    last_seen_position=position,
                    direction=direction
                )

            current_room = next((room for room in game_map.rooms if room.x <= actor.x < room.x + room.width and room.y <= actor.y < room.y + room.height), None)
            if current_room:
                actor.knowledge.add_location(f"Room at ({current_room.x}, {current_room.y})")

    def update_actor_info(self, actor, other_actor, game_map):
        if game_map.is_in_fov(int(actor.x), int(actor.y)) and game_map.is_in_fov(int(other_actor.x), int(other_actor.y)):
            is_dead = other_actor.get_component(FighterComponent).is_dead()
            is_aggressive = other_actor.get_component(ActorComponent).state == ActorState.AGGRESSIVE
            is_targeting = other_actor.get_component(ActorComponent).target == actor
            last_seen_position = (other_actor.x, other_actor.y)
            proximity = ((actor.x - other_actor.x) ** 2 + (actor.y - other_actor.y) ** 2) ** 0.5
            direction = self.get_direction(actor, other_actor)

            actor.knowledge.update_actor_info(
                other_actor.name,
                entity=other_actor,
                is_aggressive=is_aggressive,
                is_targeting=is_targeting,
                last_seen_position=last_seen_position,
                proximity=proximity,
                direction=direction,
                is_dead=is_dead
            )

    def get_direction(self, actor1, actor2_or_name):
        if isinstance(actor2_or_name, str):
            # If it's a defeated entity
            x2, y2 = self.defeated_entity_positions.get(actor2_or_name, (None, None))
            if x2 is None or y2 is None:
                return "unknown"
        else:
            # If it's an active entity
            x2, y2 = actor2_or_name.x, actor2_or_name.y

        dx = x2 - actor1.x
        dy = y2 - actor1.y
        angle = math.atan2(dy, dx)
        
        directions = ["east", "southeast", "south", "southwest", "west", "northwest", "north", "northeast"]
        index = round(4 * angle / math.pi) % 8
        return directions[index]

    async def generate_actor_relationships(self, entities):
        actor_entities = [entity for entity in entities if isinstance(entity, Actor)]
        tasks = []
        for i, actor1 in enumerate(actor_entities):
            for actor2 in actor_entities[i+1:]:
                relationship_type = self.determine_initial_relationship_type(actor1, actor2)
                initial_value = self.calculate_initial_relationship_value(relationship_type)
                tasks.append(self.generate_relationship_story(actor1, actor2, relationship_type, initial_value))
        
        results = await asyncio.gather(*tasks)
        
        for result in results:
            actor1, actor2, relationship_type, relationship_value, relationship_story = result
            self.logger.info(f"Generated relationship between {actor1.name} and {actor2.name}:")
            self.logger.info(f"  Type: {relationship_type}")
            self.logger.info(f"  Value: {relationship_value}")
            self.logger.info(f"  Story: {relationship_story}")
            actor1.knowledge.add_actor(actor2.name, relationship_type, relationship_value, relationship_story)
            actor2.knowledge.add_actor(actor1.name, relationship_type, relationship_value, relationship_story)

    def determine_initial_relationship_type(self, actor1, actor2):
        # Consider faction compatibility
        if self.are_factions_compatible(actor1, actor2):
            relationship_types = [
                "stranger",
                "acquaintance",
                "colleague",
                "friendly",
                "good friend",
                "close friend",
                "confidant",
                "ally",
                "loyal ally"
            ]
        else:
            relationship_types = [
                "stranger",
                "unfriendly",
                "antagonist",
                "rival",
                "sworn enemy"
            ]
        
        # Weighted random choice to make some relationships more common than others
        weights = [0.3, 0.2, 0.15, 0.1, 0.1, 0.05, 0.05, 0.03, 0.02]
        return random.choices(relationship_types, weights=weights[:len(relationship_types)])[0]

    def calculate_initial_relationship_value(self, relationship_type):
        relationship_values = {
            "sworn enemy": random.randint(-80, -61),
            "rival": random.randint(-60, -41),
            "antagonist": random.randint(-40, -21),
            "unfriendly": random.randint(-20, -1),
            "stranger": random.randint(-10, 10),
            "acquaintance": random.randint(1, 20),
            "friendly": random.randint(21, 30),
            "colleague": random.randint(21, 40),
            "good friend": random.randint(31, 50),
            "close friend": random.randint(41, 60),
            "confidant": random.randint(51, 70),
            "ally": random.randint(51, 80),
            "loyal ally": random.randint(71, 90)
        }
        return relationship_values.get(relationship_type, random.randint(-10, 10))

    def are_factions_compatible(self, actor1, actor2):
        faction1 = actor1.character_card['faction']
        faction2 = actor2.character_card['faction']
        
        faction_relationships = {
            "sages": ["sages", "enigmas"],
            "enigmas": ["sages", "enigmas", "monsters"],
            "monsters": ["monsters", "enigmas"]
        }
        
        return faction2 in faction_relationships.get(faction1, [])

    async def generate_relationship_story(self, actor1, actor2, relationship_type, initial_value):
        actor1_component = actor1.get_component(ActorComponent)
        actor2_component = actor2.get_component(ActorComponent)
        prompt = f"Generate a very brief story (1-2 sentences) about the {relationship_type} relationship between {actor1.name} and {actor2.name}. Their initial relationship value is {initial_value} (range: -100 to 100, where negative is unfavorable and positive is favorable). {actor1.name}'s character: {actor1_component.character_card}. {actor2.name}'s character: {actor2_component.character_card}."
        
        self.logger.info(f"Generating relationship story for {actor1.name} and {actor2.name}")
        self.logger.debug(f"Relationship story prompt: {prompt}")
        
        try:
            response = await self.async_client.messages.create(
                model="claude-3-5-sonnet-20240620",
                max_tokens=100,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            story = response.content[0].text.strip()
            self.logger.info(f"Generated relationship story: {story}")
            return actor1, actor2, relationship_type, initial_value, story
        except Exception as e:
            self.logger.error(f"Error generating relationship story: {str(e)}")
            self.logger.debug(traceback.format_exc())
            return actor1, actor2, relationship_type, initial_value, f"{actor1.name} and {actor2.name} have a {relationship_type} relationship."