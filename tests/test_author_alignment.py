"""Sabit yazar kodundan üretilmiş çıktılarla bağımsız davranış denetimi."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import local_search as search
import operators
import solver
from problem import build_distance_matrix, evaluate


class ControlledRandom:
    """C test çağırıcısıyla aynı ham sayılar; üretimde Python Random kullanılır."""
    def __init__(self, seed):
        self.state, self.calls = seed, 0

    def next(self):
        self.calls += 1
        self.state = (1664525 * self.state + 1013904223) & 0xffffffff
        return self.state & 2147483647

    def getstate(self):
        return self.state, self.calls

    def setstate(self, state):
        self.state, self.calls = state

    def randrange(self, stop):
        return self.next() % stop

    def random(self):
        return self.next() / 2147483647


class AuthorAlignmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = json.loads((ROOT / 'tests/fixtures/author_cases.json').read_text())

    def test_400_local_operator_cases_match_compiled_author_code(self):
        for case in self.cases['local']:
            with self.subTest(seed=case['seed'], mode=case['mode']):
                coordinates = {int(key): value for key, value in case['coordinates'].items()}
                demands = {int(key): value for key, value in case['demands'].items()}
                distances = build_distance_matrix(coordinates)
                before = deepcopy(case['routes'])
                rng = ControlledRandom(case['seed'])
                args = (case['routes'], distances, demands, case['capacity'])
                if case['mode'] == 0:
                    result = search.swap_search(*args)
                elif case['mode'] == 1:
                    result = search.relocate_search(*args)
                elif case['mode'] == 2:
                    result = search.repair(*args, rng)
                else:
                    result = search.local_search(*args, len(before), rng)[0]
                self.assertEqual(result, case['expected_routes'])
                self.assertEqual(evaluate(result, distances, demands, case['capacity'], len(before))['cost'], case['expected_cost'])
                self.assertEqual(rng.calls, case['rng_calls'])
                self.assertEqual(case['routes'], before)

    def test_160_population_mutation_crossover_and_generation_cases(self):
        for case in self.cases['operators']:
            with self.subTest(seed=case['seed'], mode=case['mode']):
                coordinates = {int(key): value for key, value in case['coordinates'].items()}
                demands = {int(key): value for key, value in case['demands'].items()}
                distances = build_distance_matrix(coordinates)
                population = deepcopy(case['population'])
                rng = ControlledRandom(case['seed'])
                if case['mode'] == 4:
                    result = [operators.initialize_individual(demands, case['capacity'], 3, rng)]
                elif case['mode'] == 5:
                    result = [operators.mutate(population, 0, .7, rng)]
                elif case['mode'] == 6:
                    result = [operators.crossover_exp(population[0], population[1], .7, rng)]
                else:
                    result = solver.next_generation(population, distances, demands, case['capacity'], 3, .7, .7, rng)[0]
                self.assertEqual(result, case['expected'])
                self.assertEqual(rng.calls, case['rng_calls'])
                self.assertEqual(rng.state, case['rng_state'])
                self.assertEqual(population, case['population'])

    def test_initialization_finishes_when_early_route_contains_every_customer(self):
        routes = operators.initialize_individual({0: 0, 1: 1}, 10, 4, ControlledRandom(1))
        self.assertEqual(sorted(c for route in routes for c in route), [1])
        self.assertEqual(len(routes), 4)

    def test_repair_finishes_when_even_zero_demand_has_no_valid_target(self):
        routes = [[1,2], [3,4]]
        demands = {0:0, 1:0, 2:20, 3:0, 4:20}
        distances = {i:{j:int(i != j) for j in demands} for i in demands}
        self.assertEqual(search.repair(routes, distances, demands, 10, ControlledRandom(1)), routes)

    def test_no_mutant_or_intermediate_plan_is_archived_before_selection(self):
        from unittest.mock import patch
        matrix = {i:{j:0 for j in range(3)} for i in range(3)}
        demands = {0:0,1:1,2:1}
        target = [[1,2]]
        population = [deepcopy(target) for _ in range(4)]
        with patch.object(solver,'mutate',return_value=[[2,1]]), patch.object(solver,'crossover_exp',return_value=[[2,1]]), patch.object(solver,'local_search',return_value=(target,[[2,1]])):
            chosen, best, _ = solver._advance_target(population,0,matrix,demands,10,1,.7,.7,ControlledRandom(1),100,None,None)
        self.assertEqual(chosen,target)
        self.assertEqual(best,target)

    def test_solver_commits_complete_generation_matching_c_reference(self):
        from unittest.mock import patch
        for case in self.cases['operators']:
            if case['mode'] != 7:
                continue
            with self.subTest(seed=case['seed']):
                coordinates = {int(key): value for key, value in case['coordinates'].items()}
                demands = {int(key): value for key, value in case['demands'].items()}
                distances = build_distance_matrix(coordinates)
                saved = []
                with patch.object(solver,'initialize_population',return_value=deepcopy(case['population'])), patch.object(solver.random,'Random',ControlledRandom):
                    result = solver.solve(distances,demands,case['capacity'],3,
                                          population_size=len(case['population']),max_generations=1,
                                          seed=case['seed'],checkpoint_callback=saved.append)
                self.assertEqual(saved[-1]['population'],case['expected'])
                self.assertEqual(saved[-1]['rng_state'],(case['rng_state'],case['rng_calls']))
                self.assertEqual(result['generations'],1)
                self.assertEqual(result['partial_generation_targets'],0)
