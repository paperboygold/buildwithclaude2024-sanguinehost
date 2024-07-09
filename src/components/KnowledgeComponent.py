from ecs.ecs import Component
import time

class KnowledgeComponent(Component):
    def __init__(self):
        self.known_actors = {}
        self.known_locations = set()
        self.conversation_memories = []
        self.combat_memories = []
        self.relationships = {}
        self.long_term_relationship_memory = {}

    def add_actor(self, actor_name, relationship_type, initial_value, relationship_story, is_aggressive=False, is_targeting=False, last_seen_position=None, proximity=None, direction=None):
        self.known_actors[actor_name] = {
            "relationship": relationship_type,
            "story": relationship_story,
            "is_aggressive": is_aggressive,
            "is_targeting": is_targeting,
            "last_seen_position": last_seen_position,
            "proximity": proximity,
            "direction": direction,
        }
        self.relationships[actor_name] = {"type": relationship_type, "value": initial_value}

    def update_relationship(self, actor_name, relationship_type, value):
        self.relationships[actor_name] = {"type": relationship_type, "value": value}
        
        # Update long-term memory
        if actor_name not in self.long_term_relationship_memory:
            self.long_term_relationship_memory[actor_name] = []
        
        self.long_term_relationship_memory[actor_name].append({
            "type": relationship_type,
            "value": value,
            "timestamp": time.time()
        })
        
        # Keep only the last 10 entries in long-term memory
        self.long_term_relationship_memory[actor_name] = self.long_term_relationship_memory[actor_name][-10:]

    def get_long_term_relationship_trend(self, actor_name):
        if actor_name not in self.long_term_relationship_memory:
            return None
        
        memory = self.long_term_relationship_memory[actor_name]
        if len(memory) < 2:
            return None
        
        start_value = memory[0]["value"]
        end_value = memory[-1]["value"]
        time_diff = memory[-1]["timestamp"] - memory[0]["timestamp"]
        
        trend = (end_value - start_value) / time_diff
        return trend

    def update_actor_info(self, actor_name, entity=None, is_aggressive=None, is_targeting=None, last_seen_position=None, proximity=None, direction=None, is_dead=None):
        if actor_name not in self.known_actors:
            self.known_actors[actor_name] = {}
        
        actor_info = self.known_actors[actor_name]
        
        if entity:
            actor_info['entity'] = entity
        if is_aggressive is not None:
            actor_info['is_aggressive'] = is_aggressive
        if is_targeting is not None:
            actor_info['is_targeting'] = is_targeting
        if last_seen_position:
            actor_info['last_seen_position'] = last_seen_position
        if proximity is not None:
            actor_info['proximity'] = proximity
        if direction:
            actor_info['direction'] = direction
        if is_dead is not None:
            actor_info['is_dead'] = is_dead

        # Update the 'alive' status based on 'is_dead'
        actor_info['alive'] = not actor_info.get('is_dead', False)

    def add_location(self, location):
        self.known_locations.add(location)

    def add_conversation_memory(self, memory):
        self.conversation_memories.append(memory)

    def add_combat_memory(self, memory):
        self.combat_memories.append(memory)

    def get_summary(self):
        actor_info = ", ".join([f"{name} ({info['relationship']}, {'dead' if info.get('is_dead', False) else 'alive'}, {'aggressive' if info['is_aggressive'] else 'non-aggressive'}, {'targeting' if info['is_targeting'] else 'not targeting'}, last seen at {info['last_seen_position']}, proximity: {info['proximity']}, direction: {info['direction']})" for name, info in self.known_actors.items()])
        location_info = ", ".join(self.known_locations)
        conversation_info = ". ".join(self.conversation_memories[-5:])
        combat_info = ". ".join(self.combat_memories[-5:])
        return f"Known Actors: {actor_info}. Known locations: {location_info}. Recent conversations: {conversation_info}. Recent combat: {combat_info}"

    def get_relationship_story(self, actor_name):
        return self.known_actors.get(actor_name, {}).get("story", "")

    def get_actor_info(self, actor_name):
        return self.known_actors.get(actor_name, {})