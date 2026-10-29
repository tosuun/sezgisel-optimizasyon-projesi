"""CDELS: seçim, güvenli durma ve JSON ara kaydından aynı akışla devam."""

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import platform
import random
import time

from local_search import local_search
from operators import copy_solution, crossover_exp, initialize_population, mutate
from problem import evaluate


def select(target, trial, distances, demands, capacity, max_vehicles, penalty=100):
    # Kesin daha düşük cezalı maliyeti seçer; eşitlikte target kalır.
    target_score = evaluate(target, distances, demands, capacity, max_vehicles, penalty)
    trial_score = evaluate(trial, distances, demands, capacity, max_vehicles, penalty)
    return copy_solution(trial if trial_score['cost'] < target_score['cost'] else target)


def update_best_feasible(best_routes, candidate, distances, demands,
                         capacity, max_vehicles, penalty=100):
    # Arşiv yalnız kapasiteye uygun planları saklar; cezalı aday arşivi değiştirmez.
    if candidate is None:
        return copy_solution(best_routes) if best_routes is not None else None
    score = evaluate(candidate, distances, demands, capacity, max_vehicles, penalty)
    if score['feasible']:
        if best_routes is None:
            return copy_solution(candidate)
        best_score = evaluate(best_routes, distances, demands, capacity, max_vehicles, penalty)
        if score['distance'] < best_score['distance']:
            return copy_solution(candidate)
    return copy_solution(best_routes) if best_routes is not None else None


def _reached(best, known_optimum, distances, demands, capacity, max_vehicles, penalty):
    return (known_optimum is not None and best is not None
            and evaluate(best, distances, demands, capacity, max_vehicles, penalty)
            ['distance'] == known_optimum)


def _advance_target(population, index, distances, demands, capacity, max_vehicles,
                    mutation_factor, crossover_rate, rng, penalty, best, known_optimum):
    """Tek hedefi bitirir; eski popülasyonu değiştirmez."""
    def record(candidate):
        nonlocal best
        best = update_best_feasible(best, candidate, distances, demands,
                                    capacity, max_vehicles, penalty)
        return _reached(best, known_optimum, distances, demands, capacity, max_vehicles, penalty)

    # Bir hedef için sıra: mutasyon → çaprazlama → yerel arama → seçim.
    target = population[index]
    mutant = mutate(population, index, mutation_factor, rng)
    # Ara adımda optimum bulunursa kalan işlemleri yapmadan durabiliriz.
    if record(mutant):
        return None, best, True
    trial = crossover_exp(target, mutant, crossover_rate, rng)
    if record(trial):
        return None, best, True
    improved, local_best = local_search(trial, distances, demands, capacity, max_vehicles, rng, penalty)
    reached = record(local_best)
    reached = record(improved) or reached
    return select(target, improved, distances, demands, capacity, max_vehicles, penalty), best, reached


def next_generation(population, distances, demands, capacity, max_vehicles,
                    mutation_factor, crossover_rate, rng, penalty=100,
                    best_routes=None, known_optimum=None):
    """Yeni popülasyon, en iyi geçerli plan, tamamlanan hedef sayısı."""
    if len(population) < 3:
        raise ValueError('Nesil üretimi için en az 3 birey gerekli.')
    best = copy_solution(best_routes) if best_routes is not None else None
    new_population = []
    for target in population:
        best = update_best_feasible(best, target, distances, demands, capacity, max_vehicles, penalty)
    if not _reached(best, known_optimum, distances, demands, capacity, max_vehicles, penalty):
        for index in range(len(population)):
            chosen, best, reached = _advance_target(
                population, index, distances, demands, capacity, max_vehicles,
                mutation_factor, crossover_rate, rng, penalty, best, known_optimum)
            if chosen is not None:
                new_population.append(chosen)
            if reached:
                break
    completed = len(new_population)
    # Erken durulursa işlenmeyen bireyleri eski nesilden kopyala.
    new_population.extend(copy_solution(routes) for routes in population[completed:])
    return new_population, best, completed


def _digest(value):
    # Aynı içerik aynı özeti üretir; anahtar sırası kimliği değiştirmez.
    encoded = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def _as_tuple(value):
    # JSON dizileri listeye çevirir; random.setstate iç içe tuple bekler.
    return tuple(_as_tuple(item) for item in value) if isinstance(value, list) else value


def solve(distances, demands, capacity, max_vehicles, population_size=None,
          mutation_factor=0.7, crossover_rate=0.7, penalty=100,
          max_generations=20, seed=42, known_optimum=None, *,
          time_limit_seconds=None, checkpoint_callback=None,
          checkpoint_interval_seconds=5, progress_callback=None,
          resume_state=None, checkpoint_identity=None, cancel_requested=None):
    """Süre/iptal hedef sınırında kontrol edilir; bitmiş hedefler JSON ile sürdürülür.

    Aktif hedef içindeki yerel arama kesilmez. Süre sınırı yumuşaktır;
    hedef bitince en iyi plan ve RNG/popülasyon durumu kaydedilir.
    """
    if not 0 < mutation_factor <= 1 or not 0 <= crossover_rate <= 1:
        raise ValueError('F (0,1], CR [0,1] aralığında olmalı.')
    if not math.isfinite(penalty) or penalty < 0:
        raise ValueError('Ceza sonlu ve negatif olmayan bir sayı olmalı.')
    if not isinstance(max_generations, int) or max_generations < 0:
        raise ValueError('Nesil sınırı negatif olmayan bir tam sayı olmalı.')
    if seed is None:
        raise ValueError('Tekrarlanabilir çalışma için açık bir tohum gerekli.')
    if known_optimum is not None and (not math.isfinite(known_optimum) or known_optimum < 0):
        raise ValueError('Bilinen optimum sonlu ve negatif olmayan bir sayı olmalı.')
    if time_limit_seconds is not None and (not math.isfinite(time_limit_seconds) or time_limit_seconds < 0):
        raise ValueError('Süre sınırı sonlu ve negatif olmayan bir sayı olmalı.')
    if not math.isfinite(checkpoint_interval_seconds) or checkpoint_interval_seconds < 0:
        raise ValueError('Ara kayıt aralığı sonlu ve negatif olmayan bir sayı olmalı.')
    customers = sorted(customer for customer in demands if customer != 0)
    nodes = [0] + customers
    for a in nodes:
        if a not in distances:
            raise ValueError(f'Mesafe matrisinde düğüm eksik: {a}')
        for b in nodes:
            if b not in distances[a]:
                raise ValueError(f'Mesafe matrisinde kenar eksik: {a}, {b}')
            value = distances[a][b]
            if not math.isfinite(value) or value < 0:
                raise ValueError('Mesafeler sonlu ve negatif olmayan sayılar olmalı.')
            if a == b and value != 0:
                raise ValueError('Mesafe matrisinin köşegeni sıfır olmalı.')
            if b in distances and a in distances[b] and value != distances[b][a]:
                raise ValueError('Bu CVRP uygulaması simetrik mesafe matrisi kullanır.')
    if population_size is None:
        population_size = 3 * len(customers)
    if not isinstance(population_size, int) or population_size < 3:
        raise ValueError('Popülasyon büyüklüğü en az 3 olmalı.')
    parameters = {
        'population_size': population_size, 'mutation_factor': mutation_factor,
        'crossover_rate': crossover_rate, 'penalty': penalty,
        'max_generations': max_generations, 'known_optimum': known_optimum,
        'time_limit_seconds': time_limit_seconds}
    # Ara kayıt yalnız aynı kod, problem ve ayarlarla devam ettirilebilir.
    source_hash = _digest({name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                           for name in ['solver.py', 'operators.py', 'local_search.py', 'problem.py']})
    identity = {'schema_version': 1, 'parameters': parameters, 'seed': seed,
                'problem_sha256': _digest([distances, demands, capacity, max_vehicles]),
                'solver_source_sha256': source_hash, 'python_version': platform.python_version(),
                'checkpoint_identity': checkpoint_identity}
    started = time.perf_counter()
    # Rastgele sayı üreticisi yalnız bu koşuya aittir; tohum akışı tekrarlanabilir kılar.
    rng = random.Random(seed)
    resumed = resume_state is not None
    if resumed:
        state = deepcopy(resume_state)
        if state.get('identity') != identity:
            raise ValueError('Ara kayıt veri/parametre/tohum/kod/Python kimliği bu koşuyla eşleşmiyor.')
        if (len(state.get('population', [])) != population_size
                or not 0 <= state.get('generations', -1) <= max_generations
                or len(state.get('new_population', [])) >= population_size
                or state.get('next_target') != len(state['new_population'])
                or not math.isfinite(state.get('elapsed_seconds', -1))
                or state['elapsed_seconds'] < 0
                or state.get('status') not in {'running', 'interrupted', 'finished'}):
            raise ValueError('Ara kayıt popülasyon/sayaçları geçersiz.')
        for individual in state['population'] + state['new_population']:
            if len(individual) != max_vehicles:
                raise ValueError('Ara kayıtta rota listesi sayısı farklı.')
            evaluate(individual, distances, demands, capacity, max_vehicles, penalty)
        if state.get('best_routes') is not None:
            if not evaluate(state['best_routes'], distances, demands, capacity, max_vehicles, penalty)['feasible']:
                raise ValueError('Ara kayıttaki en iyi plan geçerli değil.')
        if state['status'] == 'finished' and state.get('stop_reason') not in {'known_optimum', 'max_generations', 'time_limit'}:
            raise ValueError('Ara kayıt bitiş nedeni geçersiz.')
        # Tohumu yeniden başlatmak yerine kaydedilen rastgele sayı akışından devam et.
        rng.setstate(_as_tuple(state['rng_state']))
        elapsed_before = state['elapsed_seconds']
    else:
        population = initialize_population(demands, capacity, max_vehicles, population_size, rng)
        best = None
        for individual in population:
            best = update_best_feasible(best, individual, distances, demands, capacity, max_vehicles, penalty)
        state = {'identity': identity, 'population': population, 'new_population': [],
                 'next_target': 0, 'best_routes': best, 'generations': 0,
                 'rng_state': rng.getstate(), 'elapsed_seconds': 0,
                 'status': 'running', 'stop_reason': None}
        elapsed_before = 0

    # Devam edilen koşuda önceki aktif süre de toplam süreye katılır.
    def elapsed():
        return elapsed_before + time.perf_counter() - started

    # Geçerli plan bulunmadıysa mesafe yerine None döndür; başarı gibi raporlama.
    def make_result():
        best = state['best_routes']
        score = evaluate(best, distances, demands, capacity, max_vehicles, penalty) if best is not None else None
        return {'best_routes': copy_solution(best) if best is not None else None,
                'distance': score['distance'] if score else None, 'feasible': score is not None,
                'generations': state['generations'], 'partial_generation_targets': state['next_target'],
                'stop_reason': state['stop_reason'], 'seed': seed, 'parameters': parameters,
                'elapsed_seconds': state['elapsed_seconds'],
                'time_limit_overshoot_seconds': (max(0, state['elapsed_seconds'] - time_limit_seconds)
                                                 if time_limit_seconds is not None else 0),
                'resumed_from_checkpoint': resumed}

    if resumed and state['status'] == 'finished':
        return make_result()
    state['status'] = 'running'
    state['stop_reason'] = None
    last_checkpoint = -math.inf

    # Ara kayıt dışarıya kopya olarak verilir; çalışan durum yanlışlıkla değiştirilemez.
    def checkpoint(force=False):
        nonlocal last_checkpoint
        current = elapsed()
        if checkpoint_callback is not None and (force or current - last_checkpoint >= checkpoint_interval_seconds):
            state['elapsed_seconds'] = current
            checkpoint_callback(deepcopy(state))
            last_checkpoint = current

    checkpoint(force=True)
    try:
        while True:
            if _reached(state['best_routes'], known_optimum, distances, demands, capacity, max_vehicles, penalty):
                state['stop_reason'] = 'known_optimum'
                break
            if state['generations'] >= max_generations:
                state['stop_reason'] = 'max_generations'
                break
            if cancel_requested is not None and cancel_requested():
                state['stop_reason'] = 'interrupted'
                break
            # Süre kontrolü hedefler arasındadır; başlamış yerel arama yarıda kesilmez.
            if time_limit_seconds is not None and elapsed() >= time_limit_seconds:
                state['stop_reason'] = 'time_limit'
                break
            chosen, best, reached = _advance_target(
                state['population'], state['next_target'], distances, demands, capacity, max_vehicles,
                mutation_factor, crossover_rate, rng, penalty, state['best_routes'], known_optimum)
            state['best_routes'] = best
            if chosen is not None:
                state['new_population'].append(chosen)
                state['next_target'] += 1
            # Hedef tamamlanınca çözüm ve rastgele sayı durumu birlikte kaydedilir.
            state['rng_state'] = rng.getstate()
            # Bütün hedefler bitince yeni popülasyon eski neslin yerini alır.
            if state['next_target'] == population_size:
                state['population'] = state['new_population']
                state['new_population'] = []
                state['next_target'] = 0
                state['generations'] += 1
            if progress_callback is not None:
                score = (evaluate(best, distances, demands, capacity, max_vehicles, penalty)
                         if best is not None else None)
                progress_callback({'generations': state['generations'],
                                   'partial_generation_targets': state['next_target'],
                                   'best_distance': score['distance'] if score else None,
                                   'elapsed_seconds': elapsed()})
            checkpoint(force=reached)
            if reached:
                state['stop_reason'] = 'known_optimum'
                break
    except KeyboardInterrupt:
        # Yarım hedef tekrarında son tamamlanmış hedefin RNG kaydı kullanılır.
        state['stop_reason'] = 'interrupted'
    state['status'] = 'interrupted' if state['stop_reason'] == 'interrupted' else 'finished'
    state['elapsed_seconds'] = elapsed()
    checkpoint(force=True)
    return make_result()
