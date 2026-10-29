"""Süre sınırı, gerçek ara-kayıt devamı ve dosya tabanlı toplu deney kontrolleri."""

from copy import deepcopy
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

import run_experiments as batch
import solver
from problem import build_distance_matrix


COORDS = {0:(0,0), 1:(3,0), 2:(0,4), 3:(3,4), 4:(6,0), 5:(6,4)}
DEMANDS = {0:0, 1:6, 2:3, 3:5, 4:4, 5:2}
MATRIX = build_distance_matrix(COORDS)


class SolverControlTests(unittest.TestCase):
    def test_zero_time_limit_keeps_initial_best_and_saves_finished_state(self):
        saved = []
        result = solver.solve(MATRIX, DEMANDS, 10, 2, time_limit_seconds=0,
                              checkpoint_callback=saved.append)
        self.assertEqual(result['stop_reason'], 'time_limit')
        self.assertEqual(result['generations'], 0)
        self.assertTrue(result['feasible'])
        self.assertEqual(saved[-1]['status'], 'finished')
        self.assertEqual(saved[-1]['best_routes'], result['best_routes'])

    def test_json_checkpoint_resume_reproduces_population_and_rng(self):
        saved, cancelled = [], {'value': False}
        def progress(state):
            if state['partial_generation_targets'] == 3:
                cancelled['value'] = True
        partial = solver.solve(MATRIX, DEMANDS, 10, 2, max_generations=3,
                               checkpoint_callback=saved.append, checkpoint_interval_seconds=0,
                               cancel_requested=lambda: cancelled['value'], progress_callback=progress)
        self.assertEqual(partial['stop_reason'], 'interrupted')
        self.assertEqual(partial['partial_generation_targets'], 3)
        json_checkpoint = json.loads(json.dumps(saved[-1]))
        resumed_states, complete_states = [], []
        resumed = solver.solve(MATRIX, DEMANDS, 10, 2, max_generations=3,
                               resume_state=json_checkpoint, checkpoint_callback=resumed_states.append)
        complete = solver.solve(MATRIX, DEMANDS, 10, 2, max_generations=3,
                                checkpoint_callback=complete_states.append)
        self.assertEqual(resumed['best_routes'], complete['best_routes'])
        self.assertEqual(resumed['distance'], complete['distance'])
        for field in ['population','new_population','next_target','rng_state','best_routes','generations']:
            self.assertEqual(json.loads(json.dumps(resumed_states[-1][field])),
                             json.loads(json.dumps(complete_states[-1][field])))
        self.assertTrue(resumed['resumed_from_checkpoint'])

    def test_resume_refuses_different_problem_parameters_and_identity(self):
        saved = []
        solver.solve(MATRIX, DEMANDS, 10, 2, max_generations=2,
                     cancel_requested=lambda: True, checkpoint_callback=saved.append,
                     checkpoint_identity='first')
        for options in [dict(seed=99), dict(max_generations=3), dict(checkpoint_identity='second')]:
            kwargs = dict(max_generations=2, checkpoint_identity='first')
            kwargs.update(options)
            with self.assertRaises(ValueError):
                solver.solve(MATRIX, DEMANDS, 10, 2, resume_state=saved[-1], **kwargs)
        changed = deepcopy(MATRIX)
        changed[0][1] = changed[1][0] = MATRIX[0][1] + 1
        with self.assertRaises(ValueError):
            solver.solve(changed, DEMANDS, 10, 2, max_generations=2,
                         checkpoint_identity='first', resume_state=saved[-1])

    def test_terminal_checkpoint_does_not_restart_search(self):
        saved = []
        result = solver.solve(MATRIX, DEMANDS, 10, 2, time_limit_seconds=0,
                              checkpoint_callback=saved.append)
        with patch.object(solver, '_advance_target', side_effect=AssertionError('Yeniden arama yapılmamalı')):
            resumed = solver.solve(MATRIX, DEMANDS, 10, 2, time_limit_seconds=0, resume_state=saved[-1])
        self.assertEqual(resumed['best_routes'], result['best_routes'])
        self.assertEqual(resumed['elapsed_seconds'], result['elapsed_seconds'])
        self.assertEqual(resumed['stop_reason'], 'time_limit')

    def test_keyboard_interrupt_restarts_only_uncommitted_target(self):
        saved = []
        def interrupt_after_random_work(*args):
            for _ in range(10):
                args[8].random()
            raise KeyboardInterrupt
        with patch.object(solver, '_advance_target', side_effect=interrupt_after_random_work):
            partial = solver.solve(MATRIX, DEMANDS, 10, 2, max_generations=1,
                                   checkpoint_callback=saved.append)
        self.assertEqual(partial['stop_reason'], 'interrupted')
        self.assertEqual(saved[-1]['next_target'], 0)
        resumed = solver.solve(MATRIX, DEMANDS, 10, 2, max_generations=1, resume_state=saved[-1])
        complete = solver.solve(MATRIX, DEMANDS, 10, 2, max_generations=1)
        self.assertEqual(resumed['best_routes'], complete['best_routes'])

    def test_soft_timeout_finishes_target_and_records_overshoot(self):
        clock = {'value':0}
        advance = solver._advance_target
        def slow_target(*args):
            outcome = advance(*args)
            clock['value'] = 2
            return outcome
        saved=[]
        with patch.object(solver.time,'perf_counter',side_effect=lambda:clock['value']):
            with patch.object(solver,'_advance_target',side_effect=slow_target):
                result=solver.solve(MATRIX,DEMANDS,10,2,time_limit_seconds=1,
                                    checkpoint_callback=saved.append)
        self.assertEqual(result['stop_reason'],'time_limit')
        self.assertEqual(result['partial_generation_targets'],1)
        self.assertEqual(result['time_limit_overshoot_seconds'],1)
        self.assertEqual(saved[-1]['best_routes'],result['best_routes'])

    def test_cumulative_active_time_budget_survives_resume(self):
        saved = []
        solver.solve(MATRIX, DEMANDS, 10, 2, time_limit_seconds=100,
                     cancel_requested=lambda: True, checkpoint_callback=saved.append)
        state = deepcopy(saved[-1])
        state['elapsed_seconds'] = 101
        with patch.object(solver, '_advance_target', side_effect=AssertionError('Bütçe zaten bitti')):
            result = solver.solve(MATRIX, DEMANDS, 10, 2, time_limit_seconds=100, resume_state=state)
        self.assertEqual(result['stop_reason'], 'time_limit')
        self.assertGreaterEqual(result['elapsed_seconds'], 101)
        self.assertGreaterEqual(result['time_limit_overshoot_seconds'], 1)


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/'configs').mkdir()
        (self.root/'data').mkdir()
        entry = next(item for item in json.loads((ROOT/'data/paper90_instances.json').read_text())['instances']
                     if item['name'] == 'P-n16-k8')
        self.entry = deepcopy(entry)
        for ext, field in [('vrp','instance_path'),('sol','solution_path')]:
            name = 'P-n16-k8.' + ext
            (self.root/'data'/name).write_bytes((ROOT/entry[field]).read_bytes())
            self.entry[field] = 'data/' + name
        (self.root/'data/manifest.json').write_text(json.dumps({'instances':[self.entry]}))
        self.config = {
            'schema_version':1, 'profile_id':'g_test', 'purpose':'development_tests_only',
            'instance_manifest':'data/manifest.json', 'instances':['P-n16-k8'],
            'seeds':[0,1], 'instance_count':1, 'repeat_count':2, 'planned_run_count':2,
            'group_counts':{'P':1},
            'algorithm':{'strategy':'rand/1/exp','population_size_rule':'3 * n_customers_excluding_depot',
                         'distance_rule':'floor(euclidean_distance + 0.5)', 'mutation_factor':0.7,
                         'crossover_rate':0.7,'penalty':100,'parameter_grid_search':False},
            'known_optimum_early_stop':True,'solution_id_convention':'cvrplib',
            'max_generations_by_group':{'P':2}, 'time_limit_seconds':1,
            'checkpoint_interval_seconds':0, 'execution_ready':True,
            'source_baseline_sha256':batch.source_hashes(),
        }
        self.path = self.root/'configs/test.json'
        self.write_config()

    def write_config(self):
        self.path.write_text(json.dumps(self.config))

    def test_plan_is_read_only(self):
        result = batch.run_experiment(self.path)
        self.assertEqual(result['mode'], 'plan_only')
        self.assertEqual(result['planned_runs'], 2)
        self.assertEqual(result['preflight_errors'], [])
        self.assertFalse((self.root/'results').exists())

    def test_execute_resume_and_do_not_overwrite_completed_records(self):
        first = batch.run_experiment(self.path, execute=True, max_runs=1)
        self.assertEqual(first['terminal_runs'], 1)
        self.assertEqual(first['pending_runs'], 1)
        second = batch.run_experiment(self.path, execute=True)
        self.assertEqual(second['terminal_runs'], 2)
        self.assertEqual(second['executed_this_invocation'], 1)
        directory = Path(second['output_directory'])
        records = {path: path.read_bytes() for path in directory.glob('runs/*/result.json')}
        with patch.object(batch, 'solve', side_effect=AssertionError('Tamamlananlar atlanmalı')):
            third = batch.run_experiment(self.path, execute=True)
        self.assertEqual(third['skipped_completed'], 2)
        self.assertEqual(third['executed_this_invocation'], 0)
        self.assertTrue(all(path.read_bytes()==data for path,data in records.items()))
        for path in records:
            record = json.loads(path.read_text())
            self.assertTrue(record['independent_audit']['valid'])
            self.assertTrue((path.parent/record['metadata_file']).resolve().exists())
        self.assertFalse((directory/'lock.json').exists())

    def test_interrupted_attempt_is_kept_and_resumed(self):
        self.config['known_optimum_early_stop'] = False
        self.config['time_limit_seconds'] = 10
        self.write_config()
        stop = {'value':False}
        def progress(value):
            if value['partial_generation_targets'] == 2:
                stop['value'] = True
        partial = batch.run_experiment(self.path, execute=True, max_runs=1,
                                       cancel_requested=lambda:stop['value'], progress_callback=progress)
        directory = Path(partial['output_directory'])/'runs/P-n16-k8_seed0'
        self.assertFalse((directory/'result.json').exists())
        self.assertEqual(json.loads((directory/'attempt_0001.json').read_text())['status'],'interrupted')
        state = json.loads((directory/'checkpoint.json').read_text())['solver_state']
        self.assertEqual(state['next_target'], 2)
        completed = batch.run_experiment(self.path, execute=True, max_runs=1)
        result = json.loads((directory/'result.json').read_text())
        self.assertTrue(result['result']['resumed_from_checkpoint'])
        self.assertEqual(result['result']['generations'], 2)
        self.assertTrue((directory/'attempt_0001.json').exists())
        self.assertTrue((directory/'attempt_0002.json').exists())

    def test_error_is_saved_and_requires_explicit_retry(self):
        with patch.object(batch, 'solve', side_effect=ValueError('deneme hatası')):
            failed = batch.run_experiment(self.path, execute=True)
        self.assertEqual(failed['status'], 'error')
        directory = Path(failed['output_directory'])/'runs/P-n16-k8_seed0'
        attempt = json.loads((directory/'attempt_0001.json').read_text())
        self.assertEqual(attempt['error_type'],'ValueError')
        self.assertFalse((directory/'result.json').exists())
        blocked = batch.run_experiment(self.path, execute=True)
        self.assertEqual(blocked['status'], 'previous_error_requires_retry')
        retried = batch.run_experiment(self.path, execute=True, retry_errors=True, max_runs=1)
        self.assertEqual(retried['terminal_runs'], 1)
        self.assertTrue((directory/'attempt_0002.json').exists())

    def test_invalid_final_cost_aborts_batch(self):
        instance = batch.prepare_experiment(self.path)['loaded']['P-n16-k8'][0]
        reference_routes = batch.prepare_experiment(self.path)['loaded']['P-n16-k8'][1]['routes']
        fake = {'best_routes':reference_routes,'distance':1,'feasible':True,'stop_reason':'known_optimum'}
        with patch.object(batch,'solve',return_value=fake):
            summary = batch.run_experiment(self.path,execute=True)
        self.assertEqual(summary['status'],'error')
        self.assertEqual(summary['terminal_runs'],0)
        self.assertEqual(summary['executed_this_invocation'],1)

    def test_no_feasible_solution_is_preserved_as_terminal_run(self):
        fake = {'best_routes':None,'distance':None,'feasible':False,'stop_reason':'max_generations'}
        with patch.object(batch,'solve',return_value=fake):
            summary = batch.run_experiment(self.path,execute=True)
        self.assertEqual(summary['terminal_runs'],2)
        self.assertEqual(summary['no_feasible_solution_runs'],2)
        self.assertEqual(summary['valid_runs'],0)

    def test_tampered_data_fail_preflight_and_are_logged(self):
        with (self.root/'data/P-n16-k8.vrp').open('a') as file:
            file.write('\n')
        with patch.object(batch,'solve',side_effect=AssertionError('Veri geçmeden çözme')):
            summary = batch.run_experiment(self.path,execute=True)
        self.assertEqual(summary['status'],'preflight_failed')
        self.assertTrue((Path(summary['output_directory'])/'preflight.json').exists())

    def test_changed_config_or_environment_has_separate_identity(self):
        original = batch.prepare_experiment(self.path)
        self.config['algorithm']['mutation_factor']=0.5
        self.write_config()
        changed = batch.prepare_experiment(self.path)
        self.assertNotEqual(original['experiment_id'],changed['experiment_id'])
        with patch.object(batch,'environment',return_value={'different':'environment'}):
            other = batch.prepare_experiment(self.path)
        self.assertNotEqual(changed['experiment_id'],other['experiment_id'])

    def test_stale_source_and_unready_profile_are_refused(self):
        self.config['source_baseline_sha256']['solver.py']='wrong'
        self.write_config()
        with self.assertRaises(batch.ValidationFailure):
            batch.run_experiment(self.path,execute=True)
        self.config['source_baseline_sha256']=batch.source_hashes()
        self.config['execution_ready']=False
        self.write_config()
        self.assertEqual(batch.run_experiment(self.path)['planned_runs'],2)
        with self.assertRaises(RuntimeError):
            batch.run_experiment(self.path,execute=True)

    def test_atomic_write_and_live_lock(self):
        path=self.root/'atomic.json'
        batch.atomic_json(path,{'value':1})
        with self.assertRaises(FileExistsError):
            batch.atomic_json(path,{'value':2})
        self.assertEqual(json.loads(path.read_text()),{'value':1})
        batch.atomic_json(path,{'value':3},replace=True)
        self.assertEqual(json.loads(path.read_text()),{'value':3})
        self.assertFalse(list(self.root.glob('*.tmp')))
        prepared=batch.prepare_experiment(self.path)
        directory=prepared['directory']
        directory.mkdir(parents=True)
        (directory/'lock.json').write_text(json.dumps({'pid':os.getpid(),'hostname':socket.gethostname()}))
        with self.assertRaises(RuntimeError):
            batch.run_experiment(self.path,execute=True)
        self.assertTrue((directory/'lock.json').exists())

    def test_tampered_completed_result_is_not_trusted(self):
        summary=batch.run_experiment(self.path,execute=True,max_runs=1)
        path=Path(summary['output_directory'])/'runs/P-n16-k8_seed0/result.json'
        record=json.loads(path.read_text())
        record['result']['distance']=1
        path.write_text(json.dumps(record))
        with self.assertRaises(batch.ValidationFailure):
            batch.run_experiment(self.path,execute=True)

    def test_finished_checkpoint_recovers_missing_terminal_file(self):
        summary=batch.run_experiment(self.path,execute=True,max_runs=1)
        directory=Path(summary['output_directory'])/'runs/P-n16-k8_seed0'
        (directory/'result.json').unlink()  # Son ara kayıt ile sonuç yazımı arasındaki kesinti.
        with patch.object(solver,'_advance_target',side_effect=AssertionError('Bitmiş arama tekrarlanmamalı')):
            recovered=batch.run_experiment(self.path,execute=True,max_runs=1)
        self.assertEqual(recovered['terminal_runs'],1)
        record=json.loads((directory/'result.json').read_text())
        self.assertTrue(record['result']['resumed_from_checkpoint'])
        self.assertTrue((directory/'attempt_0001.json').exists())

    def test_stale_lock_from_dead_local_process_is_recovered(self):
        prepared=batch.prepare_experiment(self.path)
        directory=prepared['directory']
        directory.mkdir(parents=True)
        (directory/'lock.json').write_text(json.dumps({'pid':99999999,'hostname':socket.gethostname()}))
        summary=batch.run_experiment(self.path,execute=True,max_runs=0)
        self.assertEqual(summary['executed_this_invocation'],0)
        self.assertFalse((directory/'lock.json').exists())


class ActualPlanTests(unittest.TestCase):
    def test_current_90_instance_plan_is_valid_without_starting_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            screening=batch.run_experiment(ROOT/'configs/dogrulama.json',output_root=directory)
            self.assertEqual(screening['planned_runs'],270)
            self.assertEqual(screening['seeds'],[42,43,44])
            self.assertEqual(screening['preflight_errors'],[])
            self.assertTrue(screening['execution_ready'])
            self.assertFalse(list(Path(directory).iterdir()))


if __name__ == '__main__':
    unittest.main()
