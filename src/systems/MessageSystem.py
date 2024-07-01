from enum import Enum, auto
from typing import List, Tuple
from ecs.ecs import System

class MessageChannel(Enum):
    COMBAT = auto()
    DIALOGUE = auto()
    SYSTEM = auto()
    IMPORTANT = auto()
    MOVEMENT = auto()

class Message:
    def __init__(self, text: str, channel: MessageChannel, color: Tuple[int, int, int]):
        self.text = text
        self.channel = channel
        self.color = color

class MessageSystem(System):
    def __init__(self):
        self.message_log: List[Message] = []
        self.max_log_messages = 100
        self.visible_log_lines = 10
        self.visible_channels = set(MessageChannel) - {MessageChannel.MOVEMENT}

    def add_message(self, text: str, channel: MessageChannel, color: Tuple[int, int, int] = (255, 255, 255)):
        self.message_log.append(Message(text, channel, color))
        if len(self.message_log) > self.max_log_messages:
            self.message_log.pop(0)

    def get_visible_messages(self) -> List[Message]:
        return [msg for msg in reversed(self.message_log) if msg.channel in self.visible_channels][:self.visible_log_lines]

    def update(self, entities):
        # This method is required by the System class, but we don't need to update anything here
        pass

    def clear_messages(self):
        self.message_log.clear()
