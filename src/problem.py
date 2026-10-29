import math
from collections import Counter

def route_load(route, demands): #bir aracın taşıdığı toplam yük
    total_load = 0

    for customer in route:
        total_load += demands[customer]

    return total_load
def distance(customer_a, customer_b, coordinates): #iki konum arası mesafe
    x1, y1 = coordinates[customer_a]
    x2, y2 = coordinates[customer_b]

    raw_distance = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)

    # CVRPLIB kuralı: .5 ve üzerini yukarı yuvarla; round() burada aynı sonucu vermeyebilir.
    return int(raw_distance + 0.5)
def route_distance(route, distances): #bir aracın gidiş dönüş mesafesi
    total_distance = 0
    # Araç depodan çıkar; rota listesinde depo ayrıca yazılı değildir.
    previous = 0

    for customer in route:
        total_distance += distances[previous][customer]
        previous = customer

    # Son müşteriden depoya dönüşü de toplam mesafeye ekle.
    total_distance += distances[previous][0]

    return total_distance
def solution_distance(routes, distances): #bütün araçların toplam mesafesi
    total_distance = 0

    for route in routes:
        total_distance += route_distance(route, distances)

    return total_distance


def check_capacity(routes, demands, capacity): #araç kapasitesinin aşılıp aşılmadığı kontrolü
    for route in routes:
        load = route_load(route, demands)

        if load > capacity:
            return False

    return True
def check_customers(routes, demands): #her müşteri tam bir kez bulunuyor mu kontrolü
    
    visited = []

    for route in routes:
        for customer in route:
            visited.append(customer)

    expected = []

    for customer in demands:
        if customer != 0:  # Depoyu müşteri listesine katma
            expected.append(customer)

    # Sıralı listeler eşitse her müşteri tam bir kez bulunur; tekrarlar da yakalanır.
    return sorted(visited) == sorted(expected)
def check_vehicle_count(routes, max_vehicles): #kullanılan araç sayısı kontrolü
    used_vehicles = 0

    for route in routes:
        if len(route) > 0:
            used_vehicles += 1

    return used_vehicles <= max_vehicles
def validate_solution(routes, demands, capacity, max_vehicles):
    errors = []
    visited = []

    for route in routes:
        visited.extend(route)

    # Depoyu müşteri kümesinden çıkar; eksik ve yabancı kimlikleri ayrı bul.
    expected = set(demands) - {0}

    missing = expected - set(visited)
    invalid = set(visited) - expected
    repeated = {
        customer for customer, count in Counter(visited).items()
        if count > 1
    }

    if missing:
        errors.append(f"Eksik müşteriler: {sorted(missing)}")

    if repeated:
        errors.append(f"Tekrarlı müşteriler: {sorted(repeated)}")

    if invalid:
        errors.append(f"Geçersiz müşteri numaraları: {sorted(invalid)}")

    if not check_vehicle_count(routes, max_vehicles):
        errors.append("Araç sayısı sınırı aşılmış.")

    # Bilinmeyen müşteri varsa talebini okumaya çalışma.
    if not invalid:
        if not check_capacity(routes, demands, capacity):
            errors.append("Araç kapasitesi aşılmış.")

    return errors
def evaluate(routes, distances, demands, capacity,  #çözümün mesafesi ve maliyeti
             max_vehicles, penalty=100):

    if not check_customers(routes, demands):
        raise ValueError("Müşteri listesi hatalı.")

    if not check_vehicle_count(routes, max_vehicles):
        raise ValueError("Araç sayısı sınırı aşılmış.")

    total_distance = solution_distance(routes, distances)
    feasible = check_capacity(routes, demands, capacity)

    cost = total_distance

    # Ceza, kapasite aşan çözümün toplamına bir kez eklenir; müşteri başına değildir.
    if not feasible:
        cost += penalty

    return {
        "distance": total_distance,
        "feasible": feasible,
        "cost": cost,
    }

def build_distance_matrix(coordinates): #bütün nokta çiftlerinin mesafelerini bir kez hesaplayıp saklar.
    distances = {}

    for a in coordinates:
        distances[a] = {}

        for b in coordinates:
            distances[a][b] = distance(a, b, coordinates)

    return distances
