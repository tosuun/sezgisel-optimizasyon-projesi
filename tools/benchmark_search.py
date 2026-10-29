"""V2 referansıyla sabit iş yükü; mevcut çıktı dosyasının üzerine yazmaz."""
import argparse,hashlib,importlib.util,json,platform,random,statistics,sys,time
from pathlib import Path
P=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(P/'src'))
import local_search as fast
from instance_io import read_instance
from operators import initialize_individual
from problem import solution_distance
parser=argparse.ArgumentParser(description='Eski/yeni yerel aramayı aynı girdilerle karşılaştırır; ana deney değildir.')
parser.add_argument('--instances',nargs='+',default=['A-n32-k5','M-n101-k10','M-n200-k16'])
parser.add_argument('--repeats',type=int,default=3)
parser.add_argument('--output',type=Path)
options=parser.parse_args()
if options.repeats < 1: parser.error('--repeats en az 1 olmalı')
spec=importlib.util.spec_from_file_location('reference',P/'tests/fixtures/local_search_v2_reference.py')
slow=importlib.util.module_from_spec(spec);spec.loader.exec_module(slow)
rows=[]
for name in options.instances:
    d=read_instance(P/f'data/raw/cvrp/{name}.vrp')
    routes=initialize_individual(d['demands'],d['capacity'],d['max_vehicles'],random.Random(42))
    args=(routes,d['distances'],d['demands'],d['capacity'],d['max_vehicles'])
    timings={'before':[],'after':[]}
    for repeat in range(options.repeats):
        answers=[]; states=[]
        order=[('before',slow),('after',fast)]
        if repeat % 2: order.reverse()
        for label,module in order:
            rng=random.Random(123)
            start=time.perf_counter();answer=module.local_search(*args,rng)
            timings[label].append(time.perf_counter()-start)
            answers.append(answer);states.append(rng.getstate())
        assert answers[0]==answers[1] and states[0]==states[1]
    row={'instance':name,'timings_seconds':timings,'before_median':statistics.median(timings['before']),
         'after_median':statistics.median(timings['after']),'same_routes_and_rng':True,
         'distance':solution_distance(answer[0],d['distances'])}
    row['speedup']=row['before_median']/row['after_median']
    rows.append(row);print(json.dumps(row),flush=True)
report={'python':sys.version,'platform':platform.platform(),'machine':platform.machine(),
        'scope':'one full local_search, identical initialization seed42, search RNG123; alternating order',
        'repeats':options.repeats,
        'reference_sha256':hashlib.sha256((P/'tests/fixtures/local_search_v2_reference.py').read_bytes()).hexdigest(),
        'optimized_sha256':hashlib.sha256((P/'src/local_search.py').read_bytes()).hexdigest(),
        'rows':rows}
if options.output:
    with options.output.open('x',encoding='utf-8') as output:
        json.dump(report,output,ensure_ascii=False,indent=2)
        output.write('\n')
