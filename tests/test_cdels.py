"""Küçük, bağımsız maliyet hesaplarıyla CDELS davranış kontrolleri.

Proje klasöründen: python3 -B -m unittest discover -s tests -v
"""

import contextlib
from copy import deepcopy
import importlib
import io
from itertools import permutations
from pathlib import Path
import random
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

import local_search as search
import operators as op
import problem
import solver


COORDINATES = {0: (0, 0), 1: (3, 0), 2: (0, 4), 3: (3, 4), 4: (6, 0), 5: (6, 4)}
DEMANDS = {0: 0, 1: 6, 2: 3, 3: 5, 4: 4, 5: 2}
MATRIX = problem.build_distance_matrix(COORDINATES)
VALID = [[1, 4], [2, 5, 3]]
OVERLOADED = [[1, 4, 2], [5, 3]]


def independent_distance(routes, matrix):
    total = 0
    for route in routes:
        path = [0] + route + [0]
        total += sum(matrix[a][b] for a, b in zip(path, path[1:]))
    return total


def independent_valid(routes, demands, capacity, max_vehicles):
    customers = [customer for route in routes for customer in route]
    expected = [customer for customer in demands if customer != 0]
    return (sorted(customers) == sorted(expected)
            and sum(bool(route) for route in routes) <= max_vehicles
            and all(sum(demands[c] for c in route) <= capacity for route in routes))


class CrossRandom:
    def __init__(self, values, route=0, position=0):
        self.values = iter(values)
        self.route = route
        self.position = position
        self.checks = 0

    def choice(self, routes):
        assert self.route in routes
        return self.route

    def randrange(self, size):
        assert self.position < size
        return self.position

    def random(self):
        self.checks += 1
        return next(self.values)


class OperatorsTests(unittest.TestCase):
    def test_copy_and_position(self):
        original = [[1, 4], [], [2, 5, 3]]
        copied = op.copy_solution(original)
        copied[0].append(99)
        copied[1].append(7)
        self.assertEqual(original, [[1, 4], [], [2, 5, 3]])
        self.assertEqual(op.find_customer(original, 5), (2, 1))
        with self.assertRaises(ValueError):
            op.find_customer(original, 99)

    def test_initialization_and_mutation(self):
        for seed in range(10):
            rng = random.Random(seed)
            population = op.initialize_population(DEMANDS, 10, 2, 15, rng)
            before = deepcopy(population)
            self.assertEqual(len({id(r) for individual in population for r in individual}), 30)
            for target in range(15):
                mutant = op.mutate(population, target, 0.7, rng)
                self.assertEqual(sorted(c for r in mutant for c in r), [1, 2, 3, 4, 5])
                self.assertEqual(len(mutant), 2)
            self.assertEqual(population, before)
        with self.assertRaises(ValueError):
            op.initialize_individual({0: 0, 1: 11}, 10, 2, random.Random(1))
        with self.assertRaises(ValueError):
            op.mutate([VALID, VALID], 0, 0.7, random.Random(1))

    def test_perturbation_cases(self):
        self.assertEqual(op.perturbation_move(
            [[1, 4, 2], [3, 5]], [[1, 5, 2], [4, 3]], 0, 1
        ), [[1, 5, 2], [3, 4]])
        self.assertEqual(op.perturbation_move(
            [[1, 4], [3, 5, 2]], [[1, 4, 5], [3, 2]], 0, 2
        ), [[1, 4, 5], [3, 2]])
        source = [[1, 2], [3]]
        self.assertEqual(op.perturbation_move(source, [[1, 2, 3], []], 0, 2), source)

    def test_mutation_attempt_count_and_distinct_customers(self):
        class RecordingRandom(random.Random):
            def __init__(self):
                super().__init__(42)
                self.samples = []

            def sample(self, values, count):
                chosen = super().sample(values, count)
                self.samples.append(chosen)
                return chosen

        population = [VALID, OVERLOADED, [[4, 1], [3, 5, 2]]]
        for factor, expected in [(0.01, 1), (0.7, 2), (1, 3)]:
            rng = RecordingRandom()
            with patch.object(op, 'perturbation_move', wraps=op.perturbation_move) as move:
                op.mutate(population, 0, factor, rng)
            self.assertEqual(set(rng.samples[0]), {1, 2})
            self.assertEqual(len(rng.samples[1]), expected)
            self.assertEqual(len(set(rng.samples[1])), expected)
            self.assertEqual(move.call_count, expected)

    def test_nonfinite_initialization_data_are_rejected(self):
        for capacity in [float('nan'), float('inf')]:
            with self.assertRaises(ValueError):
                op.initialize_individual(DEMANDS, capacity, 2, random.Random(42))
        for demand in [float('nan'), float('inf')]:
            with self.assertRaises(ValueError):
                op.initialize_individual({0: 0, 1: demand}, 10, 2, random.Random(42))

    def test_exp_stops_entire_scan_and_skips_closed_customer(self):
        target, mutant = [[1, 2], [3, 4]], [[4, 3], [2, 1]]
        before = deepcopy((target, mutant))
        rng = CrossRandom([0.1, 0.9])
        trial = op.crossover_exp(target, mutant, 0.7, rng)
        self.assertEqual(trial, [[4, 2], [3, 1]])
        self.assertEqual(rng.checks, 2)
        self.assertEqual((target, mutant), before)

    def test_exp_endpoints_and_singleton_guard(self):
        target, mutant = [[1, 2], [3, 4]], [[4, 3], [2, 1]]
        self.assertEqual(op.crossover_exp(
            target, mutant, 0, CrossRandom([0.5])
        ), [[4, 2], [3, 1]])
        rng = CrossRandom([0.5] * 4)
        trial = op.crossover_exp(target, mutant, 1, rng)
        self.assertEqual(rng.checks, 4)
        self.assertEqual(sorted(c for r in trial for c in r), [1, 2, 3, 4])
        self.assertEqual(op.crossover_exp(
            [[1, 2], [3]], [[1, 2, 3], []], 0,
            CrossRandom([0.5], route=0, position=2)
        ), [[1, 2], [3]])
        # Koddaki <= CR sınırı: tam 0, CR=0 için de başarılı kontroldür.
        rng = CrossRandom([0, 0.5])
        op.crossover_exp(target, mutant, 0, rng)
        self.assertEqual(rng.checks, 2)

    def test_exp_small_exhaustive_customer_preservation(self):
        solutions = [
            [list(order[:cut]), list(order[cut:])]
            for order in permutations([1, 2, 3]) for cut in range(4)
        ]
        for target in solutions:
            for mutant in solutions:
                before = deepcopy((target, mutant))
                result = op.crossover_exp(target, mutant, 0.7, random.Random(42))
                self.assertEqual(sorted(c for r in result for c in r), [1, 2, 3])
                self.assertEqual(len(result), 2)
                self.assertTrue(all(not old or new for old, new in zip(target, result)))
                self.assertEqual((target, mutant), before)


class LocalSearchTests(unittest.TestCase):
    def test_swapping_matches_independent_neighborhood_minimum(self):
        routes = [[4, 1], [5, 2, 3]]
        before = deepcopy(routes)
        neighbors = [routes]
        places = [(r, p) for r, route in enumerate(routes) for p in range(len(route))]
        for i, (a, x) in enumerate(places):
            for b, y in places[i + 1:]:
                candidate = deepcopy(routes)
                candidate[a][x], candidate[b][y] = candidate[b][y], candidate[a][x]
                if independent_valid(candidate, DEMANDS, 10, 2):
                    neighbors.append(candidate)
        expected = min(independent_distance(r, MATRIX) for r in neighbors)
        result = search.swap_search(routes, MATRIX, DEMANDS, 10)
        self.assertEqual(independent_distance(result, MATRIX), expected)
        self.assertTrue(independent_valid(result, DEMANDS, 10, 2))
        self.assertEqual(routes, before)

    def test_relocation_improves_without_emptying_route(self):
        coords = {0: (0, 0), 1: (100, 0), 2: (1, 0), 3: (101, 0)}
        matrix = problem.build_distance_matrix(coords)
        demands = {0: 0, 1: 1, 2: 1, 3: 1}
        routes = [[1, 2], [3]]
        result = search.relocate_search(routes, matrix, demands, 3)
        self.assertEqual(independent_distance(result, matrix), 204)
        self.assertTrue(independent_valid(result, demands, 3, 2))
        self.assertTrue(all(result))
        self.assertEqual(routes, [[1, 2], [3]])
        self.assertEqual(search.relocate_search([[1], [2]], matrix, demands, 3), [[1], [2]])

    def test_successful_and_failed_repair(self):
        before = deepcopy(OVERLOADED)
        result = search.repair(OVERLOADED, MATRIX, DEMANDS, 10, random.Random(42))
        self.assertTrue(independent_valid(result, DEMANDS, 10, 2))
        self.assertEqual(OVERLOADED, before)
        failed = [[1, 3], [2, 4, 5]]
        self.assertEqual(search.repair(failed, MATRIX, DEMANDS, 10, random.Random(42)), failed)
        self.assertFalse(independent_valid(failed, DEMANDS, 10, 2))

    def test_repair_can_increase_distance_and_local_search_rolls_back(self):
        matrix = {a: {b: 0 for b in DEMANDS} for a in DEMANDS}
        matrix[2][3] = matrix[3][2] = 200
        matrix[2][5] = matrix[5][2] = 200
        repaired = search.repair(OVERLOADED, matrix, DEMANDS, 10, random.Random(42))
        self.assertTrue(independent_valid(repaired, DEMANDS, 10, 2))
        self.assertEqual(independent_distance(repaired, matrix), 200)
        returned, archived = search.local_search(
            OVERLOADED, matrix, DEMANDS, 10, 2, random.Random(42)
        )
        self.assertEqual(returned, OVERLOADED)  # Önceki cezalı maliyet 100 < 200.
        self.assertTrue(independent_valid(archived, DEMANDS, 10, 2))
        self.assertEqual(independent_distance(archived, matrix), 200)

    def test_full_round_repeats_then_stops_on_equal_cost(self):
        improved = [[1, 4], [2, 3, 5]]
        with patch.object(search, 'swap_search', side_effect=[deepcopy(improved), deepcopy(improved)]) as swapping:
            with patch.object(search, 'relocate_search', side_effect=lambda routes, *args: deepcopy(routes)):
                result, best = search.local_search(VALID, MATRIX, DEMANDS, 10, 2, random.Random(42))
        self.assertEqual(swapping.call_count, 2)
        self.assertEqual(result, improved)
        self.assertEqual(best, improved)
        result[0].append(99)
        self.assertNotIn(99, best[0])


class SolverTests(unittest.TestCase):
    def test_selection_ties_penalty_and_archive(self):
        zeros = {a: {b: 0 for b in DEMANDS} for a in DEMANDS}
        alternate = [[4, 1], [3, 5, 2]]
        chosen = solver.select(VALID, alternate, zeros, DEMANDS, 10, 2)
        self.assertEqual(chosen, VALID)
        chosen[0].append(99)
        self.assertNotIn(99, VALID[0])
        self.assertIsNone(solver.update_best_feasible(None, OVERLOADED, MATRIX, DEMANDS, 10, 2))
        best = solver.update_best_feasible(VALID, OVERLOADED, MATRIX, DEMANDS, 10, 2)
        self.assertEqual(best, VALID)
        # İhlalli aday, yeterince düşük cezalı maliyetle aramada kabul edilebilir.
        matrix = {a: {b: 0 for b in DEMANDS} for a in DEMANDS}
        matrix[2][5] = matrix[5][2] = 500
        self.assertEqual(solver.select(VALID, OVERLOADED, matrix, DEMANDS, 10, 2), OVERLOADED)

    def test_new_generation_preserves_previous_population(self):
        population = op.initialize_population(DEMANDS, 10, 2, 15, random.Random(42))
        before = deepcopy(population)
        new, best, completed = solver.next_generation(
            population, MATRIX, DEMANDS, 10, 2, 0.7, 0.7, random.Random(42)
        )
        self.assertEqual(population, before)
        self.assertEqual(len(new), 15)
        self.assertEqual(completed, 15)
        self.assertEqual(len({id(route) for individual in new for route in individual}), 30)
        self.assertTrue(independent_valid(best, DEMANDS, 10, 2))
        for old, chosen in zip(population, new):
            old_score = independent_distance(old, MATRIX) + (0 if independent_valid(old, DEMANDS, 10, 2) else 100)
            new_score = independent_distance(chosen, MATRIX) + (0 if independent_valid(chosen, DEMANDS, 10, 2) else 100)
            self.assertLessEqual(new_score, old_score)

    def test_pilot_matches_exhaustive_tiny_oracle_and_repeats(self):
        feasible_distances = []
        for order in permutations([1, 2, 3, 4, 5]):
            for cut in range(6):
                routes = [list(order[:cut]), list(order[cut:])]
                if independent_valid(routes, DEMANDS, 10, 2):
                    feasible_distances.append(independent_distance(routes, MATRIX))
        optimum = min(feasible_distances)
        self.assertEqual(optimum, 29)
        first = solver.solve(MATRIX, DEMANDS, 10, 2, max_generations=20, seed=42)
        second = solver.solve(MATRIX, DEMANDS, 10, 2, max_generations=20, seed=42)
        self.assertEqual(first['distance'], optimum)
        self.assertTrue(independent_valid(first['best_routes'], DEMANDS, 10, 2))
        self.assertEqual(independent_distance(first['best_routes'], MATRIX), first['distance'])
        for result in (first, second):
            self.assertGreaterEqual(result.pop('elapsed_seconds'), 0)
        self.assertEqual(first, second)
        self.assertEqual(first['generations'], 20)
        self.assertEqual(first['stop_reason'], 'max_generations')

    def test_zero_generations_and_initial_optimum(self):
        matrix = {0: {0: 0, 1: 3}, 1: {0: 3, 1: 0}}
        demands = {0: 0, 1: 1}
        result = solver.solve(matrix, demands, 1, 1, max_generations=0, known_optimum=6)
        self.assertEqual(result['distance'], 6)
        self.assertEqual(result['generations'], 0)
        self.assertEqual(result['stop_reason'], 'known_optimum')
        result = solver.solve(matrix, demands, 1, 1, max_generations=0)
        self.assertEqual(result['stop_reason'], 'max_generations')

    def test_mid_generation_optimum_is_not_counted_as_full_generation(self):
        improved = [[1, 4], [2, 3, 5]]
        initial = [deepcopy(VALID) for _ in range(3)]
        with patch.object(solver, 'initialize_population', return_value=initial):
            with patch.object(solver, 'mutate', side_effect=lambda *args: deepcopy(VALID)):
                with patch.object(solver, 'crossover_exp', side_effect=lambda *args: deepcopy(VALID)):
                    with patch.object(solver, 'local_search', return_value=(improved, improved)):
                        result = solver.solve(MATRIX, DEMANDS, 10, 2, population_size=3, known_optimum=29)
        self.assertEqual(result['stop_reason'], 'known_optimum')
        self.assertEqual(result['generations'], 0)
        self.assertEqual(result['partial_generation_targets'], 1)
        self.assertEqual(result['distance'], 29)

    def test_no_feasible_solution(self):
        demands = {0: 0, 1: 6, 2: 6, 3: 6, 4: 6, 5: 6}
        result = solver.solve(MATRIX, demands, 10, 3, max_generations=3)
        self.assertIsNone(result['best_routes'])
        self.assertIsNone(result['distance'])
        self.assertFalse(result['feasible'])
        self.assertEqual(result['stop_reason'], 'max_generations')

    def test_invalid_configuration(self):
        for options in [dict(mutation_factor=0), dict(crossover_rate=2), dict(penalty=-1),
                        dict(max_generations=-1), dict(seed=None), dict(known_optimum=-1),
                        dict(population_size=2)]:
            with self.subTest(options=options):
                with self.assertRaises(ValueError):
                    solver.solve(MATRIX, DEMANDS, 10, 2, **options)
        bad_matrix = deepcopy(MATRIX)
        bad_matrix[0][1] += 1
        with self.assertRaises(ValueError):
            solver.solve(bad_matrix, DEMANDS, 10, 2)

    def test_imports_do_not_print_or_start_pilot(self):
        src = str(Path(__file__).resolve().parents[1] / 'src')
        command = ('import sys; sys.path.insert(0, ' + repr(src)
                   + '); import problem, operators, local_search, solver')
        result = subprocess.run([sys.executable, '-B', '-c', command],
                                capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout, '')
        self.assertEqual(result.stderr, '')


if __name__ == '__main__':
    unittest.main()
