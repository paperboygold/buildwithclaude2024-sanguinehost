from ecs.ecs import Component

class RenderComponent(Component):
    def __init__(self, char: str, name: str):
        self.char = char
        self.name = name