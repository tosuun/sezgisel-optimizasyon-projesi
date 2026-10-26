import math

# 0 depo, 1–5 müşteriler
coordinates = {
    0: (0, 0),
    1: (3, 0),
    2: (0, 4),
    3: (3, 4),
    4: (6, 0),
    5: (6, 4),
}
demands = {
    0: 0,
    1: 6,
    2: 3,
    3: 5,
    4: 4,
    5: 2,
}
capacity = 10
max_vehicles = 2

routes = [[1, 4], [2, 5, 3]]

def route_load(route, demands): #bir aracın taşıdığı toplam yük
    total_load = 0

    for customer in route:
        total_load += demands[customer]

    return total_load
def distance(customer_a, customer_b, coordinates): #iki konum arası mesafe
    x1, y1 = coordinates[customer_a]
    x2, y2 = coordinates[customer_b]

    raw_distance = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)

    return int(raw_distance + 0.5)
def route_distance(route,coordinates): #bir aracın gidiş dönüş mesafesi

    total_distance = 0
    previous = 0
    for customer in route:
        total_distance += distance(previous, customer, coordinates)
        previous = customer
    total_distance += distance(previous, 0, coordinates)
    return total_distance
def solution_distance(routes, coordinates): #bütün araçların toplam mesafesi


    total_distance = 0

    for route in routes:
        total_distance += route_distance(route, coordinates)

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

    return sorted(visited) == sorted(expected)
def check_vehicle_count(routes, max_vehicles): #kullanılan araç sayısı kontrolü
    used_vehicles = 0

    for route in routes:
        if len(route) > 0:
            used_vehicles += 1

    return used_vehicles <= max_vehicles
def validate_solution(routes, demands, capacity, max_vehicles): #hata kontrolleri
    errors = []

    customers_ok = check_customers(routes, demands)

    if not customers_ok:
        errors.append("Müşteri listesi hatalı: eksik, tekrarlı veya geçersiz müşteri.")

    if not check_vehicle_count(routes, max_vehicles):
        errors.append("Araç sayısı sınırı aşılmış.")

    if customers_ok:
        if not check_capacity(routes, demands, capacity):
            errors.append("Araç kapasitesi aşılmış.")

    return errors

def evaluate(routes, coordinates, demands, capacity,  #çözümün mesafesi ve maliyeti
             max_vehicles, penalty=100):

    if not check_customers(routes, demands):
        raise ValueError("Müşteri listesi hatalı.")

    if not check_vehicle_count(routes, max_vehicles):
        raise ValueError("Araç sayısı sınırı aşılmış.")

    total_distance = solution_distance(routes, coordinates)
    feasible = check_capacity(routes, demands, capacity)

    cost = total_distance

    if not feasible:
        cost += penalty

    return {
        "distance": total_distance,
        "feasible": feasible,
        "cost": cost,
    }


routes = [[1, 4], [2, 5, 3]]

result = evaluate(
    routes, coordinates, demands, capacity, max_vehicles
)

print(result)