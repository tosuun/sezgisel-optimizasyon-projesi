# Makale 1 — Çıkarımlar

İlgili proje: [[Sezgisel Proje]]
Son düzenleme: 2026-10-24

## Makale bilgileri ve görevimiz

**A robust algorithm based on Differential Evolution with local search for the Capacitated Vehicle Routing Problem**
- Yazarlar: Israel Pereira Souza, Maria Claudia Silva Boeres, Renato Elias Nunes Moraes.
- Dergi: Swarm and Evolutionary Computation, 77 (2023), 101245.
- DOI: https://doi.org/10.1016/j.swevo.2023.101245
- Kaynak kod: https://github.com/israelpereira55/CDELS
- Yerel PDF: [Makale 1](file:///Users/tosun/Desktop/makale1.pdf)
- Dersin ilk aşaması: yöntemi Python’da uygulamak, makaledeki deneylerle karşılaştırmak ve doğrulama raporu yazmak.
- İkinci aşama ayrı: CDELS’i ikinci makalenin tek depolu CCVRP problemine uyarlamak. TIEA algoritmasını baştan yazmak bu aşamanın amacı değil.

## 1. Yöntemin özeti

- Popülasyon tabanlı evrimsel algoritmayı yerel arama prosedürleriyle birleştiren hibrit bir meta-sezgisel yöntem öneriliyor.
- Diferansiyel Evrim (Differential Evolution, DE), normalde sürekli sayılar üzerinde çalışır. Makalede müşteri sıraları üzerinde çalışabilmesi için ayrık operatörler tasarlanıyor.
- CDELS, farklı rota planları üretip bunları birbirinden yararlandıran ve küçük değişikliklerle iyileştiren bir algoritma.

## 2. CVRP: problem, girdiler ve kısıtlar

Elimizde tek depo, talepleri bilinen müşteriler ve aynı kapasitede araçlar var.

1. Her rota depodan başlar ve depoda biter.
2. Her müşteri tam bir kez ziyaret edilir; talebi araçlar arasında bölünmez.
3. Bir rotadaki taleplerin toplamı araç kapasitesini aşmaz.
4. Rota sayısı mevcut araç sayısını aşmaz.

**Amaç:** Bütün araçların toplam seyahat mesafesini azaltmak.

Örnek: Kapasite 10 ise talepleri 3, 4 ve 2 olan müşteriler aynı rotada olabilir; toplam 9. Talebi 5 olan başka müşteri eklenirse kapasite aşılır.

| Sembol | Anlamı                                |
| ------ | ------------------------------------- |
| N      | Müşteri sayısı; depo hariç            |
| K      | En fazla kullanılabilecek araç sayısı |
| Q      | Her aracın kapasitesi                 |
| qᵢ     | Müşteri i’nin talebi                  |
| dᵢⱼ    | İki nokta arasındaki mesafe           |

## 3. Diferansiyel Evrim ve temel kavramlar

DE tek çözümle değil, bir çözüm topluluğuyla çalışır. Her turda yeni adaylar üretir, mevcut çözümlerle birleştirir ve maliyeti daha iyi olanları seçer.

| Terim | Projedeki karşılığı |
| --- | --- |
| Birey | Bütün araçların rotalarını içeren tam çözüm |
| Popülasyon | Birbirinden farklı tam çözümler |
| Nesil | Popülasyonu güncellediğimiz bir tur |
| Mutasyon | Yeni aday üretmek için çözümü değiştirme |
| Çaprazlama | Mevcut çözümle adayın bilgilerini birleştirme |
| Seçilim | Karşılaştırılan çözümler arasından daha iyisini tutma |

**Bir birey bir araç değildir; bütün araçların planıdır.** Klasik DE’nin sayısal işlemleri ile CDELS’in ayrık müşteri hareketleri aynı işlem değildir.

## 4. Çözümün veri yapısı

Örnek çözüm:
- Araç 1: Depo → 1 → 3 → Depo
- Araç 2: Depo → 2 → 4 → 5 → Depo

Basit liste gösterimi: `[[1, 3], [2, 4, 5]]`.

- Her satır bir rota, her eleman bir müşteridir.
- Müşterinin hangi rotada ve o rotada kaçıncı sırada olduğu önemlidir.
- Depoya ilk gidiş ve son dönüş mesafe hesabına dahil edilir.
- Makaledeki hareketleri hızlandırmak için müşteri → rota/konum eşlemesi tutulabilir.

### Mesafe ve maliyet hesabı

Depo kimliği program içinde `0` olarak kullanılabilir. `[a, b, c]` rotası için:

```text
rota_yükü = q[a] + q[b] + q[c]
rota_mesafesi = d[0,a] + d[a,b] + d[b,c] + d[c,0]
çözüm_mesafesi = bütün rota mesafelerinin toplamı
```

Örnek: Depo–1 mesafesi 4, 1–3 mesafesi 6 ve 3–Depo mesafesi 5 ise `[1, 3]` rotasının mesafesi 15’tir.

Müşteri kapsamı ve kapasite ayrı kontrollerdir. Eksik veya tekrarlı müşteri, kapasite cezasıyla kabul edilebilecek bir aday değildir; uygulama hatasıdır.

```text
arama_maliyeti = çözüm_mesafesi + (Penalty, kapasite aşılmışsa; aksi halde 0)
```

Makaledeki ceza, kapasite aşım miktarıyla çarpılan bir katsayı değil, geçersiz bireye eklenen sabit değerdir.

## 5. Başlangıç popülasyonu

- NP adet rastgele birey oluşturulur.
- Müşteriler kapasite aşılmadan rotalara yerleştirilmeye çalışılır.
- Yerleştirilemeyen müşteriler kalırsa rastgele seçilen bir rotaya eklenir; kapasite aşılabilir.
- Böyle adayların maliyetine Penalty eklenir.

**Arama sırasında geçersiz aday tutulabilir; nihai çözüm mutlaka geçerli olmalıdır.**

## 6. Temel hareket ve mutasyon

- Bir bireyin kopyası alınır.
- Başka bir birey referans alınarak müşterinin rota ve sıra bilgisi belirlenir.
- Müşteri kopyada referans konuma taşınmaya çalışılır. Konum doluysa müşteri oradaki müşteriyle yer değiştirir.
- Referans sıra kopyadaki rotada yoksa müşteri uygun koşullarda ilgili rotanın sonuna eklenir.
- Taşıma sırasında müşterinin çıktığı rotayı boş bırakmamak için kontrol yapılır.
- F, değişiklik girişimlerinin sayısını etkiler: `ceil((N / 2) × F)`.

Bu işlem yalnızca rastgele iki müşteriyi değiştirmek değildir; popülasyondaki konum bilgisini kullanır. Daha büyük F her koşulda daha iyi sonuç anlamına gelmez.

## 7. Çaprazlama

- Mevcut bireyin kopyası alınır.
- Mutantın bazı konum bilgileri PerturbationMove ile kopyaya aktarılır.
- Önce zorunlu bir hareket girişimi, sonra CR’ye bağlı hareketler yapılır.
- Zorunlu girişim, her durumda gerçekten farklı bir çözüm oluşacağını garanti etmez.

**Uygulama notu:** Makalenin genel çaprazlama sözde kodu ile deneylerde seçilen `rand/1/exp` sürümünün ayrıntıları kaynak kodla karşılaştırılmalı. Yalnızca genel açıklamayı kodlayıp deney sürümüyle aynı olduğunu varsaymamalıyız.

## 8. Yerel arama ve onarım

| İşlem | Görevi |
| --- | --- |
| Swapping | Kapasiteyi aşmadan iki müşteriyi değiştirerek maliyeti iyileştirmek |
| Strong drop one point | Müşteriyi başka rotada maliyeti azaltacak uygun konuma taşımak; tek müşterili rotayı boşaltmamak |
| Drop one point infeasible | Kapasitesi aşılmış rotadan uygun başka rotaya müşteri taşıyarak onarmaya çalışmak |

Yerel arama iyileşme oldukça tekrarlanır. Onarım her zaman başarılı olmak zorunda değildir; başarısız aday cezalandırılır.

## 9. Seçilim ve ana döngü

Başlangıç popülasyonu → Mutasyon → Çaprazlama → Yerel arama/onarım → Seçilim → Sonraki nesil.

- Mevcut bireyle yeni aday maliyet üzerinden karşılaştırılır.
- Geçersiz aday için mesafeye sabit Penalty eklenir.
- Geçersiz bireyler yararlı rota parçaları taşıyabildiği için aramada tutulabilir.
- En iyi geçerli çözüm ayrıca izlenmelidir; kapasiteyi aşan aday sonuç diye raporlanamaz.
- Nesil sınırına ulaşınca veya bilinen optimum elde edilince durulur.

## 10. Deney ve doğrulama düzeni

- CVRPLIB’den A, B, P, E, F ve M gruplarındaki toplam 90 örnek kullanılmış.
- Her örnek 10 kez, ilk on tam sayı tohum olarak kullanılarak çalıştırılmış.
- Mesafeler TSPLIB kuralıyla en yakın tam sayıya yuvarlanmış. Python’ın varsayılan yuvarlamasıyla eşdeğer olduğunu varsaymadan kural kontrol edilmeli.
- Yazarların uygulaması C dilinde; bizim uygulamamız Python olacak. Çalışma sürelerinin doğrudan aynı olması beklenmez.

### Tablo 6 — Son deney parametreleri, sayfa 10

| Parametre | Değer |
| --- | --- |
| NP | 3 × N |
| F | 0,7 |
| CR | 0,7 |
| Strateji | rand/1/exp |
| Penalty | 100 |
| MaxGen — A, B, E, F, P | 200.000 |
| MaxGen — M | 500.000 |

Büyük deneylerden önce küçük örneklerde doğruluk kontrolü yapılmalı. Daha kısa nesil sınırıyla yapılan denemeler, makalenin tam deney koşullarının tekrarı olarak sunulmamalı.

### Sonuç ölçütleri

- BKS: Bilinen en iyi çözüm değeri; optimumluğu ayrıca belirtilmişse optimum olarak kullanılabilir.
- Best: Tekrarlar arasında bulunan en iyi değer.
- Avg.: Tekrarların ortalama değeri.
- Örnek karşılaştırma: Tablo 7’de A-n32-k5 için referans değer 784.
- Yalnızca mesafe değil; her müşterinin tam bir kez bulunması, araç sayısı ve kapasite uygunluğu da kontrol edilmeli.
- Birkaç başarılı deneme algoritmanın bütün örneklerde optimum bulacağını göstermez.

## 11. Python uygulama sırası

Her adım bir öncekinin üzerine kurulur. Küçük elle hesaplanabilir veriyle başlayan uygulama, daha sonra CVRPLIB dosyalarına geçirilir. Aşağıdaki fonksiyon adları önerilen Python tasarımıdır; makaledeki kaynak kodun birebir arayüzü değildir.

| Sıra | Kod parçası | Girdi → çıktı | Tamamlanma ölçütü |
| --- | --- | --- | --- |
| 1 | Problem verisi ve mesafe matrisi | Koordinatlar, talepler, Q, K → problem verisi | Depo ve müşteriler ayrı; mesafeler simetrik; köşegen sıfır |
| 2 | `route_load`, `route_distance`, `solution_distance` | Rota/çözüm → yük ve mesafe | Küçük örnekte elle hesapla aynı; depo dönüşü dahil |
| 3 | `validate_solution`, `evaluate` | Çözüm → uygunluk, mesafe, cezalı maliyet | Eksik/tekrarlı müşteri, kapasite aşımı ve fazla rota ayrı raporlanır |
| 4 | `initialize_population` | Problem, NP, rastgelelik üreteci → bireyler | Her bireyde müşteriler tam bir kez; kapasite aşımı doğru işaretlenir |
| 5 | `perturbation_move` | Kopyalanan çözüm, referans, konum → değiştirilmiş çözüm | Hem dolu konumda takas hem olmayan konumda ekleme çalışır; referans değişmez |
| 6 | `mutate` | İki referans birey, F → mutant | Ayrı bir kopyada belirlenen sayıda hareket girişimi; müşteri kapsamı korunur |
| 7 | `crossover` | Hedef birey, mutant, CR → aday | Kaynak kodla netleştirilen exp davranışı uygulanır; girdiler değişmez |
| 8 | `swap_search`, `relocate_search`, `repair` | Aday → iyileştirilmiş/onarılmış aday | İyileştirme ve kapasite kontrolleri doğru; onarım başarısızlığı bildirilebilir |
| 9 | `select`, `solve` | Problem ve parametreler → en iyi geçerli çözüm | Popülasyon nesiller halinde güncellenir; nihai çözüm bağımsız doğrulamadan geçer |
| 10 | Veri dosyası okuyucu ve deney çalıştırıcı | CVRPLIB dosyası, tohumlar → sonuç kayıtları | Dosya kimlikleri, talep, depo, kapasite ve mesafe kuralı doğru eşlenir |

### Veri yapısı ve kopyalama

```python
# Önerilen basit gösterim
routes = [[1, 3], [2, 4, 5]]
demands = {0: 0, 1: 3, 2: 2, 3: 4, 4: 1, 5: 2}
capacity = 10
max_vehicles = 2
```

- Problem verisi: koordinatlar, talepler, depo, kapasite, araç sınırı, mesafe matrisi.
- Birey: rota listeleri, rota yükleri, gerçek mesafe, kapasite uygunluğu, cezalı maliyet.
- Hızlandırma için müşteri → `(rota, sıra)` eşlemesi tutulabilir. Her hareketten sonra bu eşleme güncellenir.
- İç içe listelerde yalnızca dış listeyi kopyalamak yeterli değildir. Adaydaki değişiklikler ebeveynin rotalarını değiştirmemelidir.
- Dosyadaki düğüm numaraları ile Python indisleri açık bir eşlemeyle ayrılmalıdır. Dosyanın düğüm sayısı genellikle depoyu da içerir; N ise müşteri sayısıdır.

### Ana döngünün uygulama taslağı

```text
Popülasyonu oluştur.
Başlangıçtaki en iyi geçerli çözümü kaydet; yoksa henüz çözüm bulunmadı durumunu tut.
Her nesilde:
    Önceki nesilden her hedef birey için:
        Hedeften ve birbirinden farklı iki referans birey seç.
        Mutant oluştur.
        Hedef ve mutanttan çaprazlama adayı oluştur.
        Yerel arama ve gerekirse onarım uygula.
        Hedef ile adayı cezalı maliyetlerine göre karşılaştır.
        Seçileni yeni nesle ekle.
        En iyi geçerli çözümü güncelle.
    Yeni nesli mevcut popülasyon yap.
    Nesil sınırını ve varsa bilinen optimuma ulaşmayı kontrol et.
En iyi geçerli çözümü döndür; hiç bulunmadıysa bunu açıkça bildir.
```

Yeni bireyleri oluştururken önceki neslin referansları yanlışlıkla değiştirilmemelidir. Sözde kodun indisleri, eşit maliyette seçim ve son yerel arama çıktısı kaynak kodla karşılaştırılarak kesinleştirilecek uygulama ayrıntılarıdır.

## 12. İlk çalıştırmadan doğrulama raporuna

1. **Elle hesaplanabilir örnek:** 5–6 müşteri üzerinde mesafe, kapasite ve hareket sonuçlarını kontrol et.
2. **Küçük gerçek örnek:** Örneğin A-n32-k5 üzerinde veri okuma ve tüm algoritmayı çalıştır. Bu dosyada 32 düğüm depoyu içerir; müşteri sayısı 31’dir. Tablo 7 referansı 784’tür.
3. **Kısa geliştirme deneyi:** Küçük popülasyon/nesil sınırıyla hata ayıklama yap. Bu koşulları makalenin tam tekrarı olarak raporlama.
4. **Karşılaştırma deneyi:** Seçilen örnekleri belirtilen parametre ve tohumlarla tekrar çalıştır. Kullanılan bütçeyi açıkça kaydet.
5. **Rapor:** Yöntemi, uygulama tercihlerini, deney kapsamını, sonuçları ve makaleden farkları yaz.

Her koşuda kaydedilecek alanlar:

```text
örnek adı, tohum, parametreler, gerçek mesafe, geçerlilik,
çalışma süresi, tamamlanan nesil sayısı, durma nedeni, rota listeleri
```

Özet tabloda en iyi, ortalama ve standart sapma; referans değere yüzde fark; geçerli çözüm bulunan koşu sayısı yer alır.

```text
yüzde fark = 100 × (bulunan mesafe − referans mesafe) / referans mesafe
```

Aynı tohumun C ve Python’da aynı rastgele sayı dizisini vereceği varsayılmaz. Çalışma süresi karşılaştırmalarında dil, donanım ve deney bütçesi farklılıkları belirtilir.

## 13. Mevcut durum ve sonraki somut adım

- Kullanıcı tarafından doğrulanan kavrayış: Bir çözüm, bütün araçların rotalarının birlikte belirlenmesidir.
- Önceki notta kullanıcı tarafından işaretlenen genel okuma adımları tamamlanmıştı; bunlar kodun tamamlandığı anlamına gelmez.
- Bu notun hazırlanması sırasında kod dosyaları incelenmedi; uygulama adımları tamamlandı olarak işaretlenmedi.
- **Sonraki somut adım:** Küçük bir veri tanımıyla `route_load`, `route_distance` ve `solution_distance` fonksiyonlarını yazmak; elle hesaplanan örnekle karşılaştırmak.
- Çaprazlamanın exp sürümü ve diğer sözde kod ayrıntıları kaynak kodla netleştirilmeden uygulama makalenin birebir tekrarı sayılmamalı.
- İlk aşama CVRP doğrulamasıdır. CCVRP’ye geçiş, bu altyapı çalıştıktan sonra ikinci aşamada yapılır.

## 14. İlk aşamayı tamamlama eylem planı

**Hedef:** İlk makaledeki CDELS yönteminin Python uygulaması, kayıtlı doğrulama deneyleri ve doğrulama raporu. Bu plan yalnızca CVRP içindir; CCVRP uyarlaması ikinci aşamadır.

**Takip kuralı:** Aşağıdaki kutular planlanan işleri gösterir. İlgili çıktı üretilip kontrol edilince işaretlenir. Önceden yapılmış işler varsa dosyaları doğrulandıktan sonra tamamlandı sayılır. Süreler yerine somut tamamlanma ölçütleri kullanılır.

### A. Proje dosyaları ve kaynakların hazırlanması

- [ ] Mevcut proje klasörünü ve kodları incele; yapılan işleri belirle, mevcut kodun üzerine kontrolsüz yazma.
- [ ] Python ortamını hazırla; kullanılan Python ve paket sürümlerini kaydet.
- [ ] Kod, veri, deney ayarları, sonuçlar ve rapor için düzen oluştur: `src/`, `data/`, `configs/`, `results/`, `report/`.
- [ ] Makalenin PDF, DOI, kaynak kod ve veri bağlantılarını proje kaynaklarına kaydet.
- [ ] Makalenin SCI-Expanded kaydını ve yayın yılını ders dosyalarına ekle.
- [ ] Yazarların CDELS kaynak kodunu edin; incelenen sürümün tarihini veya commit kimliğini ve lisansını kaydet.

**Tamamlanma ölçütü:** Projenin çalıştırılacağı ortam ve başvurulacak kaynaklar belirli; mevcut çalışmaların durumu kayıtlı.

### B. Makale ile kaynak kodun eşleştirilmesi

- [ ] Çözüm gösterimini, rota sayısını ve başlangıç popülasyonunu kodla karşılaştır.
- [ ] `PerturbationMove` için takas, sona ekleme ve tek müşterili rotayı boş bırakmama koşullarını kesinleştir.
- [ ] Mutasyonun hareket sayısını ve referans birey seçim kurallarını kesinleştir.
- [ ] Deneylerdeki `rand/1/exp` stratejisinin çaprazlama akışını belirle; genel sözde koddan farkını kaydet.
- [ ] Yerel arama sırasını, kabul koşullarını, tekrar koşulunu ve döndürülen çözümü kontrol et.
- [ ] Cezanın uygulanması, eşit maliyet durumunda seçilim ve durma koşullarını kontrol et.
- [ ] Sözde kod ile kaynak kod farklıysa hangi davranışın uygulandığını ve gerekçesini rapor notuna yaz.

**Tamamlanma ölçütü:** Kodlanacak algoritma adımları açık; belirsiz noktalar sessizce tahmin edilmemiş.

### C. Problem verisi ve maliyet altyapısı

- [ ] 5–6 müşterili, elle hesaplanabilir küçük örnek tanımla.
- [ ] Problem girdilerini oluştur: depo, koordinatlar, talepler, Q ve K.
- [ ] Mesafe matrisini oluştur; deney verisindeki mesafe ve yuvarlama kuralını uygula.
- [ ] `route_load`, `route_distance` ve `solution_distance` fonksiyonlarını yaz.
- [ ] `validate_solution` ile müşteri eksikliği/tekrarı, geçersiz kimlik, kapasite ve araç sayısını ayrı kontrol et.
- [ ] `evaluate` ile gerçek mesafeyi ve kapasite cezası eklenmiş arama maliyetini ayrı tut.
- [ ] Elle hesaplanmış geçerli ve kapasitesi aşılmış örneklerle bu fonksiyonları kontrol et.

**Tamamlanma ölçütü:** Rotaların yükü ve maliyeti doğru; geçersiz çözümler nedenleriyle belirleniyor; depo dönüşü hesaba katılıyor.

### D. CDELS bileşenlerinin uygulanması

- [ ] Bağımsız birey kopyalama ve gerekiyorsa müşteri-konum eşlemesini uygula.
- [ ] Başlangıç popülasyonu üretimini yaz; yerleştirilemeyen müşteriler ve ceza davranışını kontrol et.
- [ ] `PerturbationMove` işlemini yaz; hem takas hem ekleme örneklerini doğrula.
- [ ] Mutasyonu yaz; hareket sayısı ve müşteri kapsamının korunduğunu kontrol et.
- [ ] Kaynak kodla eşleştirilmiş exp çaprazlamasını yaz.
- [ ] Swapping yerel aramasını yaz.
- [ ] Strong drop one point yerel aramasını yaz.
- [ ] Drop one point infeasible onarımını yaz; onarım başarısızlığını doğru ele al.
- [ ] Yerel arama tekrar döngüsünü kur.
- [ ] Cezalı maliyete göre seçilimi yaz.
- [ ] Önceki nesli değiştirmeden yeni nesli üreten ana döngüyü kur.
- [ ] En iyi geçerli çözümü ayrıca izle; geçerli çözüm bulunamazsa açık durum döndür.
- [ ] Tohum, nesil sınırı, varsa bilinen optimum ve durma nedeni kayıtlarını ekle.

**Tamamlanma ölçütü:** Küçük örnek üzerinde bütün algoritma uçtan uca çalışıyor; müşteri kaybolmuyor/çoğalmıyor; ebeveynler yanlışlıkla değişmiyor; sonuç bağımsız uygunluk kontrolünden geçiyor.

### E. Gerçek veri ve pilot doğrulama

- [ ] CVRPLIB veri dosyası okuyucusunu yaz; dosyadaki depo ve kimlikleri program indislerine eşle.
- [ ] Düğüm sayısının depoyu içerdiğini, N’nin ise müşteri sayısı olduğunu kontrol et.
- [ ] Küçük örnekler seç: örneğin P-n16-k8 ve A-n32-k5; dosyaların Q, K ve taleplerini doğrula.
- [ ] Referans çözüm dosyası varsa okuyup maliyetini hesapla; mesafe kuralını bu yolla da kontrol et.
- [ ] Kısa geliştirme koşuları yap; hatalı maliyet, geçersiz çıktı ve sonsuz döngüleri gider.
- [ ] Sonuç, referans değerin altında çıkarsa önce kapasite, kapsam ve mesafe hesabını denetle; doğrudan yeni rekor olarak yorumlama.
- [ ] Gerekirse yazarların C uygulamasını aynı örnekte çalıştırarak farkın kaynağını araştır.

**Tamamlanma ölçütü:** En az bir gerçek örnekte çözüm üretilebiliyor; veri okuma ve maliyet hesabı doğrulanmış. Referansa ulaşılmadıysa bunun hata mı arama performansı mı olduğu araştırılmış.

### F. Doğrulama deneyinin kapsamını sabitleme

- [ ] Kullanılacak örnek listesini ve gerekçesini belirle; farklı boyut ve veri gruplarını kapsama durumunu belirt.
- [ ] Dersin doğrulama beklentisini netleştir: seçili örnekler mi, makalenin bütün deneyleri mi? Beklenti belirlenmeden küçük alt kümeyi yeterli ilan etme.
- [ ] Parametreleri Tablo 6’ya göre ayarla: NP=3N, F=0.7, CR=0.7, rand/1/exp, Penalty=100.
- [ ] Tam deney tekrarı yapılacaksa MaxGen sınırlarını uygula: A/B/E/F/P için 200.000, M için 500.000; bilinen optimuma ulaşınca erken durmayı kaydet.
- [ ] Daha düşük bütçe gerekiyorsa bunu ayrı bir deney olarak tanımla ve makalenin koşullarından farkını açıkça yaz.
- [ ] Tekrar sayısını, kullanılan on tohum değerini ve kaynak kodla eşleşmesini kaydet.
- [ ] Tam F–CR parametre taramasını yeniden yapmanın gerekip gerekmediğini kapsamda belirt; doğrulama ile yeniden parametre ayarını ayır.
- [ ] Pilot süre ölçümünden toplam deney süresini tahmin et; uzun koşulardan önce uygulamanın doğruluğunu tamamla.

**Tamamlanma ölçütü:** Örnekler, parametreler, tohumlar ve hesaplama bütçesi deneyler başlamadan belirli; kapsam sınırları yazılı.

### G. Tekrarlı deneylerin yürütülmesi

- [ ] Deneyleri ayar dosyasından başlatan çalıştırıcıyı hazırla.
- [ ] Her koşuda örnek, tohum, parametre, mesafe, geçerlilik, süre, nesil sayısı, durma nedeni ve rota listesini kaydet.
- [ ] Kod sürümü, veri kaynağı, Python/paket sürümleri ve donanım bilgisini kaydet.
- [ ] Her koşunun nihai çözümünü arama kodundan bağımsız kontrol et.
- [ ] Hata veren veya geçerli çözüm bulamayan koşuları sakla; başarılı koşular arasından seçerek raporlama yapma.
- [ ] Sonuçları dosyaya kademeli kaydet; yarım kalan deneylerin tamamlanmış kayıtlarını koru.
- [ ] Makale parametreleriyle yapılan koşuları geliştirme ve farklı bütçe koşularından ayrı tut.

**Tamamlanma ölçütü:** Planlanan koşuların hepsinin sonucu veya başarısızlık durumu kayıtlı; her sayısal sonuç ilgili rotalara ve ayarlara kadar izlenebilir.

### H. Sonuçların analizi

- [ ] Her örnek için en iyi, ortalama, standart sapma, geçerli çözüm sayısı ve süre özetini çıkar.
- [ ] Makalenin aynı örneğe ait CDELS Best/Avg. sonuçlarını ve referans değerini karşılaştırma tablosuna ekle.
- [ ] Referans değere yüzde farkı hesapla; geçersiz çıktıları geçerli çözüm kalitesi gibi ortalamaya katma.
- [ ] Yakınsama kaydı varsa nesillere göre en iyi geçerli maliyet grafiğini hazırla.
- [ ] En az bir örneğin rotalarını çiz; çizimin tek başına uygunluk kontrolü olmadığını dikkate al.
- [ ] Referansa ulaşılamayan örneklerde olası nedenleri incele: uygulama farkı, yuvarlama, deney bütçesi ve rastgelelik.
- [ ] C/Python ve donanım farkları nedeniyle süreleri doğrudan algoritmik üstünlük diye yorumlama.
- [ ] İstatistiksel anlamlılık iddiası kullanılacaksa uygun analiz tasarla; makaledeki %99 güven iddiasını kendi deneyinin sonucu gibi aktarma.

**Tamamlanma ölçütü:** Sonuçlar karşılaştırılabilir tablolarla sunuluyor; farklar ve başarısızlıklar açıklanıyor; elde edilmeyen başarılar iddia edilmiyor.

### I. Doğrulama raporunun yazılması

- [ ] Amaç ve kapsam: İlk makalenin hangi yönteminin ve hangi deneylerinin tekrarlandığını yaz.
- [ ] Problem: CVRP girdileri, amaç fonksiyonu ve kısıtlarını açıkla.
- [ ] Yöntem: Gösterim, popülasyon, mutasyon, çaprazlama, yerel arama, ceza ve seçilimi anlat.
- [ ] Uygulama: Python tasarımını ve kaynak kod/sözde kodla eşleştirmede alınan kararları belirt.
- [ ] Deney düzeni: Veri setleri, örnek listesi, parametreler, tohumlar, bütçe ve ortamı yaz.
- [ ] Bulgular: Makale ile karşılaştırma tabloları, geçerlilik sonuçları ve gerekli grafikleri ekle.
- [ ] Tartışma: Başarıları, sapmaları, olası nedenleri ve sınırlılıkları açıkla.
- [ ] Sonuç: Hangi ölçüde doğrulama yapıldığını, tamamlanmayan kapsamı ve ikinci aşamaya hazır altyapıyı belirt.
- [ ] Kaynakça: Makale, veri kaynağı, yararlanılan kod ve ek kaynakları göster.
- [ ] Raporu kontrol et: Tablo değerleri ham kayıtlarla, parametreler gerçek koşularla tutarlı olsun.

**Tamamlanma ölçütü:** Rapor, hangi çalışmanın yapıldığını ve hangi kanıta dayandığını başka birinin anlayabileceği şekilde anlatıyor.

### J. Son kontrol ve ilk aşamanın kapatılması

- [ ] README’ye ortam kurulumu, veri yerleşimi, tek örnek çalıştırma ve deneyleri tekrarlama komutlarını ekle.
- [ ] Örnek bir çalıştırmayı belgelenmiş komutlarla yeniden yap; sonuç dosyası ve geçerlilik çıktısını kontrol et.
- [ ] Tohum ve ortam sabitken kendi uygulamamızın tekrar üretilebilirliğini kontrol et.
- [ ] Teslim paketine kod, ayarlar, veri erişim bilgileri, ham sonuçlar, özet tablolar ve doğrulama raporunu ekle.
- [ ] Kullanılan üçüncü taraf kodun lisans ve atıf koşullarını koru.
- [ ] Tamamlanan doğrulama kapsamını ve ikinci aşamaya kalan işleri kısa bir durum notuyla kaydet.

**İlk aşamanın bittiği nokta:** Çalışan Python CDELS uygulaması + bağımsız kontrol edilmiş sonuçlar + kapsamı açık makale karşılaştırması + tekrar çalıştırma yönergeleri + doğrulama raporu hazırdır. Yalnızca kodun çalışması veya tek örnekte optimum bulunması aşamayı tek başına tamamlamaz.
