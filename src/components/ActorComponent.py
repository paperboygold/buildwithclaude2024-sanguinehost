from enum import Enum, auto
from ecs.ecs import Component
from data.character_cards import get_character_card

class EmotionalState(Enum):
    NEUTRAL = auto()
    HAPPY = auto()
    SAD = auto()
    ANGRY = auto()
    AFRAID = auto()

class ActorState(Enum):
    IDLE = auto()
    PATROL = auto()
    ALERT = auto()
    FLEE = auto()
    AGGRESSIVE = auto()

class ActorComponent(Component):
    def __init__(self, name, appearance, personality, background, knowledge, goals, speech_style, health, defense, power, aggression_type, target_preference):
        self.name = name
        self.appearance = appearance
        self.personality = personality
        self.background = background
        self.knowledge = knowledge
        self.goals = goals
        self.speech_style = speech_style
        self.health = health
        self.defense = defense
        self.power = power
        self.aggression_type = aggression_type
        self.target_preference = target_preference
        self.character_card = {
            'name': name,
            'appearance': appearance,
            'personality': personality,
            'background': background,
            'knowledge': knowledge,
            'goals': goals,
            'speech_style': speech_style,
            'health': health,
            'defense': defense,
            'power': power,
            'aggression_type': aggression_type,
            'target_preference': target_preference
        }
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
        self.emotional_state = EmotionalState.NEUTRAL
        self.emotional_intensity = 0.0