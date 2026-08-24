"""PySide6 QTimer ile periyodik arayüz güncelleme deseni."""

from PySide6.QtCore import QObject, QTimer


class PeriodicFrameUpdater(QObject):
    def __init__(self, update_callback, interval_ms: int = 30):
        super().__init__()
        self.timer = QTimer(self)
        self.timer.timeout.connect(update_callback)
        self.timer.start(interval_ms)

    def stop(self):
        self.timer.stop()
