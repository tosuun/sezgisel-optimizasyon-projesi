"""Yazar kodunun takas/taşıma/onarım sırası; kaynak ve istisnalar raporda.

Referans: CDELS 9c605e3, common/local_search.c. MIT: LICENSE-CDELS.txt.
C'deki eski tampon değerleri yerine gerçek rota komşuları kullanılır.
"""

from operators import copy_solution, find_customer
from problem import evaluate, route_load


def _removal_delta(route, position, distances):
    customer = route[position]
    before = route[position - 1] if position else 0
    after = route[position + 1] if position + 1 < len(route) else 0
    return distances[before][after] - distances[before][customer] - distances[customer][after]


def _insertion_delta(route, position, customer, distances):
    before = route[position - 1] if position else 0
    after = route[position] if position < len(route) else 0
    return distances[before][customer] + distances[customer][after] - distances[before][after]


def _swap_delta(routes, route_a, position_a, route_b, position_b, distances):
    a, b = routes[route_a][position_a], routes[route_b][position_b]
    delta = 0
    # Bitişik müşterilerin ortak kenarını yalnız bir kez hesapla.
    affected = {(route_a, position_a), (route_a, position_a + 1),
                (route_b, position_b), (route_b, position_b + 1)}
    for route_index, edge in affected:
        route = routes[route_index]
        left = route[edge - 1] if edge else 0
        right = route[edge] if edge < len(route) else 0
        new_left, new_right = left, right
        if route_index == route_a:
            if edge - 1 == position_a:
                new_left = b
            if edge == position_a:
                new_right = b
        if route_index == route_b:
            if edge - 1 == position_b:
                new_left = a
            if edge == position_b:
                new_right = a
        delta += distances[new_left][new_right] - distances[left][right]
    return delta


def swap_search(routes, distances, demands, capacity):
    """İlk iyileştiren takası uygula; aynı müşteri konumundan yeniden tara."""
    result = copy_solution(routes)
    loads = [route_load(route, demands) for route in result]
    for route_a in range(len(result)):
        for position_a in range(len(result[route_a])):
            while True:
                moved = False
                for route_b in range(route_a, len(result)):
                    first = position_a + 1 if route_a == route_b else 0
                    for position_b in range(first, len(result[route_b])):
                        a, b = result[route_a][position_a], result[route_b][position_b]
                        if route_a != route_b:
                            if (loads[route_a] - demands[a] + demands[b] > capacity
                                    or loads[route_b] - demands[b] + demands[a] > capacity):
                                continue
                        # Aynı rotadaki takas yükü değiştirmez; aşırı yüklü rotada da denenir.
                        if _swap_delta(result, route_a, position_a, route_b, position_b, distances) < 0:
                            result[route_a][position_a], result[route_b][position_b] = b, a
                            if route_a != route_b:
                                loads[route_a] += demands[b] - demands[a]
                                loads[route_b] += demands[a] - demands[b]
                            moved = True
                            break
                    if moved:
                        break
                if not moved:
                    break
    return result


def relocate_search(routes, distances, demands, capacity):
    """Değişen rota listesini tara; uygun hedef rotaları sırayla dene."""
    result = copy_solution(routes)
    free = [capacity - route_load(route, demands) for route in result]
    for original_route in range(len(result)):
        if len(result[original_route]) <= 1:
            continue
        position = 0
        previous_load = -1
        improved = False
        possible = []
        while position < len(result[original_route]):
            customer = result[original_route][position]
            load = demands[customer]
            if load > previous_load or improved:
                possible = [index for index in range(len(result))
                            if index != original_route and free[index] >= load]
            improved = False
            for target in possible:
                source, source_position = find_customer(result, customer)
                removal = _removal_delta(result[source], source_position, distances)
                best_position, best_delta = None, 0
                for insertion in range(len(result[target]) + 1):
                    delta = removal + _insertion_delta(result[target], insertion, customer, distances)
                    if delta < best_delta:
                        best_position, best_delta = insertion, delta
                if best_position is not None:
                    result[source].pop(source_position)
                    result[target].insert(best_position, customer)
                    free[source] += load
                    free[target] -= load
                    improved = True
            # C taraması gibi, çıkarılan müşterinin yerine kayan müşteri bu turda atlanır.
            position += 1
            previous_load = load
    return result


def repair(routes, distances, demands, capacity, rng):
    """Rastgele aşırı yüklü rota/müşteri/hedef; seçilen hedefte en iyi konum."""
    result = copy_solution(routes)
    free = [capacity - route_load(route, demands) for route in result]
    while any(value < 0 for value in free):
        source = rng.randrange(len(result))
        while free[source] >= 0:
            source = rng.randrange(len(result))
        # Kaynak kodun sınırlı müşteri denemesi, başarısız onarımı mümkün kılar.
        highest_free = max(free)
        attempts = len(result[source]) + len(result[source]) // 2
        for _ in range(attempts):
            source_position = rng.randrange(len(result[source]))
            customer = result[source][source_position]
            if demands[customer] <= highest_free:
                break
        else:
            return result
        target = rng.randrange(len(result))
        while free[target] < demands[customer]:
            target = rng.randrange(len(result))
        # Aşırı yüklü kaynak rota uygun hedef olamaz; hedefte mesafe artışı kabul edilir.
        insertion = min(range(len(result[target]) + 1),
                        key=lambda index: _insertion_delta(result[target], index, customer, distances))
        result[source].pop(source_position)
        result[target].insert(insertion, customer)
        free[source] += demands[customer]
        free[target] -= demands[customer]
    return result


def local_search(routes, distances, demands, capacity, max_vehicles, rng, penalty=100):
    """İki iyileşmeyen operatörde durur; son planı geri almadan döndürür."""
    result = copy_solution(routes)
    original_cost = evaluate(result, distances, demands, capacity, max_vehicles, penalty)['cost']
    no_improvement = 0
    while True:
        result = swap_search(result, distances, demands, capacity)
        score = evaluate(result, distances, demands, capacity, max_vehicles, penalty)
        if score['cost'] < original_cost:
            original_cost, no_improvement = score['cost'], 0
        else:
            no_improvement += 1
        if no_improvement > 1:
            break
        result = relocate_search(result, distances, demands, capacity)
        score = evaluate(result, distances, demands, capacity, max_vehicles, penalty)
        if score['cost'] < original_cost:
            original_cost, no_improvement = score['cost'], 0
        else:
            no_improvement += 1
        if not score['feasible']:
            result = repair(result, distances, demands, capacity, rng)
            score = evaluate(result, distances, demands, capacity, max_vehicles, penalty)
            if score['feasible']:
                no_improvement = 0
        if no_improvement >= 2:
            break
    # Arayüz korunur; ara operatör çıktılarından ayrı bir elit arşiv üretilmez.
    score = evaluate(result, distances, demands, capacity, max_vehicles, penalty)
    return result, copy_solution(result) if score['feasible'] else None
