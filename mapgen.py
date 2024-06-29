import random
from enum import Enum
import tcod
from tcod import libtcodpy

class TileType(Enum):
    FLOOR = '.'
    WALL = '#'
    DOOR = '+'

class Tile:
    def __init__(self, tile_type):
        self.tile_type = tile_type
        self.blocked = tile_type in (TileType.WALL, TileType.DOOR)
        self.block_sight = tile_type == TileType.WALL
        self.explored = False
        self.walkable = tile_type == TileType.FLOOR

class Room:
    def __init__(self, x, y, width, height):
        self.x = x
        self.y = y
        self.width = width
        self.height = height

    def center(self):
        center_x = (self.x + self.x + self.width) // 2
        center_y = (self.y + self.y + self.height) // 2
        return (center_x, center_y)

class Map:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.tiles = [[Tile(TileType.WALL) for _ in range(width)] for _ in range(height)]
        self.rooms = []
        self.fov_map = None

    def is_valid_room(self, room):
        if room.x < 1 or room.y < 1 or room.x + room.width > self.width - 1 or room.y + room.height > self.height - 1:
            return False
        return all(self.tiles[y][x].blocked
                   for x in range(room.x - 1, room.x + room.width + 1)
                   for y in range(room.y - 1, room.y + room.height + 1))

    def add_room(self, room):
        if self.is_valid_room(room):
            for y in range(room.y, room.y + room.height):
                for x in range(room.x, room.x + room.width):
                    self.tiles[y][x] = Tile(TileType.FLOOR)
            self.rooms.append(room)
            return True
        return False

    def add_doors(self):
        for room in self.rooms:
            # Add a door on each wall of the room
            for _ in range(4):
                wall = random.choice(['north', 'south', 'east', 'west'])
                if wall == 'north':
                    x = random.randint(room.x + 1, room.x + room.width - 2)
                    y = room.y
                elif wall == 'south':
                    x = random.randint(room.x + 1, room.x + room.width - 2)
                    y = room.y + room.height - 1
                elif wall == 'east':
                    x = room.x + room.width - 1
                    y = random.randint(room.y + 1, room.y + room.height - 2)
                else:  # west
                    x = room.x
                    y = random.randint(room.y + 1, room.y + room.height - 2)
                
                if 0 < x < self.width - 1 and 0 < y < self.height - 1:
                    self.tiles[y][x] = Tile(TileType.DOOR)

    def create_h_tunnel(self, x1, x2, y):
        for x in range(min(x1, x2), max(x1, x2) + 1):
            self.tiles[y][x] = Tile(TileType.FLOOR)

    def create_v_tunnel(self, y1, y2, x):
        for y in range(min(y1, y2), max(y1, y2) + 1):
            self.tiles[y][x] = Tile(TileType.FLOOR)

    def connect_rooms(self):
        for i in range(len(self.rooms) - 1):
            room1 = self.rooms[i]
            room2 = self.rooms[i + 1]
            
            (x1, y1) = room1.center()
            (x2, y2) = room2.center()
            
            if random.random() < 0.5:
                self.create_h_tunnel(x1, x2, y1)
                self.create_v_tunnel(y1, y2, x2)
            else:
                self.create_v_tunnel(y1, y2, x1)
                self.create_h_tunnel(x1, x2, y2)

    def initialize_fov(self):
        self.fov_map = tcod.map.Map(self.width, self.height)
        for y in range(self.height):
            for x in range(self.width):
                self.fov_map.transparent[y, x] = not self.tiles[y][x].block_sight
                self.fov_map.walkable[y, x] = self.tiles[y][x].walkable

    def compute_fov(self, x, y, radius, light_walls=True, algorithm=0):
        self.fov_map.compute_fov(x, y, radius, light_walls, algorithm)

    def is_in_fov(self, x, y):
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.fov_map.fov[y, x]
        return False

    def is_walkable(self, x, y):
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.tiles[y][x].walkable
        return False

    def get_random_walkable_position(self):
        while True:
            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)
            if self.is_walkable(x, y):
                return (x, y)

    def generate(self, num_rooms, min_size=5, max_size=10):
        for _ in range(num_rooms):
            for _ in range(100):  # Try 100 times to place a room
                room_width = random.randint(min_size, max_size)
                room_height = random.randint(min_size, max_size)
                x = random.randint(1, self.width - room_width - 1)
                y = random.randint(1, self.height - room_height - 1)
                new_room = Room(x, y, room_width, room_height)
                if self.add_room(new_room):
                    break
        self.connect_rooms()
        self.add_doors()
        self.initialize_fov()

    def __str__(self):
        return '\n'.join(''.join(tile.tile_type.value for tile in row) for row in self.tiles)

def generate_map(width, height, num_rooms):
    game_map = Map(width, height)
    game_map.generate(num_rooms)
    return game_map

# Example usage
if __name__ == "__main__":
    map_width, map_height = 80, 24
    num_rooms = 10
    game_map = generate_map(map_width, map_height, num_rooms)
    print(game_map)