from typing import Dict, List, Type

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