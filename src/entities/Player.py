from ecs.ecs import Entity
from components.PositionComponent import PositionComponent
from components.RenderComponent import RenderComponent
from components.KnowledgeComponent import KnowledgeComponent

class Player(Entity):
    def __init__(self, x, y):
        super().__init__()
        self.add_component(PositionComponent(x, y))
        self.add_component(RenderComponent('@', 'Player'))
        self.add_component(KnowledgeComponent())

    @property
    def knowledge(self):
        return self.get_component(KnowledgeComponent)

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

    @char.setter
    def char(self, value):
        self.get_component(RenderComponent).char = value

    @property
    def name(self):
        return self.get_component(RenderComponent).name

    @name.setter
    def name(self, value):
        self.get_component(RenderComponent).name = value