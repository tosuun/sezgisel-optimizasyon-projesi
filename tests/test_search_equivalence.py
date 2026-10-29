"""V2 tam hesaplama ile hızlı kenar hesaplamasının karar eşdeğerliği."""
from copy import deepcopy
import importlib.util
import random
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import local_search as fast
import solver
from problem import solution_distance

spec = importlib.util.spec_from_file_location(
    'search_v2_reference', Path(__file__).parent / 'fixtures/local_search_v2_reference.py')
slow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(slow)


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

    def test_operators_and_full_search_preserve_routes_rng_and_parents(self):
        for seed in range(300):
            routes, distances, demands, capacity = case(seed)
            before = deepcopy(routes)
            args = (routes, distances, demands, capacity)
            with self.subTest(seed=seed):
                self.assertEqual(fast.swap_search(*args), slow.swap_search(*args))
                self.assertEqual(fast.relocate_search(*args), slow.relocate_search(*args))
                for name in ('repair', 'local_search'):
                    r1, r2 = random.Random(seed), random.Random(seed)
                    extra = (len(routes),) if name == 'local_search' else ()
                    expected = getattr(slow, name)(*args, *extra, r1)
                    actual = getattr(fast, name)(*args, *extra, r2)
                    self.assertEqual(actual, expected)
                    self.assertEqual(r1.getstate(), r2.getstate())
                    self.assertEqual(routes, before)
                    returned = actual[0] if name == 'local_search' else actual
                    for route in returned:
                        self.assertTrue(all(route is not parent for parent in routes))

    def test_full_solver_without_time_limit_same_decisions(self):
        for seed in range(8):
            from problem import build_distance_matrix
            distances = build_distance_matrix({i: ((i * 13) % 17, (i * 7) % 19)
                                               for i in range(9)})
            args = (distances, {i: (0 if i == 0 else 2) for i in range(9)}, 6, 3)
            kwargs = dict(population_size=24, max_generations=3, seed=seed)
            with patch.object(solver, 'local_search', slow.local_search):
                expected = solver.solve(*args, **kwargs)
            actual = solver.solve(*args, **kwargs)
            for field in ('best_routes', 'distance', 'feasible', 'generations',
                          'partial_generation_targets', 'stop_reason'):
                self.assertEqual(actual[field], expected[field])


if __name__ == '__main__':
    unittest.main()
