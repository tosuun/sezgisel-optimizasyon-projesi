"""Tek depolu EUC_2D CVRPLIB verisini ve açık kimlik kuralıyla çözümü okur."""

import math
from pathlib import Path
import re

from problem import build_distance_matrix, solution_distance, validate_solution


def read_instance(path, max_vehicles=None):
    """Dosya kimliklerini depo=0, müşteriler=1..N olacak şekilde eşler."""
    path = Path(path)
    headers = {}
    coordinates = {}
    demands = {}
    depots = []
    section = None
    depot_ended = False

    for line_number, raw in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        if line.upper() == 'EOF':
            break
        if line.upper().endswith('_SECTION'):
            section = line.upper()
            if section not in {'NODE_COORD_SECTION', 'DEMAND_SECTION', 'DEPOT_SECTION'}:
                raise ValueError(f'Desteklenmeyen veri bölümü: {section}')
            continue

        try:
            if section == 'NODE_COORD_SECTION':
                fields = line.split()
                if len(fields) != 3:
                    raise ValueError('Koordinat satırı kimlik, x ve y içermeli.')
                node, x, y = int(fields[0]), float(fields[1]), float(fields[2])
                if node < 0 or node in coordinates or not all(map(math.isfinite, (x, y))):
                    raise ValueError('Tekrarlı/geçersiz kimlik veya koordinat.')
                coordinates[node] = (x, y)
            elif section == 'DEMAND_SECTION':
                fields = line.split()
                if len(fields) != 2:
                    raise ValueError('Talep satırı kimlik ve tam sayı talep içermeli.')
                node, demand = map(int, fields)
                if node < 0 or node in demands or demand < 0:
                    raise ValueError('Tekrarlı/geçersiz kimlik veya negatif talep.')
                demands[node] = demand
            elif section == 'DEPOT_SECTION':
                for value in map(int, line.split()):
                    if depot_ended:
                        raise ValueError('Depo bitişinden sonra fazladan değer var.')
                    if value == -1:
                        depot_ended = True
                    else:
                        depots.append(value)
            else:
                parts = line.split(':', 1) if ':' in line else line.split(None, 1)
                if len(parts) != 2:
                    raise ValueError('Başlık anahtar ve değer içermeli.')
                key, value = parts[0].strip().upper(), parts[1].strip()
                if key == 'COMMENT' and key in headers:
                    headers[key] += ' ' + value
                elif key in headers:
                    raise ValueError(f'Tekrarlı başlık: {key}')
                else:
                    headers[key] = value
        except ValueError as error:
            raise ValueError(f'{path.name}, satır {line_number}: {error}') from error

    if headers.get('TYPE', '').upper() != 'CVRP':
        raise ValueError('Yalnız TYPE=CVRP destekleniyor.')
    if headers.get('EDGE_WEIGHT_TYPE', '').upper() != 'EUC_2D':
        raise ValueError('Yalnız EUC_2D ve en yakın tam sayı mesafesi destekleniyor.')
    if headers.get('NODE_COORD_TYPE', 'TWOD_COORDS').upper() != 'TWOD_COORDS':
        raise ValueError('Yalnız iki boyutlu koordinatlar destekleniyor.')

    try:
        dimension = int(headers['DIMENSION'])
        capacity = int(headers['CAPACITY'])
    except (KeyError, ValueError) as error:
        raise ValueError('DIMENSION ve CAPACITY tam sayı olarak gerekli.') from error
    if dimension < 2 or capacity <= 0:
        raise ValueError('En az bir müşteri ve pozitif kapasite gerekli.')
    if len(coordinates) != dimension or set(coordinates) != set(demands):
        raise ValueError('DIMENSION, koordinat ve talep kimlikleri eşleşmiyor.')
    if not depot_ended or len(depots) != 1 or depots[0] not in coordinates:
        raise ValueError('DEPOT_SECTION tek geçerli depo ve -1 bitişi içermeli.')

    depot = depots[0]
    if demands[depot] != 0 or any(value > capacity for value in demands.values()):
        raise ValueError('Depo talebi 0 olmalı; müşteri talebi kapasiteyi aşamaz.')

    name = headers.get('NAME', path.stem)
    vehicle_sources = {}
    if 'VEHICLES' in headers:
        vehicle_sources['VEHICLES'] = int(headers['VEHICLES'])
    match = re.search(r'-k(\d+)$', name, re.IGNORECASE)
    if match:
        vehicle_sources['NAME'] = int(match.group(1))
    match = re.search(r'No\.?\s*of\s*(?:trucks|vehicles)\s*:\s*(\d+)',
                      headers.get('COMMENT', ''), re.IGNORECASE)
    if match:
        vehicle_sources['COMMENT'] = int(match.group(1))
    if max_vehicles is not None:
        if not isinstance(max_vehicles, int):
            raise ValueError('Araç sayısı tam sayı olmalı.')
        vehicle_sources['argument'] = max_vehicles
    if not vehicle_sources or len(set(vehicle_sources.values())) != 1:
        raise ValueError(f'Araç sayısı eksik veya kaynaklar çelişkili: {vehicle_sources}')
    vehicles = next(iter(vehicle_sources.values()))
    if vehicles < 1:
        raise ValueError('Araç sayısı pozitif olmalı.')

    ordered_nodes = [depot] + sorted(node for node in coordinates if node != depot)
    original_to_internal = {node: index for index, node in enumerate(ordered_nodes)}
    internal_to_original = dict(enumerate(ordered_nodes))
    mapped_coordinates = {original_to_internal[node]: value for node, value in coordinates.items()}
    mapped_demands = {original_to_internal[node]: value for node, value in demands.items()}

    return {
        'name': name, 'dimension': dimension, 'n_customers': dimension - 1,
        'capacity': capacity, 'max_vehicles': vehicles,
        'vehicle_count_sources': vehicle_sources,
        'edge_weight_type': 'EUC_2D', 'distance_rule': 'floor(euclidean_distance + 0.5)',
        'original_depot_id': depot,
        'original_to_internal': original_to_internal,
        'internal_to_original': internal_to_original,
        'coordinates': mapped_coordinates, 'demands': mapped_demands,
        'distances': build_distance_matrix(mapped_coordinates),
        'source_path': str(path.resolve()), 'comment': headers.get('COMMENT', ''),
    }


def read_solution(path, instance, id_convention='cvrplib'):
    """cvrplib: müşteri sırası 1..N; original: .vrp dosyasındaki ham kimlikler."""
    if id_convention not in {'cvrplib', 'original'}:
        raise ValueError('Çözüm kimlik kuralı cvrplib veya original olmalı; otomatik tahmin yok.')
    routes = []
    labels = set()
    cost = None
    for raw in Path(path).read_text(encoding='utf-8-sig').splitlines():
        line = raw.strip()
        if not line or line.upper() == 'EOF':
            continue
        match = re.fullmatch(r'Route\s*#\s*(\d+)\s*:\s*(.*)', line, re.IGNORECASE)
        if match:
            label = int(match.group(1))
            if label in labels:
                raise ValueError('Tekrarlı rota numarası.')
            labels.add(label)
            route = []
            for value in match.group(2).split():
                node = int(value)
                if id_convention == 'original':
                    if node not in instance['original_to_internal']:
                        raise ValueError(f'Bilinmeyen özgün kimlik: {node}')
                    node = instance['original_to_internal'][node]
                if not 1 <= node <= instance['n_customers']:
                    raise ValueError(f'Geçersiz müşteri/depo kimliği: {node}')
                route.append(node)
            routes.append(route)
            continue
        match = re.fullmatch(r'Cost\s*:?\s*([+\-\d.eE]+)', line, re.IGNORECASE)
        if match and cost is None:
            cost = float(match.group(1))
            continue
        raise ValueError(f'Desteklenmeyen/tekrarlı çözüm satırı: {line}')

    if not routes or cost is None or not math.isfinite(cost) or cost < 0:
        raise ValueError('Referans çözüm rotalar ve sonlu, negatif olmayan Cost içermeli.')
    errors = validate_solution(routes, instance['demands'], instance['capacity'], instance['max_vehicles'])
    if errors:
        raise ValueError('Referans çözüm geçersiz: ' + '; '.join(errors))
    recomputed = solution_distance(routes, instance['distances'])
    if recomputed != cost:
        raise ValueError(f'Referans maliyeti eşleşmiyor: dosya={cost}, hesap={recomputed}')
    return {'routes': routes, 'reported_cost': int(cost) if cost.is_integer() else cost,
            'recomputed_cost': recomputed, 'id_convention': id_convention}
