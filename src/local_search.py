"""CDELS yerel araması: takas, taşıma, onarım ve tam tur karşılaştırması."""

from operators import copy_solution, find_customer
from problem import evaluate, route_load


def _removal_delta(route, position, distances):
    # Yalnız müşterinin iki komşusuyla kurduğu kenarlar değişir.
    customer = route[position]
    # İlk müşterinin önceki noktası depodur; son müşteriden sonra da depoya dönülür.
    before = route[position - 1] if position else 0
    after = route[position + 1] if position + 1 < len(route) else 0
    # Eski iki bağlantıyı çıkar, komşuları doğrudan bağla.
    return (distances[before][after] - distances[before][customer]
            - distances[customer][after])


def _insertion_delta(route, position, customer, distances):
    before = route[position - 1] if position else 0
    after = route[position] if position < len(route) else 0
    # Tek bağlantının yerine müşteriden geçen iki bağlantı eklenir.
    return (distances[before][customer] + distances[customer][after]
            - distances[before][after])


def _swap_delta(routes, route_a, position_a, route_b, position_b, distances):
    # Kenar indisleri: 0 depodan çıkış, len(rota) depoya dönüş.
    # Aynı rotada bitişik müşterilerin ortak kenarı yalnız bir kez sayılır.
    a, b = routes[route_a][position_a], routes[route_b][position_b]
    delta = 0
    # Küme, iki müşterinin ortak bağlantısını iki kez hesaplamayı önler.
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
    # Aynı tarama ve eşitlik sırası; aday başına çözüm kopyalanmaz.
    loads = [route_load(route, demands) for route in routes]
    # Negatif fark mesafenin azaldığını gösterir; yalnız iyileşen hareket seçilir.
    best_delta = 0
    best_move = None
    positions = [
        (route_index, position)
        for route_index, route in enumerate(routes)
        for position in range(len(route))
    ]
    for index, (route_a, position_a) in enumerate(positions):
        for route_b, position_b in positions[index + 1:]:
            if route_a == route_b:
                if loads[route_a] > capacity:
                    continue
            else:
                demand_a = demands[routes[route_a][position_a]]
                demand_b = demands[routes[route_b][position_b]]
                if (loads[route_a] - demand_a + demand_b > capacity
                        or loads[route_b] - demand_b + demand_a > capacity):
                    continue
            # İlgisiz rotaları yeniden hesaplamadan takasın mesafe farkını bul.
            delta = _swap_delta(
                routes, route_a, position_a, route_b, position_b, distances
            )
            if delta < best_delta:
                best_delta = delta
                best_move = (route_a, position_a, route_b, position_b)

    # Adayları denerken değil, seçilen takası uygularken çözümü kopyala.
    result = copy_solution(routes)
    if best_move is not None:
        route_a, position_a, route_b, position_b = best_move
        result[route_a][position_a], result[route_b][position_b] = (
            result[route_b][position_b], result[route_a][position_a]
        )
    return result


def relocate_search(routes, distances, demands, capacity):
    # Her müşteri için en iyi taşıma seçilir; ilk eşit aday korunur.
    result = copy_solution(routes)
    loads = [route_load(route, demands) for route in result]
    # Taşımalar rotaları değiştirse de müşterilerin inceleme sırası sabit kalır.
    customers = [customer for route in routes for customer in route]
    for customer in customers:
        source_route, source_position = find_customer(result, customer)
        # Tek müşteriyi taşıyıp kaynak rotayı boş bırakma.
        if len(result[source_route]) <= 1:
            continue
        removal = _removal_delta(result[source_route], source_position, distances)
        best_delta = 0
        best_move = None
        for target_route, route in enumerate(result):
            if target_route == source_route:
                continue
            if loads[target_route] + demands[customer] > capacity:
                continue
            for position in range(len(route) + 1):
                # Toplam fark = kaynak rotadan çıkarma + hedef rotaya ekleme.
                delta = removal + _insertion_delta(route, position, customer, distances)
                if delta < best_delta:
                    best_delta = delta
                    best_move = (target_route, position)
        if best_move is not None:
            target_route, position = best_move
            result[source_route].pop(source_position)
            result[target_route].insert(position, customer)
            loads[source_route] -= demands[customer]
            loads[target_route] += demands[customer]
    return result


def repair(routes, distances, demands, capacity, rng):
    # Rastgele rota sırası ve ilk taşınabilen müşteri kuralı değişmez.
    result = copy_solution(routes)
    loads = [route_load(route, demands) for route in result]
    while any(load > capacity for load in loads):
        overloaded_routes = [index for index, load in enumerate(loads) if load > capacity]
        # Her adımda önce hangi aşırı yüklü rotanın ele alınacağını rastgele seç.
        rng.shuffle(overloaded_routes)
        moved = False
        for source_route in overloaded_routes:
            for source_position, customer in enumerate(result[source_route]):
                if demands[customer] <= 0:
                    continue
                removal = _removal_delta(result[source_route], source_position, distances)
                best_move = None
                best_delta = None
                for target_route, route in enumerate(result):
                    if target_route == source_route:
                        continue
                    if loads[target_route] + demands[customer] > capacity:
                        continue
                    for position in range(len(route) + 1):
                        delta = removal + _insertion_delta(route, position, customer, distances)
                        # Onarımda mesafe artabilir; uygun yerler arasından en iyisini seç.
                        if best_delta is None or delta < best_delta:
                            best_move = (target_route, position)
                            best_delta = delta
                if best_move is not None:
                    target_route, position = best_move
                    result[source_route].pop(source_position)
                    result[target_route].insert(position, customer)
                    loads[source_route] -= demands[customer]
                    loads[target_route] += demands[customer]
                    moved = True
                    break
            if moved:
                break
        # Hiçbir müşteri taşınamıyorsa onarım tamamlanmamış olsa da dur.
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
        # Tur geri alınsa bile ara adımda bulunan en iyi geçerli çözümü sakla.
        if score['feasible'] and (best_distance is None or score['distance'] < best_distance):
            best_feasible = copy_solution(candidate)
            best_distance = score['distance']
        return score

    score = record(result)
    while True:
        previous = copy_solution(result)
        # Önceki değerlendirmeyi kullan; maliyet mesafe ve varsa cezayı içerir.
        previous_cost = score['cost']

        result = swap_search(result, distances, demands, capacity)
        record(result)
        result = relocate_search(result, distances, demands, capacity)
        score = record(result)
        if not score['feasible']:
            result = repair(result, distances, demands, capacity, rng)
            score = record(result)

        # Tam tur iyileştirmediyse tur başına dön; iyileştirdiyse döngü sürer.
        if score['cost'] >= previous_cost:
            return previous, best_feasible
