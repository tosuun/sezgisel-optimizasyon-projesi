"""Mesafe farklarının bağımsız tam hesapla eşdeğerliği."""
from copy import deepcopy
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import local_search as fast
from problem import solution_distance


def case(seed):
    rng = random.Random(seed)
    n = rng.randrange(2, 18)
    k = rng.randrange(1, 7)
    # Küçük tamsayılar eşit maliyetler yaratır; tek yönlü mesafeler de denenir.
    distances = {a: {b: (0 if a == b else rng.randrange(1, 9))
                     for b in range(n + 1)} for a in range(n + 1)}
    demands = {a: (rng.randrange(0, 6) if a else 0) for a in range(n + 1)}
    customers = list(range(1, n + 1))
    rng.shuffle(customers)
    routes = [[] for _ in range(k)]
    for c in customers:
        routes[rng.randrange(k)].append(c)
    return routes, distances, demands, rng.randrange(3, 15)


class SearchEquivalenceTests(unittest.TestCase):
    def test_every_delta_matches_full_recomputation(self):
        for seed in range(60):
            routes, distances, _, _ = case(seed)
            baseline = solution_distance(routes, distances)
            positions = [(r, p) for r, route in enumerate(routes) for p in range(len(route))]
            for i, (a, x) in enumerate(positions):
                for b, y in positions[i + 1:]:
                    candidate = deepcopy(routes)
                    candidate[a][x], candidate[b][y] = candidate[b][y], candidate[a][x]
                    self.assertEqual(fast._swap_delta(routes, a, x, b, y, distances),
                                     solution_distance(candidate, distances) - baseline)
                for b, route in enumerate(routes):
                    if a == b:
                        continue
                    for y in range(len(route) + 1):
                        candidate = deepcopy(routes)
                        customer = candidate[a].pop(x)
                        candidate[b].insert(y, customer)
                        delta = (fast._removal_delta(routes[a], x, distances)
                                 + fast._insertion_delta(route, y, customer, distances))
                        self.assertEqual(delta, solution_distance(candidate, distances) - baseline)


if __name__ == '__main__':
    unittest.main()
