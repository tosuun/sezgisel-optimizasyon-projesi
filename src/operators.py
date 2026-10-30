"""Sabit CDELS kaynak sürümünün ayrık operatör akışı.

Referans: 9c605e3; MIT bildirimi LICENSE-CDELS.txt içinde.
Makale sözde kodundan ayrılan sayım/örnekleme ayrıntıları raporda belirtilir.
"""

import math


def copy_solution(routes):
    #Her rota listesini de kopyalayarak bağımsız bir çözüm oluşturur.
    copied_routes = []

    for route in routes:
        # Yalnız dış listeyi kopyalamak iç rotaları ortak bırakır; onları da ayır.
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
    # K rota oluşturur; yön seçimi ve kalan müşteriler sabit C kodunu izler.
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

    # C kodu her bireyde rota doldurma yönünü rastgele seçer.
    forward = rng.randrange(2) == 1
    order = list(range(max_vehicles))
    if not forward:
        order.reverse()
    routes = [[] for _ in range(max_vehicles)]
    assigned = set()
    for route_index in order:
        checked = set(assigned)
        load = 0
        # C'deki do/while tüm müşteriler atanmışsa takılabilir; boş rotaları koruyarak çık.
        while len(checked) < len(customers):
            customer = customers[rng.randrange(len(customers))]
            if customer in checked:
                continue
            checked.add(customer)
            if load + demands[customer] < capacity:
                routes[route_index].append(customer)
                assigned.add(customer)
                load += demands[customer]
    # Referansın yönüne göre kalanlar son/ilk rotaya, kimlik sırasıyla eklenir.
    routes[order[-1]].extend(customer for customer in customers if customer not in assigned)

    return routes


def initialize_population(demands, capacity, max_vehicles, population_size, rng):
    #Birbirinden bağımsız NP başlangıç çözümü üretir.
    if not isinstance(population_size, int) or population_size < 4:
        raise ValueError("Popülasyon büyüklüğü en az 4 olan bir tam sayı olmalı.")

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

    # Referans konumdaki müşteriyi seç; diğer çözümde aynı konuma getirmeyi dene.
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

    else:
        # C referansındaki taşıma kaynak rotayı boş bırakabilir; boş rota araç kullanılmamasıdır.
        result[source_route].pop(source_position)
        result[route_index].append(customer)

    # Müşteri zaten hedefteyse takas çözümü değiştirmez.
    # Kapasite bu harekette kısıtlanmaz; sonrasında evaluate ile hesaplanır.
    return result


def mutate(population, target_index, mutation_factor, rng):
    # Kaynak kodun üç ebeveyn seçimini ve konum aktarımını uygular.
    if len(population) < 4:
        raise ValueError("Mutasyon için en az 4 birey gerekli.")

    if not isinstance(target_index, int) or not 0 <= target_index < len(population):
        raise ValueError("Hedef birey numarası geçersiz.")

    if not 0 < mutation_factor <= 1:
        raise ValueError("Mutasyon faktörü 0'dan büyük, 1'den küçük veya eşit olmalı.")

    target = population[target_index]
    customers = sorted(customer for route in target for customer in route)

    if not customers or 0 in customers or len(set(customers)) != len(customers):
        raise ValueError("Hedef çözüm müşterileri tam bir kez içermeli; depo rotada bulunamaz.")

    # x2 kullanılmasa da seçimi rastgele sayı akışını etkiler; sessizce kaldırılmaz.
    count = len(population)
    base_index, unused_index, reference_index = [rng.randrange(count) for _ in range(3)]
    while unused_index == target_index:
        unused_index = rng.randrange(count)
    while reference_index in (target_index, unused_index):
        reference_index = rng.randrange(count)
    while base_index in (target_index, unused_index, reference_index):
        base_index = rng.randrange(count)
    base, reference = population[base_index], population[reference_index]

    for parent in (base, reference):
        parent_customers = sorted(customer for route in parent for customer in route)
        if len(parent) != len(target) or parent_customers != customers:
            raise ValueError("Referans bireyler hedefle aynı rota sayısı ve müşterileri içermeli.")

    mutant = copy_solution(base)
    # C customers_num depo dahil; int dönüşümü kesri atar, do/while en az bir kez çalışır.
    movement_count = max(1, int((len(customers) + 1) * mutation_factor / 2))
    possible = [0] + customers
    available = len(customers)
    for _ in range(movement_count):
        index = rng.randrange(available) + 1
        customer = possible[index]
        route_index, position = find_customer(reference, customer)
        mutant = perturbation_move(mutant, reference, route_index, position)
        # Yayımlanmış listenin kaydırma sınırı korunur: aynı müşteri yeniden seçilebilir.
        # Bu davranış Algoritma 1'deki tekrarsız seçimden farklıdır; raporda açıkça kayıtlıdır.
        while index < available - 1:
            possible[index] = possible[index + 1]
            index += 1
        available -= 1

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
        # Daha önce işlenen müşteriye yeniden konum aktarımı uygulama.
        if customer in closed:
            return

        if position < len(trial[route_index]):
            # Takasta yerinden çıkan müşteriyi de işlenmiş olarak işaretle.
            closed.add(trial[route_index][position])

        trial = perturbation_move(trial, mutant, route_index, position)
        closed.add(customer)

    # Rastgele rota/konumda CR kontrolü olmadan bir hareket girişimi.
    first_route = rng.randrange(len(mutant))
    # Boş rota seçilirse kaynak koddaki gibi sıradaki dolu rotaya yürü.
    while not mutant[first_route]:
        first_route = (first_route + 1) % len(mutant)
    first_position = rng.randrange(len(mutant[first_route]))
    apply_component(first_route, first_position)

    # Tarama rastgele konumdan değil, ilk rotadan başlar.
    for route_index, route in enumerate(mutant):
        for position in range(len(route)):
            # İlk başarısız CR kontrolü tüm çaprazlamayı bitirir.
            if rng.random() > crossover_rate:
                return trial
            apply_component(route_index, position)

    return trial
