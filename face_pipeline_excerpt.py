"""Güvenli, kısaltılmış anlatım örneği.

Bu dosya özgün projenin çalıştırılabilir kaynak kodu değildir.
Model dosyaları, eşikler ve kullanıcı depolama ayrıntıları bilerek çıkarılmıştır.
"""


def verify_frame(frame, detector, recognizer, registered_features):
    """Bir kamera karesinin doğrulama akışını özetler."""
    faces = detector.detect(frame)
    if not faces:
        return {"status": "no_face"}

    aligned_face = align_using_landmarks(frame, faces[0])
    feature = recognizer.extract(aligned_face)
    match = compare_with_registered(feature, registered_features)

    if not match:
        return {"status": "unknown"}
    return {"status": "challenge_required"}


def align_using_landmarks(frame, detection):
    """Örnek amaçlı arayüz; gerçek hizalama ayrıntıları paylaşılmamıştır."""
    raise NotImplementedError


def compare_with_registered(feature, registered_features):
    """Örnek amaçlı arayüz; gerçek eşik ve veri yapısı paylaşılmamıştır."""
    raise NotImplementedError
