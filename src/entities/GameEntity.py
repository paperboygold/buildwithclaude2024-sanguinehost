from ecs.ecs import Entity
from components.PositionComponent import PositionComponent
from components.RenderComponent import RenderComponent

class GameEntity(Entity):
    def __init__(self, x: float, y: float, char: str, name: str):
        super().__init__()
        self.add_component(PositionComponent(x, y))
        self.add_component(RenderComponent(char, name))

    @property
    def x(self):
        return self.get_component(PositionComponent).x

    @x.setter
    def x(self, value):
        self.get_component(PositionComponent).x = value

    @property
    def y(self):
        return self.get_component(PositionComponent).y

    @y.setter
    def y(self, value):
        self.get_component(PositionComponent).y = value

    @property
    def char(self):
        return self.get_component(RenderComponent).char

    @property
    def name(self):
        return self.get_component(RenderComponent).name