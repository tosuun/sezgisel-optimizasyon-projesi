"""CVRPLIB okuyucu, kimlik eşleme ve bağımsız referans kontrolleri."""

from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from instance_io import read_instance, read_solution
from problem import distance
import run_pilot


SMALL = '''NAME : custom
TYPE : CVRP
DIMENSION : 3
EDGE_WEIGHT_TYPE : EUC_2D
CAPACITY : 10
VEHICLES : 2
NODE_COORD_SECTION
99 0 4
42 0 0
7 0.5 0
DEMAND_SECTION
7 3
99 4
42 0
DEPOT_SECTION
42
-1
EOF
'''


class InstanceIOTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'custom.vrp'
        self.path.write_text(SMALL)
        self.solution = Path(self.temp.name) / 'custom.sol'
        self.solution.write_text('Route #1: 1 2\nCost 9\n')

    def test_official_reference_instances(self):
        for name, nodes, customers, vehicles, capacity, cost in [
            ('P-n16-k8', 16, 15, 8, 35, 450),
            ('A-n32-k5', 32, 31, 5, 100, 784),
        ]:
            with self.subTest(name=name):
                instance = read_instance(ROOT / 'data' / (name + '.vrp'))
                self.assertEqual((instance['dimension'], instance['n_customers'],
                                  instance['max_vehicles'], instance['capacity']),
                                 (nodes, customers, vehicles, capacity))
                reference = read_solution(ROOT / 'data' / (name + '.sol'), instance)
                self.assertEqual(reference['recomputed_cost'], cost)
                audit = run_pilot.audit_solution(reference['routes'], instance)
                self.assertTrue(audit['valid'])
                self.assertEqual(audit['distance'], cost)

    def test_arbitrary_depot_and_unsorted_original_ids(self):
        instance = read_instance(self.path)
        self.assertEqual(instance['original_depot_id'], 42)
        self.assertEqual(instance['original_to_internal'], {42: 0, 7: 1, 99: 2})
        self.assertEqual(instance['demands'], {0: 0, 1: 3, 2: 4})
        self.assertEqual(instance['distances'][0][1], 1)
        self.assertEqual(instance['dimension'], instance['n_customers'] + 1)

    def test_explicit_solution_id_conventions(self):
        instance = read_instance(self.path)
        self.assertEqual(read_solution(self.solution, instance)['routes'], [[1, 2]])
        self.solution.write_text('Route #1: 7 99\nCost 9\n')
        self.assertEqual(read_solution(self.solution, instance, 'original')['routes'], [[1, 2]])
        with self.assertRaises(ValueError):
            read_solution(self.solution, instance)
        with self.assertRaises(ValueError):
            read_solution(self.solution, instance, 'auto')

    def test_original_customer_zero_is_not_confused_with_internal_depot(self):
        self.path.write_text(SMALL.replace('7 0.5 0', '0 0.5 0').replace('7 3', '0 3'))
        instance = read_instance(self.path)
        self.solution.write_text('Route #1: 0 99\nCost 9\n')
        self.assertEqual(read_solution(self.solution, instance, 'original')['routes'], [[1, 2]])

    def test_rounding_is_half_up_not_python_bankers_rounding(self):
        coords = {0: (0, 0), 1: (0.5, 0), 2: (2.5, 0)}
        self.assertEqual(distance(0, 1, coords), 1)
        self.assertEqual(distance(0, 2, coords), 3)

    def test_vehicle_count_must_be_given_or_explicitly_encoded(self):
        self.path.write_text(SMALL.replace('VEHICLES : 2\n', ''))
        with self.assertRaises(ValueError):
            read_instance(self.path)
        self.assertEqual(read_instance(self.path, max_vehicles=2)['max_vehicles'], 2)
        self.path.write_text(SMALL.replace('NAME : custom', 'NAME : custom-k3'))
        with self.assertRaises(ValueError):
            read_instance(self.path)
        self.path.write_text(SMALL)
        with self.assertRaises(ValueError):
            read_instance(self.path, max_vehicles=3)

    def test_unsupported_problem_and_distance_types_are_rejected(self):
        for original, replacement in [('TYPE : CVRP', 'TYPE : VRPTW'),
                                      ('EUC_2D', 'GEO'), ('EUC_2D', 'EXPLICIT')]:
            self.path.write_text(SMALL.replace(original, replacement))
            with self.assertRaises(ValueError):
                read_instance(self.path)

    def test_bad_node_and_demand_data_are_rejected(self):
        cases = [SMALL.replace('DIMENSION : 3', 'DIMENSION : 4'),
                 SMALL.replace('99 0 4', '42 0 4'),
                 SMALL.replace('7 3', '7 -3'),
                 SMALL.replace('7 3', '7 11'),
                 SMALL.replace('42 0\nDEPOT_SECTION', '42 1\nDEPOT_SECTION'),
                 SMALL.replace('7 0.5 0', '7 nan 0'),
                 SMALL.replace('7 3', '8 3')]
        for text in cases:
            self.path.write_text(text)
            with self.assertRaises(ValueError):
                read_instance(self.path)

    def test_single_depot_and_terminator_are_required(self):
        for text in [SMALL.replace('42\n-1', '42\n7\n-1'),
                     SMALL.replace('42\n-1', '42'),
                     SMALL.replace('42\n-1', '123\n-1')]:
            self.path.write_text(text)
            with self.assertRaises(ValueError):
                read_instance(self.path)

    def test_bad_reference_coverage_and_cost_are_rejected(self):
        instance = read_instance(self.path)
        for text in ['Route #1: 1\nCost 2\n',
                     'Route #1: 1 1 2\nCost 9\n',
                     'Route #1: 0 1 2\nCost 9\n',
                     'Route #1: 1 2\nCost 8\n',
                     'Route #1: 1 2\n',
                     'Route #1: 1\nRoute #1: 2\nCost 8\n']:
            self.solution.write_text(text)
            with self.assertRaises(ValueError):
                read_solution(self.solution, instance)

    def test_comment_best_value_is_not_used_as_optimum(self):
        self.path.write_text(SMALL.replace('TYPE : CVRP', 'COMMENT : Best value: 12345\nTYPE : CVRP'))
        instance = read_instance(self.path)
        self.assertEqual(read_solution(self.solution, instance)['reported_cost'], 9)

    def test_independent_audit_reports_coverage_capacity_and_vehicles(self):
        instance = read_instance(self.path)
        self.assertTrue(run_pilot.audit_solution([[1, 2]], instance)['valid'])
        self.assertFalse(run_pilot.audit_solution([[1]], instance)['valid'])
        self.assertFalse(run_pilot.audit_solution([[1, 2, 99]], instance)['valid'])
        altered = deepcopy(instance)
        altered['capacity'] = 5
        self.assertFalse(run_pilot.audit_solution([[1, 2]], altered)['valid'])
        altered['max_vehicles'] = 1
        self.assertFalse(run_pilot.audit_solution([[1], [2]], altered)['valid'])

    def test_pilot_records_reference_and_original_ids(self):
        instance = read_instance(self.path)
        fake = {'best_routes': [[1, 2]], 'distance': 9, 'feasible': True}
        with patch.object(run_pilot, 'solve', return_value=fake):
            record = run_pilot.run_pilot(self.path, self.solution, max_generations=0)
        self.assertEqual(record['reference']['reported_cost'], 9)
        self.assertEqual(record['gap_percent'], 0)
        self.assertEqual(record['best_routes_original_node_ids'], [[7, 99]])
        self.assertEqual(len(record['source_sha256']), 6)

    def test_actual_small_reference_pilot(self):
        record = run_pilot.run_pilot(
            ROOT / 'data' / 'P-n16-k8.vrp', ROOT / 'data' / 'P-n16-k8.sol',
            max_generations=5, seed=42, known_optimum=450,
        )
        self.assertEqual(record['result']['distance'], 450)
        self.assertTrue(record['independent_audit']['valid'])
        self.assertEqual(record['gap_percent'], 0)
        self.assertEqual(record['result']['stop_reason'], 'known_optimum')

    def test_pilot_below_asserted_optimum_or_wrong_cost_is_error(self):
        fake = {'best_routes': [[1], [2]], 'distance': 8, 'feasible': True}
        with patch.object(run_pilot, 'solve', return_value=fake):
            with self.assertRaises(ValueError):
                run_pilot.run_pilot(self.path, self.solution, known_optimum=9)
        fake = {'best_routes': [[1, 2]], 'distance': 1, 'feasible': True}
        with patch.object(run_pilot, 'solve', return_value=fake):
            with self.assertRaises(ValueError):
                run_pilot.run_pilot(self.path, self.solution)


if __name__ == '__main__':
    unittest.main()
