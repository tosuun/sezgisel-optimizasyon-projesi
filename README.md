# CDELS - CVRP uygulaması ve makaleyle karşılaştırma

90 CVRP problemi üzerinde üç tekrarlı, sınırlı bütçeli doğrulama hazırlığı. Yeni deney henüz çalıştırılmadı. İkinci probleme uyarlama sonraki aşamadır.

## Dosyalar

| Konum | İçerik |
|---|---|
| `src/` | Problem, operatörler, yerel arama ve çalıştırıcılar |
| `data/` | 90 özgün CVRPLIB problemi, referans çözümleri ve makale değerleri |
| `configs/dogrulama.json` | 90 problem × 3 tohum = 270 koşu |
| `tools/analiz.py` | Çoklu tekrar analizi, makale tabloları ve grafikler |
| `tests/` | Algoritma, dosya okuma, kesintiden devam ve analiz kontrolleri |
| `results/experiments/` | Deney başlayınca üretilecek ham kayıtlar |
| `results/analysis/` | Deney tamamlandıktan sonra üretilecek analiz |

Önceki tek tekrarlı sonuçlar ve bunlara dayanan rapor/sunum proje dışına yedeklendi. Kişisel konuşma notları `sunum/` içinde korundu; içlerindeki eski sayılar yeni sonuç değildir. Sunum ve kişisel notlar Git'e gönderilmez.

## Deney ayarları

Tohumlar **42, 43, 44**; NP=3N, F=CR=0.7, ceza=100, rand/1/exp. Her koşu en fazla **20 nesil** ve **120 saniyelik yumuşak süre sınırı** kullanır; aktif hedef tamamlanırken süre aşılabilir. Optimum bulunursa erken durur. Bu, makalenin 10 tekrar ve 200000/500000 nesillik bütçesinin birebir tekrarı değildir.

Bütçe, üç tekrarın tümünde aynı tutulur. Sonradan 10 tekrara tamamlamak istenirse mevcut üç koşunun kaynak, veri, ortam ve parametre kimlikleri doğrulanarak aktarılması gerekir; yalnız `seeds` listesini değiştirmek kayıtları otomatik taşımaz.

## Çalıştırma

Python 3.12+ gerekir. Çözücü ve tablo analizi standart kütüphaneyi kullanır. Grafikler için isteğe bağlı `matplotlib` gerekir. Komutlar proje klasöründe, aynı Python ortamında çalıştırılır.

Kontroller:

```bash
python3 -B -m unittest discover -s tests -q
```

Plan kontrolü; deney başlatmaz:

```bash
python3 -B src/run_experiments.py configs/dogrulama.json
```

270 koşuyu başlatma veya kesintiden sonra devam etme:

```bash
python3 -B src/run_experiments.py configs/dogrulama.json --execute
```

Aynı kod, veri, ayar ve ortamla tamamlanan koşular atlanır. `Ctrl+C`, aktif hedefin ardından kayıtla durmayı ister. Kaynak dosyalarını, ayarları ve Python ortamını deney sırasında değiştirmeyin. Farklı kimlikli deneyler birleştirilmez.

Deney tamamlandığında çıktısındaki `output_directory` yolunu kullanın:

```bash
python3 -B tools/analiz.py --experiment "DENEY_KLASORUNUN_TAM_YOLU" --output results/analysis --grafikler
```

`DENEY_KLASORUNUN_TAM_YOLU` yerine gerçek yolu yazın. `results/analysis` mevcut olmamalı; yeniden analizde yeni bir çıktı adı seçin. Grafik istemiyorsanız `--grafikler` seçeneğini çıkarın. Analiz optimizasyon çalıştırmaz; bütün 270 terminal sonuç mevcut değilse nihai tablo üretmez.

## Üretilecek karşılaştırmalar

- `ozet.json`: Her koşu, problem başına Best/Avg./örnek SD, sapmalar ve grup özeti.
- `makale_karsilastirma.md`: Makalenin s. 10-13'teki Tablo 6-12 düzeninde CDELS karşılaştırması. A, B, P ve E/F/M grupları ayrı; X1/X2 alt kümeleri korunur.
- `figures/makale_grup_sapmalari.png`: Makale ve bizim Best/Avg. BKS sapmaları.
- `figures/makale_optimum_sayilari.png`: En az bir tekrarda ve tüm tekrarlarda optimum bulunan problemler.
- `figures/sapma_dagilimi.png`: Bizim Best/Avg. sapma dağılımı.
- `figures/makale_sureleri.png`: Makalenin ortalama CPU süresi ve bizim ortalama geçen süremiz; farklı donanım ve bütçeler doğrudan hız üstünlüğü göstermez.
- `figures/rota_A-n32-k5.png`: Geçerli çözüm varsa örnek problemin en iyi tekrarı.

Geçerli çözüm bulunamayan koşular sayılır. Bir problemde bir tekrar bile geçersizse Avg./SD hesaplanmaz; yalnız başarılı koşularla ortalama iyileştirilmez. Best varsa geçerli koşuların en iyisidir ve geçerli tekrar sayısıyla birlikte verilir. SD örnek standart sapmadır (n-1); makalede bulunmayan SD veya ham tekrar değerleri üretilmez. Makalenin istatistiksel testleri bu tablolarda yeniden üretildiği iddia edilmez.

Makale: Souza, Boeres ve Moraes, “A robust algorithm based on Differential Evolution with local search for the Capacitated Vehicle Routing Problem”, Swarm and Evolutionary Computation 77 (2023), 101245. [DOI](https://doi.org/10.1016/j.swevo.2023.101245). [Yazarların CDELS kodu](https://github.com/israelpereira55/CDELS) yöntem incelemesinde referans alınmıştır.
