# Test Sonuçları

Sonuçlar Raspberry Pi 4 üzerinde geliştirilen prototipin tez çalışmasındaki deneylerden özetlenmiştir.

| Test senaryosu | Sonuç |
|---|---:|
| Kayıtlı kullanıcı, aynı ortam | 10/10 |
| Kayıtlı kullanıcı, farklı ortam | 10/10 |
| Kayıtlı kullanıcı, gözlüksüz | 9–10/10 |
| Kısmi yüz kapatma, aynı ortam | 8/10 |
| Kısmi yüz kapatma, farklı ortam | 0/10 |
| Bilinmeyen kişi | Kilit açılmadı |
| Telefon ekranı / fotoğraf denemesi | Kilit açılmadı |

## Performans gözlemleri

- Boşta yaklaşık 8 FPS
- Doğrulama sırasında yaklaşık 6–7,3 FPS
- Kayıt sırasında yaklaşık 5,3–6,5 FPS
- Uzun süreli çalışmada yaklaşık 80–81 °C sıcaklık gözlemi
- Throttling gözlemi: 0x0

## Yorum

Kontrollü koşullarda kayıtlı kullanıcı doğrulaması başarılıdır. Kısmi yüz kapatma, ortam değişimi ve gerçek kullanım koşulları performansı düşürebilir. Bu nedenle ölçümler üretim seviyesi güvenlik veya doğruluk garantisi değildir.
