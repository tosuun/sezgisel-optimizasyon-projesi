"""CDELS seçimi, nesil üretimi ve tohumla tekrarlanabilir ana döngüsü."""

import math
import random
import time

from local_search import local_search
from operators import copy_solution, crossover_exp, initialize_population, mutate
from problem import evaluate


def select(target, trial, distances, demands, capacity, max_vehicles, penalty=100):
    """Kesin daha düşük cezalı maliyeti seçer; eşitlikte target kalır."""
    target_score = evaluate(target, distances, demands, capacity, max_vehicles, penalty)
    trial_score = evaluate(trial, distances, demands, capacity, max_vehicles, penalty)
    chosen = trial if trial_score['cost'] < target_score['cost'] else target
    return copy_solution(chosen)


def update_best_feasible(best_routes, candidate, distances, demands,
                         capacity, max_vehicles, penalty=100):
    """İhlalli adayı sonuca katmaz; saklanan planı bağımsız kopya tutar."""
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


def next_generation(population, distances, demands, capacity, max_vehicles,
                    mutation_factor, crossover_rate, rng, penalty=100,
                    best_routes=None, known_optimum=None):
    """Yeni popülasyon, en iyi geçerli plan ve tamamlanan target sayısını verir."""
    if len(population) < 3:
        raise ValueError("Nesil üretimi için en az 3 birey gerekli.")

    best = copy_solution(best_routes) if best_routes is not None else None
    new_population = []

    def record(candidate):
        nonlocal best
        best = update_best_feasible(
            best, candidate, distances, demands, capacity, max_vehicles, penalty
        )
        return (known_optimum is not None and best is not None
                and evaluate(best, distances, demands, capacity, max_vehicles, penalty)
                ['distance'] == known_optimum)

    def finish():
        # Optimum ara adımda bulunursa kalan hedefleri değiştirmeden kopyala.
        completed_targets = len(new_population)
        remaining = [copy_solution(routes) for routes in population[completed_targets:]]
        return new_population + remaining, best, completed_targets

    for target in population:
        if record(target):
            return finish()

    for target_index, target in enumerate(population):
        mutant = mutate(population, target_index, mutation_factor, rng)
        if record(mutant):
            return finish()

        trial = crossover_exp(target, mutant, crossover_rate, rng)
        if record(trial):
            return finish()

        improved, local_best = local_search(
            trial, distances, demands, capacity, max_vehicles, rng, penalty
        )
        reached = record(local_best)
        reached = record(improved) or reached
        chosen = select(target, improved, distances, demands, capacity, max_vehicles, penalty)
        new_population.append(chosen)
        if reached:
            return finish()

    return new_population, best, len(new_population)


def solve(distances, demands, capacity, max_vehicles, population_size=None,
          mutation_factor=0.7, crossover_rate=0.7, penalty=100,
          max_generations=20, seed=42, known_optimum=None):
    """CDELS çalıştırır; hiç geçerli plan yoksa rota ve mesafe None döner."""
    if not 0 < mutation_factor <= 1:
        raise ValueError("Mutasyon faktörü (0, 1] aralığında olmalı.")
    if not 0 <= crossover_rate <= 1:
        raise ValueError("Çaprazlama oranı [0, 1] aralığında olmalı.")
    if not math.isfinite(penalty) or penalty < 0:
        raise ValueError("Ceza sonlu ve negatif olmayan bir sayı olmalı.")
    if not isinstance(max_generations, int) or max_generations < 0:
        raise ValueError("Nesil sınırı negatif olmayan bir tam sayı olmalı.")
    if seed is None:
        raise ValueError("Tekrarlanabilir çalışma için açık bir tohum gerekli.")
    if known_optimum is not None and (not math.isfinite(known_optimum) or known_optimum < 0):
        raise ValueError("Bilinen optimum sonlu ve negatif olmayan bir sayı olmalı.")

    customers = sorted(customer for customer in demands if customer != 0)
    nodes = [0] + customers
    for a in nodes:
        if a not in distances:
            raise ValueError(f"Mesafe matrisinde düğüm eksik: {a}")
        for b in nodes:
            if b not in distances[a]:
                raise ValueError(f"Mesafe matrisinde kenar eksik: {a}, {b}")
            value = distances[a][b]
            if not math.isfinite(value) or value < 0:
                raise ValueError("Mesafeler sonlu ve negatif olmayan sayılar olmalı.")
            if a == b and value != 0:
                raise ValueError("Mesafe matrisinin köşegeni sıfır olmalı.")
            if b in distances and a in distances[b] and value != distances[b][a]:
                raise ValueError("Bu CVRP uygulaması simetrik mesafe matrisi kullanır.")

    if population_size is None:
        population_size = 3 * len(customers)

    started = time.perf_counter()
    rng = random.Random(seed)
    population = initialize_population(demands, capacity, max_vehicles, population_size, rng)
    best = None
    for individual in population:
        best = update_best_feasible(
            best, individual, distances, demands, capacity, max_vehicles, penalty
        )

    generations = 0
    partial_targets = 0
    stop_reason = 'max_generations'

    def reached_optimum():
        return (known_optimum is not None and best is not None
                and evaluate(best, distances, demands, capacity, max_vehicles, penalty)
                ['distance'] == known_optimum)

    if reached_optimum():
        stop_reason = 'known_optimum'
    else:
        while generations < max_generations:
            population, best, completed = next_generation(
                population, distances, demands, capacity, max_vehicles,
                mutation_factor, crossover_rate, rng, penalty, best, known_optimum
            )
            if completed == population_size:
                generations += 1
                partial_targets = 0
            else:
                partial_targets = completed

            if reached_optimum():
                stop_reason = 'known_optimum'
                break
            if completed != population_size:
                raise RuntimeError("Nesil optimuma ulaşılmadan yarıda kaldı.")

    best_score = (evaluate(best, distances, demands, capacity, max_vehicles, penalty)
                  if best is not None else None)
    return {
        'best_routes': copy_solution(best) if best is not None else None,
        'distance': best_score['distance'] if best_score is not None else None,
        'feasible': best_score is not None,
        'generations': generations,
        'partial_generation_targets': partial_targets,
        'stop_reason': stop_reason,
        'seed': seed,
        'parameters': {
            'population_size': population_size,
            'mutation_factor': mutation_factor,
            'crossover_rate': crossover_rate,
            'penalty': penalty,
            'max_generations': max_generations,
            'known_optimum': known_optimum,
        },
        'elapsed_seconds': time.perf_counter() - started,
    }
