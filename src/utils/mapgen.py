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
        self.is_open = False

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

class BSPNode:
    def __init__(self, x, y, width, height):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.left = None
        self.right = None
        self.room = None

class Map:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.tiles = [[Tile(TileType.WALL) for _ in range(width)] for _ in range(height)]
        self.rooms = []
        self.fov_map = None

    def split_node(self, node, min_size, remaining_rooms):
        if remaining_rooms <= 0 or node.width <= min_size * 2 or node.height <= min_size * 2:
            return

        split_horizontally = random.choice([True, False])
        if node.width > node.height and node.width / node.height >= 1.25:
            split_horizontally = False
        elif node.height > node.width and node.height / node.width >= 1.25:
            split_horizontally = True

        max_size = (node.height if split_horizontally else node.width) - min_size
        if max_size <= min_size:
            return

        split = random.randint(min_size, max_size)

        if split_horizontally:
            node.left = BSPNode(node.x, node.y, node.width, split)
            node.right = BSPNode(node.x, node.y + split, node.width, node.height - split)
        else:
            node.left = BSPNode(node.x, node.y, split, node.height)
            node.right = BSPNode(node.x + split, node.y, node.width - split, node.height)

        left_rooms = remaining_rooms // 2
        right_rooms = remaining_rooms - left_rooms

        self.split_node(node.left, min_size, left_rooms)
        self.split_node(node.right, min_size, right_rooms)

    def create_rooms(self, node, remaining_rooms):
        if remaining_rooms <= 0:
            return 0

        if not node.left and not node.right:
            if self.create_room(node):
                return 1
            return 0

        left_rooms = self.create_rooms(node.left, remaining_rooms // 2) if node.left else 0
        right_rooms = self.create_rooms(node.right, remaining_rooms - left_rooms) if node.right else 0

        return left_rooms + right_rooms

    def create_room(self, node):
        room_width = random.randint(3, min(node.width - 2, 10))
        room_height = random.randint(3, min(node.height - 2, 10))
        room_x = node.x + random.randint(1, node.width - room_width - 1)
        room_y = node.y + random.randint(1, node.height - room_height - 1)
        new_room = Room(room_x, room_y, room_width, room_height)
        
        # Check if the room overlaps with existing rooms
        for existing_room in self.rooms:
            if (new_room.x < existing_room.x + existing_room.width and
                new_room.x + new_room.width > existing_room.x and
                new_room.y < existing_room.y + existing_room.height and
                new_room.y + new_room.height > existing_room.y):
                return False

        self.add_room(new_room)
        node.room = new_room
        return True

    def add_room(self, room):
        for y in range(room.y, room.y + room.height):
            for x in range(room.x, room.x + room.width):
                self.tiles[y][x] = Tile(TileType.FLOOR)
        self.rooms.append(room)

    def connect_rooms(self, node):
        if node.left and node.right:
            self.connect_rooms(node.left)
            self.connect_rooms(node.right)
            if node.left.room and node.right.room:
                self.create_corridor(node.left.room, node.right.room)

    def connect_all_rooms(self):
        for i in range(len(self.rooms) - 1):
            self.create_corridor(self.rooms[i], self.rooms[i + 1])

    def create_corridor(self, room1, room2):
        x1, y1 = room1.center()
        x2, y2 = room2.center()
        if random.random() < 0.5:
            self.create_h_tunnel(x1, x2, y1)
            self.create_v_tunnel(y1, y2, x2)
        else:
            self.create_v_tunnel(y1, y2, x1)
            self.create_h_tunnel(x1, x2, y2)

    def add_doors(self, max_doors_per_room=1):
        for room in self.rooms:
            doors_added = 0
            sides = [(room.x - 1, room.y, room.height, 0, 1),
                     (room.x + room.width, room.y, room.height, 0, 1),
                     (room.x, room.y - 1, room.width, 1, 0),
                     (room.x, room.y + room.height, room.width, 1, 0)]
            random.shuffle(sides)
            
            for x, y, length, dx, dy in sides:
                for i in range(length):
                    door_x, door_y = x + i * dx, y + i * dy
                    if self.is_valid_door_position(door_x, door_y) and self.is_on_corridor(door_x, door_y):
                        self.tiles[door_y][door_x] = Tile(TileType.DOOR)
                        doors_added += 1
                        if doors_added >= max_doors_per_room:
                            break
            if doors_added >= max_doors_per_room:
                break

    def is_valid_door_position(self, x, y):
        if not (0 <= x < self.width and 0 <= y < self.height):
            return False
        
        adjacent_tiles = [
            self.tiles[y-1][x].tile_type if y > 0 else None,
            self.tiles[y+1][x].tile_type if y < self.height - 1 else None,
            self.tiles[y][x-1].tile_type if x > 0 else None,
            self.tiles[y][x+1].tile_type if x < self.width - 1 else None
        ]
        
        return (self.tiles[y][x].tile_type == TileType.WALL and
                TileType.FLOOR in adjacent_tiles and
                adjacent_tiles.count(TileType.WALL) >= 2)

    def is_on_corridor(self, x, y):
        adjacent_floors = sum(1 for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]
                              if 0 <= x + dx < self.width and 0 <= y + dy < self.height
                              and self.tiles[y + dy][x + dx].tile_type == TileType.FLOOR)
        return adjacent_floors >= 2

    def create_h_tunnel(self, x1, x2, y):
        for x in range(min(x1, x2), max(x1, x2) + 1):
            self.tiles[y][x] = Tile(TileType.FLOOR)

    def create_v_tunnel(self, y1, y2, x):
        for y in range(min(y1, y2), max(y1, y2) + 1):
            self.tiles[y][x] = Tile(TileType.FLOOR)

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
        attempts = 0
        max_attempts = 1000
        while attempts < max_attempts:
            x = random.randint(1, self.width - 2)
            y = random.randint(1, self.height - 2)
            if self.is_walkable(x, y):
                return (x, y)
            attempts += 1
        raise ValueError("Could not find a walkable position after 1000 attempts")

    def generate(self, num_rooms, min_size=6, max_size=10):
        self.rooms = []
        root = BSPNode(1, 1, self.width - 2, self.height - 2)
        self.split_node(root, min_size, num_rooms)
        
        self.create_rooms(root, num_rooms)
        self.connect_rooms(root)
        self.connect_all_rooms()
        self.add_doors(max_doors_per_room=1)
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