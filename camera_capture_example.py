"""USB kamera yaşam döngüsünün sade örneği.

Model, kullanıcı verisi ve erişim kararı içermez; yalnızca kamera kaynağının
açılması, kare okunması ve düzgün kapatılmasını gösterir.
"""

import cv2 as cv


def read_camera_frame(camera_index: int = 0):
    camera = cv.VideoCapture(camera_index)
    try:
        if not camera.isOpened():
            raise RuntimeError("Kamera açılamadı")

        ok, frame = camera.read()
        return frame if ok else None
    finally:
        camera.release()
