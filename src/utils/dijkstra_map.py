import heapq

class DijkstraMap:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.map = [[float('inf')] * width for _ in range(height)]

    def compute(self, goals, is_walkable_func):
        heap = []
        for x, y in goals:
            if 0 <= x < self.width and 0 <= y < self.height:
                self.map[y][x] = 0
                heapq.heappush(heap, (0, x, y))

        while heap:
            dist, x, y = heapq.heappop(heap)

            for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                nx, ny = x + dx, y + dy
                if (0 <= nx < self.width and 0 <= ny < self.height and
                    is_walkable_func(nx, ny)):
                    new_dist = dist + 1
                    if new_dist < self.map[ny][nx]:
                        self.map[ny][nx] = new_dist
                        heapq.heappush(heap, (new_dist, nx, ny))

    def get_direction(self, x, y):
        if not (0 <= x < self.width and 0 <= y < self.height):
            return None

        best_dir = None
        best_value = self.map[y][x]

        for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
            nx, ny = x + dx, y + dy
            if (0 <= nx < self.width and 0 <= ny < self.height and
                self.map[ny][nx] < best_value):
                best_dir = (dx, dy)
                best_value = self.map[ny][nx]

        return best_dir