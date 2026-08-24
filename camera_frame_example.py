"""Kameradan gelen OpenCV karesini Qt arayüzünde göstermenin sade örneği.

Bu, projedeki genel görüntü aktarım deseninin temizlenmiş bir örneğidir;
yüz tanıma modeli veya özgün doğrulama kodu içermez.
"""

import cv2 as cv
from PySide6.QtGui import QImage, QPixmap


def frame_to_pixmap(frame):
    """BGR OpenCV karesini QLabel/Pixmap kullanımına hazırlar."""
    if frame is None or frame.size == 0:
        return None

    rgb_frame = cv.cvtColor(frame, cv.COLOR_BGR2RGB)
    height, width, channels = rgb_frame.shape
    stride = channels * width
    image = QImage(rgb_frame.data, width, height, stride, QImage.Format_RGB888)
    return QPixmap.fromImage(image.copy())
