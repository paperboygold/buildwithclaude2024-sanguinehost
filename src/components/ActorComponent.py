from enum import Enum, auto
from ecs.ecs import Component
from data.character_cards import get_character_card

class ActorState(Enum):
    IDLE = auto()
    PATROL = auto()
    ALERT = auto()
    FLEE = auto()
    AGGRESSIVE = auto()

class ActorComponent(Component):
    def __init__(self, name: str, character_card_key: str):
        self.name = name
        self.character_card = get_character_card(character_card_key, "")
        self.state = ActorState.IDLE
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
        self.aggressor = None
        self.aggressive_targets = set()
        self.last_target_evaluation = 0
        self.hostile_towards = set()