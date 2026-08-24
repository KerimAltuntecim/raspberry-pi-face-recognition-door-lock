"""GPIO kilit çıkışının güvenli ve kısaltılmış gösterimi."""

LOCK_OUTPUT = 17  # Prototipte kullanılan GPIO hattı


def set_lock_output(gpio, unlocked: bool) -> None:
    """Doğrulama sonucuna göre prototip çıkışını günceller."""
    gpio.output(LOCK_OUTPUT, gpio.HIGH if unlocked else gpio.LOW)


def handle_verification_result(gpio, result: str) -> None:
    """Gerçek uygulamadaki durum makinesinin sadeleştirilmiş örneği."""
    set_lock_output(gpio, unlocked=(result == "verified"))
