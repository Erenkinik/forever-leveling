"""Flight paths for a route: which flight masters the player has found, and when flying beats walking."""
import heapq
import math

from pipeline.generate.config import DISCOVER_YARDS, FLIGHT_SPEED_RATIO, FLY_MIN_SAVING_YARDS
from pipeline.normalize.taxi import to_world


class Flights:
    """The faction's flight masters (data/canonical/taxi.json) and the ones found so far on the route.

    Distances are straight lines in world yards; a flight counts FLIGHT_SPEED_RATIO times shorter than a walk of
    the same length, and only flies through flight masters already found.
    """

    def __init__(self, taxi: dict, faction: str) -> None:
        self.nodes = {int(k): n for k, n in taxi["nodes"].items() if faction in n["factions"]}
        self.bounds = {int(k): b for k, b in taxi["bounds"].items()}
        self.links: dict[int, set[int]] = {n: set() for n in self.nodes}
        for a, b in taxi["paths"]:
            if a in self.nodes and b in self.nodes:
                self.links[a].add(b)
                self.links[b].add(a)  # flights run both ways
        self.known: set[int] = set()

    def world(self, map_id: int, x: float, y: float) -> tuple[float, float, int] | None:
        """World (X, Y, continent) of a map point; None for a map without bounds."""
        b = self.bounds.get(map_id)
        if b is None:
            return None
        xw, yw = to_world(x, y, b)
        return xw, yw, int(b[4])

    def _yards(self, a: tuple[float, float, int], b: tuple[float, float, int]) -> float:
        return math.dist(a[:2], b[:2]) if a[2] == b[2] else math.inf

    def _node_point(self, node: int) -> tuple[float, float, int]:
        n = self.nodes[node]
        return n["world"][0], n["world"][1], n["continent"]

    def found_near(self, map_id: int, x: float, y: float) -> list[int]:
        """Flight masters not found yet within DISCOVER_YARDS of this point, nearest first."""
        here = self.world(map_id, x, y)
        if here is None:
            return []
        near = [(self._yards(here, self._node_point(n)), n) for n in self.nodes if n not in self.known]
        return [n for d, n in sorted(near) if d <= DISCOVER_YARDS]

    def _flight_yards(self, start: int) -> dict[int, float]:
        """Flight length from `start` to every found flight master reachable through found ones."""
        dist = {start: 0.0}
        queue = [(0.0, start)]
        while queue:
            d, n = heapq.heappop(queue)
            if d > dist[n]:
                continue
            for m in self.links[n] & self.known:
                nd = d + math.dist(self.nodes[n]["world"], self.nodes[m]["world"])
                if nd < dist.get(m, math.inf):
                    dist[m] = nd
                    heapq.heappush(queue, (nd, m))
        return dist

    def plan(self, src: tuple[int, float, float], dst: tuple[int, float, float]) -> tuple[int, int] | None:
        """(from, to) flight masters when walking to the first, flying and walking on from the second saves at least
        FLY_MIN_SAVING_YARDS of walking; None otherwise."""
        a, b = self.world(*src), self.world(*dst)
        if a is None or b is None or a[2] != b[2] or not self.known:
            return None
        walk = self._yards(a, b)
        best, best_cost = None, walk - FLY_MIN_SAVING_YARDS
        for start in sorted(self.known):
            to_start = self._yards(a, self._node_point(start))
            if to_start >= best_cost:
                continue
            for end, flown in self._flight_yards(start).items():
                if end == start:
                    continue
                cost = to_start + flown / FLIGHT_SPEED_RATIO + self._yards(self._node_point(end), b)
                if cost < best_cost:
                    best, best_cost = (start, end), cost
        return best
