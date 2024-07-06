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

class ActorKnowledgeSystem(System):
    def __init__(self, game):
        self.game = game
        self.logger = logging.getLogger(__name__)
        self.relationships_generated = False
        self.async_client = AsyncAnthropic(api_key=game.anthropic_client.api_key)

    def update(self, entities, game_map):
        self.update_actor_knowledge(entities, game_map)

    def generate_initial_relationships(self, entities):
        if not self.relationships_generated and not self.game.disable_dialogue_system:
            asyncio.run(self.generate_actor_relationships(entities))
            self.relationships_generated = True

    def update_actor_knowledge(self, entities, game_map):
        alive_actors = [entity for entity in entities if isinstance(entity, Actor)]
        
        for actor in alive_actors:
            for other_actor in entities:
                if isinstance(other_actor, Actor) and other_actor != actor:
                    if game_map.is_in_fov(int(actor.x), int(actor.y)) and game_map.is_in_fov(int(other_actor.x), int(other_actor.y)):
                        known_info = actor.knowledge.get_actor_info(other_actor.name)
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

            current_room = next((room for room in game_map.rooms if room.x <= actor.x < room.x + room.width and room.y <= actor.y < room.y + room.height), None)
            if current_room:
                actor.knowledge.add_location(f"Room at ({current_room.x}, {current_room.y})")

    def get_direction(self, actor1, actor2):
        dx = actor2.x - actor1.x
        dy = actor2.y - actor1.y
        angle = math.atan2(dy, dx)
        
        directions = ["east", "northeast", "north", "northwest", "west", "southwest", "south", "southeast"]
        index = round(4 * angle / math.pi) % 8
        return directions[index]

    async def generate_actor_relationships(self, entities):
        actor_entities = [entity for entity in entities if isinstance(entity, Actor)]
        tasks = []
        for i, actor1 in enumerate(actor_entities):
            for actor2 in actor_entities[i+1:]:
                relationship_type = "stranger"
                if random.random() < 0.5:  # 50% chance of a non-stranger relationship
                    relationship_type = random.choice([
                        "friend", "rival", "mentor", "student", "ally", "enemy",
                        "acquaintance", "family", "colleague"
                    ])
                tasks.append(self.generate_relationship_story(actor1, actor2, relationship_type))
        
        results = await asyncio.gather(*tasks)
        
        for result in results:
            actor1, actor2, relationship_type, relationship_story = result
            actor1.knowledge.add_actor(actor2.name, relationship_type, relationship_story)
            actor2.knowledge.add_actor(actor1.name, relationship_type, relationship_story)

    async def generate_relationship_story(self, actor1, actor2, relationship_type):
        actor1_component = actor1.get_component(ActorComponent)
        actor2_component = actor2.get_component(ActorComponent)
        prompt = f"Generate a very brief story (1-2 sentences) about the {relationship_type} relationship between {actor1.name} and {actor2.name}. {actor1.name}'s character: {actor1_component.character_card}. {actor2.name}'s character: {actor2_component.character_card}."
        
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
            return actor1, actor2, relationship_type, story
        except Exception as e:
            self.logger.error(f"Error generating relationship story: {str(e)}")
            self.logger.debug(traceback.format_exc())
            return actor1, actor2, relationship_type, f"{actor1.name} and {actor2.name} have a {relationship_type} relationship."
