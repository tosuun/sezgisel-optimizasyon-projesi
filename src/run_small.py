from problem import build_distance_matrix, evaluate, validate_solution
from solver import solve


def main():
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

    distances = build_distance_matrix(coordinates)
    routes = [[1, 4], [2, 5, 3]]

    valid_routes = [[1, 4], [2, 5, 3]]
    overloaded_routes = [[1, 4, 2], [5, 3]]

    print("Geçerli çözüm:")
    print(evaluate(
        valid_routes, distances, demands, capacity, max_vehicles
    ))

    print("Kapasitesi aşılmış çözüm:")
    print(evaluate(
        overloaded_routes, distances, demands, capacity, max_vehicles
    ))
    print(validate_solution(
        [[1, 4], [2, 3]],
        demands, capacity, max_vehicles
    ))

    print(validate_solution(
        [[1, 4], [2, 5, 3, 2]],
        demands, capacity, max_vehicles
    ))

    print(validate_solution(
        [[1, 4], [2, 5, 3, 99]],
        demands, capacity, max_vehicles
    ))

    print("\nCDELS küçük doğruluk denemesi (tohum=42, NP=15, 20 nesil):")
    result = solve(
        distances, demands, capacity, max_vehicles,
        population_size=15, max_generations=20, seed=42,
    )
    print(result)
    if result['best_routes'] is not None:
        print("Son planın bağımsız uygunluk kontrolü:")
        print(validate_solution(result['best_routes'], demands, capacity, max_vehicles))
        for vehicle, route in enumerate(result['best_routes'], start=1):
            path = [0] + route + [0]
            print(f"Araç {vehicle}: " + " → ".join(map(str, path)))


if __name__ == "__main__":
    main()
