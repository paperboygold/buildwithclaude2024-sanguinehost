from ecs.ecs import Component

class KnowledgeComponent(Component):
    def __init__(self):
        self.known_actors = {}
        self.known_locations = set()
        self.conversation_memories = []
        self.combat_memories = []

    def add_actor(self, actor_name, relationship="stranger", relationship_story=""):
        self.known_actors[actor_name] = {"relationship": relationship, "story": relationship_story}

    def update_relationship(self, actor_name, relationship, relationship_story=""):
        if actor_name in self.known_actors:
            self.known_actors[actor_name]["relationship"] = relationship
            if relationship_story:
                self.known_actors[actor_name]["story"] = relationship_story

    def add_location(self, location):
        self.known_locations.add(location)

    def add_conversation_memory(self, memory):
        self.conversation_memories.append(memory)

    def add_combat_memory(self, memory):
        self.combat_memories.append(memory)

    def get_summary(self):
        actor_info = ", ".join([f"{name} ({info['relationship']})" for name, info in self.known_actors.items()])
        location_info = ", ".join(self.known_locations)
        conversation_info = ". ".join(self.conversation_memories[-5:])
        combat_info = ". ".join(self.combat_memories[-5:])
        return f"Known Actors: {actor_info}. Known locations: {location_info}. Recent conversations: {conversation_info}. Recent combat: {combat_info}"

    def get_relationship_story(self, actor_name):
        return self.known_actors.get(actor_name, {}).get("story", "")