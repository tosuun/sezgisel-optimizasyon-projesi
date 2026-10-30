# CDELS - CVRP Python uygulaması

90 CVRP problemi için yazarların sabit kod akışına göre düzeltilmiş Python yeniden uygulaması. İkinci probleme uyarlama sonraki aşamadır.

Önceki 270 koşu, bunlara ait tablolar/grafikler ve geçici düzeltme kontrol çıktıları proje dışına yedeklendi. `results/` yeni deney için temizdir. Eski kayıtlar yeni deneyle birleştirilmez.

## Kaynak ve yöntem

[ESLESTIRME.md](report/ESLESTIRME.md), düzeltilen akışı, kaynak kod/makale farklarını, sayfa numaralarını ve bilinen sınırları açıklar. Referans commit: `9c605e3283cac03d0605128dc05cb3cd180411bb`. Çeviride esas alınan kodun MIT bildirimi [LICENSE-CDELS.txt](LICENSE-CDELS.txt) içinde korunur.

Arama işlemlerinin sırası için yayımlanan C kodu, deney NP/MaxGen/tekrar değerleri için makale esas alınır. NP depo hariç 3N'dir; C main'in depo dahil varsayılanı uygulanmaz. Mutasyonun int dönüşümü ve müşteri listesi, yerel arama ve onarım gibi kaynak/sözde kod farkları raporda saklanmadan belirtilir. Kamuya açık sürümün tarihsel deney commit'i olduğu veya aynı rastgele dizilerin üretildiği garanti edilmez.

## Dosyalar

| Konum | İçerik |
|---|---|
| `src/` | Problem hesabı, operatörler, yerel arama, çözücü ve çalıştırıcılar |
| `data/` | 90 CVRPLIB problemi, referans çözümleri ve makale değerleri |
| `configs/dogrulama.json` | Yeni protokol, 90 × 10 = 900 koşu |
| `tools/analiz.py` | Çoklu tekrar analizi, makale tabloları ve grafikler |
| `tests/` | Doğruluk, kesintiden devam, analiz ve gerçek C çıktılarıyla davranış denetimleri |
| `report/ESLESTIRME.md` | Uygulama kararları ve doğrulama kanıtlarının kapsamı |
| `results/experiments/` | Yeni deney başladığında üretilecek ham kayıtlar |

Kişisel konuşma notları korunur; eski sayılar güncel sonuç değildir. `sunum/` Git dışında kalır.

## Yeni deney ayarları

Tohumlar **1..10**; NP=3N (depo hariç), F=CR=0.7, ceza=100, rand/1/exp. A/B/P/E/F için **200000**, M için **500000** tamamlanmış nesil; **süre kesmesi yok**; optimum nesil sonunda kontrol edilir. “İlk on tamsayı” ifadesindeki açık liste belirsizliği raporda belirtilir.

**900 koşuluk çalışma henüz yapılmadı. Büyük problemler uzun sürebilir; önceki kısa deneyin süresi tam bütçenin süre tahmini değildir.** Sürüm, ayar veya ortam değişirse ayrı deney kimliği oluşturulur. Eski sonuçlar aktarılmaz.

## Çalıştırma

Python 3.12+; çözücü/analiz standart kütüphane kullanır. Aşağıdaki komutlar mevcut `sezgisel-opt-env` ortamını kullanır. Grafikler için isteğe bağlı matplotlib gerekir. Proje klasöründe, aynı Python ortamında:

```bash
../sezgisel-opt-env/bin/python3 -B -m unittest discover -s tests -q
```

Yalnız plan kontrolü, deney başlatmaz:

```bash
../sezgisel-opt-env/bin/python3 -B src/run_experiments.py configs/dogrulama.json
```

Uzun deneyi kullanıcı başlatmak istediğinde:

```bash
../sezgisel-opt-env/bin/python3 -B src/run_experiments.py configs/dogrulama.json --execute
```

`Ctrl+C` aktif hedef ardından ara kayıtla durmayı ister; aynı komutla devam edilir. Biten koşular yeniden hesaplanmaz. CPU süresi ve geçen süre ayrı kaydedilir. Deney sırasında kaynak kodu, veriyi, ayarı ve Python ortamını değiştirmeyin.

Tamamlanınca çıktının `output_directory` yolunu kullanın:

```bash
../sezgisel-opt-env/bin/python3 -B tools/analiz.py --experiment "YENI_DENEY_KLASORUNUN_TAM_YOLU" --output results/analysis_author_aligned --grafikler
```

Çıktı klasörü yeni olmalı. Grafik istemiyorsanız `--grafikler` seçeneğini çıkarın. Analiz optimizasyon başlatmaz; bütün terminal koşular olmadan nihai tablo üretmez. En iyi, ortalama, örnek standart sapma, Best/Avg. BKS sapması, geçerli tekrar sayısı ve CPU/geçen süre raporlanır. Bir tekrar geçersizse problem Avg./SD değeri verilmez; başarısız koşu sessizce dışlanmaz.

## Doğrulama kapsamı

72 otomatik test; C kodundan elde edilmiş 560 referans örneği, ayrıca 40 örnekte çözücünün tamamladığı popülasyon ve rastgele sayı durumu karşılaştırması. Küçük gerçek problemlerde 6/6 optimum kontrolü. Bunlar bütün veri kümesinin nihai performans sonucu değildir.

Makale: Souza, Boeres ve Moraes, “A robust algorithm based on Differential Evolution with local search for the Capacitated Vehicle Routing Problem”, Swarm and Evolutionary Computation 77 (2023), 101245. [DOI](https://doi.org/10.1016/j.swevo.2023.101245). [Yazar kodu](https://github.com/israelpereira55/CDELS).
