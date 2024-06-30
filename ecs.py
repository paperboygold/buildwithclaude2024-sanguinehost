from typing import Dict, List, Type
from character_cards import get_character_card
from enum import Enum, auto

class Component:
    pass

class System:
    def update(self, entities: List['Entity']):
        pass

class Entity:
    def __init__(self):
        self.components: Dict[Type[Component], Component] = {}

    def add_component(self, component: Component):
        self.components[type(component)] = component

    def remove_component(self, component_type: Type[Component]):
        if component_type in self.components:
            del self.components[component_type]

    def get_component(self, component_type: Type[Component]):
        return self.components.get(component_type)

    def has_component(self, component_type: Type[Component]):
        return component_type in self.components

class NPCState(Enum):
    IDLE = auto()
    PATROL = auto()
    ALERT = auto()
    FLEE = auto()

class NPCComponent(Component):
    def __init__(self, name: str, character_card_key: str):
        self.name = name
        self.character_card = get_character_card(character_card_key, "")
        self.state = NPCState.IDLE
        self.target = None
        self.dijkstra_map = None
        self.last_move_time = 0
        self.move_delay = 0.5
        self.last_conversation_time = 0
        self.conversation_cooldown = 10
        self.dialogue_history = []
        self.current_conversation = None
        self.conversation_partner = None
        self.conversation_turns = 0

class KnowledgeComponent(Component):
    def __init__(self):
        self.known_npcs = {}
        self.known_locations = set()

    def add_npc(self, npc_name, relationship="stranger", relationship_story=""):
        self.known_npcs[npc_name] = {"relationship": relationship, "story": relationship_story}

    def update_relationship(self, npc_name, relationship, relationship_story=""):
        if npc_name in self.known_npcs:
            self.known_npcs[npc_name]["relationship"] = relationship
            if relationship_story:
                self.known_npcs[npc_name]["story"] = relationship_story

    def add_location(self, location):
        self.known_locations.add(location)

    def get_summary(self):
        npc_info = ", ".join([f"{name} ({info['relationship']})" for name, info in self.known_npcs.items()])
        location_info = ", ".join(self.known_locations)
        return f"Known NPCs: {npc_info}. Known locations: {location_info}."

    def get_relationship_story(self, npc_name):
        return self.known_npcs.get(npc_name, {}).get("story", "")