import math


class Rect(object):
    """
    A rectangle on the map. used to characterize a room.
    """
    def __init__(self, x, y, w, h):
        self.x1 = x
        self.y1 = y
        self.x2 = x + max(0, w)
        self.y2 = y + max(0, h)

    def __eq__(self, other):
        return (self.x1 == other.x1 and
                self.x2 == other.x2 and
                self.y1 == other.y1 and
                self.y2 == other.y2)

    def __repr__(self):
        return ('Rect: from ' + str(self.x1) + ' ' + str(self.y1) + ' to ' +
                str(self.x2) + ' ' + str(self.y2))

    def center(self):
        return Location((self.x1 + self.x2) / 2,
                        (self.y1 + self.y2) / 2)

    def intersect(self, other):
        """
        Returns true if two rectangles intersect.
        """
        return (self.x1 <= other.x2 and self.x2 >= other.x1 and
                self.y1 <= other.y2 and self.y2 >= other.y1)

    def contains(self, location):
        return (location.x > self.x1 and location.x <= self.x2 and
                location.y > self.y1 and location.y <= self.y2)

    def width(self):
        return self.x2 - self.x1

    def height(self):
        return self.y2 - self.y1


class Location(object):
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __eq__(self, other):
        return (isinstance(other, self.__class__) and
                self.x == other.x and self.y == other.y)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __add__(self, other):
        return Location(self.x + other.x, self.y + other.y)

    def __sub__(self, other):
        return Location(self.x - other.x, self.y - other.y)

    def __mul__(self, n):
        return Location(self.x * n, self.y * n)

    __rmul__ = __mul__

    def __str__(self):  # ignored??
        return str(self.x) + ' ' + str(self.y)

    def __repr__(self):
        return str(self.x) + ' ' + str(self.y)

    def set(self, x, y):
        self.x = x
        self.y = y

    def bound(self, rect):
        if (self.x > rect.x2):
            self.x = rect.x2
        if (self.y > rect.y2):
            self.y = rect.y2
        if (self.x < rect.x1):
            self.x = rect.x1
        if (self.y < rect.y1):
            self.y = rect.y1

    def to_string(self):
        return str(self.x) + ', ' + str(self.y)

    def distance(self, other):
        dx = self.x - other.x
        dy = self.y - other.y
        return math.sqrt(dx ** 2 + dy ** 2)


class Direction(object):
    def __init__(self, x, y, left=None, right=None):
        self.x = x
        self.y = y
        self.left = left
        self.right = right

    def __eq__(self, other):
        return (isinstance(other, self.__class__) and
                self.x == other.x and self.y == other.y)

    def __ne__(self, other):
        return not self.__eq__(other)

    def length(self):
        """
        Usually 1, but sometimes we have unnormalized Directions.
        """
        return math.sqrt(self.x ** 2 + self.y ** 2)

    def normalize(self):
        """
        Normalize to length 1 (preserving direction), then round and
        convert to integer so the movement is restricted to the map grid.
        If length is 0, remains 0.
        """
        distance = self.length()
        if distance > 0:
            self.x = int(round(self.x / distance))
            self.y = int(round(self.y / distance))


north = Direction(0, -1)
south = Direction(0, 1)
west = Direction(-1, 0)
east = Direction(1, 0)
northwest = Direction(-1, -1)
northeast = Direction(1, -1)
southwest = Direction(-1, 1)
southeast = Direction(1, 1)

north.left = northwest
northwest.left = west
west.left = southwest
southwest.left = south
south.left = southeast
southeast.left = east
east.left = northeast
northeast.left = north

north.right = northeast
northeast.right = east
east.right = southeast
southeast.right = south
south.right = southwest
southwest.right = west
west.right = northwest
northwest.right = north

directions = [north, northeast, east, southeast,
              south, southwest, west, northwest]
