"""Gerçek CVRPLIB dosyasında referans ve kısa CDELS doğrulaması."""

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import platform

from instance_io import read_instance, read_solution
from solver import solve


def audit_solution(routes, instance):
    """Arama maliyetine/matrisine güvenmeden koordinatlardan tekrar denetler."""
    # Her müşteriden tam bir tane beklenir; Counter eksik ve tekrarları birlikte yakalar.
    expected = {customer: 1 for customer in instance['demands'] if customer != 0}
    visited = Counter(customer for route in routes for customer in route)
    errors = []
    if dict(visited) != expected:
        errors.append('Müşteriler tam bir kez bulunmuyor veya kimlik geçersiz.')
    used = sum(bool(route) for route in routes)
    if used > instance['max_vehicles']:
        errors.append('Araç sayısı sınırı aşılmış.')
    loads = []
    distance = 0
    known = all(customer in expected for customer in visited)
    if known:
        for route in routes:
            load = sum(instance['demands'][customer] for customer in route)
            loads.append(load)
            # Depodan çıkış ve depoya dönüş bağlantılarını açıkça ekle.
            path = [0] + route + [0]
            for a, b in zip(path, path[1:]):
                x1, y1 = instance['coordinates'][a]
                x2, y2 = instance['coordinates'][b]
                # Aramanın mesafe matrisini kullanmadan koordinatlardan bağımsız hesap yap.
                distance += math.floor(math.hypot(x2 - x1, y2 - y1) + 0.5)
        if any(load > instance['capacity'] for load in loads):
            errors.append('Araç kapasitesi aşılmış.')
    else:
        distance = None
    return {'valid': not errors, 'errors': errors, 'distance': distance,
            'route_loads': loads, 'used_vehicles': used}


def run_pilot(instance_path, solution_path, max_generations=5, seed=42,
              known_optimum=None, max_vehicles=None, id_convention='cvrplib'):
    instance = read_instance(instance_path, max_vehicles)
    reference = read_solution(solution_path, instance, id_convention)
    reference_audit = audit_solution(reference['routes'], instance)
    if not reference_audit['valid'] or reference_audit['distance'] != reference['reported_cost']:
        raise ValueError('Referans çözüm bağımsız koordinat hesabıyla doğrulanamadı.')
    if known_optimum is not None and known_optimum != reference['reported_cost']:
        raise ValueError('Girilen bilinen optimum, doğrulanmış referansla eşleşmiyor.')

    # Referans rotaları başlangıç olarak verme; algoritma kendi popülasyonunu üretir.
    result = solve(
        instance['distances'], instance['demands'], instance['capacity'], instance['max_vehicles'],
        population_size=3 * instance['n_customers'], mutation_factor=0.7,
        crossover_rate=0.7, penalty=100, max_generations=max_generations,
        seed=seed, known_optimum=known_optimum,
    )
    audit = None
    gap = None
    original_routes = None
    if result['best_routes'] is not None:
        audit = audit_solution(result['best_routes'], instance)
        if not audit['valid'] or audit['distance'] != result['distance']:
            raise ValueError('Bulunan planın bağımsız kontrolü başarısız.')
        if known_optimum is not None and audit['distance'] < known_optimum:
            raise ValueError('Bulunan maliyet bilinen optimumun altında: veri/mesafe/kısıtlar incelenmeli.')
        cost = reference['reported_cost']
        # Sapma yüzdesi: bulunan mesafenin referansın ne kadar üstünde olduğunu gösterir.
        gap = 100 * (result['distance'] - cost) / cost if cost else (0 if result['distance'] == 0 else None)
        original_routes = [[instance['internal_to_original'][c] for c in route]
                           for route in result['best_routes']]

    # Sonucun hangi kod sürümüyle üretildiğini kaydet.
    source_hashes = {
        name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
        for name in ['problem.py', 'operators.py', 'local_search.py', 'solver.py', 'instance_io.py', 'run_pilot.py']
    }
    return {
        'stage': 'E_short_pilot_not_paper_replication',
        'instance': {key: instance[key] for key in [
            'name', 'dimension', 'n_customers', 'capacity', 'max_vehicles',
            'vehicle_count_sources', 'original_depot_id', 'distance_rule',
        ]},
        'input_files': {
            'instance_path': str(Path(instance_path).resolve()),
            'solution_path': str(Path(solution_path).resolve()),
            'instance_sha256': hashlib.sha256(Path(instance_path).read_bytes()).hexdigest(),
            'solution_sha256': hashlib.sha256(Path(solution_path).read_bytes()).hexdigest(),
            'solution_id_convention': id_convention,
        },
        'reference': {**reference, 'independent_audit': reference_audit,
                      'optimum_asserted_by_caller': known_optimum is not None},
        'result': result, 'independent_audit': audit,
        'best_routes_original_node_ids': original_routes,
        'gap_percent': gap, 'python_version': platform.python_version(),
        'platform': platform.platform(), 'source_sha256': source_hashes,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('instance', type=Path)
    parser.add_argument('solution', type=Path)
    parser.add_argument('--max-generations', type=int, default=5)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--known-optimum', type=int, default=None,
                        help='Yalnız optimumluğu ayrıca doğrulanmış değer için kullanılır.')
    parser.add_argument('--vehicles', type=int, default=None)
    parser.add_argument('--solution-ids', choices=['cvrplib', 'original'], default='cvrplib')
    parser.add_argument('--output', type=Path, default=None)
    args = parser.parse_args()
    record = run_pilot(args.instance, args.solution, args.max_generations, args.seed,
                       args.known_optimum, args.vehicles, args.solution_ids)
    text = json.dumps(record, ensure_ascii=False, indent=2) + '\n'
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        # x kipi, aynı isimli eski bir sonucu yanlışlıkla ezmeyi engeller.
        with args.output.open('x') as file:
            file.write(text)
    print(text, end='')


if __name__ == '__main__':
    main()
