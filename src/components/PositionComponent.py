from ecs.ecs import Component

class PositionComponent(Component):
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y