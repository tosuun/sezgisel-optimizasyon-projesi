"""CDELS yerel araması: takas, taşıma, onarım ve tam tur karşılaştırması."""

from operators import copy_solution, find_customer
from problem import check_capacity, evaluate, route_load, solution_distance


def swap_search(routes, distances, demands, capacity):
    #Bütün müşteri çiftlerinden en fazla mesafe azaltan uygun tek takası yapar.
    best = copy_solution(routes)
    best_distance = solution_distance(routes, distances)
    positions = [
        (route_index, position)
        for route_index, route in enumerate(routes)
        for position in range(len(route))
    ]

    for index, (route_a, position_a) in enumerate(positions):
        for route_b, position_b in positions[index + 1:]:
            candidate = copy_solution(routes)
            candidate[route_a][position_a], candidate[route_b][position_b] = (
                candidate[route_b][position_b], candidate[route_a][position_a]
            )
            if any(route_load(candidate[r], demands) > capacity
                   for r in {route_a, route_b}):
                continue

            candidate_distance = solution_distance(candidate, distances)
            if candidate_distance < best_distance:
                best = candidate
                best_distance = candidate_distance

    return best


def relocate_search(routes, distances, demands, capacity):
    #Her müşteriyi sabit sırayla, başka rotadaki en iyi uygun konuma dener.
    result = copy_solution(routes)
    customers = [customer for route in routes for customer in route]

    for customer in customers:
        source_route, source_position = find_customer(result, customer)
        if len(result[source_route]) <= 1:
            continue

        best = result
        best_distance = solution_distance(result, distances)
        for target_route in range(len(result)):
            if target_route == source_route:
                continue
            if route_load(result[target_route], demands) + demands[customer] > capacity:
                continue

            for position in range(len(result[target_route]) + 1):
                candidate = copy_solution(result)
                candidate[source_route].pop(source_position)
                candidate[target_route].insert(position, customer)
                candidate_distance = solution_distance(candidate, distances)
                if candidate_distance < best_distance:
                    best = candidate
                    best_distance = candidate_distance

        result = best

    return result


def repair(routes, distances, demands, capacity, rng):
    #Uygun tek müşteri taşımalarıyla kapasiteyi onarır; başarısız kalabilir.
    result = copy_solution(routes)

    while not check_capacity(result, demands, capacity):
        overloaded_routes = [
            index for index, route in enumerate(result)
            if route_load(route, demands) > capacity
        ]
        rng.shuffle(overloaded_routes)
        moved = False

        for source_route in overloaded_routes:
            for source_position, customer in enumerate(result[source_route]):
                if demands[customer] <= 0:
                    continue

                best = None
                best_distance = None
                for target_route in range(len(result)):
                    if target_route == source_route:
                        continue
                    if route_load(result[target_route], demands) + demands[customer] > capacity:
                        continue

                    for position in range(len(result[target_route]) + 1):
                        candidate = copy_solution(result)
                        candidate[source_route].pop(source_position)
                        candidate[target_route].insert(position, customer)
                        candidate_distance = solution_distance(candidate, distances)
                        if best_distance is None or candidate_distance < best_distance:
                            best = candidate
                            best_distance = candidate_distance

                if best is not None:
                    result = best
                    moved = True
                    break

            if moved:
                break

        # Hiçbir ihlalli rotadan müşteri taşınamıyorsa yeniden denemek döngü yaratır.
        if not moved:
            break

    return result


def local_search(routes, distances, demands, capacity, max_vehicles, rng, penalty=100):
    #Tur iyileşmezse önceki çözümü, ayrıca görülen en iyi geçerli planı döndürür.
    result = copy_solution(routes)
    best_feasible = None
    best_distance = None

    def record(candidate):
        nonlocal best_feasible, best_distance
        score = evaluate(candidate, distances, demands, capacity, max_vehicles, penalty)
        if score['feasible'] and (best_distance is None or score['distance'] < best_distance):
            best_feasible = copy_solution(candidate)
            best_distance = score['distance']
        return score

    record(result)
    while True:
        previous = copy_solution(result)
        previous_cost = evaluate(
            previous, distances, demands, capacity, max_vehicles, penalty
        )['cost']

        result = swap_search(result, distances, demands, capacity)
        record(result)
        result = relocate_search(result, distances, demands, capacity)
        score = record(result)
        if not score['feasible']:
            result = repair(result, distances, demands, capacity, rng)
            record(result)

        current = evaluate(result, distances, demands, capacity, max_vehicles, penalty)
        if current['cost'] >= previous_cost:
            return previous, best_feasible
