"""Ayar dosyasından toplu deney; varsayılan yalnız planı kontrol eder."""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
from importlib import metadata as package_metadata
import json
import math
import os
from pathlib import Path
import platform
import signal
import socket
import sys
import tempfile
import time
import traceback

from instance_io import read_instance, read_solution
from problem import evaluate
from run_pilot import audit_solution
from solver import solve


SOURCE_FILES = ['problem.py', 'operators.py', 'local_search.py', 'solver.py',
                'instance_io.py', 'run_pilot.py', 'run_experiments.py']


class ValidationFailure(RuntimeError):
    """Veri, kayıt kimliği veya bağımsız maliyet kontrolü başarısız."""


def utc_now():
    return datetime.now(timezone.utc).isoformat()


# Veri ve ayarların kısa kimliğini üretir; farklı deneylerin karışmasını önler.
def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# Sonucu etkileyen kaynak dosyalarının içerik özetlerini toplar.
def source_hashes():
    return {name: file_hash(Path(__file__).with_name(name)) for name in SOURCE_FILES}


# Python, bilgisayar ve paket sürümleri sonuçların hangi ortamda alındığını gösterir.
def environment():
    packages = {}
    for dist in package_metadata.distributions():
        name = dist.metadata.get('Name')
        if name:
            packages[name.lower()] = dist.version
    return {'python_version': platform.python_version(),
            'python_implementation': platform.python_implementation(),
            'executable': str(Path(sys.executable).resolve()),
            'platform': platform.platform(), 'machine': platform.machine(),
            'processor': platform.processor(), 'cpu_count': os.cpu_count(),
            'hostname': socket.gethostname(), 'package_versions': dict(sorted(packages.items()))}


def atomic_json(path, record, replace=False):
    """Tam JSON'u aynı klasöre yazıp atomik olarak yayımlar; sonuçlar ezilmez."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.' + path.name, suffix='.tmp', delete=False) as file:
            temporary = Path(file.name)
            json.dump(record, file, ensure_ascii=False, indent=2, allow_nan=False)
            file.write('\n')
            file.flush()
            os.fsync(file.fileno())
        # Önce tam dosyayı hazırla; kaydetme sırasında yarım JSON bırakma.
        if replace:
            os.replace(temporary, path)
        else:
            # Aynı diskte hard link, hedef zaten varsa atomik olarak başarısız olur.
            os.link(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


# Başlama, ara kayıt ve bitiş olaylarını satır satır kaydeder.
def append_event(directory, event, **fields):
    with (directory / 'events.jsonl').open('a', encoding='utf-8') as file:
        file.write(json.dumps({'time_utc': utc_now(), 'event': event, **fields},
                              ensure_ascii=False, allow_nan=False) + '\n')
        file.flush()


@contextmanager
def experiment_lock(directory):
    # Aynı deneyin iki ayrı süreç tarafından eşzamanlı yürütülmesini engelle.
    path = directory / 'lock.json'
    if path.exists():
        lock = json.loads(path.read_text())
        if lock.get('hostname') != socket.gethostname():
            raise RuntimeError('Deney başka bir bilgisayarın kilidini taşıyor.')
        try:
            os.kill(int(lock['pid']), 0)
        except ProcessLookupError:
            path.unlink()  # Aynı bilgisayarda artık olmayan süreçten kalan kilit.
        else:
            raise RuntimeError('Aynı deney için başka bir çalıştırıcı hâlâ etkin.')
    with path.open('x') as file:
        json.dump({'pid': os.getpid(), 'hostname': socket.gethostname(), 'created_utc': utc_now()}, file)
    try:
        yield
    finally:
        path.unlink(missing_ok=True)


def prepare_experiment(config_path, project_root=None, output_root=None):
    config_path = Path(config_path).resolve()
    root = Path(project_root).resolve() if project_root else config_path.parent.parent
    config = json.loads(config_path.read_text())
    instances, seeds = config['instances'], config['seeds']
    if (not instances or len(instances) != len(set(instances))
            or not seeds or len(seeds) != len(set(seeds))
            or any(not isinstance(seed, int) or isinstance(seed, bool) or seed < 0 for seed in seeds)):
        raise ValueError('Örnekler/tohumlar tekil ve tohumlar negatif olmayan tam sayı olmalı.')
    if seeds != sorted(seeds):
        raise ValueError('Tohum sırası artan olmalı.')
    if (config['instance_count'] != len(instances) or config['repeat_count'] != len(seeds)
            or config['planned_run_count'] != len(instances) * len(seeds)):
        raise ValueError('Profilin örnek/tekrar/koşu sayıları tutarsız.')
    algorithm = config['algorithm']
    if (algorithm['strategy'] != 'rand/1/exp'
            or algorithm['population_size_rule'] not in {'3 * n_customers_excluding_depot', '3 * n_nodes_including_depot'}
            or algorithm['distance_rule'] != 'floor(euclidean_distance + 0.5)'
            or algorithm.get('parameter_grid_search', False)):
        raise ValueError('Bu çalıştırıcı yalnız kayıtlı CDELS/mesafe kurallarını destekler.')
    if not 0 < algorithm['mutation_factor'] <= 1 or not 0 <= algorithm['crossover_rate'] <= 1:
        raise ValueError('F veya CR geçersiz.')
    if not math.isfinite(algorithm['penalty']) or algorithm['penalty'] < 0:
        raise ValueError('Ceza geçersiz.')
    limit = config.get('time_limit_seconds')
    if limit is not None and (not math.isfinite(limit) or limit < 0):
        raise ValueError('Süre sınırı geçersiz.')
    for limit in config['max_generations_by_group'].values():
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 0:
            raise ValueError('Nesil sınırı geçersiz.')

    # Ayarlardaki örnek adlarını veri listesindeki gerçek dosyalarla eşleştir.
    manifest_path = root / config['instance_manifest']
    manifest = json.loads(manifest_path.read_text())
    by_name = {entry['name']: entry for entry in manifest['instances']}
    if len(by_name) != len(manifest['instances']) or any(name not in by_name for name in instances):
        raise ValueError('Manifestte eksik/tekrarlı örnek var.')
    actual_counts = {}
    # Uzun deney başlamadan bütün veri dosyalarını ve referans çözümleri doğrula.
    for name in instances:
        group = by_name[name]['group']
        actual_counts[group] = actual_counts.get(group, 0) + 1
        if group not in config['max_generations_by_group']:
            raise ValueError('Bir veri grubunun nesil sınırı eksik.')
    if actual_counts != config['group_counts']:
        raise ValueError('Grup sayıları profil kapsamıyla eşleşmiyor.')

    code = source_hashes()
    env = environment()
    preflight = []
    data_hashes = {}
    loaded = {}
    for name in instances:
        entry = by_name[name]
        try:
            instance_path, solution_path = root / entry['instance_path'], root / entry['solution_path']
            hashes = {'vrp': file_hash(instance_path), 'sol': file_hash(solution_path)}
            data_hashes[name] = hashes
            if hashes != {'vrp': entry['vrp_sha256'], 'sol': entry['sol_sha256']}:
                raise ValidationFailure('Veri hashleri doğrulanmış manifestle eşleşmiyor.')
            instance = read_instance(instance_path)
            for field in ['dimension', 'n_customers', 'max_vehicles', 'capacity']:
                if instance[field] != entry[field]:
                    raise ValidationFailure(f'Veri/manifest alanı farklı: {field}')
            reference = read_solution(solution_path, instance, config['solution_id_convention'])
            audit = audit_solution(reference['routes'], instance)
            if (not audit['valid'] or audit['distance'] != entry['reference_cost']
                    or reference['reported_cost'] != entry['reference_cost']):
                raise ValidationFailure('Referans bağımsız denetimden geçmedi.')
            if config['known_optimum_early_stop'] and not entry['current_catalog_proven_optimum']:
                raise ValidationFailure('Erken durma için optimumluk doğrulanmamış.')
            loaded[name] = (instance, reference, audit)
            preflight.append({'name': name, 'status': 'passed'})
        except Exception as error:
            data_hashes.setdefault(name, {'unavailable': str(error)})
            preflight.append({'name': name, 'status': 'error', 'error_type': type(error).__name__, 'error': str(error)})

    baseline = config.get('source_baseline_sha256', {})
    changed = [name for name, sha in baseline.items() if code.get(name) != sha]
    # Kod, veri, ayar veya ortam değişirse deney kimliği de değişir.
    key = {'profile_sha256': file_hash(config_path), 'manifest_sha256': file_hash(manifest_path),
           'source_sha256': code, 'environment_sha256': digest(env), 'data_sha256': data_hashes}
    experiment_id = config['profile_id'] + '-' + digest(key)[:16]
    output = Path(output_root).resolve() if output_root else root / 'results' / 'experiments'
    return {'root': root, 'config_path': config_path, 'config': config,
            'manifest_path': manifest_path, 'entries': by_name, 'loaded': loaded,
            'preflight': preflight, 'identity': key, 'environment': env,
            'experiment_id': experiment_id, 'directory': output / experiment_id,
            'baseline_changed_files': changed,
            'jobs': [(name, seed) for name in instances for seed in seeds]}


def _audit_result(result, instance, reference):
    routes = result['best_routes']
    if routes is None:
        if result['feasible'] or result['distance'] is not None:
            raise ValidationFailure('Geçerli plan yokken sayısal başarı raporlandı.')
        return None
    audit = audit_solution(routes, instance)
    if not audit['valid'] or not result['feasible'] or audit['distance'] != result['distance']:
        raise ValidationFailure('Nihai plan bağımsız uygunluk/maliyet denetiminden geçmedi.')
    if audit['distance'] < reference['reported_cost']:
        raise ValidationFailure('Maliyet doğrulanmış optimumun altında; çalışma durduruldu.')
    return audit


def run_experiment(config_path, *, project_root=None, output_root=None, execute=False,
                   max_runs=None, retry_errors=False, cancel_requested=None, progress_callback=None):
    prepared = prepare_experiment(config_path, project_root, output_root)
    config, directory = prepared['config'], prepared['directory']
    plan = {'experiment_id': prepared['experiment_id'], 'output_directory': str(directory),
            'profile_id': config['profile_id'], 'planned_runs': len(prepared['jobs']),
            'instance_count': config['instance_count'], 'seeds': config['seeds'],
            'execution_ready': config.get('execution_ready', False),
            'preflight_errors': [item for item in prepared['preflight'] if item['status'] != 'passed'],
            'baseline_changed_files': prepared['baseline_changed_files']}
    # --execute verilmedikçe yalnız planı göster; optimizasyonu başlatma.
    if not execute:
        return {'mode': 'plan_only', **plan}
    if not config.get('execution_ready', False):
        raise RuntimeError('Profil çalıştırılmaya açık değil; protokolün kontrol adımları tamamlanmalı.')
    # Eski sonuçlarla farklı kodun sonuçlarını aynı profil altında birleştirme.
    if prepared['baseline_changed_files']:
        raise ValidationFailure('Kod profildeki sürümden farklı; yeni sürümlü profil gerekli.')
    if max_runs is not None and (not isinstance(max_runs, int) or max_runs < 0):
        raise ValueError('Koşu sayısı sınırı negatif olmayan tam sayı olmalı.')

    directory.mkdir(parents=True, exist_ok=True)
    with experiment_lock(directory):
        metadata_path = directory / 'metadata.json'
        metadata = {'experiment_id': prepared['experiment_id'], 'identity': prepared['identity'],
                    'config': config, 'config_path': str(prepared['config_path']),
                    'environment': prepared['environment'], 'created_utc': utc_now()}
        if metadata_path.exists():
            if json.loads(metadata_path.read_text())['identity'] != prepared['identity']:
                raise ValidationFailure('Mevcut deney kimliği farklı; kayıtlar birleştirilmedi.')
        else:
            atomic_json(metadata_path, metadata)
        atomic_json(directory / 'preflight.json', prepared['preflight'], replace=True)
        if plan['preflight_errors']:
            summary = {**plan, 'status': 'preflight_failed', 'terminal_runs': 0,
                       'pending_runs': len(prepared['jobs']), 'updated_utc': utc_now()}
            atomic_json(directory / 'summary.json', summary, replace=True)
            append_event(directory, 'preflight_failed', errors=plan['preflight_errors'])
            return summary

        summary = {**plan, 'status': 'prepared', 'terminal_runs': 0, 'valid_runs': 0,
                   'no_feasible_solution_runs': 0, 'interrupted_attempts': 0, 'error_attempts': 0,
                   'pending_runs': len(prepared['jobs']), 'executed_this_invocation': 0,
                   'skipped_completed': 0, 'last_run': None}

        def save_summary():
            summary['pending_runs'] = len(prepared['jobs']) - summary['terminal_runs']
            summary['updated_utc'] = utc_now()
            atomic_json(directory / 'summary.json', summary, replace=True)

        append_event(directory, 'batch_started', max_runs=max_runs)
        stop_batch = False
        for name, seed in prepared['jobs']:
            instance, reference, reference_audit = prepared['loaded'][name]
            entry = prepared['entries'][name]
            run_id = f'{name}_seed{seed}'
            run_directory = directory / 'runs' / run_id
            run_identity = {'experiment_identity_sha256': digest(prepared['identity']),
                            'name': name, 'seed': seed,
                            'instance_sha256': entry['vrp_sha256'], 'solution_sha256': entry['sol_sha256']}
            result_path = run_directory / 'result.json'
            checkpoint_path = run_directory / 'checkpoint.json'
            attempts = sorted(run_directory.glob('attempt_*.json')) if run_directory.exists() else []
            old_attempts = [json.loads(path.read_text()) for path in attempts]
            summary['interrupted_attempts'] += sum(item['status'] == 'interrupted' for item in old_attempts)
            summary['error_attempts'] += sum(item['status'] == 'error' for item in old_attempts)
            # Tamamlanmış koşuyu yeniden denetle, sonra tekrar çalıştırmadan atla.
            if result_path.exists():
                existing = json.loads(result_path.read_text())
                if existing['run_identity'] != run_identity or existing['status'] not in {'completed', 'no_feasible_solution'}:
                    raise ValidationFailure('Tamamlanmış koşu kimliği/durumu farklı.')
                _audit_result(existing['result'], instance, reference)
                summary['terminal_runs'] += 1
                summary['valid_runs'] += existing['status'] == 'completed'
                summary['no_feasible_solution_runs'] += existing['status'] == 'no_feasible_solution'
                summary['skipped_completed'] += 1
                continue
            if stop_batch:
                continue
            if cancel_requested is not None and cancel_requested():
                summary['status'] = 'interrupted'
                stop_batch = True
                continue
            if max_runs is not None and summary['executed_this_invocation'] >= max_runs:
                summary['status'] = 'invocation_run_limit'
                stop_batch = True
                continue
            if old_attempts and old_attempts[-1]['status'] == 'error' and not retry_errors:
                summary['status'] = 'previous_error_requires_retry'
                stop_batch = True
                continue

            run_directory.mkdir(parents=True, exist_ok=True)
            number = len(attempts) + 1
            attempt_path = run_directory / f'attempt_{number:04d}.json'
            started_utc = utc_now()

            # Ara kayıttaki en iyi planı da doğrula; sonra güvenli biçimde diske yaz.
            def checkpoint(state):
                if state['best_routes'] is not None:
                    score = evaluate(state['best_routes'], instance['distances'], instance['demands'],
                                     instance['capacity'], instance['max_vehicles'], config['algorithm']['penalty'])
                    _audit_result({'best_routes': state['best_routes'], 'distance': score['distance'],
                                   'feasible': score['feasible']}, instance, reference)
                last_checkpoint = {'run_identity': run_identity, 'solver_state': state,
                                   'saved_utc': utc_now()}
                atomic_json(checkpoint_path, last_checkpoint, replace=True)
                append_event(directory, 'checkpoint', run_id=run_id,
                             generations=state['generations'], next_target=state['next_target'],
                             elapsed_seconds=state['elapsed_seconds'])

            try:
                if source_hashes() != prepared['identity']['source_sha256']:
                    raise ValidationFailure('Koşular arasında kaynak kod değişti.')
                for path_field, hash_field in [('instance_path', 'vrp_sha256'), ('solution_path', 'sol_sha256')]:
                    if file_hash(prepared['root'] / entry[path_field]) != entry[hash_field]:
                        raise ValidationFailure('Koşular arasında veri dosyası değişti.')
                resume_state = None
                # Yarım kalan koşu yalnız kendi kimliğiyle eşleşen ara kayıttan sürer.
                if checkpoint_path.exists():
                    previous = json.loads(checkpoint_path.read_text())
                    if previous['run_identity'] != run_identity:
                        raise ValidationFailure('Ara kayıt başka bir koşuya ait.')
                    resume_state = previous['solver_state']
                append_event(directory, 'run_started', run_id=run_id, attempt=number,
                             resumed=resume_state is not None)
                def progress(value):
                    if progress_callback is not None:
                        progress_callback({'run_id': run_id, **value})
                result = solve(
                    instance['distances'], instance['demands'], instance['capacity'], instance['max_vehicles'],
                    # Sabit kaynak kod NP hesabında depo dahil DIMENSION kullanır.
                    population_size=3 * (instance['dimension'] if config['algorithm']['population_size_rule']
                                         == '3 * n_nodes_including_depot' else instance['n_customers']),
                    mutation_factor=config['algorithm']['mutation_factor'],
                    crossover_rate=config['algorithm']['crossover_rate'], penalty=config['algorithm']['penalty'],
                    max_generations=config['max_generations_by_group'][entry['group']], seed=seed,
                    known_optimum=reference['reported_cost'] if config['known_optimum_early_stop'] else None,
                    time_limit_seconds=config.get('time_limit_seconds'), checkpoint_callback=checkpoint,
                    checkpoint_interval_seconds=config.get('checkpoint_interval_seconds', 5),
                    checkpoint_identity=digest(run_identity), resume_state=resume_state,
                    cancel_requested=cancel_requested, progress_callback=progress,
                )
                audit = _audit_result(result, instance, reference)
                if source_hashes() != prepared['identity']['source_sha256']:
                    raise ValidationFailure('Koşu sırasında kaynak kod değişti.')
                # Kesinti, geçerli sonuç ve çözüm bulunamaması ayrı durumlar olarak kaydedilir.
                status = ('interrupted' if result['stop_reason'] == 'interrupted' else
                          'completed' if result['feasible'] else 'no_feasible_solution')
                record = {
                    'run_identity': run_identity, 'run_id': run_id, 'attempt': number, 'status': status,
                    'started_utc': started_utc, 'finished_utc': utc_now(),
                    'profile_id': config['profile_id'], 'purpose': config['purpose'],
                    'instance': {field: instance[field] for field in ['name','dimension','n_customers','capacity','max_vehicles']},
                    'reference': {**reference, 'independent_audit': reference_audit},
                    'result': result, 'independent_audit': audit,
                    'gap_percent': (100 * (result['distance'] - reference['reported_cost']) / reference['reported_cost']
                                    if audit and reference['reported_cost'] else 0 if audit else None),
                    'best_routes_original_node_ids': (
                        [[instance['internal_to_original'][c] for c in route] for route in result['best_routes']]
                        if result['best_routes'] is not None else None),
                    'metadata_file': '../../metadata.json',
                }
                atomic_json(attempt_path, record)
                if status != 'interrupted':
                    atomic_json(result_path, record)
                    summary['terminal_runs'] += 1
                    summary['valid_runs'] += status == 'completed'
                    summary['no_feasible_solution_runs'] += status == 'no_feasible_solution'
                else:
                    summary['interrupted_attempts'] += 1
                    summary['status'] = 'interrupted'
                    stop_batch = True
                append_event(directory, 'run_finished', run_id=run_id, status=status,
                             stop_reason=result['stop_reason'], distance=result['distance'])
            # Hata kaydını koru ve grubu durdur; başarısız koşuyu başarı sayma.
            except Exception as error:
                record = {'run_identity': run_identity, 'run_id': run_id, 'attempt': number,
                          'status': 'error', 'started_utc': started_utc, 'finished_utc': utc_now(),
                          'error_type': type(error).__name__, 'error': str(error),
                          'traceback': traceback.format_exc(),
                          'checkpoint_available': checkpoint_path.exists()}
                if not attempt_path.exists():
                    atomic_json(attempt_path, record)
                summary['error_attempts'] += 1
                summary['status'] = 'error'
                stop_batch = True
                append_event(directory, 'run_error', run_id=run_id, error_type=type(error).__name__, error=str(error))
            summary['executed_this_invocation'] += 1
            summary['last_run'] = run_id
            save_summary()
        if summary['terminal_runs'] == len(prepared['jobs']):
            summary['status'] = 'completed'
        elif summary['status'] == 'prepared':
            summary['status'] = 'pending'
        save_summary()
        append_event(directory, 'batch_stopped', status=summary['status'], terminal_runs=summary['terminal_runs'])
        return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', type=Path)
    parser.add_argument('--execute', action='store_true', help='Açıkça verilmezse yalnız plan kontrol edilir.')
    parser.add_argument('--max-runs', type=int, default=None, help='Bu çağrıda başlatılacak yeni koşu sayısı.')
    parser.add_argument('--output-root', type=Path, default=None)
    parser.add_argument('--retry-errors', action='store_true')
    args = parser.parse_args()
    stop = {'requested': False}
    display = {'run_id': None, 'last_time': -math.inf}
    # Ctrl+C isteğini işaretle; çalışan hedef bitince güvenli durma yapılır.
    def request_stop(signum, frame):
        stop['requested'] = True
        print('Durdurma istendi; aktif hedef bitince ara kayıt alınacak.', file=sys.stderr, flush=True)
    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    # İlerlemeyi her hedefte yazmak yerine yaklaşık 10 saniyede bir göster.
    def show_progress(value):
        now = time.monotonic()
        if value['run_id'] != display['run_id'] or now - display['last_time'] >= 10:
            print(f"{value['run_id']}: nesil {value['generations']}, "
                  f"hedef {value['partial_generation_targets']}, "
                  f"en iyi {value['best_distance']}, {value['elapsed_seconds']:.1f} s",
                  file=sys.stderr, flush=True)
            display.update(run_id=value['run_id'], last_time=now)
    summary = run_experiment(args.config, execute=args.execute, max_runs=args.max_runs,
                             output_root=args.output_root, retry_errors=args.retry_errors,
                             cancel_requested=lambda: stop['requested'], progress_callback=show_progress)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary.get('status') in {'error','preflight_failed','previous_error_requires_retry'} or summary.get('preflight_errors'):
        raise SystemExit(2)


if __name__ == '__main__':
    main()
