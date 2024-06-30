from ecs.ecs import Component

class WorldStateComponent(Component):
    def __init__(self):
        self.player_actions = []
        self.discovered_areas = set()
        self.defeated_enemies = []
        self.acquired_items = []

    def update(self, action, data):
        if action == "move":
            self.player_actions.append(f"Moved to {data}")
        elif action == "discover":
            self.discovered_areas.add(data)
        elif action == "defeat":
            self.defeated_enemies.append(data)
        elif action == "acquire":
            self.acquired_items.append(data)

    def get_summary(self):
        return f"""
Player Actions: {', '.join(self.player_actions[-5:])}
Discovered Areas: {', '.join(self.discovered_areas)}
Defeated Enemies: {', '.join(self.defeated_enemies[-5:])}
Acquired Items: {', '.join(self.acquired_items[-5:])}
"""
