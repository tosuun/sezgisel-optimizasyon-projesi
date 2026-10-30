"""Çoklu tekrar istatistikleri, bağımsız denetim ve makale tablo anlamları."""

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
spec = importlib.util.spec_from_file_location('analysis_tool', ROOT / 'tools/analiz.py')
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)
from instance_io import read_instance, read_solution
from problem import solution_distance
import run_experiments as batch


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.config = analysis.read_json(ROOT / 'configs/dogrulama.json')
        self.config.update(profile_id='analysis_fixture', instances=['P-n16-k8', 'A-n32-k5'],
                           instance_count=2, group_counts={'P': 1, 'A': 1}, seeds=[42, 43, 44],
                           repeat_count=3, planned_run_count=6, time_limit_seconds=120,
                           max_generations_by_group={group: 20 for group in 'ABPEFM'})
        self.path = self.directory / 'fixture.json'
        self.path.write_text(json.dumps(self.config))
        # Yalnız plan hazırlanır; çözücü çalıştırılmaz. Sonuçlar bilinen referanslardan kurulur.
        prepared = batch.prepare_experiment(self.path, project_root=ROOT, output_root=self.directory)
        self.experiment = prepared['directory']
        self.experiment.mkdir()
        metadata = {'experiment_id': prepared['experiment_id'], 'identity': prepared['identity'],
                    'config': self.config, 'environment': prepared['environment']}
        (self.experiment / 'metadata.json').write_text(json.dumps(metadata))
        for name, seed in prepared['jobs']:
            instance, reference, _ = prepared['loaded'][name]
            entry = prepared['entries'][name]
            routes = deepcopy(reference['routes'])
            # İkinci tohumda bir rota içindeki sırayı değiştir; müşteri ve yük korunur.
            if seed == 43:
                route = next((route for route in routes if len(route) >= 3), None)
                if route:
                    route[0], route[1] = route[1], route[0]
            distance = solution_distance(routes, instance['distances'])
            parameters = dict(population_size=3 * entry['n_customers'],
                              mutation_factor=self.config['algorithm']['mutation_factor'],
                              crossover_rate=self.config['algorithm']['crossover_rate'],
                              penalty=self.config['algorithm']['penalty'], max_generations=20,
                              time_limit_seconds=120, known_optimum=entry['reference_cost'])
            if self.config['algorithm'].get('implementation_protocol'):
                parameters['implementation_protocol'] = self.config['algorithm']['implementation_protocol']
            record = {
                'run_identity': {'experiment_identity_sha256': analysis.digest(prepared['identity']),
                                 'name': name, 'seed': seed, 'instance_sha256': entry['vrp_sha256'],
                                 'solution_sha256': entry['sol_sha256']},
                'instance': {'name': name}, 'profile_id': self.config['profile_id'],
                'status': 'completed', 'gap_percent': analysis.percentage_gap(distance, entry['reference_cost']),
                'result': {'best_routes': routes, 'distance': distance, 'feasible': True, 'seed': seed,
                           'elapsed_seconds': seed - 40, 'stop_reason': 'max_generations',
                           'generations': 20, 'partial_generation_targets': 0, 'parameters': parameters},
            }
            run_directory = self.experiment / 'runs' / f'{name}_seed{seed}'
            run_directory.mkdir(parents=True)
            (run_directory / 'result.json').write_text(json.dumps(record))

    def result_path(self, name='A-n32-k5', seed=43):
        return self.experiment / 'runs' / f'{name}_seed{seed}' / 'result.json'

    def test_best_average_sample_sd_and_optimum_counts(self):
        data = analysis.analyze(self.experiment)
        self.assertEqual(data['summary']['run_count'], 6)
        row = next(row for row in data['instances'] if row['name'] == 'A-n32-k5')
        distances = [analysis.read_json(self.result_path(seed=seed))['result']['distance'] for seed in [42, 43, 44]]
        expected_average = sum(distances) / 3
        expected_sd = (sum((value - expected_average) ** 2 for value in distances) / 2) ** .5
        self.assertEqual(row['best'], 784)
        self.assertEqual(row['avg'], expected_average)
        self.assertAlmostEqual(row['std'], expected_sd)
        self.assertGreater(row['std'], 0)
        self.assertEqual(row['optimum_runs'], 2)
        self.assertFalse(row['all_optimum'])
        table = analysis.comparison_tables(data)
        self.assertIn('| A | 1/1 | 1/1 | 0/1 | 1/1 |', table)
        self.assertIn('3 tekrar', table)
        for field in ['gap_best', 'gap_avg']:
            self.assertEqual(sum(interval[field] for interval in data['histogram']), 2)

    def test_incomplete_experiment_refused(self):
        self.result_path().unlink()
        with self.assertRaisesRegex(ValueError, '5/6'):
            analysis.analyze(self.experiment)

    def test_mixed_experiment_refused(self):
        path = self.result_path()
        record = analysis.read_json(path)
        record['run_identity']['experiment_identity_sha256'] = 'wrong'
        path.write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError, 'başka bir deneye'):
            analysis.analyze(self.experiment)

    def test_wrong_distance_refused(self):
        path = self.result_path()
        record = analysis.read_json(path)
        record['result']['distance'] += 1
        path.write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError, 'mesafesi'):
            analysis.analyze(self.experiment)

    def test_no_feasible_solution_is_counted_not_silently_dropped(self):
        path = self.result_path()
        record = analysis.read_json(path)
        record.update(status='no_feasible_solution', gap_percent=None)
        record['result'].update(best_routes=None, distance=None, feasible=False)
        path.write_text(json.dumps(record))
        data = analysis.analyze(self.experiment)
        row = next(row for row in data['instances'] if row['name'] == 'A-n32-k5')
        self.assertEqual(row['valid_runs'], 2)
        self.assertEqual(row['best'], 784)
        self.assertIsNone(row['avg'])
        self.assertIsNone(row['std'])
        self.assertIsNone(data['summary']['mean_gap_avg'])
        self.assertEqual(data['summary']['no_feasible_solution_runs'], 1)
        self.assertEqual(data['histogram'][-1]['gap_avg'], 1)

    def test_time_label_uses_config_and_no_limit_is_supported(self):
        data = analysis.analyze(self.experiment)
        for limit, expected in [(37, '37 s (yumuşak)'), (None, 'Sınır yok')]:
            data['config']['time_limit_seconds'] = limit
            self.assertIn(expected, analysis.comparison_tables(data))

    def test_paper_budget_and_cpu_table_column_counts_are_reported_correctly(self):
        self.assertTrue(analysis.paper_budget_matches(analysis.read_json(ROOT/'configs/dogrulama.json')))
        data = analysis.analyze(self.experiment)
        self.assertFalse(analysis.paper_budget_matches(data['config']))
        text = analysis.comparison_tables(data)
        self.assertIn('sınırlı bütçeli ön deney', text)
        for line in text.split('## Tablo 12')[1].splitlines():
            if line.startswith('|'):
                self.assertEqual(line.count('|'), 6)
        data['config'].update(repeat_count=10,time_limit_seconds=None,
                             max_generations_by_group={group:500000 if group=='M' else 200000 for group in 'ABPEFM'})
        text = analysis.comparison_tables(data)
        self.assertIn('Her iki tarafta da problem başına 10 tekrar', text)
        self.assertIn('bildirilen deney bütçesiyle eşleştirilmiştir', text)
        self.assertNotIn('bu sınırlı bütçeli ön deney', text)


if __name__ == '__main__':
    unittest.main()
