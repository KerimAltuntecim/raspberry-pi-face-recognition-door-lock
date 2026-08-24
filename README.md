# Raspberry Pi Face Recognition Door Lock

**English summary:** Documentation-only portfolio of a Raspberry Pi 4 smart door-lock prototype using OpenCV face recognition, PySide6 and GPIO control.

Dokümantasyon odaklı bir Raspberry Pi 4 akıllı kapı kilidi prototipi. Sistem, USB kamera ile yüz algılama ve tanıma yapar; doğrulama sonrasında GPIO üzerinden kilit durumunu temsil eden bir çıkışı kontrol eder.

> Bu depo portföy amacıyla hazırlanmıştır. Özgün proje kaynak kodu, kullanıcı yüz verileri, yüz gömüleri, ses kayıtları ve kişisel bilgiler paylaşılmamıştır.

## Öne çıkan yetenekler

- Raspberry Pi 4 üzerinde Linux tabanlı gerçek zamanlı görüntü işleme
- OpenCV YuNet ile yüz algılama ve yüz noktalarıyla hizalama
- SFace tabanlı yüz özelliklerinin karşılaştırılması
- PySide6 ile kamera, kayıt, doğrulama ve kullanıcı yönetimi arayüzü
- Piper ile çevrimdışı sesli karşılama
- RPi.GPIO ile kilit/LED çıkış kontrolü
- Kayıt sırasında farklı yüz açılarıyla veri toplama
- Doğrulama sonrası basit baş hareketi challenge-response adımı

## Kaynak kod ve kurulum

`face_engine.py` ve `main_gui.py`, projenin temizlenmiş public kaynak kodudur. Model dosyaları, Piper ses modeli, ikonlar ve kullanıcı kayıtları depoya dahil edilmemiştir.

1. Raspberry Pi üzerinde Python 3.10+ ortamı oluşturun.
2. `pip install -r requirements.txt` komutunu çalıştırın ve Raspberry Pi GPIO paketini kurun.
3. YuNet, SFace ve isteğe bağlı Piper model dosyalarını `models/` klasörüne yerleştirin.
4. Gerekirse `.env.example` içindeki yolları ortam değişkeni olarak ayarlayın.
5. `python main_gui.py` ile arayüzü başlatın.

Bu kurulum yönergeleri eğitim/prototip kullanımı içindir. Model dosyalarının lisansları ayrıca kontrol edilmelidir.

## Sistem akışı

```text
USB kamera → yüz algılama → hizalama → yüz özelliği çıkarma
                                      ↓
                            kayıtlı özelliklerle karşılaştırma
                                      ↓
                          challenge-response → GPIO kilit çıkışı
```

## Donanım ve yazılım

| Alan | Kullanım |
|---|---|
| Raspberry Pi 4 | Ana işlemci ve Linux platformu |
| USB kamera | Görüntü alma |
| GPIO çıkışı | Kilit/LED prototip kontrolü |
| Python | Uygulama geliştirme |
| OpenCV + NumPy | Görüntü işleme ve özellik karşılaştırma |
| PySide6 | Masaüstü kullanıcı arayüzü |
| Piper | Çevrimdışı sesli geri bildirim |

## Deneysel sonuçlar

Tezdeki prototip ölçümlerine göre kayıtlı kullanıcı doğrulaması kontrollü ve farklı ortam testlerinde yüksek başarı göstermiştir. Kısmi yüz kapatma durumunda başarı düşmüştür. Doğrulama sırasında yaklaşık 6–7 FPS, boşta yaklaşık 8 FPS ölçülmüştür. Uzun süreli çalışmada Raspberry Pi sıcaklığının izlenmesi gerektiği görülmüştür.

Bu sonuçlar prototip testlerine aittir; üretim seviyesinde güvenlik veya gelişmiş anti-spoofing garantisi olarak değerlendirilmemelidir.

| Senaryo | Gözlem |
|---|---|
| Kayıtlı kullanıcı / aynı ortam | 10/10 doğrulama |
| Kayıtlı kullanıcı / farklı ortam | 10/10 doğrulama |
| Gözlüksüz doğrulama | 9–10/10 aralığı |
| Kısmi yüz kapatma | Ortama göre düşen başarı |
| Bilinmeyen kişi / fotoğraf | Kilit açılmaması beklenir |
| Performans | Boşta yaklaşık 8 FPS; doğrulamada yaklaşık 6–7 FPS |

## Paylaşılan örnekler

Depo kökündeki `camera_capture_example.py`, `camera_frame_example.py`, `gpio_output_example.py`, `qt_timer_example.py` ve `state_flow_example.py` dosyaları, gerçek projede kullanılan genel teknik desenlerin temizlenmiş örnekleridir. Kamera yaşam döngüsü, kare dönüşümü, GPIO çıkışı hazırlama, Qt zamanlayıcısı ve durum akışını gösterir; tek başına tam uygulama değildir ve özgün eşik/depolama ayrıntılarını içermez.

## Gizlilik ve güvenlik

- Yüz fotoğrafları, yüz vektörleri ve ses kayıtları depoya eklenmez.
- Gerçek kullanıcı kayıt klasörleri ve cihaz kimlik bilgileri paylaşılmaz.
- Challenge-response burada yalnızca deneysel bir canlılık kontrolüdür; tek başına güvenli erişim sistemi değildir.
- Gerçek kapı kilidi uygulamasında güvenli muhafaza, erişim günlüğü, hata durumları ve ek anti-spoofing katmanları gerekir.

## Gelecek geliştirmeler

- Daha güçlü canlılık tespiti ve spoofing önleme
- Raspberry Pi için daha iyi soğutma ve uzun süreli yük testi
- Güvenli kullanıcı/veri depolama ve erişim günlüğü
- Fiziksel kilit sürücüsü için fail-safe tasarım ve elektriksel izolasyon
- Kurulum ve bakım adımlarının otomatikleştirilmesi

## Kaynak kullanım notu

Bu depo kaynak kodu ve proje yaklaşımını portföy incelemesi amacıyla paylaşır. Kodun yeniden kullanılması, dağıtılması veya ticari bir ürüne dahil edilmesi için yazardan ayrıca izin alınmalıdır.
