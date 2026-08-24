# Raspberry Pi Face Recognition Door Lock

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

## Paylaşılan örnekler

`examples/` klasöründeki Python dosyaları, gerçek uygulamanın güvenli ve kısaltılmış anlatım örnekleridir. Tek başına çalıştırılabilir tam uygulama değildir ve özgün eşik/depolama ayrıntılarını içermez.

## Gizlilik ve güvenlik

- Yüz fotoğrafları, yüz vektörleri ve ses kayıtları depoya eklenmez.
- Gerçek kullanıcı kayıt klasörleri ve cihaz kimlik bilgileri paylaşılmaz.
- Challenge-response burada yalnızca deneysel bir canlılık kontrolüdür; tek başına güvenli erişim sistemi değildir.
- Gerçek kapı kilidi uygulamasında güvenli muhafaza, erişim günlüğü, hata durumları ve ek anti-spoofing katmanları gerekir.

## Lisans

Dokümantasyon ve örnek kodlar MIT lisansı ile paylaşılmıştır. Özgün bitirme projesi kaynak kodu bu lisans kapsamında yayınlanmamıştır.
