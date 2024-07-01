import random
from enum import Enum
import tcod
from tcod import libtcodpy

class MapType(Enum):
    DUNGEON = 0
    CAVE = 1

class TileType(Enum):
    FLOOR = '.'
    WALL = '#'
    DOOR = '+'

class Tile:
    def __init__(self, tile_type):
        self.tile_type = tile_type
        self.blocked = tile_type in (TileType.WALL, TileType.DOOR)
        self.block_sight = tile_type in (TileType.WALL, TileType.DOOR)
        self.explored = False
        self.walkable = tile_type == TileType.FLOOR
        self.is_open = False

    def toggle_door(self):
        if self.tile_type == TileType.DOOR:
            self.is_open = not self.is_open
            self.blocked = not self.is_open
            self.block_sight = not self.is_open
            self.walkable = self.is_open

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
    def __init__(self, width, height, map_type=MapType.DUNGEON):
        self.width = width
        self.height = height
        self.map_type = map_type
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
                    if self.is_valid_door_position(door_x, door_y):
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
        
        north, south, west, east = adjacent_tiles
        
        # Check for horizontal door placement
        if (north == TileType.WALL and south == TileType.WALL and
            west == TileType.FLOOR and east == TileType.FLOOR):
            # Check if there's an opening on either side
            if (self.tiles[y][x-2].tile_type == TileType.FLOOR or
                self.tiles[y][x+2].tile_type == TileType.FLOOR):
                return True
        
        # Check for vertical door placement
        if (west == TileType.WALL and east == TileType.WALL and
            north == TileType.FLOOR and south == TileType.FLOOR):
            # Check if there's an opening above or below
            if (self.tiles[y-2][x].tile_type == TileType.FLOOR or
                self.tiles[y+2][x].tile_type == TileType.FLOOR):
                return True
        
        return False

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
                tile = self.tiles[y][x]
                self.fov_map.transparent[y, x] = not tile.block_sight
                self.fov_map.walkable[y, x] = tile.walkable
                if tile.tile_type == TileType.DOOR and not tile.is_open:
                    self.fov_map.transparent[y, x] = False

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

    def generate(self, num_rooms=0, min_size=6, max_size=10):
        if self.map_type == MapType.DUNGEON:
            self.generate_dungeon(num_rooms, min_size, max_size)
        elif self.map_type == MapType.CAVE:
            self.generate_cave()

    def generate_dungeon(self, num_rooms, min_size, max_size):
        self.rooms = []
        root = BSPNode(1, 1, self.width - 2, self.height - 2)
        self.split_node(root, min_size, num_rooms)
        
        self.create_rooms(root, num_rooms)
        self.connect_rooms(root)
        self.connect_all_rooms()
        self.add_doors(max_doors_per_room=2)  # Increased to 2 for better chances
        self.initialize_fov()

    def generate_cave(self):
        # Initialize the cave with random walls, keeping borders solid
        cave = [[1 if x == 0 or x == self.width - 1 or y == 0 or y == self.height - 1 else
                 (1 if random.random() < 0.45 else 0)
                 for x in range(self.width)] for y in range(self.height)]

        # Cellular automata iterations
        for _ in range(4):
            new_cave = [[0 for _ in range(self.width)] for _ in range(self.height)]
            for y in range(self.height):
                for x in range(self.width):
                    if x == 0 or x == self.width - 1 or y == 0 or y == self.height - 1:
                        new_cave[y][x] = 1  # Keep borders solid
                    else:
                        wall_count = sum(cave[ny][nx] 
                                         for ny in range(max(0, y-1), min(self.height, y+2))
                                         for nx in range(max(0, x-1), min(self.width, x+2))
                                         if (ny, nx) != (y, x))
                        if cave[y][x] == 1:
                            new_cave[y][x] = 1 if wall_count >= 4 else 0
                        else:
                            new_cave[y][x] = 1 if wall_count >= 5 else 0
            cave = new_cave

        # Ensure connectivity
        cave = self.ensure_connectivity(cave)

        # Set the tiles based on the cave layout
        for y in range(self.height):
            for x in range(self.width):
                self.tiles[y][x] = Tile(TileType.WALL if cave[y][x] else TileType.FLOOR)

        # Add some random cave chambers
        for _ in range(3):  # Add 3 random chambers
            chamber_width = random.randint(5, 10)
            chamber_height = random.randint(5, 10)
            x = random.randint(1, self.width - chamber_width - 1)
            y = random.randint(1, self.height - chamber_height - 1)
            self.create_chamber(x, y, chamber_width, chamber_height)
        
        self.connect_chambers()
        self.initialize_fov()

    def ensure_connectivity(self, cave):
        start_x, start_y = self.width // 2, self.height // 2
        
        # Find a starting open space near the center
        if cave[start_y][start_x] == 1:
            for r in range(1, min(self.width, self.height) // 2):
                for i in range(-r, r + 1):
                    for j in range(-r, r + 1):
                        new_x, new_y = start_x + i, start_y + j
                        if 0 <= new_x < self.width and 0 <= new_y < self.height and cave[new_y][new_x] == 0:
                            start_x, start_y = new_x, new_y
                            break
                    if cave[start_y][start_x] == 0:
                        break
                if cave[start_y][start_x] == 0:
                    break
        
        # Flood fill from the starting point
        self.flood_fill(cave, start_x, start_y)
        
        # Convert unreached areas to walls
        for y in range(self.height):
            for x in range(self.width):
                if cave[y][x] == 0:
                    cave[y][x] = 1
                elif cave[y][x] == 2:
                    cave[y][x] = 0
        
        return cave

    def flood_fill(self, cave, x, y):
        if x < 0 or x >= self.width or y < 0 or y >= self.height or cave[y][x] != 0:
            return
        
        cave[y][x] = 2  # Mark as reached
        
        self.flood_fill(cave, x + 1, y)
        self.flood_fill(cave, x - 1, y)
        self.flood_fill(cave, x, y + 1)
        self.flood_fill(cave, x, y - 1)

    def create_chamber(self, x, y, width, height):
        for chamber_y in range(y, y + height):
            for chamber_x in range(x, x + width):
                if 0 <= chamber_x < self.width and 0 <= chamber_y < self.height:
                    if random.random() < 0.8:  # 80% chance to be floor, for a more natural look
                        self.tiles[chamber_y][chamber_x] = Tile(TileType.FLOOR)

    def connect_chambers(self):
        # Find all floor tiles
        floor_tiles = [(x, y) for y in range(self.height) for x in range(self.width) 
                       if self.tiles[y][x].tile_type == TileType.FLOOR]
        
        # Use a simple algorithm to connect nearby floor tiles
        for _ in range(len(floor_tiles) // 10):  # Adjust this number to control connectivity
            start = random.choice(floor_tiles)
            end = min(floor_tiles, key=lambda p: ((p[0]-start[0])**2 + (p[1]-start[1])**2))
            self.create_tunnel(start[0], start[1], end[0], end[1])

    def create_tunnel(self, x1, y1, x2, y2):
        # Simple line drawing algorithm to create a tunnel
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        err = dx - dy

        while True:
            self.tiles[y1][x1] = Tile(TileType.FLOOR)
            if x1 == x2 and y1 == y2:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x1 += sx
            if e2 < dx:
                err += dx
                y1 += sy

    def __str__(self):
        return '\n'.join(''.join(tile.tile_type.value for tile in row) for row in self.tiles)

def generate_map(width, height, num_rooms, map_type=MapType.DUNGEON):
    game_map = Map(width, height, map_type)
    game_map.generate(num_rooms)
    return game_map

# Example usage
if __name__ == "__main__":
    map_width, map_height = 80, 24
    num_rooms = 10
    game_map = generate_map(map_width, map_height, num_rooms)
    print(game_map)

