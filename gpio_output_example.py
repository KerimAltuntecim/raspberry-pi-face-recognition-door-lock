"""RPi.GPIO ile güvenli bir prototip çıkışının hazırlanması.

Bu örnek gerçek kilit sürücüsü veya erişim yetkilendirme kodu değildir.
"""

import RPi.GPIO as GPIO


OUTPUT_PIN = 17


def initialize_output():
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(OUTPUT_PIN, GPIO.OUT, initial=GPIO.LOW)


def set_output(enabled: bool):
    GPIO.output(OUTPUT_PIN, GPIO.HIGH if enabled else GPIO.LOW)


def release_output():
    GPIO.output(OUTPUT_PIN, GPIO.LOW)
    GPIO.cleanup(OUTPUT_PIN)
