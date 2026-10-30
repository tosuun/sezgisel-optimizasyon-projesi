# CDELS eşleştirme ve düzeltme kaydı

30 Ekim 2026. Referans: [yazarların sabit kaynak sürümü](https://github.com/israelpereira55/CDELS/tree/9c605e3283cac03d0605128dc05cb3cd180411bb), commit `9c605e3283cac03d0605128dc05cb3cd180411bb` (28 Şubat 2023). Makale: [Souza, Boeres ve Moraes, 2023](https://doi.org/10.1016/j.swevo.2023.101245).

## Ne düzeltildi?

Önceki uygulama, makaledeki genel sözde kod ile kendi yorumlarımızı birleştiriyordu. Yayımlanmış C uygulamasının yerel arama ve seçim akışıyla eşdeğer değildi. 20 nesil/120 saniye ile tamamlanan 270 koşu **ön deney** olarak korunmuştur; bu sonuçlar yeni sürüme veya nihai 900 koşuya aktarılmaz.

Yeni protokol adı: **author_flow_9c605e3_safe**. Arama işlemlerinin sırası için sabit C kodu, deneyin NP/MaxGen/tekrar parametreleri için makale esas alınır. C kodu ile makale çeliştiğinde ayrım aşağıda açıkça belirtilmiştir. Bu, belirsiz bir karışım yerine isimlendirilmiş ve sınanmış bir yeniden uygulamadır. Yayımlanmış bütün sonuçların aynı çıkacağı veya belirsiz tarihsel deney sürümünün birebir kopyalandığı iddia edilmez.

| Bileşen | Yeni uygulama |
|---|---|
| Başlangıç | Her bireyde rastgele ileri/geri rota doldurma; C kodundaki `< Q` kabul koşulu. Kalanlar seçilen yöndeki son rotaya, kimlik sırasıyla eklenir. |
| Mutasyon | Target dışındaki üç farklı ebeveynin seçimi ve rastgele sayı tüketimi korunur. Kullanılmayan ikinci ebeveynin seçimi silinmez. C kodunun depo dahil sayım ve int dönüşümü uygulanır: `max(1, int(DIMENSION × F / 2))`. |
| Mutasyon müşteri listesi | Yayımlanan C listesinin kaydırma sınırı korunur; aynı müşteri yeniden seçilebilir. Bu, makale Algoritma 1'deki tekrarsız seçimden **farklıdır**. Gizlenmiş bir eşdeğerlik varsayımı değildir. |
| PerturbationMove | Hedef doluysa takas; değilse sona taşıma. C kodu gibi kaynak rota boş kalabilir. Boş rota, kullanılmayan araçtır; bütün müşteriler yine tam bir kez bulunur. Bu, makale Algoritma 2'nin tek müşterili rotayı koruma kuralından ayrılır. |
| Exp çaprazlama | İlk rota bütün K rotadan seçilir; boşsa sıradaki dolu rotaya yürünür. Zorunlu hareket, kapalı müşteri listesi, ilk rotadan tarama ve ilk CR aşımında tüm taramayı bitirme C koduyla eşleştirilmiştir. |
| Takas | En iyi tek takası seçme kaldırıldı. İlk iyileştiren takas hemen uygulanır; aynı konumdan tarama yeniden başlar. Tek çağrıda birden çok takas olabilir. |
| Taşıma | Sabit müşteri kopyası üzerinden küresel en iyi hedefi seçme kaldırıldı. Değişen rota listesi ve hedef rotaların sırası C kodunu izler; müşteri bir çağrıda birden fazla hedefe taşınabilir. |
| Onarım | Karıştırılmış rotalar/ilk uygun müşteri/küresel en iyi hedef kaldırıldı. Rastgele aşırı yüklü rota, sınırlı rastgele müşteri denemesi ve rastgele uygun hedef seçilir; yalnız seçilen hedefte en iyi konum bulunur. |
| Yerel arama | Tam tur geri alma kaldırıldı. İyileşmeyen operatör sayacı kullanılır; iki başarısız operatörde durulur. Onarım geçerlilik sağlarsa sayaç sıfırlanır. Son plan döner. |
| Seçim ve elitizm | Kesin daha düşük cezalı maliyet kabul edilir. Popülasyondaki geçerli elit hedef, kapasitesi ihlalli trial ile değiştirilmez. |
| En iyi çözüm | Ham mutant/trial ve yerel aramanın ara çıktılarından arşiv oluşturma kaldırıldı. Yalnız seçimden sağ kalan bireyler en iyiyi günceller. |
| Optimumda durma | Başlangıçta veya hedef ortasında çıkış kaldırıldı. Kontrol tamamlanmış neslin sonunda yapılır. |
| CPU süresi | `time.process_time()` ile CPU zamanı ayrı, `time.perf_counter()` ile geçen süre ayrı kaydedilir. Ara kayıttan devamda iki süre de biriktirilir. |

## Bilinçli sınırlar ve güvenlik düzeltmeleri

- Makale s. 8 ve Tablo 6'da N müşteri sayısıdır: **NP=3N, depo hariç**. C `main.c` varsayılanı `3 × DIMENSION` kullanır. Biz deney parametresini makaleyle eşleştirir, bu C varsayılanını açıkça geçersiz kılarız. Örneğin A-n32-k5 için NP=93, C main varsayılanı 96'dır. Üç ebeveyn + hedef gereği yalnız N=1 gibi veri kümesinde olmayan yapay örneklerde NP alt sınırı 4'tür.
- C başlığındaki MAX_GEN=5000 alınmaz; makalenin 200000/500000 değerleri kullanılır. Sayımımız tamamlanmış nesiller üzerindedir. C'nin başlangıcı 1 sayan sayaç ayrıntısı taşınmaz.
- Başlangıçta bütün müşteriler erken atanırsa C'deki do/while takılabilir. Python kalan rotaları boş tutarak biter.
- Tek müşterili/boş rotalarda C tamponundaki eski veya tanımsız komşular kullanılmaz. Gerçek rota komşuları ve depo ile mesafe farkı hesaplanır. Bağımsız tam mesafe hesabı bunu sınar.
- Sıfır talepli müşteri var ve hiçbir uygun hedef yoksa C onarımı takılabilir. Python gerçek en büyük boş kapasiteyle başarısız onarımı sonlandırır.
- Başlangıçtaki ilk ihlalli birey C'deki gibi yanlışlıkla geçerli elit sayılmaz. Hiç geçerli çözüm bulunmadıysa sonuç açıkça başarısızdır; sahte mesafe raporlanmaz.
- Python ve C rastgele sayı üreticileri aynı tohumda aynı diziyi vermez. Makale s. 8'de yalnız “ilk on tamsayı” yazılıdır; tam liste verilmez. **1..10**, açık Python deney tercihidir; doğrulanmış tarihsel tohum listesi olduğu iddia edilmez.
- Kamuya açık commit'in makaledeki tabloları üreten tam deney commit'i olduğu doğrulanmamıştır. Birebir tarihsel sonuç/süre garantisi verilemez.

## Bağımsız C karşılaştırması

Yazarların kaynak fonksiyonları değiştirilmeden geçici test çağırıcılarıyla derlendi (`cc -O0`). İki dilde de aynı denetimli ham rastgele sayılar kullanıldı. Üretimde bu denetimli üretici kullanılmaz; Python Random kullanılır. Kaynak SHA-256'ları, derleyici bilgisi ve C çıktıları `tests/fixtures/author_cases.json` içinde kayıtlıdır.

- Takas, taşıma, onarım ve yerel arama: **400 örneğin rotaları, maliyetleri ve rastgele sayı tüketimi eşleşti**.
- Başlangıç, mutasyon, exp çaprazlama ve tam nesil üretimi: **160 örneğin rotaları ve rastgele sayı durumu eşleşti**.
- Aynı 40 tam-nesil C örneği, ayrıca gerçek Python `solve()` döngüsünden geçirilerek tamamlanmış popülasyon ve RNG kaydı karşılaştırılır.
- Eski 175 → 154 karşı örneği artık **175 → 139** verir; sonuç C ile aynıdır.
- Bunlar sınanmış küçük girdiler için davranış kanıtıdır; bütün olası girdilerde veya tarihsel deneyde bit düzeyinde eşdeğerlik ispatı değildir. Güvenlik düzeltmeleriyle değişen sınır durumları ayrı test edilir.
- Eski kendi V2 sürümümüzü referans alan test kaldırıldı. Mesafe farkının bağımsız tam hesapla denetimi korunurken yöntem referansı gerçek yazar çıktıları oldu.

## Deney protokolü

| Parametre | Değer |
|---|---|
| Veri | Makalenin aynı 90 CVRPLIB problemi; aynı K, Q, BKS ve dosya özetleri |
| Tekrar | Problem başına 10; toplam 900 koşu |
| Tohum | 1,2,3,4,5,6,7,8,9,10; yukarıdaki açık sınırlamayla |
| NP | 3 × depo hariç müşteri sayısı |
| F / CR / ceza | 0.7 / 0.7 / 100 |
| Strateji | rand/1/exp; yukarıda tanımlanan kamuya açık kaynak akışı |
| MaxGen | A/B/P/E/F: 200000; M: 500000 |
| Süre kesmesi | **Yok**; eski 120 saniye sınırı nihai deneye uygulanmaz |
| Durma | Tam nesil sonunda optimum veya tamamlanmış nesil sınırı |
| Karşılaştırma | S. 10-12 Tablo 7-11: Best, Avg., optimum sayıları; s. 13 Tablo 12: ortalama CPU zamanı. Bizim örnek SD ayrıca verilir. |

İşletim sistemi/Python/donanım farklıdır. CPU zamanı ayrı kaydedilmesi bile makalenin i5-3570/gcc 5.4 -O3 ölçümüyle doğrudan hız üstünlüğü iddiası kurmaz.

## Küçük gerçek problem kontrolü

P-n16-k8 ve A-n32-k5, tohum 1/2/3 ile makalenin nesil sınırları altında, süre kesmesi olmadan denendi. Altı koşu da optimuma ulaştı: sırasıyla **450** ve **784**. Rotalar, kapasiteler ve mesafeler bağımsız kontrol edildi. Küçük bir toplu çalıştırma + analiz denemesi de JSON, tablo, CPU alanları ve beş grafik üretimini sınar; aynı komutun ikinci çağrısı bitmiş altı koşuyu atlar.

B-n57-k7 ve M-n121-k7 için 5 saniyelik ayrı süre tanıları yapılmıştır. Bunlar **nihai karşılaştırma sonucu değildir**; 900 koşuya eklenmez. Büyük örnekte bu süre bir tam nesli bile bitirmeye yetmemiştir. Önceki 79 dakikalık kısa deneyi 10/3 ile çarparak tam bütçenin süresini tahmin etmek doğru değildir.

**900 koşuluk yeni deney henüz başlatılmadı.** Küçük pilotun başarılı olması, 90 problemde makaledeki 88 optimumun bulunacağını garanti etmez. Nihai başarı ancak yeni deney tamamlandıktan sonra değerlendirilir.
