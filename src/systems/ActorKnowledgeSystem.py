from ecs.ecs import System
from components.ActorComponent import ActorComponent
from entities.Actor import Actor
import random
import logging
import traceback

class ActorKnowledgeSystem(System):
    def __init__(self, game):
        self.game = game
        self.logger = logging.getLogger(__name__)
        self.relationships_generated = False

    def update(self, entities):
        self.update_actor_knowledge(entities)

    def generate_initial_relationships(self, entities):
        if not self.relationships_generated and not self.game.disable_dialogue_system:
            self.generate_actor_relationships(entities)
            self.relationships_generated = True

    def update_actor_knowledge(self, entities):
        for actor in [entity for entity in entities if isinstance(entity, Actor)]:
            for other_actor in [e for e in entities if isinstance(e, Actor) and e != actor]:
                if self.game.world.game_map.is_in_fov(int(actor.x), int(actor.y)) and self.game.world.game_map.is_in_fov(int(other_actor.x), int(other_actor.y)):
                    actor.knowledge.add_actor(other_actor.name)
            
            current_room = next((room for room in self.game.world.game_map.rooms if room.x <= actor.x < room.x + room.width and room.y <= actor.y < room.y + room.height), None)
            if current_room:
                actor.knowledge.add_location(f"Room at ({current_room.x}, {current_room.y})")

    def generate_actor_relationships(self, entities):
        actor_entities = [entity for entity in entities if isinstance(entity, Actor)]
        for i, actor1 in enumerate(actor_entities):
            for actor2 in actor_entities[i+1:]:
                relationship_type = "stranger"
                if random.random() < 0.5:  # 50% chance of a non-stranger relationship
                    relationship_type = random.choice([
                        "friend", "rival", "mentor", "student", "ally", "enemy",
                        "acquaintance", "family", "colleague"
                    ])
                relationship_story = self.generate_relationship_story(actor1, actor2, relationship_type)
                actor1.knowledge.add_actor(actor2.name, relationship_type, relationship_story)
                actor2.knowledge.add_actor(actor1.name, relationship_type, relationship_story)

    def generate_relationship_story(self, actor1, actor2, relationship_type):
        actor1_component = actor1.get_component(ActorComponent)
        actor2_component = actor2.get_component(ActorComponent)
        prompt = f"Generate a very brief story (1-2 sentences) about the {relationship_type} relationship between {actor1.name} and {actor2.name}. {actor1.name}'s character: {actor1_component.character_card}. {actor2.name}'s character: {actor2_component.character_card}."
        
        self.logger.info(f"Generating relationship story for {actor1.name} and {actor2.name}")
        self.logger.debug(f"Relationship story prompt: {prompt}")
        
        try:
            response = self.game.anthropic_client.messages.create(
                model="claude-3-5-sonnet-20240620",
                max_tokens=100,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            story = response.content[0].text.strip()
            self.logger.info(f"Generated relationship story: {story}")
            return story
        except Exception as e:
            self.logger.error(f"Error generating relationship story: {str(e)}")
            self.logger.debug(traceback.format_exc())
            return f"{actor1.name} and {actor2.name} have a {relationship_type} relationship."