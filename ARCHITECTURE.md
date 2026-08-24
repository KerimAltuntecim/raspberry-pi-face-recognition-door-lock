# Sistem Mimarisi

Bu belge, kaynak kodu paylaşılmadan Raspberry Pi tabanlı akıllı kapı kilidi prototipinin çalışma mimarisini açıklar.

## Katmanlar

### 1. Görüntü alma

USB kamera üzerinden sürekli kare alınır. Görüntü akışı, kullanıcı arayüzünde canlı önizleme ve doğrulama motoru tarafından ortak olarak kullanılır.

### 2. Yüz algılama ve hizalama

OpenCV YuNet yüz algılama modeli karedeki yüzü ve yüz noktalarını belirler. Yüz noktaları, farklı kamera açıları ve yüz konumlarının karşılaştırılabilir olması için hizalama adımında kullanılır.

### 3. Özellik çıkarma ve karşılaştırma

Hizalanmış yüz, SFace tabanlı tanıma modeline gönderilir. Üretilen özellik vektörü, kayıt sırasında oluşturulan kullanıcı özellikleriyle karşılaştırılır. Gerçek eşik değeri ve veri depolama yapısı bu public depoda paylaşılmamıştır.

### 4. Doğrulama durumu

Sistem; `bekleniyor`, `yüz bulunamadı`, `bilinmeyen kişi`, `challenge gerekli`, `doğrulandı` ve `reddedildi` gibi durumlar üzerinden ilerler. Eşleşme tek başına kilidi açmaz; deneysel baş hareketi kontrolü tamamlandıktan sonra GPIO katmanına izin gönderilir.

### 5. Kullanıcı arayüzü

PySide6 arayüzü kamera görüntüsünü, kayıt/doğrulama işlemlerini, kullanıcı listesini ve hata durumlarını gösterir. Görüntü işleme motoru ile arayüz birbirinden ayrılarak test ve bakım kolaylaştırılmıştır.

### 6. Çıkış ve ses katmanı

Başarılı doğrulama sonucunda RPi.GPIO üzerinden prototip kilit/LED çıkışı kontrol edilir. Piper, çevrimdışı sesli geri bildirim için kullanılır.

## Güvenlik sınırları

Bu çalışma bir prototiptir. Challenge-response adımı gelişmiş canlılık tespiti değildir. Gerçek ürün için güvenli veri saklama, erişim günlüğü, fail-safe kilit sürücüsü, fiziksel izolasyon ve daha güçlü anti-spoofing yöntemleri eklenmelidir.
