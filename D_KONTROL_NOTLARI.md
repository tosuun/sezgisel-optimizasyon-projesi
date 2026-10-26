# D aşaması — CDELS çekirdeği

26 Ekim 2026. İlk doğruluk sürümü: küçük, elle denetlenebilir CVRP verisi üzerinde çalışır. Gerçek CVRPLIB dosyasını okuma ve makaledeki deneyleri tekrarlama sonraki aşamalardır.

## İnceleme sırası

| Dosya | İçerik |
| --- | --- |
| `src/problem.py` | Mesafe matrisi, yük/mesafe hesabı, uygunluk ve sabit ceza |
| `src/operators.py` | Kopya, konum bulma, başlangıç, PerturbationMove, mutasyon, exp çaprazlama |
| `src/local_search.py` | Swapping, Strong Drop One Point, onarım ve tekrar/geri alma |
| `src/solver.py` | Seçim, en iyi geçerli kayıt, tek nesil ve `solve` |
| `src/run_small.py` | Eski C kontrol örnekleri ve beş müşterili uçtan uca pilot |
| `tests/test_cdels.py` | Bağımsız maliyet hesapları ve davranış kontrolleri |

## Çalıştırma

Terminalde projenin `proje` klasöründen:

```bash
python3 -B src/run_small.py
python3 -B -m unittest discover -s tests -v
```

Ek paket gerektirmez; Python standart kütüphanesini kullanır.

Pilot: N=5, K=2, Q=10, NP=15, F=0.7, CR=0.7, ceza=100, tohum=42, 20 yeni nesil. Bilinen optimum çalıştırıcıya girilmez. Beklenen plan `[[2, 3, 5], [1, 4]]`, mesafe 29, uygunluk True ve durma nedeni `max_generations`. Süre makineye ve koşuya göre değişir. Test, bu küçük problemde bütün müşteri sıraları ve iki rotalı bölmeleri ayrıca tarayarak en düşük değerin 29 olduğunu doğrular; bu sonuç başka veri setlerine genellenmez.

## Uygulama kararları

- Kaynaklar verilen `rng` nesnesi üzerinden seçilir; `solve` bir kez `random.Random(seed)` oluşturur. NP farklı çözüm sayısı değildir: aynı rota planı yeniden üretilebilir, ama listeler bağımsızdır.
- N depo hariç sayılır. Başlangıç tam kapasiteyi kabul eder; sığmayan müşteriler tek rastgele rotaya eklenir. Geçersiz müşteri kapsamı hata; kapasite ihlali ise aday başına tek sabit ceza nedenidir.
- Mutasyon hedef dışındaki iki farklı bireyi seçer. Kopya üzerinde `ceil(N*F/2)` farklı seçilmiş müşteriye hareket denenir.
- Exp çaprazlama: rastgele dolu rota/konumda zorunlu hareket, ardından ilk rotadan tarama. İlk `random > CR` kontrolünde tüm tarama biter. Seçilmiş müşteriler kapatılır; takasta yer değiştiren müşteri de kapatılır. Kapalı müşteri yeniden hareketin seçilen müşterisi yapılmaz; başka takasta yerinden edilemeyeceği garanti edilmez. Kaynak koddaki `<= CR` sınırı korunur: rastgele sayı tam 0 ise CR=0 kontrolü de geçebilir.
- PerturbationMove ve exp, sona taşıma sırasında tek müşterili kaynak rotayı korur. Kapasite bu operatörlerde aşılabilir. Bu koruma, başlangıçta boş olan bir rotanın sonradan dolmasını engellemez.
- Yerel arama tam turu: takas → başka rotaya iyileştiren taşıma → gerekirse onarım. Tur sonu cezalı maliyet kesin azalırsa tekrar edilir; aksi hâlde tur başındaki bağımsız kopya döner. C kaynağının iyileşmeyen operatör sayacı kullanılmaz. Yerel arama ayrıca karşılaştığı en iyi geçerli planı döndürür; kabul edilmeyen onarımdaki geçerli planın kaybolmaması bu projeye ait açık kayıt tercihidir.
- Eşit maliyette target korunur; eşit iyileştirmede ilk taranan hareket seçilir. En iyi geçerli çözüm popülasyondan ayrı ve bağımsız kopya olarak saklanır. İhlalli sonuç başarılı plan olarak döndürülmez.
- Başlangıç g=0; tamamlanan her NP hedef güncellemesi bir nesildir. Bilinen optimum ara adımda bulunursa kalan eski bireyler kopyalanarak popülasyon boyutu korunur. `generations` yalnız tamamlanmış nesilleri, `partial_generation_targets` yarım kalan nesilde tamamlanan hedefleri sayar. Optimum yalnız geçerli arşiv üzerinden kontrol edilir.
- Konumlar ilk sürümde aranır; maliyetler tam hesaplanır. C kodunun hızlandırılmış işlem maliyetine veya aynı rastgele sayı dizisine sahip olunduğu iddia edilmez.

## Kontrol kapsamı

Testler; kopya bağımsızlığı, müşteri kapsamı, başlangıç ve mutasyon kuralları, exp sınırları ve erken durma, en iyi takas, uygun taşıma, başarılı/başarısız onarım, maliyeti artıran onarımda tur geri alma, ayrı geçerli kayıt, cezalı seçim, eski nesli değiştirmeme, sabit tohumla tekrar, sıfır nesil, başlangıç/ara nesil optimumu, geçerli plan bulunamaması ve küçük problemin tam taramayla maliyet doğrulamasını içerir.

Makale–kod tercihlerinin ayrıntısı Obsidian `Makale-1 Çıkarımlar` notunun B ve D bölümlerindedir. Sonucu etkileyen tercihler doğrulama raporuna aktarılmalıdır; bu küçük pilot, makaledeki deneylerin tekrarı olarak sunulmamalıdır.
