"""90 son planı yeniden denetler ve analiz özetini yeni bir klasöre yazar.

Proje kökünde: python3 -B tools/analiz.py --output results/analiz_yeni
Grafikler için --grafikler eklenebilir; bu seçenek matplotlib gerektirir.
"""
from pathlib import Path
import argparse, collections, hashlib, json, statistics, sys
P=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(P/'src'))
from instance_io import read_instance,read_solution
from run_pilot import audit_solution
from problem import route_distance


def analyze():
    D=P/'results/experiments/paper90_screening_v3-818bc1da2558489d'
    meta=json.loads((D/'metadata.json').read_text())
    manifest=json.loads((P/'data/paper90_instances.json').read_text())
    entries={e['name']:e for e in manifest['instances']}
    records=[]
    for path in sorted((D/'runs').glob('*/result.json')):
     r=json.loads(path.read_text());name=r['instance']['name'];e=entries[name]
     d=read_instance(P/e['instance_path']);sol=read_solution(P/e['solution_path'],d)
     a=audit_solution(r['result']['best_routes'],d);ref_a=audit_solution(sol['routes'],d)
     assert a['valid'] and a['distance']==r['result']['distance']
     assert ref_a['valid'] and ref_a['distance']==e['reference_cost']==sol['reported_cost']==e['paper_bks']
     assert hashlib.sha256((P/e['instance_path']).read_bytes()).hexdigest()==e['vrp_sha256']==r['run_identity']['instance_sha256']
     assert hashlib.sha256((P/e['solution_path']).read_bytes()).hexdigest()==e['sol_sha256']==r['run_identity']['solution_sha256']
     assert r['result']['seed']==42 and r['status']=='completed'
     gap=100*(r['result']['distance']-e['reference_cost'])/e['reference_cost']
     assert abs(gap-r['gap_percent'])<1e-9 and gap>=0
     records.append({'name':name,'group':e['group'],'n':e['n_customers'],'k':e['max_vehicles'],'capacity':e['capacity'],'optimum':e['reference_cost'],
     'paper_best':e['paper_cdels_best'],'paper_avg':e['paper_cdels_average'],'paper_seconds':e['paper_average_seconds'],
     'distance':a['distance'],'gap':gap,'gap_to_paper_best':100*(a['distance']-e['paper_cdels_best'])/e['paper_cdels_best'],
     'seconds':r['result']['elapsed_seconds'],'stop':r['result']['stop_reason'],'generations':r['result']['generations'],
     'partial':r['result']['partial_generation_targets'],'np':r['result']['parameters']['population_size'],'valid':a['valid']})
    assert len(records)==90
    records.sort(key=lambda r:('ABPEFM'.index(r['group']),r['n'],r['name']))
    groups=[]
    for g in 'ABPEFM':
     rows=[r for r in records if r['group']==g]
     groups.append({'name':g,'count':len(rows),'optimum':sum(r['gap']==0 for r in rows),'paper_optimum':sum(r['paper_best']==r['optimum'] for r in rows),
     'mean_gap':statistics.mean(r['gap'] for r in rows),'median_gap':statistics.median(r['gap'] for r in rows),'seconds':sum(r['seconds'] for r in rows)})
    # Açık aralıklar birbirini dışlar.
    bins=[('0',lambda x:x==0),('(0, 1]',lambda x:0<x<=1),('(1, 5]',lambda x:1<x<=5),('(5, 10]',lambda x:5<x<=10),('(10, 20]',lambda x:10<x<=20),('>20',lambda x:x>20)]
    hist=[{'label':label,'count':sum(test(r['gap']) for r in records)} for label,test in bins]
    assert sum(x['count'] for x in hist)==90
    summary={'count':90,'valid':90,'optimum':sum(r['gap']==0 for r in records),'paper_best_optimum':sum(r['paper_best']==r['optimum'] for r in records),
     'mean_gap':statistics.mean(r['gap'] for r in records),'median_gap':statistics.median(r['gap'] for r in records),
     'max_gap':max(r['gap'] for r in records),'seconds':sum(r['seconds'] for r in records),'median_seconds':statistics.median(r['seconds'] for r in records),
     'stops':dict(collections.Counter(r['stop'] for r in records)),'within5':sum(r['gap']<=5 for r in records),'within1':sum(r['gap']<=1 for r in records),
     'mean_gap_without_worst':statistics.mean(r['gap'] for r in records if r['name']!='M-n200-k16')}
    name='A-n32-k5';e=entries[name];d=read_instance(P/e['instance_path']);rr=json.loads((D/f'runs/{name}_seed42/result.json').read_text())
    routes=rr['result']['best_routes']
    route_data={'name':name,'capacity':d['capacity'],'max_vehicles':d['max_vehicles'],'distance':rr['result']['distance'],'optimum':e['reference_cost'],
     'coordinates':d['coordinates'],'routes':routes,'loads':[sum(d['demands'][c] for c in route) for route in routes],
     'distances':[route_distance(route,d['distances']) for route in routes],'n':d['n_customers']}
    assert sum(route_data['distances'])==route_data['distance']
    data={'summary':summary,'groups':groups,'histogram':hist,'records':records,'route':route_data,'environment':meta['environment'],
     'experiment_id':meta['experiment_id'],'config':meta['config']}
    return data

def draw_figures(data,output):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError as error:
        raise SystemExit('Grafikleri yeniden üretmek için matplotlib gerekli. Analiz özeti kaydedildi.') from error
    D=data
    O=output/'figures'
    O.mkdir()
    colors=['#007f86','#435fb3','#bf633d','#9070ac','#899632']
    # Rota bilimsel koordinat grafiğidir; gerçek coğrafi harita değildir.
    r=D['route'];c={int(k):v for k,v in r['coordinates'].items()}
    fig,ax=plt.subplots(figsize=(8,6.6),layout='constrained')
    for i,route in enumerate(r['routes']):
     path=[0]+route+[0];xy=[c[j] for j in path]
     ax.plot([p[0] for p in xy],[p[1] for p in xy],'-o',lw=1.7,ms=4,color=colors[i],label=f'Rota {i+1} (yük {r["loads"][i]})')
    for customer,(x,y) in c.items():
     if customer:ax.annotate(str(customer),(x,y),xytext=(3,3),textcoords='offset points',fontsize=8)
    ax.scatter(*c[0],marker='s',s=100,color='#132a42',edgecolor='white',zorder=5,label='Depo')
    ax.annotate('Depo',c[0],xytext=(7,-12),textcoords='offset points',fontsize=10,fontweight='bold')
    ax.set(xlabel='x koordinatı',ylabel='y koordinatı',title='A-n32-k5: 31 müşteri, 5 rota, toplam mesafe 784')
    ax.set_aspect('equal',adjustable='datalim');ax.margins(.12);ax.grid(alpha=.15);ax.legend(fontsize=9,loc='upper right')
    fig.savefig(O/'rota_A-n32-k5.png',dpi=200);plt.close(fig)
    fig,ax=plt.subplots(figsize=(8,4.6),layout='constrained')
    g=D['groups'];vals=[x['mean_gap'] for x in g]
    b=ax.bar([f"{x['name']} (n={x['count']})" for x in g],vals,color=['#007f86']*4+['#bf633d']*2,width=.6)
    ax.bar_label(b,labels=[f'{x:.2f}%' for x in vals],padding=4,fontsize=11)
    ax.set(ylabel='Optimumdan ortalama sapma (%)',ylim=(0,31),title='Veri gruplarına göre çözüm kalitesi');ax.yaxis.grid(alpha=.15);ax.set_axisbelow(True)
    fig.savefig(O/'grup_sapmalari.png',dpi=200);plt.close(fig)
    fig,ax=plt.subplots(figsize=(8,4.6),layout='constrained')
    h=D['histogram'];b=ax.bar([x['label'] for x in h],[x['count'] for x in h],color='#007f86',width=.6)
    ax.bar_label(b,padding=4,fontsize=12);ax.set(xlabel='Optimumdan sapma aralığı (%)',ylabel='Örnek sayısı',ylim=(0,33),title='90 örnekte sapmaların dağılımı');ax.yaxis.grid(alpha=.15);ax.set_axisbelow(True)
    fig.savefig(O/'sapma_dagilimi.png',dpi=200);plt.close(fig)
    fig,ax=plt.subplots(figsize=(8,4.6),layout='constrained')
    ax.scatter([x['n'] for x in D['records']],[x['gap'] for x in D['records']],s=34,color='#007f86',alpha=.7)
    for name in ['M-n200-k16','M-n121-k7','B-n57-k7']:
     row=next(x for x in D['records'] if x['name']==name)
     ax.annotate(name,(row['n'],row['gap']),xytext=(-8,6),textcoords='offset points',ha='right',fontsize=9)
    ax.set(xlabel='Müşteri sayısı (depo hariç)',ylabel='Optimumdan sapma (%)',title='Örnek büyüklüğü ve sapma',ylim=(-2,82));ax.grid(alpha=.15)
    fig.savefig(O/'buyukluk_ve_sapma.png',dpi=200);plt.close(fig)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True,help='Mevcut olmayan yeni çıktı klasörü')
    parser.add_argument('--grafikler',action='store_true')
    args=parser.parse_args()
    output=args.output.resolve()
    if output.exists(): parser.error('Çıktı klasörü zaten mevcut; yeni bir ad seçin.')
    data=analyze()
    output.mkdir(parents=True)
    (output/'ozet.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if args.grafikler: draw_figures(data,output)
    print(json.dumps(data['summary'],ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
