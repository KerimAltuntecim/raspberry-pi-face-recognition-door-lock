import sys
import cv2 as cv

from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QImage, QPixmap, QKeyEvent, QPainter, QPen, QColor, QFont, QIcon
from PySide6.QtWidgets import (
     QApplication, QWidget, QLabel, QPushButton, QVBoxLayout,
     QHBoxLayout, QFrame, QTextEdit, QListWidget, QStackedWidget,
     QLineEdit
)

from face_engine import FaceAccessEngine


class CircularProgressWidget(QWidget):
    def __init__(self, title="ON", color="#4ade80", parent=None):
        super().__init__(parent)
        self.title = title
        self.color = QColor(color)
        self.percent = 0

        self.setMinimumSize(150, 150)
        self.setMaximumSize(170, 170)

    def set_percent(self, value):
        self.percent = max(0, min(100, int(value)))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        side = min(w, h)

        cx = w / 2
        cy = h / 2

        circle_size = side - 24
        x = (w - circle_size) / 2
        y = (h - circle_size) / 2

        # Arka halka
        bg_pen = QPen(QColor("#2b3348"), 10)
        painter.setPen(bg_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(int(x), int(y), int(circle_size), int(circle_size))

        # İlerleme halkası
        progress_pen = QPen(self.color, 10)
        painter.setPen(progress_pen)

        start_angle = 90 * 16
        span_angle = int(-(self.percent / 100) * 360 * 16)
        painter.drawArc(int(x), int(y), int(circle_size), int(circle_size), start_angle, span_angle)

        # Başlık
        title_font = QFont("Arial", 13, QFont.Bold)
        painter.setFont(title_font)
        painter.setPen(QColor("#e5e7eb"))
        painter.drawText(0, int(cy - 25), w, 20, Qt.AlignCenter, self.title)

        # Yüzde
        percent_font = QFont("Arial", 24, QFont.Bold)
        painter.setFont(percent_font)
        painter.setPen(self.color)
        painter.drawText(0, int(cy - 2), w, 36, Qt.AlignCenter, f"{self.percent}%")


class DebugWindow(QWidget):
    def __init__(self, close_callback=None):
        super().__init__()
        self.close_callback = close_callback
        self.setWindowTitle("Debug Menusu")
        self.resize(420, 620)

    def closeEvent(self, event):
        if self.close_callback is not None:
            self.close_callback()
        super().closeEvent(event)


class FaceAccessWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.engine = FaceAccessEngine()

        # Sağ panel ve kamera çerçevesi için durum modu:
        # idle    -> tarama bekleniyor
        # staff   -> personel / normal kayıt onaylandı
        # suspect -> kayıtlı şüpheli şahıs eşleşmesi
        self.security_ui_mode = "idle"

        self.setWindowTitle("Face Access Control System")
        self.resize(1450, 860)
        self.setFocusPolicy(Qt.StrongFocus)

        self.build_ui()
        self.apply_styles()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(30)

        self.update_status("Sistem hazir")
        self.refresh_users()
        self.update_enroll_form_state()
        self.update_enroll_progress_widgets()
        self.update_scanned_person_panel()
        self.update_liveness_banner()

    # =====================================================
    # ANA ARAYUZ
    # =====================================================
    def build_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(14)

        # =================================================
        # SOL PANEL
        # =================================================
        self.left_panel = QFrame()
        self.left_panel.setObjectName("leftPanel")
        self.left_panel.setFixedWidth(270)

        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(18, 18, 18, 18)
        left_layout.setSpacing(14)

        self.title_label = QLabel("FACE ACCESS\nCONTROL")
        self.title_label.setObjectName("titleLabel")
        self.title_label.setAlignment(Qt.AlignCenter)

        self.btn_home = QPushButton()
        self.btn_home.setIcon(QIcon("icons/home.svg"))
        self.btn_home.setObjectName("iconCircleButton")
        self.btn_home.setIconSize(QSize(70, 70))
        self.btn_home.setToolTip("Ana Menu")

        self.btn_enroll = QPushButton("1  Yeni Kayit")
        self.btn_verify = QPushButton("2  Giriş Yap")
        self.btn_debug = QPushButton("3  Debug")
        self.btn_users = QPushButton("4  Kullanicilar")

        self.btn_exit = QPushButton()
        self.btn_exit.setIcon(QIcon("icons/power.svg"))
        self.btn_exit.setObjectName("iconCircleButton")
        self.btn_exit.setIconSize(QSize(70, 70))
        self.btn_exit.setToolTip("Cikis")

        self.btn_home.clicked.connect(self.go_menu)
        self.btn_enroll.clicked.connect(self.go_enroll)
        self.btn_verify.clicked.connect(self.go_verify)
        self.btn_debug.clicked.connect(self.go_debug)
        self.btn_users.clicked.connect(self.go_users)
        self.btn_exit.clicked.connect(self.close)

        left_layout.addWidget(self.title_label)
        left_layout.addSpacing(20)
        left_layout.addWidget(self.btn_enroll)
        left_layout.addWidget(self.btn_verify)
        left_layout.addWidget(self.btn_debug)
        left_layout.addWidget(self.btn_users)
        left_layout.addStretch()

        bottom_icon_row = QHBoxLayout()
        bottom_icon_row.setSpacing(12)
        bottom_icon_row.addStretch()
        bottom_icon_row.addWidget(self.btn_home)
        bottom_icon_row.addWidget(self.btn_exit)
        bottom_icon_row.addStretch()
        left_layout.addLayout(bottom_icon_row)

        # =================================================
        # ORTA PANEL
        # =================================================
        self.center_panel = QFrame()
        self.center_panel.setObjectName("centerPanel")

        center_layout = QVBoxLayout(self.center_panel)
        center_layout.setContentsMargins(18, 18, 18, 18)
        center_layout.setSpacing(12)

        self.header_label = QLabel("Ana Ekran")
        self.header_label.setObjectName("headerLabel")

        self.pages = QStackedWidget()

        # ---------------- MAIN PAGE ----------------
        self.page_main = QWidget()
        main_page_layout = QVBoxLayout(self.page_main)
        main_page_layout.setContentsMargins(0, 0, 0, 0)
        main_page_layout.setSpacing(10)

        # Şüpheli eşleşmesinde üstte büyük kırmızı uyarı olarak görünür.
        self.alert_banner = QLabel("DİKKAT! KAYITLI ŞÜPHELİ ŞAHIS EŞLEŞMESİ")
        self.alert_banner.setObjectName("alertBanner")
        self.alert_banner.setAlignment(Qt.AlignCenter)
        self.alert_banner.hide()
        # Canlılık testi sırasında sağa/sola bakma komutunu büyük göstermek için kullanılır.
        self.liveness_banner = QLabel("")
        self.liveness_banner.setObjectName("livenessBanner")
        self.liveness_banner.setAlignment(Qt.AlignCenter)
        self.liveness_banner.setWordWrap(True)
        self.liveness_banner.setMinimumHeight(120)
        self.liveness_banner.hide()

        self.camera_label_main = QLabel("KAMERA")
        self.camera_label_main.setObjectName("cameraLabel")
        self.camera_label_main.setAlignment(Qt.AlignCenter)
        self.camera_label_main.setMinimumSize(780, 560)

        self.status_label_main = QLabel("Durum: Bekleniyor")
        self.status_label_main.setObjectName("statusLabel")

        main_page_layout.addWidget(self.alert_banner)
        main_page_layout.addWidget(self.liveness_banner)
        main_page_layout.addWidget(self.camera_label_main, 1)
        main_page_layout.addWidget(self.status_label_main)

        # ---------------- ENROLL PAGE ----------------
        self.page_enroll = QWidget()

        enroll_root_layout = QHBoxLayout(self.page_enroll)
        enroll_root_layout.setContentsMargins(0, 0, 0, 0)
        enroll_root_layout.setSpacing(14)

        # SOL: Kamera kartı
        self.enroll_camera_card = QFrame()
        self.enroll_camera_card.setObjectName("cardFrame")
        self.enroll_camera_card.setProperty("state", "normal")

        enroll_camera_layout = QVBoxLayout(self.enroll_camera_card)
        enroll_camera_layout.setContentsMargins(14, 14, 14, 14)
        enroll_camera_layout.setSpacing(10)

        self.camera_label_enroll = QLabel("ENROLL CAMERA")
        self.camera_label_enroll.setObjectName("cameraLabel")
        self.camera_label_enroll.setAlignment(Qt.AlignCenter)
        self.camera_label_enroll.setMinimumSize(700, 520)

        # Yönlendirme kartı
        self.direction_card = QFrame()
        self.direction_card.setObjectName("directionCard")
        self.direction_card.setProperty("state", "normal")

        direction_layout = QVBoxLayout(self.direction_card)
        direction_layout.setContentsMargins(12, 10, 12, 10)
        direction_layout.setSpacing(4)

        self.direction_title = QLabel("YONLENDIRME")
        self.direction_title.setObjectName("directionTitle")
        self.direction_title.setAlignment(Qt.AlignCenter)

        self.enroll_info = QLabel("Kayit icin yuzunuzu cerceveye getirin")
        self.enroll_info.setObjectName("directionValue")
        self.enroll_info.setAlignment(Qt.AlignCenter)

        direction_layout.addWidget(self.direction_title)
        direction_layout.addWidget(self.enroll_info)

        # Dairesel kayıt ilerleme widgetları
        self.progress_row = QHBoxLayout()
        self.progress_row.setSpacing(18)

        self.progress_front = CircularProgressWidget("ÖN", "#60a5fa")
        self.progress_right = CircularProgressWidget("SAĞ", "#4ade80")
        self.progress_left = CircularProgressWidget("SOL", "#f472b6")

        self.progress_row.addStretch()
        self.progress_row.addWidget(self.progress_front)
        self.progress_row.addWidget(self.progress_right)
        self.progress_row.addWidget(self.progress_left)
        self.progress_row.addStretch()

        enroll_camera_layout.addWidget(self.camera_label_enroll, 1)
        enroll_camera_layout.addWidget(self.direction_card)
        enroll_camera_layout.addLayout(self.progress_row)

        # SAG: Form kartı
        self.enroll_form_card = QFrame()
        self.enroll_form_card.setObjectName("cardFrame")
        self.enroll_form_card.setFixedWidth(385)

        enroll_form_layout = QVBoxLayout(self.enroll_form_card)
        enroll_form_layout.setContentsMargins(18, 18, 18, 18)
        enroll_form_layout.setSpacing(10)

        self.enroll_panel_title = QLabel("Kayit Adimlari")
        self.enroll_panel_title.setObjectName("subHeaderLabel")

        self.enroll_step_label = QLabel("Asama: Yuz ornekleri")
        self.enroll_step_label.setObjectName("stepLabel")

        self.enroll_form_hint = QLabel(
            "2 ön, 2 sağ, 2 sol örnek alınır. "
            "Sonrasında şahıs ismi, cinsiyet, kayıt türü ve şahıs bilgisi girilir."
        )
        self.enroll_form_hint.setObjectName("formHintLabel")
        self.enroll_form_hint.setWordWrap(True)

        # ---------------- ISIM BOLUMU ----------------
        self.name_section = QFrame()
        self.name_section.setObjectName("formSectionCard")
        name_section_layout = QVBoxLayout(self.name_section)
        name_section_layout.setContentsMargins(14, 14, 14, 14)
        name_section_layout.setSpacing(8)

        self.name_title = QLabel("Şahıs İsmi / Kayıt Adı")
        self.name_title.setObjectName("fieldTitle")

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Şahıs ismini girin")

        self.enroll_next_name_btn = QPushButton("Şahıs İsmini Onayla")
        self.enroll_next_name_btn.setObjectName("primaryActionButton")

        name_section_layout.addWidget(self.name_title)
        name_section_layout.addWidget(self.name_input)
        name_section_layout.addWidget(self.enroll_next_name_btn)

        # ---------------- CINSIYET BOLUMU ----------------
        self.gender_section = QFrame()
        self.gender_section.setObjectName("formSectionCard")
        gender_section_layout = QVBoxLayout(self.gender_section)
        gender_section_layout.setContentsMargins(14, 14, 14, 14)
        gender_section_layout.setSpacing(8)

        self.gender_title = QLabel("Cinsiyet")
        self.gender_title.setObjectName("fieldTitle")

        self.gender_male_btn = QPushButton("Erkek")
        self.gender_female_btn = QPushButton("Kadin")
        self.gender_male_btn.setCheckable(True)
        self.gender_female_btn.setCheckable(True)

        gender_btn_layout = QHBoxLayout()
        gender_btn_layout.setSpacing(10)
        gender_btn_layout.addWidget(self.gender_male_btn)
        gender_btn_layout.addWidget(self.gender_female_btn)

        gender_section_layout.addWidget(self.gender_title)
        gender_section_layout.addLayout(gender_btn_layout)

        # ---------------- KAYIT TURU BOLUMU ----------------
        self.person_type_section = QFrame()
        self.person_type_section.setObjectName("formSectionCard")
        person_type_layout = QVBoxLayout(self.person_type_section)
        person_type_layout.setContentsMargins(14, 14, 14, 14)
        person_type_layout.setSpacing(8)

        self.person_type_title = QLabel("Kayit Turu")
        self.person_type_title.setObjectName("fieldTitle")

        self.person_staff_btn = QPushButton("Personel")
        self.person_suspect_btn = QPushButton("Şüpheli")
        self.person_staff_btn.setCheckable(True)
        self.person_suspect_btn.setCheckable(True)

        person_type_btn_layout = QHBoxLayout()
        person_type_btn_layout.setSpacing(10)
        person_type_btn_layout.addWidget(self.person_staff_btn)
        person_type_btn_layout.addWidget(self.person_suspect_btn)

        person_type_layout.addWidget(self.person_type_title)
        person_type_layout.addLayout(person_type_btn_layout)

        # ---------------- SAHIS BILGISI / ACIKLAMA BOLUMU ----------------
        self.record_note_section = QFrame()
        self.record_note_section.setObjectName("formSectionCard")
        record_note_layout = QVBoxLayout(self.record_note_section)
        record_note_layout.setContentsMargins(14, 14, 14, 14)
        record_note_layout.setSpacing(8)

        self.record_note_title = QLabel("Şahıs Bilgisi / Kayıt Açıklaması")
        self.record_note_title.setObjectName("fieldTitle")

        self.record_note_input = QTextEdit()
        self.record_note_input.setPlaceholderText(
            "Personel için görev/kurum bilgisi; şüpheli için olay, risk veya kontrol notu girin."
        )
        self.record_note_input.setFixedHeight(115)

        self.record_note_submit_btn = QPushButton("Kaydi Tamamla")
        self.record_note_submit_btn.setObjectName("primaryActionButton")

        record_note_layout.addWidget(self.record_note_title)
        record_note_layout.addWidget(self.record_note_input)
        record_note_layout.addWidget(self.record_note_submit_btn)

        self.enroll_warning_label = QLabel("")
        self.enroll_warning_label.setObjectName("warningBox")
        self.enroll_warning_label.setWordWrap(True)

        self.enroll_next_name_btn.clicked.connect(self.handle_name_submit)
        self.gender_male_btn.clicked.connect(lambda: self.handle_gender_submit("erkek"))
        self.gender_female_btn.clicked.connect(lambda: self.handle_gender_submit("kadin"))
        self.person_staff_btn.clicked.connect(lambda: self.handle_person_type_submit("personel"))
        self.person_suspect_btn.clicked.connect(lambda: self.handle_person_type_submit("supheli"))
        self.record_note_submit_btn.clicked.connect(self.handle_record_note_submit)

        enroll_form_layout.addWidget(self.enroll_panel_title)
        enroll_form_layout.addWidget(self.enroll_step_label)
        enroll_form_layout.addWidget(self.enroll_form_hint)
        enroll_form_layout.addSpacing(4)
        enroll_form_layout.addWidget(self.name_section)
        enroll_form_layout.addWidget(self.gender_section)
        enroll_form_layout.addWidget(self.person_type_section)
        enroll_form_layout.addWidget(self.record_note_section)
        enroll_form_layout.addSpacing(8)
        enroll_form_layout.addWidget(self.enroll_warning_label)
        enroll_form_layout.addStretch()

        enroll_root_layout.addWidget(self.enroll_camera_card, 1)
        enroll_root_layout.addWidget(self.enroll_form_card)

        # ---------------- USERS PAGE ----------------
        self.page_users = QWidget()
        users_layout = QVBoxLayout(self.page_users)
        users_layout.setContentsMargins(0, 0, 0, 0)
        users_layout.setSpacing(10)

        self.users_title = QLabel("Kayitli Kullanicilar")
        self.users_title.setObjectName("subHeaderLabel")

        self.users_list = QListWidget()
        self.users_list.itemClicked.connect(self.handle_user_selected)

        # Kullanıcı seçildiğinde users/<kullanıcı>/images/front_*.png içinden
        # bir ön yüz fotoğrafı 180x180 alanda gösterilir.
        self.user_photo_label = QLabel("Ön fotoğraf seçilmedi")
        self.user_photo_label.setObjectName("userPhotoLabel")
        self.user_photo_label.setAlignment(Qt.AlignCenter)
        self.user_photo_label.setFixedSize(180, 180)

        self.user_detail_title = QLabel("Kullanici Detayi")
        self.user_detail_title.setObjectName("subHeaderLabel")

        self.user_detail_box = QTextEdit()
        self.user_detail_box.setReadOnly(True)
        self.user_detail_box.setPlaceholderText("Listeden bir kullanici secin")

        self.users_hint = QLabel("Kullanıcıya tıklayınca detayları burada görünür.")
        self.users_hint.setObjectName("statusLabel")

        users_layout.addWidget(self.users_title)
        users_layout.addWidget(self.users_list, 1)

        photo_row = QHBoxLayout()
        photo_row.addStretch()
        photo_row.addWidget(self.user_photo_label)
        photo_row.addStretch()
        users_layout.addLayout(photo_row)

        users_layout.addWidget(self.user_detail_title)
        users_layout.addWidget(self.user_detail_box, 1)
        users_layout.addWidget(self.users_hint)

        # ---------------- DEBUG WINDOW ----------------
        # Debug artık stacked page içinde değil, ayrı pencere olarak açılır.
        # Böylece test sırasında ana ekran açık kalırken debug değerleri yandan izlenebilir.
        self.build_debug_window()

        self.pages.addWidget(self.page_main)
        self.pages.addWidget(self.page_enroll)
        self.pages.addWidget(self.page_users)

        center_layout.addWidget(self.header_label)
        center_layout.addWidget(self.pages)

        # =================================================
        # SAG PANEL
        # =================================================
        self.right_panel = QFrame()
        self.right_panel.setObjectName("rightPanel")
        self.right_panel.setFixedWidth(340)

        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(18, 18, 18, 18)
        right_layout.setSpacing(12)

        self.info_title = QLabel("Taranan Kişi Bilgileri")
        self.info_title.setObjectName("infoTitle")

        self.security_status_label = QLabel("TARAMA BEKLENİYOR")
        self.security_status_label.setObjectName("securityStatusLabel")
        self.security_status_label.setAlignment(Qt.AlignCenter)
        self.security_status_label.setWordWrap(True)
        self.security_status_label.setMinimumHeight(64)

        self.lbl_user = QLabel("Kullanici: -")
        self.lbl_sim = QLabel("SIM: -")
        self.lbl_type = QLabel("Kayıt Türü: -")
        self.lbl_pose = QLabel("Pose: -")
        self.lbl_liveness = QLabel("Canlılık: -")
        self.lbl_lock = QLabel("Erişim: Beklemede")
        self.lbl_fps = QLabel("FPS: -")

        # Eski log paneli artık taranan kişinin bilgilerini gösteren alan oldu.
        # İsim olarak log_box tutuldu ki eski kod mantığı bozulmasın.
        self.log_box = QTextEdit()
        self.log_box.setObjectName("scannedInfoBox")
        self.log_box.setReadOnly(True)
        self.log_box.setPlaceholderText("Taranan kisi bilgileri burada gorunecek")

        right_layout.addWidget(self.info_title)
        right_layout.addWidget(self.security_status_label)
        right_layout.addWidget(self.lbl_user)
        right_layout.addWidget(self.lbl_sim)
        right_layout.addWidget(self.lbl_type)
        right_layout.addWidget(self.lbl_pose)
        right_layout.addWidget(self.lbl_liveness)
        right_layout.addWidget(self.lbl_lock)
        right_layout.addWidget(self.lbl_fps)
        right_layout.addSpacing(10)
        right_layout.addWidget(QLabel("Detay"))
        right_layout.addWidget(self.log_box, 1)

        main_layout.addWidget(self.left_panel)
        main_layout.addWidget(self.center_panel, 1)
        main_layout.addWidget(self.right_panel)

    # =====================================================
    # KARE ALANI
    # =====================================================
    def draw_enroll_guide_on_frame(self, frame):
        if self.engine.app_state != self.engine.APP_ENROLL_ALIGN:
            return frame

        h, w = frame.shape[:2]
        x1, y1, x2, y2 = self.engine.get_guide_rect(w, h)

        guide_ok = self.engine.last_face_aligned_ok
        color = (0, 255, 0) if guide_ok else (0, 0, 255)

        length = 30
        thickness = 3

        cv.line(frame, (x1, y1), (x1 + length, y1), color, thickness)
        cv.line(frame, (x1, y1), (x1, y1 + length), color, thickness)

        cv.line(frame, (x2, y1), (x2 - length, y1), color, thickness)
        cv.line(frame, (x2, y1), (x2, y1 + length), color, thickness)

        cv.line(frame, (x1, y2), (x1 + length, y2), color, thickness)
        cv.line(frame, (x1, y2), (x1, y2 - length), color, thickness)

        cv.line(frame, (x2, y2), (x2 - length, y2), color, thickness)
        cv.line(frame, (x2, y2), (x2, y2 - length), color, thickness)

        return frame

    # =====================================================
    # ENROLL PROGRESS WIDGET
    # =====================================================
    def update_enroll_progress_widgets(self):
        target = max(1, self.engine.ENROLL_TARGET_COUNT)

        front_count = self.engine.enroll_counts.get(self.engine.POSE_FRONT, 0)
        right_count = self.engine.enroll_counts.get(self.engine.POSE_RIGHT, 0)
        left_count = self.engine.enroll_counts.get(self.engine.POSE_LEFT, 0)

        front_percent = int((front_count / target) * 100)
        right_percent = int((right_count / target) * 100)
        left_percent = int((left_count / target) * 100)

        self.progress_front.set_percent(front_percent)
        self.progress_right.set_percent(right_percent)
        self.progress_left.set_percent(left_percent)

    # =====================================================
    # FORM GORSEL DURUMU
    # =====================================================
    def set_form_section_style(self, section_widget, active=False):
        if active:
            section_widget.setStyleSheet("""
                QFrame {
                    background-color: #111f34;
                    border: 1px solid #60a5fa;
                    border-radius: 14px;
                }
            """)
        else:
            section_widget.setStyleSheet("""
                QFrame {
                    background-color: #0f1726;
                    border: 1px solid #2b3750;
                    border-radius: 14px;
                }
            """)

    def set_action_button_style(self, button, state="inactive"):
        if state == "active":
            button.setStyleSheet("""
                QPushButton {
                    background-color: #16324d;
                    border: 1px solid #3b82f6;
                    color: #eff6ff;
                    border-radius: 14px;
                    padding: 14px;
                    font-size: 15px;
                    font-weight: bold;
                    min-height: 44px;
                    text-align: center;
                }
                QPushButton:hover {
                    background-color: #1f4466;
                }
            """)
        elif state == "completed":
            button.setStyleSheet("""
                QPushButton {
                    background-color: #183553;
                    border: 1px solid #60a5fa;
                    color: #eff6ff;
                    border-radius: 14px;
                    padding: 14px;
                    font-size: 15px;
                    font-weight: bold;
                    min-height: 44px;
                    text-align: center;
                }
                QPushButton:hover {
                    background-color: #21476d;
                }
            """)
        else:
            button.setStyleSheet("""
                QPushButton {
                    background-color: #1e293b;
                    border: 1px solid #334155;
                    color: #94a3b8;
                    border-radius: 14px;
                    padding: 14px;
                    font-size: 15px;
                    font-weight: bold;
                    min-height: 44px;
                    text-align: center;
                }
                QPushButton:hover {
                    background-color: #273449;
                }
            """)

    def make_two_choice_style(self, checked=False, enabled=True, danger=False):
        if not enabled:
            if checked:
                border = "#60a5fa" if not danger else "#f87171"
                bg = "#17324a" if not danger else "#3b1111"
                color = "#e0f2fe" if not danger else "#fee2e2"
            else:
                border = "#334155"
                bg = "#1e293b"
                color = "#64748b"
        else:
            if checked:
                border = "#60a5fa" if not danger else "#ef4444"
                bg = "#17324a" if not danger else "#4a1414"
                color = "#e0f2fe" if not danger else "#fee2e2"
            else:
                border = "#334155"
                bg = "#1e293b"
                color = "white"

        return f"""
            QPushButton {{
                background-color: {bg};
                border: 1px solid {border};
                color: {color};
                border-radius: 12px;
                padding: 12px;
                font-size: 14px;
                font-weight: bold;
                min-height: 42px;
            }}
            QPushButton:hover {{
                background-color: {'#1f4466' if not danger else '#5b1717'};
                border: 1px solid {'#60a5fa' if not danger else '#f87171'};
            }}
        """

    def update_gender_button_styles(self):
        enabled = self.gender_male_btn.isEnabled()
        self.gender_male_btn.setStyleSheet(
            self.make_two_choice_style(self.gender_male_btn.isChecked(), enabled, danger=False)
        )
        self.gender_female_btn.setStyleSheet(
            self.make_two_choice_style(self.gender_female_btn.isChecked(), enabled, danger=False)
        )

    def update_person_type_button_styles(self):
        enabled = self.person_staff_btn.isEnabled()
        self.person_staff_btn.setStyleSheet(
            self.make_two_choice_style(self.person_staff_btn.isChecked(), enabled, danger=False)
        )
        self.person_suspect_btn.setStyleSheet(
            self.make_two_choice_style(self.person_suspect_btn.isChecked(), enabled, danger=True)
        )

    def set_card_active(self, widget, active):
        widget.setProperty("state", "active" if active else "normal")
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()

    # =====================================================
    # STIL
    # =====================================================
    def apply_styles(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #0f172a;
                color: #e5e7eb;
                font-size: 15px;
            }

            QFrame#leftPanel, QFrame#centerPanel, QFrame#rightPanel {
                background-color: #111827;
                border: 1px solid #1f2937;
                border-radius: 18px;
            }

            QLabel#titleLabel {
                font-size: 24px;
                font-weight: bold;
                color: #f8fafc;
                padding: 12px;
            }

            QLabel#headerLabel {
                font-size: 22px;
                font-weight: bold;
                color: #f8fafc;
                padding: 4px;
            }

            QLabel#subHeaderLabel {
                font-size: 18px;
                font-weight: bold;
                color: #f8fafc;
                padding: 4px;
            }

            QLabel#cameraLabel {
                background-color: #020617;
                border: 2px solid #334155;
                border-radius: 16px;
                font-size: 28px;
                font-weight: bold;
                color: #38bdf8;
            }

            QLabel#alertBanner {
                background-color: #7f1d1d;
                border: 2px solid #ef4444;
                border-radius: 14px;
                color: #ffffff;
                font-size: 24px;
                font-weight: bold;
                padding: 14px;
            }

            QLabel#statusLabel {
                font-size: 16px;
                color: #93c5fd;
                padding: 8px;
            }

            QLabel#userPhotoLabel {
                background-color: #020617;
                border: 1px solid #334155;
                border-radius: 18px;
                color: #64748b;
                font-size: 14px;
                font-weight: bold;
            }

            QLabel#infoTitle {
                font-size: 20px;
                font-weight: bold;
                color: #f8fafc;
                padding-bottom: 8px;
            }

            QLabel#securityStatusLabel {
                background-color: #172033;
                border: 1px solid #334155;
                border-radius: 12px;
                color: #cbd5e1;
                padding: 12px;
                font-size: 16px;
                font-weight: bold;
            }

            QLabel#formHintLabel {
                color: #94a3b8;
                font-size: 13px;
                padding-left: 2px;
                padding-right: 2px;
            }

            QPushButton {
                background-color: #1e293b;
                color: white;
                border: 1px solid #334155;
                border-radius: 14px;
                padding: 14px;
                text-align: left;
                font-size: 15px;
                font-weight: bold;
            }

            QPushButton:hover {
                background-color: #334155;
            }

            QPushButton:pressed {
                background-color: #475569;
            }

            QPushButton#iconCircleButton {
                background-color: #1e293b;
                color: white;
                border: 1px solid #334155;
                border-radius: 22px;
                min-width: 44px;
                max-width: 44px;
                min-height: 44px;
                max-height: 44px;
                padding: 0px;
                font-size: 20px;
                font-weight: bold;
                text-align: center;
            }

            QPushButton#iconCircleButton:hover {
                background-color: #334155;
            }

            QPushButton#iconCircleButton:pressed {
                background-color: #475569;
            }

            QLineEdit, QListWidget, QTextEdit {
                background-color: #020617;
                border: 1px solid #334155;
                border-radius: 12px;
                padding: 10px;
                color: #e5e7eb;
            }

            QTextEdit#scannedInfoBox {
                background-color: #020617;
                border: 1px solid #334155;
                border-radius: 12px;
                padding: 12px;
                color: #e5e7eb;
                font-size: 14px;
            }

            QFrame#cardFrame {
                background-color: #0b1220;
                border: 1px solid #253046;
                border-radius: 18px;
            }

            QFrame#cardFrame[state="active"] {
                border: 2px solid #3b82f6;
            }

            QFrame#directionCard {
                background-color: #0b1220;
                border: 1px solid #253046;
                border-radius: 14px;
            }

            QFrame#directionCard[state="active"] {
                border: 2px solid #3b82f6;
            }

            QLabel#directionTitle {
                color: #93c5fd;
                font-size: 12px;
                font-weight: bold;
                letter-spacing: 1px;
                qproperty-alignment: AlignCenter;
            }

            QLabel#directionValue {
                color: #e5e7eb;
                font-size: 16px;
                font-weight: bold;
                padding: 2px 0 4px 0;
            }

            QLabel#stepLabel {
                background-color: #172033;
                border: 1px solid #334155;
                border-radius: 12px;
                padding: 10px;
                color: #cbd5e1;
                font-size: 15px;
                font-weight: bold;
            }

            QLabel#fieldTitle {
                color: #e2e8f0;
                font-size: 14px;
                font-weight: bold;
                padding-top: 2px;
            }
            
            QLabel#livenessBanner {
                background-color: #1e293b;
                border: 2px solid #334155;
                border-radius: 18px;
                color: #e5e7eb;
                font-size: 34px;
                font-weight: bold;
                padding: 18px;
            }

            QLabel#warningBox {
                background-color: #2a1313;
                border: 1px solid #7f1d1d;
                border-radius: 12px;
                padding: 12px;
                color: #fca5a5;
                font-size: 14px;
                min-height: 48px;
            }

            QLineEdit {
                min-height: 42px;
            }

            QPushButton {
                min-height: 44px;
            }
        """)

        self.set_form_section_style(self.name_section, active=False)
        self.set_form_section_style(self.gender_section, active=False)
        self.set_form_section_style(self.person_type_section, active=False)
        self.set_form_section_style(self.record_note_section, active=False)
        self.update_gender_button_styles()
        self.update_person_type_button_styles()

    # =====================================================
    # SAG PANEL / GUVENLIK GORUNUMU
    # =====================================================
    def set_security_ui_mode(self, mode):
        """
        Sağ panel ve kamera alanının güvenlik durumuna göre renklerini değiştirir.

        mode:
        - idle    : tarama bekleniyor
        - staff   : personel / normal kayıt onaylandı
        - suspect : kayıtlı şüpheli şahıs eşleşmesi
        """
        if self.security_ui_mode == mode:
            return

        self.security_ui_mode = mode

        if mode == "suspect":
            self.alert_banner.show()
            self.right_panel.setStyleSheet("""
                QFrame#rightPanel {
                    background-color: #1f0b0b;
                    border: 2px solid #ef4444;
                    border-radius: 18px;
                }
            """)
            self.camera_label_main.setStyleSheet("""
                QLabel#cameraLabel {
                    background-color: #020617;
                    border: 4px solid #ef4444;
                    border-radius: 16px;
                    font-size: 28px;
                    font-weight: bold;
                    color: #fecaca;
                }
            """)
            self.security_status_label.setStyleSheet("""
                QLabel#securityStatusLabel {
                    background-color: #7f1d1d;
                    border: 2px solid #ef4444;
                    border-radius: 12px;
                    color: #ffffff;
                    padding: 12px;
                    font-size: 16px;
                    font-weight: bold;
                }
            """)
            self.log_box.setStyleSheet("""
                QTextEdit#scannedInfoBox {
                    background-color: #1f0b0b;
                    border: 1px solid #ef4444;
                    border-radius: 12px;
                    padding: 12px;
                    color: #fee2e2;
                    font-size: 14px;
                }
            """)

        elif mode == "staff":
            self.alert_banner.hide()
            self.right_panel.setStyleSheet("""
                QFrame#rightPanel {
                    background-color: #071c14;
                    border: 2px solid #22c55e;
                    border-radius: 18px;
                }
            """)
            self.camera_label_main.setStyleSheet("""
                QLabel#cameraLabel {
                    background-color: #020617;
                    border: 4px solid #22c55e;
                    border-radius: 16px;
                    font-size: 28px;
                    font-weight: bold;
                    color: #bbf7d0;
                }
            """)
            self.security_status_label.setStyleSheet("""
                QLabel#securityStatusLabel {
                    background-color: #064e3b;
                    border: 2px solid #22c55e;
                    border-radius: 12px;
                    color: #dcfce7;
                    padding: 12px;
                    font-size: 16px;
                    font-weight: bold;
                }
            """)
            self.log_box.setStyleSheet("""
                QTextEdit#scannedInfoBox {
                    background-color: #052e20;
                    border: 1px solid #22c55e;
                    border-radius: 12px;
                    padding: 12px;
                    color: #dcfce7;
                    font-size: 14px;
                }
            """)

        else:
            self.alert_banner.hide()
            self.right_panel.setStyleSheet("")
            self.camera_label_main.setStyleSheet("")
            self.security_status_label.setStyleSheet("")
            self.log_box.setStyleSheet("")

    def make_scanned_person_text(self, info):
        if info is None:
            return "Taranan kişi bilgisi bekleniyor.\n\nKişi tanındığında detaylar burada görünecek."

        username = info.get("username", "-")
        person_type_label = info.get("person_type_label", "-")
        gender = info.get("gender", "-") or "-"
        title = info.get("title", "-") or "-"
        role = info.get("role", "-") or "-"
        record_note = info.get("record_note", "-") or "-"
        welcome_text = info.get("welcome_text", "-") or "-"

        sim_text = "-"
        if self.engine.matched_user_score is not None:
            sim_text = f"{self.engine.matched_user_score:.4f}"

        return (
            f"Ad / Kayıt: {username}\n"
            f"Kayıt Türü: {person_type_label}\n"
            f"Rol: {role}\n"
            f"Cinsiyet: {gender}\n"
            f"Hitap: {title}\n"
            f"Benzerlik (SIM): {sim_text}\n\n"
            f"Açıklama / Şahıs Bilgisi:\n{record_note}\n\n"
            f"Sesli Karşılama:\n{welcome_text}\n"
        )

    def update_scanned_person_panel(self):
        """
        Sağ panelde taranan kişi bilgisini gösterir.

        Önemli:
        - Kişi sadece tanındığında renk değiştirmiyoruz.
        - Canlılık testi bitmeden yeşil/kırmızı moda geçmiyoruz.
        - Personel için yeşil mod sadece APP_UNLOCKED durumunda.
        - Şüpheli için kırmızı mod sadece APP_ALERT durumunda.
        """

        info = self.engine.matched_user_info
        active_alert = bool(getattr(self.engine, "alert_active", False))
        state = self.engine.app_state
        if state == self.engine.APP_LIVENESS_FAILED:
            self.security_status_label.setText("CANLILIK BAŞARISIZ\nTEKRAR DENEYİN")
            self.lbl_type.setText("Kayıt Türü: -")
            self.log_box.setPlainText(
                "Canlılık doğrulaması başarısız.\n\n"
                "Kişi istenen sağ/sol hareketini zamanında tamamlayamadı."

            )
            self.set_security_ui_mode("idle")
            return

        if info is None:
            self.security_status_label.setText("TARAMA BEKLENİYOR")
            self.lbl_type.setText("Kayıt Türü: -")
            self.log_box.setPlainText(self.make_scanned_person_text(None))
            self.set_security_ui_mode("idle")
            return

        person_type_label = info.get("person_type_label", "-")
        is_suspect = bool(info.get("is_suspect", False))

        self.lbl_type.setText(f"Kayıt Türü: {person_type_label}")
        self.log_box.setPlainText(self.make_scanned_person_text(info))

        # Şüpheli uyarısı sadece canlılık geçildikten sonra aktif olur.
        if state == self.engine.APP_ALERT or active_alert:
            self.security_status_label.setText("UYARI\nKAYITLI ŞÜPHELİ ŞAHIS")
            self.set_security_ui_mode("suspect")

        # Personel yeşil onay sadece canlılık geçildikten sonra aktif olur.
        elif state == self.engine.APP_UNLOCKED or self.engine.lock_state == self.engine.STATE_UNLOCKED:
            self.security_status_label.setText("GİRİŞ ONAYLANDI\nPERSONEL KAYDI")
            self.set_security_ui_mode("staff")

        # Kişi tanındı ama canlılık testi henüz geçilmedi.
        elif state == self.engine.APP_VERIFY_CHALLENGE:
            if is_suspect:
                self.security_status_label.setText("ŞÜPHELİ EŞLEŞME\nCANLILIK BEKLENİYOR")
            else:
                self.security_status_label.setText("PERSONEL EŞLEŞME\nCANLILIK BEKLENİYOR")

            # Canlılık bitmeden kırmızı/yeşil renk vermiyoruz.
            self.set_security_ui_mode("idle")

        else:
            self.security_status_label.setText("TARAMA DEVAM EDİYOR")
            self.set_security_ui_mode("idle")
            
    # =====================================================
    # CANLILIK BANNERI
    # =====================================================        
    def update_liveness_banner(self):
        """
        Canlılık testi sırasında sağa/sola bakma komutunu
        veya başarısızlık durumunu PySide6 tarafında büyük gösterir.
        """

        # Canlılık başarısızsa 2 saniyelik net uyarı göster.
        if self.engine.app_state == self.engine.APP_LIVENESS_FAILED:
            self.liveness_banner.setStyleSheet("""
                QLabel#livenessBanner {
                    background-color: #2a1313;
                    border: 2px solid #ef4444;
                    border-radius: 18px;
                    color: #fee2e2;
                    font-size: 34px;
                    font-weight: bold;
                    padding: 18px;
                }
            """)
            self.liveness_banner.setText(
                "CANLILIK BAŞARISIZ\n"
                "LÜTFEN TEKRAR DENEYİN"
            )
            self.liveness_banner.show()
            return

        if self.engine.app_state != self.engine.APP_VERIFY_CHALLENGE:
            self.liveness_banner.setStyleSheet("")
            self.liveness_banner.hide()
            return

        if not self.engine.challenge_active:
            self.liveness_banner.setStyleSheet("")
            self.liveness_banner.hide()
            return

        import time
        left_time = max(0.0, self.engine.challenge_deadline - time.time())

        if self.engine.current_challenge == self.engine.CHALLENGE_TURN_LEFT:
            direction_text = "← SOLA BAKIN"
        elif self.engine.current_challenge == self.engine.CHALLENGE_TURN_RIGHT:
            direction_text = "SAĞA BAKIN →"
        else:
            direction_text = "CANLILIK"

        # Normal canlılık bannerı koyu mavi temaya geri döner.
        self.liveness_banner.setStyleSheet("")
        self.liveness_banner.setText(
            f"{direction_text}\n"
            f"KALAN SÜRE: {left_time:.1f} sn"
        )
        self.liveness_banner.show()
    def build_debug_window(self):
        """
        Debug alanını ayrı pencere olarak kurar.
        Ana arayüz akışı korunur; sadece debug görünümü stacked page yerine
        bağımsız bir pencereye taşınır.
        """
        self.debug_window = DebugWindow(close_callback=self.on_debug_window_closed)

        debug_layout = QVBoxLayout(self.debug_window)
        debug_layout.setContentsMargins(16, 16, 16, 16)
        debug_layout.setSpacing(10)

        self.debug_title = QLabel("Debug Menusu")
        self.debug_title.setObjectName("subHeaderLabel")

        self.debug_user = QLabel("Matched User: -")
        self.debug_person_type = QLabel("Person Type: -")
        self.debug_faces = QLabel("Faces: -")
        self.debug_sim = QLabel("SIM: -")
        self.debug_fps = QLabel("FPS: -")
        self.debug_lock = QLabel("Kilit: -")
        self.debug_live = QLabel("Liveness: -")
        self.debug_state = QLabel("State: -")
        self.debug_pose = QLabel("Pose: -")
        self.debug_yaw = QLabel("Yaw: -")
        self.debug_guide = QLabel("Guide Align: -")
        self.debug_threshold = QLabel("Threshold: -")
        self.debug_interval = QLabel("Recognition Interval: -")
        self.debug_challenge_left = QLabel("Challenge Left: -")
        self.debug_status = QLabel("Status Text: -")
        self.debug_enroll = QLabel("Enroll Counts: -")

        debug_layout.addWidget(self.debug_title)
        debug_layout.addWidget(self.debug_user)
        debug_layout.addWidget(self.debug_person_type)
        debug_layout.addWidget(self.debug_faces)
        debug_layout.addWidget(self.debug_sim)
        debug_layout.addWidget(self.debug_fps)
        debug_layout.addWidget(self.debug_lock)
        debug_layout.addWidget(self.debug_live)
        debug_layout.addWidget(self.debug_state)
        debug_layout.addWidget(self.debug_pose)
        debug_layout.addWidget(self.debug_yaw)
        debug_layout.addWidget(self.debug_guide)
        debug_layout.addWidget(self.debug_threshold)
        debug_layout.addWidget(self.debug_interval)
        debug_layout.addWidget(self.debug_challenge_left)
        debug_layout.addWidget(self.debug_status)
        debug_layout.addWidget(self.debug_enroll)
        debug_layout.addStretch()

        self.debug_window.setStyleSheet("""
            QWidget {
                background-color: #0f172a;
                color: #e5e7eb;
                font-size: 14px;
            }
            QLabel {
                color: #e5e7eb;
                padding: 4px 0;
            }
        """)

    def on_debug_window_closed(self):
        if self.engine.app_state == self.engine.APP_DEBUG:
            self.engine.go_menu()

    # =====================================================
    # SAYFA GECISLERI
    # =====================================================
    def update_status(self, text):
        self.status_label_main.setText(f"Durum: {text}")

    def refresh_users(self):
        self.users_list.clear()
        for user in self.engine.list_registered_users():
            self.users_list.addItem(user)

    def get_front_user_image_path(self, username):
        """
        Kullanıcı detay ekranında gösterilecek ön yüz fotoğrafını seçer.

        Sadece FRONT kayıtlarından seçim yapar:
        - front_01.png
        - front_02.png
        - varsa diğer front_*.png dosyaları
        """
        img_dir = self.engine.user_dir(username) / "images"

        if not img_dir.exists():
            return None

        preferred_names = [
            "front_01.png",
            "front_02.png",
            "front_03.png",
        ]

        for image_name in preferred_names:
            image_path = img_dir / image_name
            if image_path.exists():
                return image_path

        front_images = sorted(img_dir.glob("front_*.png"))
        if len(front_images) == 0:
            return None

        return front_images[0]

    def show_user_photo(self, username):
        """
        Kullanıcı detay ekranında 180x180 alanda ön yüz fotoğrafını gösterir.
        """
        image_path = self.get_front_user_image_path(username)

        if image_path is None:
            self.user_photo_label.clear()
            self.user_photo_label.setText("Ön fotoğraf yok")
            return

        pixmap = QPixmap(str(image_path))

        if pixmap.isNull():
            self.user_photo_label.clear()
            self.user_photo_label.setText("Fotoğraf okunamadı")
            return

        scaled = pixmap.scaled(
            self.user_photo_label.width(),
            self.user_photo_label.height(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        self.user_photo_label.setPixmap(scaled)

    def handle_user_selected(self, item):
        username = item.text()
        info = self.engine.get_user_display_info(username)
        self.show_user_photo(username)

        if info is None:
            self.user_detail_box.setPlainText("Kullanici bilgisi okunamadi.")
            return

        audio_text = "Var" if info.get("audio_exists", False) else "Yok"
        vip_text = "Evet" if bool(info.get("vip", False)) else "Hayir"

        role_text = info.get("role", "normal")
        gender_text = info.get("gender", "") or "-"
        title_text = info.get("title", "") or "-"
        welcome_text = info.get("welcome_text", "") or "-"
        person_type_label = info.get("person_type_label", "-")
        record_note = info.get("record_note", "") or "-"

        detail_text = (
            f"Kullanici Adi: {info.get('username', username)}\n"
            f"Kayıt Türü: {person_type_label}\n"
            f"VIP: {vip_text}\n"
            f"Rol: {role_text}\n"
            f"Cinsiyet: {gender_text}\n"
            f"Hitap: {title_text}\n"
            f"Karsilama Metni: {welcome_text}\n"
            f"Açıklama / Şahıs Bilgisi:\n{record_note}\n\n"
            f"Ses Dosyasi: {audio_text}\n"
            f"Kayitli Feature Sayisi: {info.get('feature_count', 0)}\n"
            f"Kayitli Goruntu Sayisi: {info.get('image_count', 0)}\n"
        )

        self.user_detail_box.setPlainText(detail_text)

    def go_menu(self):
        self.engine.go_menu()
        self.header_label.setText("Ana Ekran")
        self.pages.setCurrentWidget(self.page_main)
        self.update_status("Ana menuye donuldu")
        self.set_security_ui_mode("idle")
        self.liveness_banner.hide()

    def go_enroll(self):
        self.engine.start_enroll()
        self.header_label.setText("Yeni Kayit")
        self.pages.setCurrentWidget(self.page_enroll)
        self.update_status("Kayit ekranina gecildi")

        self.name_input.clear()
        self.record_note_input.clear()
        self.gender_male_btn.setChecked(False)
        self.gender_female_btn.setChecked(False)
        self.person_staff_btn.setChecked(False)
        self.person_suspect_btn.setChecked(False)

        self.update_enroll_form_state()
        self.update_enroll_progress_widgets()
        self.set_card_active(self.enroll_camera_card, True)
        self.set_card_active(self.direction_card, True)
        self.liveness_banner.hide()

    def go_verify(self):
        self.engine.start_verify()
        self.header_label.setText("Giriş Yap / Kimlik Eşleştirme")
        self.pages.setCurrentWidget(self.page_main)
        self.update_status("Giriş ekranına geçildi")
        self.update_scanned_person_panel()
        self.liveness_banner.hide()

    def go_users(self):
        self.engine.show_users()
        self.header_label.setText("Kayitli Kullanicilar")
        self.refresh_users()
        self.pages.setCurrentWidget(self.page_users)
        self.update_status("Kullanici listesi acildi")
        self.user_detail_box.clear()
        self.user_detail_box.setPlaceholderText("Listeden bir kullanici secin")
        self.user_photo_label.clear()
        self.user_photo_label.setText("Ön fotoğraf seçilmedi")

    def go_debug(self):
        self.engine.show_debug()
        self.debug_window.show()
        self.debug_window.raise_()
        self.debug_window.activateWindow()
        self.update_status("Debug penceresi acildi")

    # =====================================================
    # ENROLL FORM KONTROL
    # =====================================================
    def update_enroll_form_state(self):
        state = self.engine.app_state

        name_active = (state == self.engine.APP_ENROLL_NAME)
        gender_active = (state == self.engine.APP_ENROLL_GENDER)
        person_type_active = (state == self.engine.APP_ENROLL_PERSON_TYPE)
        record_note_active = (state == self.engine.APP_ENROLL_RECORD_NOTE)

        name_completed = state in [
            self.engine.APP_ENROLL_GENDER,
            self.engine.APP_ENROLL_PERSON_TYPE,
            self.engine.APP_ENROLL_RECORD_NOTE
        ]
        gender_completed = state in [
            self.engine.APP_ENROLL_PERSON_TYPE,
            self.engine.APP_ENROLL_RECORD_NOTE
        ]
        person_type_completed = state == self.engine.APP_ENROLL_RECORD_NOTE

        self.name_input.setEnabled(name_active)
        self.enroll_next_name_btn.setEnabled(name_active)

        self.gender_male_btn.setEnabled(gender_active)
        self.gender_female_btn.setEnabled(gender_active)

        self.person_staff_btn.setEnabled(person_type_active)
        self.person_suspect_btn.setEnabled(person_type_active)

        self.record_note_input.setEnabled(record_note_active)
        self.record_note_submit_btn.setEnabled(record_note_active)

        if name_active:
            self.set_action_button_style(self.enroll_next_name_btn, state="active")
        elif name_completed:
            self.set_action_button_style(self.enroll_next_name_btn, state="completed")
        else:
            self.set_action_button_style(self.enroll_next_name_btn, state="inactive")

        if record_note_active:
            self.set_action_button_style(self.record_note_submit_btn, state="active")
        elif person_type_completed:
            self.set_action_button_style(self.record_note_submit_btn, state="completed")
        else:
            self.set_action_button_style(self.record_note_submit_btn, state="inactive")

        self.set_form_section_style(self.name_section, active=name_active)
        self.set_form_section_style(self.gender_section, active=gender_active)
        self.set_form_section_style(self.person_type_section, active=person_type_active)
        self.set_form_section_style(self.record_note_section, active=record_note_active)

        self.gender_male_btn.setChecked(self.engine.typed_gender == "erkek")
        self.gender_female_btn.setChecked(self.engine.typed_gender == "kadin")

        self.person_staff_btn.setChecked(self.engine.typed_person_type == self.engine.PERSON_TYPE_STAFF)
        self.person_suspect_btn.setChecked(self.engine.typed_person_type == self.engine.PERSON_TYPE_SUSPECT)

        self.update_gender_button_styles()
        self.update_person_type_button_styles()

        warning_text = ""

        if state == self.engine.APP_ENROLL_ALIGN:
            self.enroll_step_label.setText("Asama: Yuz ornekleri toplaniyor")
        elif state == self.engine.APP_ENROLL_NAME:
            self.enroll_step_label.setText("Asama: Şahıs ismi girisi")
            warning_text = self.engine.name_warning_text
            self.name_input.setFocus()
        elif state == self.engine.APP_ENROLL_GENDER:
            self.enroll_step_label.setText("Asama: Cinsiyet secimi")
            warning_text = self.engine.gender_warning_text
        elif state == self.engine.APP_ENROLL_PERSON_TYPE:
            self.enroll_step_label.setText("Asama: Kayit turu secimi")
            warning_text = self.engine.person_type_warning_text
        elif state == self.engine.APP_ENROLL_RECORD_NOTE:
            self.enroll_step_label.setText("Asama: Sahis bilgisi / kayit aciklamasi")
            warning_text = self.engine.record_note_warning_text
            self.record_note_input.setFocus()

        self.enroll_warning_label.setText(warning_text)

        if self.enroll_warning_label.text().strip() == "":
            self.enroll_warning_label.hide()
        else:
            self.enroll_warning_label.show()

    def handle_name_submit(self):
        ok = self.engine.submit_enroll_name(self.name_input.text())
        self.update_enroll_form_state()
        if ok:
            self.name_input.clear()

    def handle_gender_submit(self, gender_value):
        self.engine.submit_enroll_gender(gender_value)
        self.update_enroll_form_state()

    def handle_person_type_submit(self, person_type_value):
        ok = self.engine.submit_enroll_person_type(person_type_value)
        self.update_enroll_form_state()
        if ok:
            self.record_note_input.clear()

    def handle_record_note_submit(self):
        old_user_count = len(self.engine.list_registered_users())
        ok = self.engine.submit_enroll_record_note(self.record_note_input.toPlainText())
        self.update_enroll_form_state()

        if ok:
            self.refresh_users()
            self.go_menu()
            self.update_status("Kayit tamamlandi")
            self.record_note_input.clear()

            new_user_count = len(self.engine.list_registered_users())
            if new_user_count > old_user_count:
                self.refresh_users()

    # =====================================================
    # FRAME GUNCELLEME
    # =====================================================
    def update_frame(self):
        ok, frame = self.engine.process_frame()
        if not ok or frame is None:
            return

        frame = self.draw_enroll_guide_on_frame(frame)

        frame_rgb = cv.cvtColor(frame, cv.COLOR_BGR2RGB)
        h, w, ch = frame_rgb.shape
        bytes_per_line = ch * w

        qt_image = QImage(
            frame_rgb.data,
            w,
            h,
            bytes_per_line,
            QImage.Format_RGB888
        )

        pixmap = QPixmap.fromImage(qt_image)

        # Pi 4'te FPS düşmesin diye FastTransformation kullanıyoruz.
        scaled_main = pixmap.scaled(
            self.camera_label_main.width(),
            self.camera_label_main.height(),
            Qt.KeepAspectRatio,
            Qt.FastTransformation
        )
        self.camera_label_main.setPixmap(scaled_main)

        scaled_enroll = pixmap.scaled(
            self.camera_label_enroll.width(),
            self.camera_label_enroll.height(),
            Qt.KeepAspectRatio,
            Qt.FastTransformation
        )
        self.camera_label_enroll.setPixmap(scaled_enroll)

        # Sağ panel temel bilgileri
        self.lbl_user.setText(f"Kullanici: {self.engine.matched_user_name or '-'}")

        sim_value =  self.engine.last_display_sim
        if sim_value is None:
            sim_value = self.engine.matched_user_score

        if sim_value is not None:
            self.lbl_sim.setText(f"SIM: {sim_value:.4f}")
        else:
            self.lbl_sim.setText("SIM: -")

        self.lbl_pose.setText(f"Pose: {self.engine.last_pose_text}")
        self.lbl_liveness.setText(self.engine.challenge_text())
        
        if self.engine.app_state == self.engine.APP_ALERT or getattr(self.engine, "alert_active", False):
            access_text = "Reddedildi"
        elif self.engine.lock_state == self.engine.STATE_UNLOCKED:
            access_text = "Onaylandı"
        else:
            access_text = "Beklemede"

        self.lbl_lock.setText(f"Erişim: {access_text}")
        self.lbl_fps.setText(f"FPS: {self.engine.fps:.2f}")

        self.update_scanned_person_panel()
        self.update_liveness_banner()

        # Enroll yönlendirme
        need_pose = self.engine.current_needed_pose()

        in_enroll_flow = self.engine.app_state in [
            self.engine.APP_ENROLL_ALIGN,
            self.engine.APP_ENROLL_NAME,
            self.engine.APP_ENROLL_GENDER,
            self.engine.APP_ENROLL_PERSON_TYPE,
            self.engine.APP_ENROLL_RECORD_NOTE
        ]

        if need_pose is not None:
            self.enroll_info.setText(self.engine.pose_instruction_text(need_pose))
            self.enroll_info.setStyleSheet("color: #e5e7eb; font-size: 16px; font-weight: bold;")
            self.set_card_active(self.enroll_camera_card, True)
            self.set_card_active(self.direction_card, True)
        else:
            if in_enroll_flow:
                self.enroll_info.setText("Tum pozlar tamamlandi")
                self.enroll_info.setStyleSheet("color: #60a5fa; font-size: 17px; font-weight: bold;")
                self.set_card_active(self.enroll_camera_card, False)
                self.set_card_active(self.direction_card, True)
            else:
                self.enroll_info.setText("Kayit icin yuzunuzu cerceveye getirin")
                self.enroll_info.setStyleSheet("color: #e5e7eb; font-size: 16px; font-weight: bold;")
                self.set_card_active(self.enroll_camera_card, False)
                self.set_card_active(self.direction_card, False)

        self.update_enroll_progress_widgets()
        self.update_enroll_form_state()

        # Debug ekranı bilgileri
        self.debug_user.setText(f"Matched User: {self.engine.matched_user_name or '-'}")
        self.debug_person_type.setText(f"Person Type: {self.engine.matched_person_type_label or '-'}")
        self.debug_faces.setText(f"Faces: {self.engine.last_num_faces}")

        sim_value =  self.engine.last_display_sim
        if sim_value is None:
            sim_value = self.engine.matched_user_score

        if sim_value is not None:
            self.debug_sim.setText(f"SIM: {sim_value:.4f}")
        else:
            self.debug_sim.setText("SIM: -")

        self.debug_fps.setText(f"FPS: {self.engine.fps:.2f}")
        self.debug_lock.setText(f"Kapi: {self.engine.lock_state}")
        self.debug_live.setText(f"Liveness: {self.engine.challenge_text()}")
        self.debug_state.setText(f"State: {self.engine.app_state}")
        self.debug_pose.setText(f"Pose: {self.engine.last_pose_text}")

        if self.engine.last_best_yaw is not None:
            self.debug_yaw.setText(f"Yaw: {self.engine.last_best_yaw:.4f}")
        else:
            self.debug_yaw.setText("Yaw: -")

        self.debug_guide.setText(f"Guide Align: {'OK' if self.engine.last_face_aligned_ok else 'NO'}")
        self.debug_threshold.setText(f"Threshold: {self.engine.THRESHOLD:.2f}")
        self.debug_interval.setText(f"Recognition Interval: {self.engine.RECOGNITION_INTERVAL}")

        import time
        if self.engine.challenge_active:
            left_time = max(0.0, self.engine.challenge_deadline - time.time())
            self.debug_challenge_left.setText(f"Challenge Left: {left_time:.1f}s")
        else:
            self.debug_challenge_left.setText("Challenge Left: -")

        self.debug_status.setText(f"Status Text: {self.engine.status_text or '-'}")
        self.debug_enroll.setText(
            f"Enroll Counts: F={self.engine.enroll_counts[self.engine.POSE_FRONT]} "
            f"R={self.engine.enroll_counts[self.engine.POSE_RIGHT]} "
            f"L={self.engine.enroll_counts[self.engine.POSE_LEFT]}"
        )

    # =====================================================
    # KLAVYE KONTROL
    # =====================================================
    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()

        if key == Qt.Key_Q:
            self.close()
            return

        if self.engine.app_state == self.engine.APP_MENU:
            if key == Qt.Key_1:
                self.go_enroll()
            elif key == Qt.Key_2:
                self.go_verify()
            elif key == Qt.Key_3:
                self.go_debug()
            elif key == Qt.Key_4:
                self.go_users()

        elif self.engine.app_state == self.engine.APP_ENROLL_NAME:
            if key == Qt.Key_Escape:
                self.go_menu()
            elif key in (Qt.Key_Return, Qt.Key_Enter):
                self.handle_name_submit()

        elif self.engine.app_state == self.engine.APP_ENROLL_GENDER:
            if key == Qt.Key_Escape:
                self.go_menu()
            elif key in (Qt.Key_E, Qt.Key_1):
                self.handle_gender_submit("erkek")
            elif key in (Qt.Key_K, Qt.Key_2):
                self.handle_gender_submit("kadin")

        elif self.engine.app_state == self.engine.APP_ENROLL_PERSON_TYPE:
            if key == Qt.Key_Escape:
                self.go_menu()
            elif key in (Qt.Key_P, Qt.Key_1):
                self.handle_person_type_submit("personel")
            elif key in (Qt.Key_S, Qt.Key_2):
                self.handle_person_type_submit("supheli")

        elif self.engine.app_state == self.engine.APP_ENROLL_RECORD_NOTE:
            if key == Qt.Key_Escape:
                self.go_menu()
            elif key in (Qt.Key_Return, Qt.Key_Enter) and (event.modifiers() & Qt.ControlModifier):
                self.handle_record_note_submit()

        elif self.engine.app_state == self.engine.APP_DEBUG:
            if key == Qt.Key_Escape:
                if hasattr(self, "debug_window") and self.debug_window.isVisible():
                    self.debug_window.close()
                self.go_menu()

        else:
            if key == Qt.Key_Escape:
                self.go_menu()

        super().keyPressEvent(event)

    # =====================================================
    # PENCERE KAPANISI
    # =====================================================
    def closeEvent(self, event):
        if hasattr(self, "debug_window") and self.debug_window.isVisible():
            self.debug_window.close()
        self.engine.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FaceAccessWindow()
    window.show()
    sys.exit(app.exec())
                                                                                                                                                          