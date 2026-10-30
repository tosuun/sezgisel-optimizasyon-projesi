"""Tek deneyin tüm tekrarlarını denetler; makale tabloları ve grafikler üretir.

--experiment deney klasörünü, --output yeni analiz klasörünü seçer.
Bu araç optimizasyon başlatmaz. Eksik deneyden nihai karşılaştırma üretmez.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

from instance_io import read_instance, read_solution
from problem import route_distance
from run_pilot import audit_solution

GROUP_ORDER = 'ABPEFM'


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def require(condition, message):
    # Veri denetimleri Python -O seçeneğinde de çalışmalı.
    if not condition:
        raise ValueError(message)


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value):
    encoded = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def percentage_gap(distance, reference):
    if distance is None:
        return None
    if reference == 0:
        require(distance == 0, 'Sıfır referansa göre yüzde sapma hesaplanamaz.')
        return 0
    return 100 * (distance - reference) / reference


def complete_mean(values):
    # Eksik sonucu dışlayıp ortalamayı olduğundan iyi gösterme.
    values = list(values)
    return statistics.mean(values) if values and all(value is not None for value in values) else None


def inspect_run(path, entry, experiment_identity, config):
    """Bir terminal sonucu ve kullandığı veri dosyalarını bağımsız doğrular."""
    record = read_json(path)
    result = record['result']
    identity = record['run_identity']
    name, seed = identity['name'], identity['seed']
    require(name == record['instance']['name'] == entry['name'], 'Problem adları çelişiyor.')
    require(seed == result['seed'] and seed in config['seeds'], f'{name}: Tohum bilgisi çelişiyor.')
    require(identity['experiment_identity_sha256'] == experiment_identity,
            f'{name}: Sonuç başka bir deneye ait.')
    require(record['profile_id'] == config['profile_id'], f'{name}: Profil farklı.')
    require(record['status'] in {'completed', 'no_feasible_solution'},
            f'{name}: Koşu tamamlanmamış.')
    require(path.parent.name == f'{name}_seed{seed}', f'{name}: Koşu klasörü yanlış.')

    instance_path = PROJECT_ROOT / entry['instance_path']
    solution_path = PROJECT_ROOT / entry['solution_path']
    for source, expected_hash, recorded_hash in [
        (instance_path, entry['vrp_sha256'], identity['instance_sha256']),
        (solution_path, entry['sol_sha256'], identity['solution_sha256']),
    ]:
        require(file_hash(source) == expected_hash == recorded_hash,
                f'{name}: Veri dosyası kayıttaki sürümle eşleşmiyor.')
    instance = read_instance(instance_path)
    reference = read_solution(solution_path, instance, config['solution_id_convention'])
    reference_audit = audit_solution(reference['routes'], instance)
    require(reference_audit['valid'] and reference_audit['distance']
            == reference['reported_cost'] == entry['reference_cost'] == entry['paper_bks'],
            f'{name}: Referans çözüm veya makale değeri doğrulanamadı.')

    expected_parameters = {
        'population_size': 3 * (entry['dimension'] if config['algorithm']['population_size_rule']
                                == '3 * n_nodes_including_depot' else entry['n_customers']),
        'mutation_factor': config['algorithm']['mutation_factor'],
        'crossover_rate': config['algorithm']['crossover_rate'],
        'penalty': config['algorithm']['penalty'],
        'max_generations': config['max_generations_by_group'][entry['group']],
        'time_limit_seconds': config.get('time_limit_seconds'),
        'known_optimum': entry['reference_cost'] if config['known_optimum_early_stop'] else None,
    }
    if config['algorithm'].get('implementation_protocol'):
        expected_parameters['implementation_protocol'] = config['algorithm']['implementation_protocol']
    require(all(result['parameters'][key] == value for key, value in expected_parameters.items()),
            f'{name}: Koşu ayarları deney profiliyle eşleşmiyor.')
    require(result['stop_reason'] in {'known_optimum', 'max_generations', 'time_limit'},
            f'{name}: Geçersiz bitiş nedeni.')
    seconds = result['elapsed_seconds']
    require(isinstance(seconds, (int, float)) and 0 <= seconds < float('inf'),
            f'{name}: Geçersiz çalışma süresi.')

    if result.get('cpu_seconds') is not None:
        require(0 <= result['cpu_seconds'] < float('inf'), f'{name}: Geçersiz CPU süresi.')
    routes = result['best_routes']
    distance = None
    if routes is None:
        require(record['status'] == 'no_feasible_solution' and not result['feasible']
                and result['distance'] is None and record['gap_percent'] is None,
                f'{name}: Geçerli plan olmadan başarı raporlanmış.')
    else:
        audit = audit_solution(routes, instance)
        require(record['status'] == 'completed' and result['feasible'] and audit['valid']
                and audit['distance'] == result['distance'],
                f'{name}: Sonucun uygunluğu veya mesafesi doğrulanamadı.')
        distance = audit['distance']
        gap = percentage_gap(distance, entry['reference_cost'])
        require(gap >= 0 and abs(gap - record['gap_percent']) < 1e-9,
                f'{name}: Sapma yanlış veya maliyet optimumun altında.')
    return {
        'name': name, 'seed': seed, 'status': record['status'], 'valid': routes is not None,
        'distance': distance, 'gap': percentage_gap(distance, entry['reference_cost']),
        'seconds': seconds, 'cpu_seconds': result.get('cpu_seconds'), 'stop': result['stop_reason'],
        'generations': result['generations'], 'partial': result['partial_generation_targets'],
        'routes': routes,
    }


def summarize_instance(entry, runs):
    """Tek problemin tekrarlarından Best, Avg. ve örnek standart sapmayı çıkarır."""
    valid_runs = [run for run in runs if run['valid']]
    distances = [run['distance'] for run in runs]
    best_run = min(valid_runs, key=lambda run: (run['distance'], run['seed'])) if valid_runs else None
    average = complete_mean(distances)
    # Bir tekrar bile geçersizse Avg./SD yoktur; yalnız başarılı koşuları ortalama.
    deviation = statistics.stdev(distances) if average is not None and len(runs) > 1 else None
    return {
        'name': entry['name'], 'group': entry['group'], 'n': entry['n_customers'],
        'k': entry['max_vehicles'], 'capacity': entry['capacity'], 'optimum': entry['reference_cost'],
        'paper_best': entry['paper_cdels_best'], 'paper_avg': entry['paper_cdels_average'],
        'paper_seconds': entry['paper_average_seconds'],
        'repeat_count': len(runs), 'valid_runs': len(valid_runs),
        'best': best_run['distance'] if best_run else None, 'avg': average, 'std': deviation,
        'best_seed': best_run['seed'] if best_run else None,
        'gap_best': percentage_gap(best_run['distance'], entry['reference_cost']) if best_run else None,
        'gap_avg': percentage_gap(average, entry['reference_cost']),
        'paper_gap_best': percentage_gap(entry['paper_cdels_best'], entry['reference_cost']),
        'paper_gap_avg': percentage_gap(entry['paper_cdels_average'], entry['reference_cost']),
        'seconds_avg': statistics.mean(run['seconds'] for run in runs),
        'cpu_seconds_avg': complete_mean(run['cpu_seconds'] for run in runs),
        'seconds_sum': sum(run['seconds'] for run in runs),
        'optimum_runs': sum(run['distance'] == entry['reference_cost'] for run in valid_runs),
        'all_optimum': all(run['valid'] and run['distance'] == entry['reference_cost'] for run in runs),
        'stops': dict(Counter(run['stop'] for run in runs)),
    }


def summarize_groups(instances):
    groups = []
    for group in GROUP_ORDER:
        rows = [row for row in instances if row['group'] == group]
        if not rows:
            continue
        groups.append({
            'name': group, 'count': len(rows),
            'best_optimum': sum(row['gap_best'] == 0 for row in rows),
            'all_optimum': sum(row['all_optimum'] for row in rows),
            'paper_best_optimum': sum(row['paper_best'] == row['optimum'] for row in rows),
            'paper_all_optimum': sum(row['paper_avg'] == row['optimum'] for row in rows),
            'mean_gap_best': complete_mean(row['gap_best'] for row in rows),
            'mean_gap_avg': complete_mean(row['gap_avg'] for row in rows),
            'paper_mean_gap_best': complete_mean(row['paper_gap_best'] for row in rows),
            'paper_mean_gap_avg': complete_mean(row['paper_gap_avg'] for row in rows),
        })
    return groups


def gap_histogram(instances):
    intervals = [
        ('0', lambda gap: gap == 0), ('(0, 1]', lambda gap: 0 < gap <= 1),
        ('(1, 5]', lambda gap: 1 < gap <= 5), ('(5, 10]', lambda gap: 5 < gap <= 10),
        ('(10, 20]', lambda gap: 10 < gap <= 20), ('>20', lambda gap: gap > 20),
    ]
    histogram = []
    for label, contains in intervals:
        histogram.append({'label': label, **{
            field: sum(row[field] is not None and contains(row[field]) for row in instances)
            for field in ['gap_best', 'gap_avg']}})
    histogram.append({'label': 'Hesaplanamadı', **{
        field: sum(row[field] is None for row in instances) for field in ['gap_best', 'gap_avg']}})
    return histogram


def sample_route(instances, runs, entries):
    # A-n32-k5'in en iyi tekrarı seçilir; yoksa başka bir geçerli örnek kullanılır.
    available = [row for row in instances if row['best'] is not None]
    if not available:
        return None
    row = next((row for row in available if row['name'] == 'A-n32-k5'), available[0])
    run = next(run for run in runs if (run['name'], run['seed']) == (row['name'], row['best_seed']))
    instance = read_instance(PROJECT_ROOT / entries[row['name']]['instance_path'])
    routes = run['routes']
    return {
        'name': row['name'], 'seed': run['seed'], 'distance': row['best'],
        'coordinates': instance['coordinates'], 'routes': routes,
        'loads': [sum(instance['demands'][customer] for customer in route) for route in routes],
        'distances': [route_distance(route, instance['distances']) for route in routes],
        'capacity': row['capacity'], 'n': row['n'],
    }


def analyze(experiment_directory):
    metadata = read_json(experiment_directory / 'metadata.json')
    config = metadata['config']
    manifest_path = PROJECT_ROOT / config['instance_manifest']
    require(file_hash(manifest_path) == metadata['identity']['manifest_sha256'],
            'Veri listesi deneyden sonra değişmiş.')
    entries = {entry['name']: entry for entry in read_json(manifest_path)['instances']}
    names, seeds = config['instances'], config['seeds']
    jobs = {(name, seed) for name in names for seed in seeds}
    require(names and seeds and len(set(names)) == len(names) and len(set(seeds)) == len(seeds),
            'Örnek ve tohum listeleri boş veya tekrarlı.')
    require(config['instance_count'] == len(names) and config['repeat_count'] == len(seeds)
            and config['planned_run_count'] == len(jobs), 'Deney sayıları tutarsız.')
    experiment_identity = digest(metadata['identity'])
    require(metadata['experiment_id'] == config['profile_id'] + '-' + experiment_identity[:16],
            'Deney kimliği metadata ile eşleşmiyor.')
    observed = set()
    runs = []
    for path in sorted((experiment_directory / 'runs').glob('*/result.json')):
        raw_identity = read_json(path)['run_identity']
        job = (raw_identity['name'], raw_identity['seed'])
        require(job in jobs and job not in observed, f'Fazladan veya tekrarlı koşu: {job}')
        runs.append(inspect_run(path, entries[job[0]], experiment_identity, config))
        observed.add(job)
    require(observed == jobs,
            f'Deney tamamlanmamış: {len(observed)}/{len(jobs)} terminal sonuç. Eksik koşuları tamamlayın.')
    instances = [summarize_instance(entries[name], sorted(
        [run for run in runs if run['name'] == name], key=lambda run: run['seed'])) for name in names]
    instances.sort(key=lambda row: (GROUP_ORDER.index(row['group']), row['n'], row['k']))
    summary = {
        'instance_count': len(instances), 'repeat_count': len(seeds), 'run_count': len(runs),
        'valid_runs': sum(run['valid'] for run in runs),
        'no_feasible_solution_runs': sum(not run['valid'] for run in runs),
        'instances_best_optimum': sum(row['gap_best'] == 0 for row in instances),
        'instances_all_optimum': sum(row['all_optimum'] for row in instances),
        'optimum_runs': sum(row['optimum_runs'] for row in instances),
        'paper_best_optimum': sum(row['paper_best'] == row['optimum'] for row in instances),
        'paper_all_optimum': sum(row['paper_avg'] == row['optimum'] for row in instances),
        'mean_gap_best': complete_mean(row['gap_best'] for row in instances),
        'mean_gap_avg': complete_mean(row['gap_avg'] for row in instances),
        'total_solver_seconds': sum(run['seconds'] for run in runs),
        'total_cpu_seconds': (sum(run['cpu_seconds'] for run in runs)
                              if all(run['cpu_seconds'] is not None for run in runs) else None),
        'stops': dict(Counter(run['stop'] for run in runs)),
    }
    return {
        'schema_version': 2, 'experiment_id': metadata['experiment_id'], 'config': config,
        'environment': metadata['environment'], 'summary': summary, 'instances': instances,
        'runs': runs, 'groups': summarize_groups(instances), 'histogram': gap_histogram(instances),
        'route': sample_route(instances, runs, entries),
    }


def format_number(value, decimals=3):
    return '-' if value is None else f'{value:.{decimals}f}'


def markdown_row(values):
    return '| ' + ' | '.join(map(str, values)) + ' |'


def paper_budget_matches(config):
    return (config['repeat_count'] == 10 and config.get('time_limit_seconds') is None
            and all(config['max_generations_by_group'][group] == (500000 if group == 'M' else 200000)
                    for group in GROUP_ORDER))


def comparison_tables(data):
    config, instances = data['config'], data['instances']
    repeats = config['repeat_count']
    limit = config.get('time_limit_seconds')
    limit_label = 'Sınır yok' if limit is None else f'{limit:g} s (yumuşak)'
    lines = [
        '# CDELS - makaleyle karşılaştırma', '', f"Deney: `{data['experiment_id']}`.",
        f"{len(instances)} problem; {repeats} tekrar; tohumlar: {config['seeds']}.", '',
        'Kaynak: Souza, Boeres ve Moraes (2023), bölüm 5.2, s. 10-13. '
        'https://doi.org/10.1016/j.swevo.2023.101245', '',
        'Makalenin CDELS sütunları karşılaştırılır. Diğer algoritmaların sonuçları bu tablolara alınmaz.',
        'Best: tekrarların en düşük mesafesi. Avg.: aritmetik ortalama. SD: örnek standart sapma (n-1).',
        (f'Makale 10 tekrar kullanır; bizim deney {repeats} tekrar kullanır. Best değerleri farklı '
         'sayıda denemeden seçildiği için eşit deney fırsatını temsil etmez.' if repeats != 10 else
         'Her iki tarafta da problem başına 10 tekrar vardır; aynı sayılı C/Python tohumları aynı diziyi üretmez.'),
        f"Yöntem protokolü: {config['algorithm'].get('implementation_protocol', 'önceki ön deney')}. "
        'Kaynak/sözde kod ayrımları proje kökündeki report/ESLESTIRME.md içinde açıklanır.',
        'BKS sapması = 100 × (sonuç - BKS) / BKS. Grup sapmaları problem yüzdelerinin ortalamasıdır.',
        'Bir koşuda geçerli çözüm yoksa o problemde Avg./SD verilmez (-); Best varsa yalnız '
        'geçerli koşuların en iyisidir. Geçerli tekrar sayısı her satırda belirtilir.',
        ('Tekrar, nesil ve süre kesmesi ayarları makaledeki bildirilen deney bütçesiyle eşleştirilmiştir. '
         'Bu, yayımlanmış performansın elde edildiğini tek başına kanıtlamaz.' if paper_budget_matches(config) else
         'Deney bütçesi makaleden farklıdır; bu sınırlı bütçeli ön deney tam performans tekrarı değildir.'), '',
        '## Tablo 6 - Parametreler (makale s. 10)', '',
        '| Parametre | Makale | Bizim deney |', '|---|---|---|',
        '| NP (N depo hariç müşteri sayısı) | 3N | '
        + ('3(N+1), kamuya açık C koduyla aynı' if config['algorithm']['population_size_rule']
           == '3 * n_nodes_including_depot' else '3N') + ' |',
        f"| F | 0.7 | {config['algorithm']['mutation_factor']} |",
        f"| CR | 0.7 | {config['algorithm']['crossover_rate']} |",
        f"| Strateji | rand/1/exp | {config['algorithm']['strategy']} |",
        f"| Ceza | 100 | {config['algorithm']['penalty']} |", f'| Tekrar | 10 | {repeats} |',
        '| MaxGen A/B/P/E/F | 200000 | ' + ', '.join(
            f"{group}: {config['max_generations_by_group'][group]}" for group in 'ABPEF') + ' |',
        f"| MaxGen M | 500000 | {config['max_generations_by_group']['M']} |",
        f"| Süre sınırı | Tablo 6'da belirtilmiyor | {limit_label} |", '',
    ]
    for number, groups, page in [(7, 'A', 10), (8, 'B', 11), (9, 'P', 11), (10, 'EFM', 12)]:
        rows = [row for row in instances if row['group'] in groups]
        if not rows:
            continue
        lines.extend([
            f'## Tablo {number} - {"/".join(groups)} (makale s. {page})', '',
            '| Problem | BKS | Makale Avg. | Makale Best | Bizim Avg. | Bizim Best | SD | Best sapma (%) | Avg. sapma (%) | Geçerli tekrar |',
            '|---|---:|---:|---:|---:|---:|---:|---:|---:|---|',
        ])
        for row in rows:
            lines.append(markdown_row([
                row['name'], row['optimum'], format_number(row['paper_avg']), row['paper_best'],
                format_number(row['avg']), row['best'] if row['best'] is not None else '-',
                format_number(row['std']), format_number(row['gap_best']), format_number(row['gap_avg']),
                f"{row['valid_runs']}/{row['repeat_count']}",
            ]))
        common = [row for row in rows if row['name'] != 'A-n45-k7'] if number == 7 else rows
        if number == 10:
            common = [row for row in rows if row['group'] == 'E']
        for label, subset in [('X1 (tümü)', rows), ('X2 (makaledeki ortak alt küme)', common)]:
            if subset:
                means = [format_number(complete_mean(row[field] for row in subset))
                         for field in ['optimum', 'paper_avg', 'paper_best', 'avg', 'best']]
                gaps = [format_number(complete_mean(row[field] for row in subset))
                        for field in ['gap_best', 'gap_avg']]
                lines.append(markdown_row([label] + means + ['-'] + gaps + ['-']))
        lines.append('')

    lines.extend([
        '## Tablo 11 - Optimum bulunan problem sayıları (makale s. 12)', '',
        'Makalede Avg. sütunu tüm tekrarlarda optimum bulunan problem sayısıdır. '
        'Bizim tüm-tekrar sütunumuz aynı tanımı kendi tekrar sayımıza uygular.', '',
        '| Grup | Makale tüm 10 tekrarda | Makale en az 1 tekrarda | Bizim tüm tekrarlarda | Bizim en az 1 tekrarda |',
        '|---|---:|---:|---:|---:|',
    ])
    columns = ['paper_all_optimum', 'paper_best_optimum', 'all_optimum', 'best_optimum']
    for group in data['groups']:
        lines.append(markdown_row([group['name']] + [f"{group[field]}/{group['count']}" for field in columns]))
    lines.extend([markdown_row(['Toplam'] + [
        f"{sum(group[field] for group in data['groups'])}/{len(instances)}" for field in columns]), '',
        '## Tablo 12 - Çalışma süreleri (makale s. 13)', '',
        'Makale: 10 tekrarın ortalama CPU süresi. Bizim CPU ve geçen aktif süre ayrı sütunlardadır. '
        "Donanım ve Python/C farklıdır; bütçe ve durma koşulları Tablo 6'da belirtilir. Doğrudan hız üstünlüğü çıkarılamaz.", '',
        '| Problem | Makale ortalama CPU (s) | Bizim ortalama CPU (s) | Bizim ortalama geçen süre (s) | Durma nedenleri |',
        '|---|---:|---:|---:|---|',
    ])
    for row in instances:
        stops = ', '.join(f'{reason}: {count}' for reason, count in sorted(row['stops'].items()))
        lines.append(markdown_row([row['name'], format_number(row['paper_seconds']),
                                   format_number(row['cpu_seconds_avg']), format_number(row['seconds_avg']), stops]))
    return '\n'.join(lines) + '\n'


def draw_figures(data, output):
    """Makale ve bizim Best/Avg. değerlerini aynı grafiklerde karşılaştırır."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError as error:
        raise ValueError('Grafikler için matplotlib gerekli; JSON ve tablolar kaydedildi.') from error
    directory = output / 'figures'
    directory.mkdir()
    colors = ['#364e75', '#98a7bb', '#007f86', '#e29943']
    groups = data['groups']
    positions = list(range(len(groups)))
    series = [
        ('paper_mean_gap_best', 'Makale Best', colors[0]),
        ('paper_mean_gap_avg', 'Makale Avg.', colors[1]),
        ('mean_gap_best', 'Bizim Best', colors[2]),
        ('mean_gap_avg', 'Bizim Avg.', colors[3]),
    ]
    figure, axes = plt.subplots(figsize=(10, 5.5), layout='constrained')
    for index, (field, label, color) in enumerate(series):
        values = [group[field] if group[field] is not None else float('nan') for group in groups]
        bars = axes.bar([position + (index - 1.5) * .2 for position in positions], values,
                        width=.19, label=label, color=color)
        axes.bar_label(bars, fmt='%.2f', padding=3, fontsize=7)
    axes.set_xticks(positions, [f"{group['name']} (n={group['count']})" for group in groups])
    axes.set(ylabel='BKS sapması (%)', title='Makale ve uygulama: grup bazında ortalama sapma')
    axes.legend(fontsize=9)
    axes.yaxis.grid(alpha=.15)
    axes.set_axisbelow(True)
    axes.margins(y=.2)
    figure.savefig(directory / 'makale_grup_sapmalari.png', dpi=180)
    plt.close(figure)

    figure, axes = plt.subplots(figsize=(10, 5.5), layout='constrained')
    for index, (field, label, color) in enumerate([
        ('paper_best_optimum', 'Makale: en az 1/10', colors[0]),
        ('paper_all_optimum', 'Makale: tüm 10', colors[1]),
        ('best_optimum', f"Bizim: en az 1/{data['config']['repeat_count']}", colors[2]),
        ('all_optimum', f"Bizim: tüm {data['config']['repeat_count']}", colors[3]),
    ]):
        bars = axes.bar([position + (index - 1.5) * .2 for position in positions],
                        [group[field] for group in groups], width=.19, label=label, color=color)
        axes.bar_label(bars, padding=3, fontsize=8)
    axes.set_xticks(positions, [f"{group['name']} (n={group['count']})" for group in groups])
    axes.set(ylabel='Problem sayısı', title='Makale ve uygulama: optimum bulunan problemler')
    axes.legend(fontsize=8)
    axes.margins(y=.25)
    figure.savefig(directory / 'makale_optimum_sayilari.png', dpi=180)
    plt.close(figure)

    histogram = data['histogram']
    positions = list(range(len(histogram)))
    figure, axes = plt.subplots(figsize=(10, 5), layout='constrained')
    for offset, field, label, color in [(-.2, 'gap_best', 'Bizim Best', colors[2]), (.2, 'gap_avg', 'Bizim Avg.', colors[3])]:
        bars = axes.bar([position + offset for position in positions], [row[field] for row in histogram],
                        width=.38, label=label, color=color)
        axes.bar_label(bars, padding=3, fontsize=9)
    axes.set_xticks(positions, [row['label'] for row in histogram])
    axes.set(xlabel='BKS sapması (%)', ylabel='Problem sayısı', title='Tekrarların Best/Avg. sapma dağılımı')
    axes.legend()
    axes.margins(y=.2)
    figure.savefig(directory / 'sapma_dagilimi.png', dpi=180)
    plt.close(figure)

    # Süreler farklı ölçüm ve bütçelerdir; log eksen yalnız görünürlüğü artırır.
    instances = data['instances']
    time_field = 'cpu_seconds_avg' if all(row['cpu_seconds_avg'] is not None for row in instances) else 'seconds_avg'
    time_label = 'CPU' if time_field == 'cpu_seconds_avg' else 'geçen'
    timed = [row for row in instances if row['paper_seconds'] > 0 and row[time_field] > 0]
    figure, axes = plt.subplots(figsize=(10, 5), layout='constrained')
    axes.scatter([row['paper_seconds'] for row in timed], [row[time_field] for row in timed], color=colors[2], alpha=.7)
    axes.set(xscale='log', yscale='log', xlabel='Makale ortalama CPU süresi (s)',
             ylabel=f'Bizim ortalama {time_label} süresi (s)', title='Çalışma süreleri: donanım ve uygulama koşulları farklı')
    axes.grid(alpha=.15)
    figure.savefig(directory / 'makale_sureleri.png', dpi=180)
    plt.close(figure)

    route = data['route']
    if route is not None:
        figure, axes = plt.subplots(figsize=(9, 7), layout='constrained')
        coordinates = {int(key): value for key, value in route['coordinates'].items()}
        for index, customers in enumerate(route['routes']):
            if not customers:
                continue
            points = [coordinates[node] for node in [0] + customers + [0]]
            axes.plot([point[0] for point in points], [point[1] for point in points], '-o', ms=4,
                      label=f"Rota {index + 1}, yük {route['loads'][index]}")
        for node, point in coordinates.items():
            if node:
                axes.annotate(str(node), point, xytext=(3, 3), textcoords='offset points', fontsize=8)
        axes.scatter(*coordinates[0], marker='s', s=100, color='#172b45', zorder=5, label='Depo')
        axes.set(xlabel='x koordinatı', ylabel='y koordinatı',
                 title=f"{route['name']}: en iyi tekrar (tohum {route['seed']}), mesafe {route['distance']}")
        axes.set_aspect('equal', adjustable='datalim')
        axes.margins(.12)
        axes.legend(fontsize=8)
        axes.grid(alpha=.15)
        figure.savefig(directory / f"rota_{route['name']}.png", dpi=180)
        plt.close(figure)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experiment', type=Path, required=True, help='Tamamlanmış deneyin klasörü')
    parser.add_argument('--output', type=Path, required=True, help='Yeni analiz klasörü')
    parser.add_argument('--grafikler', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        parser.error('Çıktı klasörü mevcut; yeni bir ad seçin.')
    try:
        data = analyze(args.experiment.resolve())
        # Analiz tüm doğrulamalardan geçmeden çıktı klasörü oluşturulmaz.
        output.mkdir(parents=True)
        (output / 'ozet.json').write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        (output / 'makale_karsilastirma.md').write_text(comparison_tables(data), encoding='utf-8')
        if args.grafikler:
            draw_figures(data, output)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, f'Analiz tamamlanamadı: {error}\n')
    print(json.dumps(data['summary'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
