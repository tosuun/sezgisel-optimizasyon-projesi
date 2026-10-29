# CDELS — CVRP uygulaması ve sonuç karşılaştırması

İlk makaledeki CDELS yönteminin Python uygulaması ve 90 CVRP örneği üzerinde sınırlı bütçeli doğrulama çalışması. İlk aşamanın raporu ve sunumu hazırdır. İkinci probleme uyarlama sonraki aşamadır.

- [Doğrulama raporu (PDF)](report/DOGRULAMA.pdf) ve [düzenlenebilir metni](report/DOGRULAMA.md)
- [Sunum (14 slayt)](sunum/CDELS_Ilk_Asama_Sunum.pptx)
- [Konuşma notları ve olası sorular](sunum/KONUSMA_NOTLARI.md)

## Dosyalar

| Konum | İçerik |
|---|---|
| `src/` | Problem, operatörler, yerel arama ve çalıştırıcılar |
| `data/` | CVRPLIB örnekleri, referans çözümleri ve makale sonuçları |
| `configs/dogrulama.json` | Güncel 90 örneklik deneyin tek ayar dosyası |
| `results/experiments/` | Güncel 90 koşunun ham sonuçları, ortam bilgisi ve ara kayıtları |
| `report/` | Doğrulama raporu (PDF/Markdown), grafikler ve tam karşılaştırma tablosu |
| `sunum/` | Düzenlenebilir sunum ve konuşma notları |
| `results/analysis/` | 90 örneğin analiz özeti ve sabit tohumlu tekrar kontrolü |
| `tests/` | Doğruluk, kesintiden devam ve eski/yeni karar eşdeğerliği kontrolleri |
| `tools/` | Analiz özeti üretimi ve isteğe bağlı hız ölçümü |

## Çalıştırma

Python 3.12 veya üzeri kullanın. Mevcut uygulama yalnız Python standart kütüphanesini kullanır; ek paket kurulumu gerekmez. Aşağıdaki komutlar `proje` klasöründe çalıştırılır.

Kontroller:

```bash
python3 -B -m unittest discover -s tests -q
```

Tek gerçek örneği çalıştırıp bağımsız denetim sonucunu kaydetme (çıktı adı yeni olmalı):

```bash
python3 -B src/run_pilot.py data/raw/cvrp/A-n32-k5.vrp data/raw/cvrp/A-n32-k5.sol --max-generations 20 --seed 42 --known-optimum 784 --output results/tek_ornek.json
```

90 örneğin analizini yeniden üretme (çıktı klasörü yeni olmalı, optimizasyon başlatmaz):

```bash
python3 -B tools/analiz.py --output results/analiz_yeni
```

Grafikleri de yeniden üretmek için `--grafikler` eklenebilir. Yalnız bu isteğe bağlı seçenek `matplotlib` gerektirir. Raporun hazır grafikleri `report/figures/` altındadır.

90 örneğin verilerini ve ayarını kontrol etme; deney başlatmaz:

```bash
python3 -B src/run_experiments.py configs/dogrulama.json
```

90 örneklik deneyi çalıştırma:

```bash
python3 -B src/run_experiments.py configs/dogrulama.json --execute
```

Bu ayar tek tohum (42), en fazla 20 nesil ve koşu başına yaklaşık 120 saniyelik sınır kullanır. Aktif hedef tamamlanacağı için süre biraz aşılabilir. Aynı kod, veri, ayar ve ortamla tamamlanmış koşular yeniden hesaplanmaz; sonuçlar korunur. Ortam değişirse ayrı deney klasörü oluşturulur. `Ctrl+C` aktif hedefin ardından durmayı ve kaydı ister; aynı komutla devam edilir.

## Mevcut sonuç

90/90 geçerli çözüm, 20 optimum; toplam çözücü süresi yaklaşık 26 dakika 31 saniye. Bu, makalenin tüm deney bütçesinin birebir tekrarı değildir. Tek koşu maliyeti ile makalenin tekrarlı Best/Avg değerleri raporda ayrı gösterilir. İlk aşama bu açıkça sınırlanmış kapsamda tamamlandı. Makalenin on tekrarlı tam performansını veya istatistiksel üstünlüğünü yeniden ürettiği iddia edilmez. İkinci probleme uyarlama sonraki aşamaya bırakıldı.

Makale: Souza, Boeres ve Moraes, “A robust algorithm based on Differential Evolution with local search for the Capacitated Vehicle Routing Problem”, Swarm and Evolutionary Computation 77 (2023), 101245. [DOI](https://doi.org/10.1016/j.swevo.2023.101245). Yazarların [CDELS kaynak kodu](https://github.com/israelpereira55/CDELS) yöntem incelemesinde referans alınmıştır.
