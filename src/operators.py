import math


def copy_solution(routes):
    #Her rota listesini de kopyalayarak bağımsız bir çözüm oluşturur.
    copied_routes = []

    for route in routes:
        copied_routes.append(route.copy())

    return copied_routes


def find_customer(routes, customer):
    #Müşterinin (rota, konum) bilgisini döndürür; indisler 0'dan başlar.
    for route_index, route in enumerate(routes):
        for position, current_customer in enumerate(route):
            if current_customer == customer:
                return route_index, position

    raise ValueError(f"Müşteri çözümde bulunamadı: {customer}")

def initialize_individual(demands, capacity, max_vehicles, rng):
    #K rota oluşturur; sığmayan müşterileri tek rastgele rotaya ekler.
    if not math.isfinite(capacity) or capacity <= 0:
        raise ValueError("Araç kapasitesi pozitif olmalı.")

    if not isinstance(max_vehicles, int) or max_vehicles < 1:
        raise ValueError("Araç sayısı pozitif bir tam sayı olmalı.")

    if 0 not in demands or demands[0] != 0:
        raise ValueError("Depo 0 olmalı ve talebi 0 olmalı.")

    customers = sorted(customer for customer in demands if customer != 0)

    if not customers:
        raise ValueError("En az bir müşteri olmalı.")

    for customer in customers:
        if (not math.isfinite(demands[customer])
                or demands[customer] < 0 or demands[customer] > capacity):
            raise ValueError(f"Müşteri talebi 0 ile kapasite arasında olmalı: {customer}")

    if sum(demands[customer] for customer in customers) > capacity * max_vehicles:
        raise ValueError("Toplam talep, araçların toplam kapasitesini aşıyor.")

    routes = [[] for _ in range(max_vehicles)]
    remaining = customers

    for route in routes:
        candidates = remaining.copy()
        rng.shuffle(candidates)
        remaining = []
        load = 0

        for customer in candidates:
            if load + demands[customer] <= capacity:
                route.append(customer)
                load += demands[customer]
            else:
                remaining.append(customer)

    # Bütün müşteriler çözümde bulunmalı; kapasite ihlali cezayla ele alınır.
    if remaining:
        selected_route = rng.randrange(max_vehicles)
        routes[selected_route].extend(remaining)

    return routes


def initialize_population(demands, capacity, max_vehicles, population_size, rng):
    #Birbirinden bağımsız NP başlangıç çözümü üretir.
    if not isinstance(population_size, int) or population_size < 3:
        raise ValueError("Popülasyon büyüklüğü en az 3 olan bir tam sayı olmalı.")

    population = []

    for _ in range(population_size):
        individual = initialize_individual(demands, capacity, max_vehicles, rng)
        population.append(individual)

    return population


def perturbation_move(routes, reference, route_index, position):
    #Referanstaki konuma göre takas/taşıma yapar; yeni çözüm döndürür.
    if len(routes) != len(reference):
        raise ValueError("Çözüm ve referans aynı sayıda rota listesi içermeli.")

    if not isinstance(route_index, int) or not 0 <= route_index < len(reference):
        raise ValueError("Referans rota numarası geçersiz.")

    if not isinstance(position, int) or not 0 <= position < len(reference[route_index]):
        raise ValueError("Referans rota konumu geçersiz.")

    customer = reference[route_index][position]

    if customer == 0:
        raise ValueError("Depo müşteri gibi taşınamaz.")

    source_route, source_position = find_customer(routes, customer)
    result = copy_solution(routes)

    if position < len(result[route_index]):
        # Hedef konum dolu: seçilen müşteriyle oradaki müşteriyi takas et.
        displaced_customer = result[route_index][position]
        result[route_index][position] = customer
        result[source_route][source_position] = displaced_customer

    elif len(result[source_route]) > 1:
        # Hedef konum yok: kaynak rotayı boşaltmadan hedefin sonuna taşı.
        result[source_route].pop(source_position)
        result[route_index].append(customer)

    # Müşteri zaten yerindeyse veya tek müşterili rota korunuyorsa değişmez.
    # Kapasite bu harekette kısıtlanmaz; sonrasında evaluate ile hesaplanır.
    return result


def mutate(population, target_index, mutation_factor, rng):
    #İki farklı referans bireyden, konum hareketleriyle mutant üretir.
    if len(population) < 3:
        raise ValueError("Mutasyon için en az 3 birey gerekli.")

    if not isinstance(target_index, int) or not 0 <= target_index < len(population):
        raise ValueError("Hedef birey numarası geçersiz.")

    if not 0 < mutation_factor <= 1:
        raise ValueError("Mutasyon faktörü 0'dan büyük, 1'den küçük veya eşit olmalı.")

    target = population[target_index]
    customers = sorted(customer for route in target for customer in route)

    if not customers or 0 in customers or len(set(customers)) != len(customers):
        raise ValueError("Hedef çözüm müşterileri tam bir kez içermeli; depo rotada bulunamaz.")

    possible_indices = [
        index for index in range(len(population)) if index != target_index
    ]
    base_index, reference_index = rng.sample(possible_indices, 2)
    base = population[base_index]
    reference = population[reference_index]

    for parent in (base, reference):
        parent_customers = sorted(customer for route in parent for customer in route)
        if len(parent) != len(target) or parent_customers != customers:
            raise ValueError("Referans bireyler hedefle aynı rota sayısı ve müşterileri içermeli.")

    mutant = copy_solution(base)
    movement_count = math.ceil(len(customers) * mutation_factor / 2)
    selected_customers = rng.sample(customers, movement_count)

    for customer in selected_customers:
        route_index, position = find_customer(reference, customer)
        mutant = perturbation_move(mutant, reference, route_index, position)

    return mutant


def crossover_exp(target, mutant, crossover_rate, rng):
    #Target kopyasına mutant konumlarını aktarır; ilk CR aşımında durur.
    if not 0 <= crossover_rate <= 1:
        raise ValueError("Çaprazlama oranı 0 ile 1 arasında olmalı.")

    customers = sorted(customer for route in target for customer in route)
    mutant_customers = sorted(customer for route in mutant for customer in route)
    if (not customers or 0 in customers or len(set(customers)) != len(customers)
            or customers != mutant_customers or len(target) != len(mutant)):
        raise ValueError("Target ve mutant aynı müşterileri birer kez ve aynı rota sayısıyla içermeli.")

    trial = copy_solution(target)
    closed = set()

    def apply_component(route_index, position):
        nonlocal trial
        customer = mutant[route_index][position]
        if customer in closed:
            return

        if position < len(trial[route_index]):
            closed.add(trial[route_index][position])

        trial = perturbation_move(trial, mutant, route_index, position)
        closed.add(customer)

    # Rastgele rota/konumda CR kontrolü olmadan bir hareket girişimi.
    nonempty_routes = [index for index, route in enumerate(mutant) if route]
    first_route = rng.choice(nonempty_routes)
    first_position = rng.randrange(len(mutant[first_route]))
    apply_component(first_route, first_position)

    # Tarama rastgele konumdan değil, ilk rotadan başlar.
    for route_index, route in enumerate(mutant):
        for position in range(len(route)):
            if rng.random() > crossover_rate:
                return trial
            apply_component(route_index, position)

    return trial
