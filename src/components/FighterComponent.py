from ecs.ecs import Component

class FighterComponent(Component):
    def __init__(self, hp, defense, power):
        self.max_hp = hp
        self.hp = hp
        self.defense = defense
        self.power = power