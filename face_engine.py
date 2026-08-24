from collections import deque
import cv2 as cv
import time
import numpy as np
from pathlib import Path
import random
import json
import os
import RPi.GPIO as GPIO
import subprocess
import threading
import wave


class FaceAccessEngine:
    # =========================================================
    # SABITLER
    # =========================================================
    GUIDE_BOX_W = 360
    GUIDE_BOX_H = 420

    MIN_FACE_W = 100
    MIN_FACE_H = 100

    # Giriş ekranında birden fazla yüz olabileceği için daha küçük yüzleri de tarıyoruz.
    # Kayıt ekranında ise yukarıdaki MIN_FACE_W/H ve tek kişi şartı korunur.
    VERIFY_MIN_FACE_W = 60
    VERIFY_MIN_FACE_H = 60

    # Hızlı kayıt: 2 ön + 2 sağ + 2 sol = toplam 6 yüz örneği.
    ENROLL_TARGET_COUNT = 2
    ENROLL_CAPTURE_DELAY_SEC = 0.6

    # Sesli yönlendirme çalarken hemen fotoğraf çekilmesin diye bekleme süresi.
    ENROLL_PROMPT_WAIT_SEC = 1.8

    # Kayıt sırasında kişi değişmesini engellemek için kullanılır.
    # İlk kabul edilen yüz referans kabul edilir; sonraki pozlar bu referansla karşılaştırılır.
    # Sağ/sol pozlarda SIM düşebileceği için ana THRESHOLD kadar sert tutulmaz.
    ENROLL_SAME_PERSON_THRESHOLD = 0.50

    FRONT_YAW_MAX = 0.08
    SIDE_YAW_MIN = 0.18

    POSE_FRONT = "FRONT"
    POSE_RIGHT = "RIGHT"
    POSE_LEFT = "LEFT"

    TOP_K = 1
    THRESHOLD = 0.65

    # Pi 4 optimizasyonu
    RECOGNITION_INTERVAL = 4

    # Canlılık testi geri getirildi.
    # Hem personel hem şüpheli için eşleşmeden sonra sağ/sol hareket istenir.
    CHALLENGE_TIMEOUT_SEC = 8.0
    CHALLENGE_YAW_DELTA = 0.14
    CHALLENGE_FREEZE_SEC = 0.8
    LIVENESS_FAIL_DURATION_SEC = 2.0
    CHALLENGE_SUCCESS_HOLD_FRAMES = 2

    # Çoklu yüz ortamında canlılık hedefini takip etmek için kullanılır.
    # Hedef yüz bu mesafeden fazla uzaklaşırsa hedef kayboldu / farklı kişi geçti kabul edilir.
    CHALLENGE_MAX_TRACK_DISTANCE = 190.0

    # Kamera bazen 1-2 frame yüzü kaçırabilir. Bu küçük tolerans yanlış fail'i azaltır.
    CHALLENGE_TARGET_LOST_GRACE_SEC = 0.80

    # Canlılık geçildikten sonra, hareketi yapan yüzün hâlâ aynı kişi olduğunu
    # bir kez daha SFace ile doğrulamak için kullanılan daha toleranslı eşik.
    CHALLENGE_RECHECK_THRESHOLD = 0.40

    CHALLENGE_NONE = "NONE"
    CHALLENGE_TURN_LEFT = "TURN_LEFT"
    CHALLENGE_TURN_RIGHT = "TURN_RIGHT"

    UNLOCK_DURATION_SEC = 8.0
    ALERT_DURATION_SEC = 10.0

    STATE_LOCKED = "LOCKED"
    STATE_UNLOCKED = "UNLOCKED"

    APP_MENU = "MENU"
    APP_ENROLL_ALIGN = "ENROLL_ALIGN"
    APP_ENROLL_NAME = "ENROLL_NAME"
    APP_ENROLL_GENDER = "ENROLL_GENDER"
    APP_ENROLL_PERSON_TYPE = "ENROLL_PERSON_TYPE"
    APP_ENROLL_RECORD_NOTE = "ENROLL_RECORD_NOTE"

    # Mail adımı artık kullanılmıyor ama eski GUI referansları için sabit tutuluyor.
    APP_ENROLL_EMAIL = "ENROLL_EMAIL"

    APP_VERIFY_ALIGN = "VERIFY_ALIGN"
    APP_VERIFY_RECOGNIZE = "VERIFY_RECOGNIZE"
    APP_VERIFY_CHALLENGE = "VERIFY_CHALLENGE"
    APP_UNLOCKED = "UNLOCKED"
    APP_ALERT = "ALERT"
    APP_USER_LIST = "USER_LIST"
    APP_DEBUG = "DEBUG"
    APP_LIVENESS_FAILED = "LIVENESS_FAILED"

    # Kişi türleri
    PERSON_TYPE_STAFF = "staff"
    PERSON_TYPE_SUSPECT = "suspect"

    ARC_FACE_REF = np.array([
        [38.2946, 51.6963],
        [73.5318, 51.5014],
        [56.0252, 71.7366],
        [41.5493, 92.3655],
        [70.7299, 92.2041]
    ], dtype=np.float32)

    # =========================================================
    # DEKORATIF LANDMARK / MESH GÖRÜNTÜSÜ
    # SADECE GÖRSEL AMAÇLI
    # =========================================================
    MESH_ENABLED = True
    MESH_LINE_COLOR = (235, 225, 170)
    MESH_POINT_COLOR = (255, 255, 255)
    MESH_HALO_COLOR = (250, 245, 230)
    MESH_LINE_THICKNESS = 1
    MESH_POINT_RADIUS = 3
    MESH_HALO_RADIUS = 5
    MESH_ALPHA = 0.52

    def __init__(self):
        # =========================================================
        # GPIO
        # =========================================================
        self.LED = 17
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.LED, GPIO.OUT)
        # =========================================================
        # MAIL
        # =========================================================
        # Mail sistemi projeden çıkarıldı.
        self.EMAIL_ENABLED = False

        # =========================================================
        # GÖRÜNÜM / MODEL
        # =========================================================
        self.MIRROR_VIEW = True
        # Model files are downloaded separately and are not included in this repo.
        # Paths can be overridden with environment variables on the target device.
        self.model_path = os.getenv(
            "YUNET_MODEL_PATH", "models/face_detection_yunet_2023mar.onnx"
        )
        self.sface_model_path = os.getenv(
            "SFACE_MODEL_PATH", "models/face_recognition_sface_2021dec.onnx"
        )

        # =========================================================
        # PIPER
        # =========================================================
        self.PIPER_EXECUTABLE = os.getenv("PIPER_EXECUTABLE", "piper")
        self.PIPER_MODEL = os.getenv(
            "PIPER_MODEL", "models/tr_TR-dfki-medium.onnx"
        )

        # =========================================================
        # SİSTEM SESLERİ
        # =========================================================
        self.SYSTEM_AUDIO_DIR = Path("system_audio")
        self.SYSTEM_AUDIO_DIR.mkdir(exist_ok=True)

        self.enroll_prompt_audio = {
            self.POSE_FRONT: self.SYSTEM_AUDIO_DIR / "enroll_front.wav",
            self.POSE_RIGHT: self.SYSTEM_AUDIO_DIR / "enroll_right.wav",
            self.POSE_LEFT: self.SYSTEM_AUDIO_DIR / "enroll_left.wav",
        }

        self.enroll_prompt_text = {
            self.POSE_FRONT: "Lütfen kameraya bakın.",
            self.POSE_RIGHT: "Lütfen sağa dönün.",
            self.POSE_LEFT: "Lütfen sola dönün.",
        }

        # Yeni dosya adı kullanıyoruz ki eski "Lütfen isminizi girin" sesi tekrar çalmasın.
        self.enroll_photos_done_audio = self.SYSTEM_AUDIO_DIR / "enroll_photos_done_person_name.wav"
        self.enroll_photos_done_text = "Fotoğraflar çekildi. Lütfen şahıs ismini girin."

        # Personel tanındığında çalacak onay sinyali.
        self.success_beep_audio = self.SYSTEM_AUDIO_DIR / "personnel_approved.wav"

        # Şüpheli/riskli kayıt eşleşmesinde daha dikkat çekici uyarı sesi.
        self.suspect_alert_audio = self.SYSTEM_AUDIO_DIR / "suspect_alert.wav"

        # Canlılık testi sırasında çalacak sağ/sol yönlendirme sesleri.
        # Challenge başladığında sadece bir kere çalınır.
        # Eğer sağ/sol yönleri kamerada ters algılanırsa aşağıdaki iki metni yer değiştirmen yeterli.
        self.challenge_prompt_audio = {
            self.CHALLENGE_TURN_LEFT: self.SYSTEM_AUDIO_DIR / "challenge_left.wav",
            self.CHALLENGE_TURN_RIGHT: self.SYSTEM_AUDIO_DIR / "challenge_right.wav",
        }

        self.challenge_prompt_text = {
            self.CHALLENGE_TURN_LEFT: "Lütfen sola bakın.",
            self.CHALLENGE_TURN_RIGHT: "Lütfen sağa bakın.",
        }

        self.last_spoken_enroll_pose = None
        self.enroll_pose_ready_time = 0.0
        self.enroll_done_audio_played = False
        self.last_enroll_guide_candidate_count = 0
        self.last_enroll_identity_score = None

        # =========================================================
        # KULLANICI KLASÖRÜ
        # =========================================================
        self.USERS_DIR = Path("users")
        self.USERS_DIR.mkdir(exist_ok=True)

        # =========================================================
        # RUNTIME
        # =========================================================
        self.app_state = self.APP_MENU
        self.lock_state = self.STATE_LOCKED
        self.unlock_until = 0.0

        self.alert_until = 0.0
        self.alert_active = False
        self.liveness_failed_until = 0.0
        self.liveness_failed_text = ""

        self.current_challenge = self.CHALLENGE_NONE
        self.challenge_active = False
        self.challenge_ok = False
        self.challenge_deadline = 0.0
        self.challenge_baseline_yaw = 0.0
        self.challenge_freeze_until = 0.0

        # Canlılık testinin hangi kişiye/yüze uygulanacağını tutar.
        self.challenge_target_name = None
        self.challenge_target_person_type = None
        self.challenge_target_person_type_label = None
        self.challenge_target_record_note = ""
        self.challenge_target_center = None
        self.challenge_target_box = None
        self.challenge_target_lost_since = None
        self.challenge_target_lost_since = None

        self.score_buffer = deque(maxlen=7)
        self.status_text = ""
        self.status_time = 0.0
        self.last_display_sim = None

        self.enroll_samples = []
        self.enroll_counts = {
            self.POSE_FRONT: 0,
            self.POSE_RIGHT: 0,
            self.POSE_LEFT: 0,
        }
        self.last_enroll_capture_time = 0.0
        self.typed_name = ""
        self.name_warning_text = ""
        self.typed_gender = ""
        self.gender_warning_text = ""

        # Etkinlik sürümünde mail girişi yok.
        self.typed_email = ""
        self.email_warning_text = ""

        # Yeni kayıt bilgileri
        self.typed_person_type = ""
        self.person_type_warning_text = ""
        self.typed_record_note = ""
        self.record_note_warning_text = ""

        self.pending_username = ""

        self.matched_user_name = None
        self.matched_user_score = None
        self.matched_person_type = None
        self.matched_person_type_label = None
        self.matched_record_note = ""
        self.matched_user_info = None
        self.pre_challenge_frame = None

        # Çoklu yüz tanıma sonuçları.
        # Bu liste isimleri kafaların üstüne yazmak için kullanılır.
        self.last_face_labels = []
        self.last_recognition_results = []
        self.last_recognition_time = 0.0

        self.fps = 0.0
        self.frame_count = 0
        self.fps_t0 = time.time()
        self.recognition_counter = 0
        self.debug_window_open = False

        # =========================================================
        # MODELLER
        # =========================================================
        self.detector = cv.FaceDetectorYN_create(
            self.model_path,
            "",
            (320, 320),
            0.6,
            0.3,
            5000
        )

        self.recognizer = cv.FaceRecognizerSF_create(
            self.sface_model_path,
            ""
        )

        self.ensure_enroll_prompt_audios()
        self.ensure_extra_system_audios()

        # =========================================================
        # KAMERA
        # =========================================================
        self.cap = cv.VideoCapture(0)
        self.cap.set(cv.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv.CAP_PROP_FRAME_HEIGHT, 480)

        try:
            self.cap.set(cv.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass

        # =========================================================
        # GALLERY
        # =========================================================
        self.named_gallery = self.load_named_gallery_from_disk()

        # =========================================================
        # DEBUG VERİLERİ
        # =========================================================
        self.last_num_faces = 0
        self.last_best_yaw = None
        self.last_face_aligned_ok = False
        self.last_pose_text = "-"

        # Kayıt ekranı debug / durum bilgileri
        self.last_enroll_guide_candidate_count = 0
        self.last_enroll_identity_score = None

    def show_debug(self):
        self.app_state = self.APP_DEBUG
        self.debug_window_open = True

    # =========================================================
    # YARDIMCI KLASÖR / PROFİL
    # =========================================================
    def user_dir(self, name):
        return self.USERS_DIR / name

    def user_images_dir(self, name):
        p = self.user_dir(name) / "images"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def user_features_dir(self, name):
        p = self.user_dir(name) / "features"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def user_audio_dir(self, name):
        p = self.user_dir(name) / "audio"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def user_profile_path(self, name):
        return self.user_dir(name) / "profile.json"

    def user_welcome_audio_path(self, name):
        return self.user_audio_dir(name) / "welcome.wav"

    def normalize_person_type(self, person_type):
        """
        GUI tarafından gelebilecek farklı yazımları tek tipe indirger.
        Kabul edilen ana değerler:
        - staff   -> Personel
        - suspect -> Şüpheli
        """
        value = str(person_type).strip().lower()

        if value in ["personel", "staff", "normal", "gorevli", "görevli"]:
            return self.PERSON_TYPE_STAFF

        if value in ["supheli", "şüpheli", "suspect", "riskli", "risk"]:
            return self.PERSON_TYPE_SUSPECT

        return self.PERSON_TYPE_STAFF

    def person_type_label(self, person_type):
        value = self.normalize_person_type(person_type)

        if value == self.PERSON_TYPE_SUSPECT:
            return "Şüpheli"

        return "Personel"

    def is_suspect_type(self, person_type):
        return self.normalize_person_type(person_type) == self.PERSON_TYPE_SUSPECT

    def save_user_profile(
        self,
        name,
        email="",
        gender="",
        vip=False,
        role=None,
        welcome_text=None,
        person_type=None,
        record_note=""
    ):
        """
        Kullanıcı profil dosyasını kaydeder.

        Güvenlik demo profil yapısı:
        - name: Kullanıcı/kayıt adı
        - email: Bu sürümde boş
        - gender: erkek/kadin
        - person_type: staff veya suspect
        - person_type_label: Personel veya Şüpheli
        - role: Ekranda gösterilecek rol bilgisi
        - record_note: Şahıs bilgisi / kayıt açıklaması / şüpheli olay notu
        - welcome_text: Personel için hoş geldiniz metni
        """
        name = str(name).strip()
        email = str(email).strip()
        gender = str(gender).strip().lower()
        person_type = self.normalize_person_type(person_type or self.PERSON_TYPE_STAFF)
        person_type_label = self.person_type_label(person_type)
        record_note = str(record_note).strip()

        if role is None or str(role).strip() == "":
            role = person_type_label
        else:
            role = str(role).strip()

        if welcome_text is None or str(welcome_text).strip() == "":
            final_welcome_text = self.make_welcome_text(name, gender)
        else:
            final_welcome_text = self.make_welcome_text(name, gender, custom_text=welcome_text)

        profile = {
            "name": name,
            "email": email,
            "gender": gender,
            "vip": bool(vip),
            "role": role,
            "person_type": person_type,
            "person_type_label": person_type_label,
            "record_note": record_note,
            "welcome_text": final_welcome_text
        }

        with open(self.user_profile_path(name), "w", encoding="utf-8") as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)

    def get_user_profile(self, name):
        path = self.user_profile_path(name)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def get_user_display_info(self, username):
        profile = self.get_user_profile(username)
        if profile is None:
            return None

        email = profile.get("email", "")
        gender = profile.get("gender", "")
        vip = bool(profile.get("vip", False))

        # Eski kayıtlarda person_type yoksa Personel kabul edilir.
        person_type = self.normalize_person_type(profile.get("person_type", self.PERSON_TYPE_STAFF))
        person_type_label = profile.get("person_type_label", self.person_type_label(person_type))
        role = profile.get("role", person_type_label)
        record_note = profile.get("record_note", "")

        title = self.make_title_from_gender(gender)

        welcome_text = profile.get("welcome_text", "")
        if not welcome_text:
            welcome_text = self.make_welcome_text(username, gender)

        feature_count = 0
        image_count = 0

        feat_dir = self.user_dir(username) / "features"
        img_dir = self.user_dir(username) / "images"
        audio_path = self.user_welcome_audio_path(username)

        if feat_dir.exists():
            feature_count = len(list(feat_dir.glob("*.npy")))

        if img_dir.exists():
            image_count = len(list(img_dir.glob("*.png")))

        return {
            "username": username,
            "email": email,
            "gender": gender,
            "title": title,
            "vip": vip,
            "role": role,
            "person_type": person_type,
            "person_type_label": person_type_label,
            "is_suspect": self.is_suspect_type(person_type),
            "record_note": record_note,
            "welcome_text": welcome_text,
            "audio_exists": audio_path.exists(),
            "feature_count": feature_count,
            "image_count": image_count,
        }

    def get_user_gender(self, name):
        profile = self.get_user_profile(name)
        if profile is None:
            return ""
        return profile.get("gender", "")

    def get_user_person_type(self, name):
        profile = self.get_user_profile(name)
        if profile is None:
            return self.PERSON_TYPE_STAFF
        return self.normalize_person_type(profile.get("person_type", self.PERSON_TYPE_STAFF))

    def get_user_record_note(self, name):
        profile = self.get_user_profile(name)
        if profile is None:
            return ""
        return profile.get("record_note", "")

    def list_registered_users(self):
        users = []
        for p in sorted(self.USERS_DIR.glob("*")):
            if p.is_dir():
                users.append(p.name)
        return users

    # =========================================================
    # SES
    # =========================================================
    def make_title_from_gender(self, gender):
        gender = str(gender).strip().lower()
        if gender == "erkek":
            return "Bey"
        elif gender == "kadin":
            return "Hanım"
        return ""

    def make_welcome_text(self, display_name, gender="", custom_text=None):
        if custom_text is not None and str(custom_text).strip() != "":
            return str(custom_text).strip()

        title = self.make_title_from_gender(gender)

        if title:
            return f"{display_name} {title}, hoş geldiniz"

        return f"{display_name}, hoş geldiniz"

    def generate_text_audio(self, text, output_path):
        try:
            subprocess.run(
                [
                    self.PIPER_EXECUTABLE,
                    "--model",
                    self.PIPER_MODEL,
                    "--output_file",
                    str(output_path)
                ],
                input=text,
                text=True,
                check=True
            )
            print(f"[SYSTEM AUDIO] Olusturuldu -> {output_path}")
            return True
        except Exception as e:
            print(f"[SYSTEM AUDIO ERROR] Ses olusturulamadi: {e}")
            return False

    def generate_success_beep_audio(self, output_path):
        """
        Personel girişi onaylandığında çalacak kısa onay sinyalini üretir.
        İki kademeli yükselen ton kullanır.
        """
        try:
            sample_rate = 44100

            duration_1 = 0.10
            frequency_1 = 880.0
            t1 = np.linspace(0, duration_1, int(sample_rate * duration_1), endpoint=False)
            tone1 = 0.42 * np.sin(2 * np.pi * frequency_1 * t1)

            gap = np.zeros(int(sample_rate * 0.045))

            duration_2 = 0.14
            frequency_2 = 1320.0
            t2 = np.linspace(0, duration_2, int(sample_rate * duration_2), endpoint=False)
            tone2 = 0.45 * np.sin(2 * np.pi * frequency_2 * t2)

            full = np.concatenate([tone1, gap, tone2])

            fade_len = int(sample_rate * 0.012)
            if fade_len > 0 and len(full) > 2 * fade_len:
                full[:fade_len] *= np.linspace(0.0, 1.0, fade_len)
                full[-fade_len:] *= np.linspace(1.0, 0.0, fade_len)

            audio = (full * 32767).astype(np.int16)

            with wave.open(str(output_path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(audio.tobytes())

            print(f"[SYSTEM AUDIO] Personel onay sinyali olusturuldu -> {output_path}")
            return True

        except Exception as e:
            print(f"[SYSTEM AUDIO ERROR] Personel onay sinyali olusturulamadi: {e}")
            return False

    def generate_suspect_alert_audio(self, output_path):
        """
        Şüpheli eşleşmesinde çalacak daha dikkat çekici uyarı sesini üretir.
        Üç kısa pulse kullanır.
        """
        try:
            sample_rate = 44100
            frequency = 950.0
            pulse_duration = 0.18
            gap_duration = 0.08
            pulses = []

            for _ in range(3):
                t = np.linspace(0, pulse_duration, int(sample_rate * pulse_duration), endpoint=False)
                tone = 0.55 * np.sin(2 * np.pi * frequency * t)

                fade_len = int(sample_rate * 0.015)
                if fade_len > 0 and len(tone) > 2 * fade_len:
                    tone[:fade_len] *= np.linspace(0.0, 1.0, fade_len)
                    tone[-fade_len:] *= np.linspace(1.0, 0.0, fade_len)

                pulses.append(tone)
                pulses.append(np.zeros(int(sample_rate * gap_duration)))

            full = np.concatenate(pulses)
            audio = (full * 32767).astype(np.int16)

            with wave.open(str(output_path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(audio.tobytes())

            print(f"[SYSTEM AUDIO] Suspect alert olusturuldu -> {output_path}")
            return True

        except Exception as e:
            print(f"[SYSTEM AUDIO ERROR] Suspect alert olusturulamadi: {e}")
            return False

    def ensure_enroll_prompt_audios(self):
        for pose, audio_path in self.enroll_prompt_audio.items():
            if audio_path.exists():
                continue

            text = self.enroll_prompt_text.get(pose, "")
            if text:
                self.generate_text_audio(text, audio_path)

    def ensure_extra_system_audios(self):
        if not self.enroll_photos_done_audio.exists():
            self.generate_text_audio(self.enroll_photos_done_text, self.enroll_photos_done_audio)

        if not self.success_beep_audio.exists():
            self.generate_success_beep_audio(self.success_beep_audio)

        if not self.suspect_alert_audio.exists():
            self.generate_suspect_alert_audio(self.suspect_alert_audio)

        # Canlılık yönlendirme sesleri yoksa oluşturulur.
        for challenge_type, audio_path in self.challenge_prompt_audio.items():
            if audio_path.exists():
                continue

            text = self.challenge_prompt_text.get(challenge_type, "")
            if text:
                self.generate_text_audio(text, audio_path)

    def play_audio_file(self, audio_path):
        if not audio_path.exists():
            print(f"[AUDIO WARNING] Dosya bulunamadi: {audio_path}")
            return

        try:
            subprocess.run(["aplay", str(audio_path)], check=True)
        except Exception as e:
            print(f"[AUDIO ERROR] Ses calinamadi: {e}")

    def play_audio_file_async(self, audio_path):
        threading.Thread(target=self.play_audio_file, args=(audio_path,), daemon=True).start()

    def speak_enroll_pose_instruction(self, pose):
        if pose is None:
            return

        if self.last_spoken_enroll_pose == pose:
            return

        audio_path = self.enroll_prompt_audio.get(pose)
        if audio_path is None:
            return

        self.last_spoken_enroll_pose = pose
        self.enroll_pose_ready_time = time.time() + self.ENROLL_PROMPT_WAIT_SEC
        self.play_audio_file_async(audio_path)

    def generate_user_welcome_audio(self, username, display_name=None, gender="", welcome_text=None):
        output_path = self.user_welcome_audio_path(username)

        if display_name is None:
            display_name = username

        if welcome_text is not None and str(welcome_text).strip() != "":
            text_to_speak = str(welcome_text).strip()
        else:
            profile = self.get_user_profile(username)

            if profile is not None:
                profile_welcome_text = profile.get("welcome_text", "")
                profile_name = profile.get("name", display_name)
                profile_gender = profile.get("gender", gender)

                if profile_welcome_text is not None and str(profile_welcome_text).strip() != "":
                    text_to_speak = str(profile_welcome_text).strip()
                else:
                    text_to_speak = self.make_welcome_text(profile_name, profile_gender)
            else:
                text_to_speak = self.make_welcome_text(display_name, gender)

        try:
            subprocess.run(
                [
                    self.PIPER_EXECUTABLE,
                    "--model",
                    self.PIPER_MODEL,
                    "--output_file",
                    str(output_path)
                ],
                input=text_to_speak,
                text=True,
                check=True
            )
            print(f"[AUDIO] Ses dosyasi olusturuldu -> {output_path}")
            print(f"[AUDIO TEXT] {text_to_speak}")
            return True

        except Exception as e:
            print(f"[AUDIO ERROR] Ses dosyasi olusturulamadi: {e}")
            return False

    def play_user_welcome_audio(self, username):
        audio_path = self.user_welcome_audio_path(username)

        if not audio_path.exists():
            print(f"[AUDIO WARNING] Ses dosyasi bulunamadi: {audio_path}")
            return

        try:
            subprocess.run(["aplay", str(audio_path)], check=True)
            print(f"[AUDIO] Ses calindi -> {audio_path}")
        except Exception as e:
            print(f"[AUDIO ERROR] Ses dosyasi calinamadi: {e}")

    def play_success_then_welcome(self, username):
        if self.success_beep_audio.exists():
            self.play_audio_file(self.success_beep_audio)

        if username is not None:
            self.play_user_welcome_audio(username)

    def play_success_then_welcome_async(self, username):
        threading.Thread(target=self.play_success_then_welcome, args=(username,), daemon=True).start()

    def play_suspect_alert_async(self):
        self.play_audio_file_async(self.suspect_alert_audio)

    def play_challenge_prompt_async(self):
        """
        Canlılık testi başladığında sağa/sola bakma komutunu hoparlörden söyler.
        """
        audio_path = self.challenge_prompt_audio.get(self.current_challenge)

        if audio_path is None:
            return

        self.play_audio_file_async(audio_path)

    # =========================================================
    # MATEMATİK / FEATURE
    # =========================================================
    def l2_normalize(self, vec):
        norm = np.linalg.norm(vec)
        if norm < 1e-10:
            return vec
        return vec / norm

    def extract_fast_feature(self, aligned_face):
        feat = self.recognizer.feature(aligned_face).flatten().astype(np.float32)
        feat = self.l2_normalize(feat)
        return feat.reshape(1, -1)

    def extract_robust_feature(self, aligned_face):
        variants = [aligned_face]

        blur1 = cv.GaussianBlur(aligned_face, (3, 3), 0)
        variants.append(blur1)

        feats = []
        for img in variants:
            feat = self.recognizer.feature(img).flatten().astype(np.float32)
            feat = self.l2_normalize(feat)
            feats.append(feat)

        robust_feat = np.mean(feats, axis=0).astype(np.float32)
        robust_feat = self.l2_normalize(robust_feat)
        return robust_feat.reshape(1, -1)

    def match_against_gallery(self, query_feature, gallery_features):
        if gallery_features is None or len(gallery_features) == 0:
            return None

        scores = []
        for ref_feature in gallery_features:
            sim = self.recognizer.match(
                ref_feature,
                query_feature,
                cv.FaceRecognizerSF_FR_COSINE
            )
            scores.append(float(sim))

        scores.sort(reverse=True)
        k = min(self.TOP_K, len(scores))
        return sum(scores[:k]) / k

    def load_named_gallery_from_disk(self):
        named_gallery = []

        for udir in sorted(self.USERS_DIR.glob("*")):
            if not udir.is_dir():
                continue

            feat_dir = udir / "features"
            if not feat_dir.exists():
                continue

            feats = []
            for feature_path in sorted(feat_dir.glob("*.npy")):
                feat = np.load(str(feature_path)).astype(np.float32)
                if feat.ndim == 1:
                    feat = feat.reshape(1, -1)
                feats.append(feat)

            if len(feats) > 0:
                named_gallery.append({
                    "name": udir.name,
                    "features": feats
                })

        return named_gallery

    def smooth_score(self, new_score):
        if new_score is None:
            return None
        self.score_buffer.append(new_score)
        arr = np.array(self.score_buffer, dtype=np.float32)
        return float(np.median(arr))

    def reset_score_smoothing(self):
        self.score_buffer.clear()

    # =========================================================
    # GUI KONTROL / FORM ADIMLARI
    # =========================================================
    def submit_enroll_name(self, name_text):
        username = name_text.strip()

        if len(username) == 0:
            self.name_warning_text = "Isim bos olamaz."
            return False

        if self.user_dir(username).exists():
            self.name_warning_text = "Bu isim zaten kayitli. Farkli isim girin."
            return False

        self.pending_username = username
        self.typed_name = username
        self.name_warning_text = ""
        self.typed_gender = ""
        self.gender_warning_text = ""
        self.app_state = self.APP_ENROLL_GENDER
        return True

    def submit_enroll_gender(self, gender_text):
        """
        Cinsiyet seçilince kayıt bitmez.
        Sonraki adım: Personel / Şüpheli kayıt türü seçimi.
        """
        g = gender_text.strip().lower()

        if g not in ["erkek", "kadin"]:
            self.gender_warning_text = "Lutfen erkek veya kadin secin."
            return False

        if len(self.pending_username) == 0:
            self.gender_warning_text = "Kullanici adi bulunamadi."
            return False

        self.typed_gender = g
        self.gender_warning_text = ""
        self.typed_person_type = ""
        self.person_type_warning_text = ""
        self.typed_record_note = ""
        self.record_note_warning_text = ""
        self.app_state = self.APP_ENROLL_PERSON_TYPE
        return True

    def submit_enroll_person_type(self, person_type_text):
        person_type = self.normalize_person_type(person_type_text)

        if person_type not in [self.PERSON_TYPE_STAFF, self.PERSON_TYPE_SUSPECT]:
            self.person_type_warning_text = "Lutfen Personel veya Supheli secin."
            return False

        self.typed_person_type = person_type
        self.person_type_warning_text = ""
        self.typed_record_note = ""
        self.record_note_warning_text = ""
        self.app_state = self.APP_ENROLL_RECORD_NOTE
        return True

    def submit_enroll_record_note(self, record_note_text):
        """
        Şahıs bilgisi / kayıt açıklaması girildikten sonra kaydı tamamlar.
        """
        if len(self.pending_username) == 0:
            self.record_note_warning_text = "Kullanici adi bulunamadi."
            return False

        if self.typed_person_type == "":
            self.record_note_warning_text = "Kayit turu secilmedi."
            return False

        record_note = str(record_note_text).strip()
        if record_note == "":
            # Demo akışı bölünmesin diye boş açıklamayı otomatik dolduruyoruz.
            if self.is_suspect_type(self.typed_person_type):
                record_note = "Şüpheli kayıt açıklaması girilmedi. Manuel kontrol önerilir."
            else:
                record_note = "Personel kaydı. Ek açıklama girilmedi."

        username = self.pending_username
        person_type = self.normalize_person_type(self.typed_person_type)
        role = self.person_type_label(person_type)

        self.typed_record_note = record_note
        self.record_note_warning_text = ""

        self.save_enroll_session(username)

        self.save_user_profile(
            username,
            email="",
            gender=self.typed_gender.strip().lower(),
            person_type=person_type,
            role=role,
            record_note=record_note
        )

        audio_ok = self.generate_user_welcome_audio(
            username,
            username,
            self.typed_gender.strip().lower()
        )

        if audio_ok:
            self.status_text = f"Kullanici kaydedildi: {username} | Tur: {role}"
        else:
            self.status_text = f"Kullanici kaydedildi ama ses dosyasi olusturulamadi: {username}"

        self.status_time = time.time()
        self.named_gallery = self.load_named_gallery_from_disk()
        self.reset_enroll_session()
        self.app_state = self.APP_MENU
        return True

    def submit_enroll_email(self, email_text):
        self.email_warning_text = "Mail sistemi projeden kaldirildi. Bu adim kullanilmiyor."
        return False

    # =========================================================
    # HİZALAMA / POSE
    # =========================================================
    def align_face_similarity(self, frame, lmks, output_size=(112, 112)):
        src = lmks.astype(np.float32)
        dst = self.ARC_FACE_REF.copy()

        if output_size[0] != 112:
            scale = output_size[0] / 112.0
            dst *= scale

        M, _ = cv.estimateAffinePartial2D(src, dst, method=cv.LMEDS)
        if M is None:
            return None

        aligned = cv.warpAffine(
            frame,
            M,
            output_size,
            flags=cv.INTER_LINEAR,
            borderMode=cv.BORDER_CONSTANT,
            borderValue=(0, 0, 0)
        )
        return aligned

    def get_guide_rect(self, frame_w, frame_h):
        x1 = (frame_w - self.GUIDE_BOX_W) // 2
        y1 = (frame_h - self.GUIDE_BOX_H) // 2
        x2 = x1 + self.GUIDE_BOX_W
        y2 = y1 + self.GUIDE_BOX_H
        return x1, y1, x2, y2

    def face_inside_guide(self, face, frame_shape):
        h, w = frame_shape[:2]
        gx1, gy1, gx2, gy2 = self.get_guide_rect(w, h)

        x, y, w_box, h_box = map(int, face[:4])
        cx = x + w_box // 2
        cy = y + h_box // 2

        inside = (gx1 <= cx <= gx2) and (gy1 <= cy <= gy2)
        size_ok = (w_box >= self.MIN_FACE_W and h_box >= self.MIN_FACE_H)
        return inside and size_ok

    def find_enroll_guide_face(self, face_items, frame_shape):
        """
        Kayıt sırasında arkadan geçen insanları yok saymak için sadece
        kılavuz kutunun içindeki yüzleri aday kabul eder.

        Kurallar:
        - Kamera görüntüsünde birden fazla yüz olabilir.
        - Kılavuz kutunun dışında kalan yüzler kayıt için yok sayılır.
        - Kılavuz kutunun içinde tam 1 uygun yüz varsa o yüz kayıt adayıdır.
        - Kılavuz kutunun içinde 0 veya 2+ yüz varsa fotoğraf alınmaz.
        """
        candidates = []

        for item in face_items:
            if item.get("aligned") is None:
                continue

            face = item.get("face")
            if face is None:
                continue

            if self.face_inside_guide(face, frame_shape):
                candidates.append(item)

        self.last_enroll_guide_candidate_count = len(candidates)

        if len(candidates) == 1:
            return candidates[0]

        now = time.time()
        if len(candidates) > 1 and now - self.status_time > 0.8:
            self.status_text = "Kılavuz alanında birden fazla yüz var. Fotoğraf alınmadı."
            self.status_time = now
        elif len(candidates) == 0 and now - self.status_time > 1.2:
            self.status_text = "Kayıt için yüzünüzü kılavuz alanına getirin."
            self.status_time = now

        return None

    def enroll_same_person_ok(self, new_feature):
        """
        Kayıt sırasında pozlar arasında kişinin değişmesini engeller.

        İlk kabul edilen fotoğraf referans olur. Sonraki her yeni feature,
        daha önce kabul edilen tüm feature'larla karşılaştırılır.
        En iyi SIM belirlenen eşikten düşükse fotoğraf alınmaz.
        """
        if new_feature is None:
            return False

        if len(self.enroll_samples) == 0:
            self.last_enroll_identity_score = None
            return True

        best_sim = -1.0

        for sample in self.enroll_samples:
            ref_feature = sample.get("feature")
            if ref_feature is None:
                continue

            sim = self.recognizer.match(
                ref_feature,
                new_feature,
                cv.FaceRecognizerSF_FR_COSINE
            )
            best_sim = max(best_sim, float(sim))

        self.last_enroll_identity_score = best_sim

        if best_sim < self.ENROLL_SAME_PERSON_THRESHOLD:
            self.status_text = (
                "Kayıt kişisi değişmiş olabilir. Fotoğraf alınmadı. "
                f"SIM={best_sim:.4f}"
            )
            self.status_time = time.time()
            return False

        return True

    def compute_yaw_like(self, lmks):
        eye_a = lmks[0]
        eye_b = lmks[1]
        nose = lmks[2]

        eye_center = 0.5 * (eye_a + eye_b)
        eye_distance = np.linalg.norm(eye_b - eye_a)

        if eye_distance < 1e-6:
            return None

        return float((nose[0] - eye_center[0]) / eye_distance)

    def classify_pose_from_yaw(self, yaw_like):
        if yaw_like is None:
            return None

        if abs(yaw_like) <= self.FRONT_YAW_MAX:
            return self.POSE_FRONT
        elif yaw_like >= self.SIDE_YAW_MIN:
            return self.POSE_RIGHT
        elif yaw_like <= -self.SIDE_YAW_MIN:
            return self.POSE_LEFT
        return None

    def pose_instruction_text(self, pose):
        if pose == self.POSE_FRONT:
            return "Tam karsi bakin"
        elif pose == self.POSE_RIGHT:
            return "Saga bakin"
        elif pose == self.POSE_LEFT:
            return "Sola bakin"
        return "Poz belirlenemedi"

    # =========================================================
    # ÇOKLU YÜZ / LABEL YARDIMCILARI
    # =========================================================
    def build_face_items(self, frame, faces):
        """
        YuNet çıktısındaki tüm yüzleri ortak bir liste formatına çevirir.
        Giriş ekranında çoklu yüz desteği bu liste üzerinden çalışır.
        """
        items = []

        if faces is None or len(faces) == 0:
            return items

        for face in faces:
            x, y, w_box, h_box = map(int, face[:4])
            lmks = face[4:14].reshape(5, 2).astype(np.float32)
            yaw = self.compute_yaw_like(lmks)
            center = (x + w_box / 2.0, y + h_box / 2.0)

            aligned = None
            try:
                aligned = self.recognizer.alignCrop(frame, face)
            except Exception:
                aligned = None

            items.append({
                "face": face,
                "box": (x, y, w_box, h_box),
                "lmks": lmks,
                "yaw": yaw,
                "center": center,
                "aligned": aligned,
                "area": float(w_box * h_box),
            })

        return items

    def verify_face_usable(self, item):
        x, y, w_box, h_box = item["box"]
        return (
            item.get("aligned") is not None and
            w_box >= self.VERIFY_MIN_FACE_W and
            h_box >= self.VERIFY_MIN_FACE_H
        )

    def draw_face_label(self, frame, box, text, color):
        """
        Yüzün üstüne sadece isim yazar.
        Dikdörtgen, SIM, kayıt türü veya ekstra bilgi basmaz.
        Yazı renkli olur; okunabilirlik için arkasına siyah gölge verilir.
        """

        x, y, w_box, h_box = box
        x1 = max(0, int(x))
        y1 = max(0, int(y))

        label_y = max(28, y1 - 12)

        font = cv.FONT_HERSHEY_SIMPLEX
        font_scale = 0.75
        thickness = 2

        # Siyah gölge
        cv.putText(
            frame,
            text,
            (x1 + 2, label_y + 2),
            font,
            font_scale,
            (0, 0, 0),
            thickness + 2,
            cv.LINE_AA
        )

        # Renkli isim
        cv.putText(
            frame,
            text,
            (x1, label_y),
            font,
            font_scale,
            color,
            thickness,
            cv.LINE_AA
        )

    def draw_last_face_labels(self, frame):
        """
        Son tanıma sonuçlarını kameranın üstüne basar.
        Her frame'de SFace çalıştırılmadığı için son label'lar kısa süre korunur.
        """
        if time.time() - self.last_recognition_time > 1.2:
            return

        for item in self.last_face_labels:
            self.draw_face_label(frame, item["box"], item["text"], item["color"])

    def recognize_faces_in_items(self, face_items):
        """
        Giriş ekranında tüm yüzleri tek tek veritabanıyla karşılaştırır.
        Eşik üstü eşleşen kişileri döndürür.
        Şüpheli/personel bilgisi profile.json içinden alınır.
        """
        results = []
        labels = []
        frame_best_sim = None

        if len(self.named_gallery) == 0:
            self.last_face_labels = []
            self.last_recognition_results = []
            self.last_recognition_time = time.time()
            return results

        for item in face_items:
            if not self.verify_face_usable(item):
                continue

            query_feature = self.extract_fast_feature(item["aligned"])

            best_name = None
            best_sim = -1.0

            for gallery_item in self.named_gallery:
                sim = self.match_against_gallery(query_feature, gallery_item["features"])
                if sim is not None and sim > best_sim:
                    best_sim = sim
                    best_name = gallery_item["name"]
                if best_sim >= 0:
                    if frame_best_sim is None or best_sim > frame_best_sim:
                        frame_best_sim = best_sim

            if best_name is None:
                continue

            if best_sim >= self.THRESHOLD:
                info = self.get_user_display_info(best_name)
                if info is None:
                    person_type = self.PERSON_TYPE_STAFF
                    person_type_label = "Personel"
                    is_suspect = False
                    record_note = ""
                else:
                    person_type = info.get("person_type", self.PERSON_TYPE_STAFF)
                    person_type_label = info.get("person_type_label", self.person_type_label(person_type))
                    is_suspect = bool(info.get("is_suspect", False))
                    record_note = info.get("record_note", "")

                color = (0, 0, 255) if is_suspect else (0, 200, 0)
                label_text = best_name

                result = {
                    "name": best_name,
                    "sim": float(best_sim),
                    "info": info,
                    "person_type": person_type,
                    "person_type_label": person_type_label,
                    "is_suspect": is_suspect,
                    "record_note": record_note,
                    "box": item["box"],
                    "center": item["center"],
                    "yaw": item["yaw"],
                    "item": item,
                }
                results.append(result)
                labels.append({
                    "box": item["box"],
                    "text": label_text,
                    "color": color,
                })

        self.last_face_labels = labels
        self.last_recognition_results = results
        self.last_recognition_time = time.time()
        self.last_display_sim = frame_best_sim
        return results

    def choose_challenge_target(self, recognition_results):
        """
        Canlılık testi hedefini seçer.
        Öncelik:
        1. En yüksek SIM değerli şüpheli
        2. Şüpheli yoksa en yüksek SIM değerli personel
        """
        if not recognition_results:
            return None

        suspects = [r for r in recognition_results if r.get("is_suspect", False)]
        if suspects:
            return max(suspects, key=lambda r: r.get("sim", -1.0))

        return max(recognition_results, key=lambda r: r.get("sim", -1.0))

    def set_matched_from_result(self, result):
        self.matched_user_name = result.get("name")
        self.matched_user_score = result.get("sim")
        self.matched_user_info = result.get("info")
        self.matched_person_type = result.get("person_type")
        self.matched_person_type_label = result.get("person_type_label")
        self.matched_record_note = result.get("record_note", "")

    def find_challenge_target_face(self, face_items):
        """
        Çoklu yüz varken challenge'ın aynı kişide devam etmesi için,
        başlangıçta kaydettiğimiz hedef merkeze en yakın yüzü seçer.

        Not:
        - Sadece en yakın yüzü almak yeterli değildir.
        - En yakın yüz bile çok uzaktaysa, hedef yüz ekrandan çıktı veya
          başka biri hedef bölgeye yaklaştı kabul edilir.
        """
        if self.challenge_target_center is None or not face_items:
            return None

        tx, ty = self.challenge_target_center
        best_item = None
        best_dist = None

        for item in face_items:
            if item.get("yaw") is None:
                continue

            cx, cy = item["center"]

            # Gerçek piksel mesafesi
            dist = ((cx - tx) ** 2 + (cy - ty) ** 2) ** 0.5

            if best_dist is None or dist < best_dist:
                best_dist = dist
                best_item = item

        if best_item is None:
            return None

        # En yakın yüz bile çok uzaksa artık aynı hedef yüz değildir.
        if best_dist is None or best_dist > self.CHALLENGE_MAX_TRACK_DISTANCE:
            return None

        # Hedef takip noktasını güncelle.
        self.challenge_target_center = best_item["center"]
        self.challenge_target_box = best_item["box"]

        return best_item

    def verify_challenge_target_identity(self, target_item):
        """
        Canlılık testi geçildikten sonra erişim vermeden önce,
        hareketi yapan yüzün gerçekten başta tanınan kişi olup olmadığını tekrar kontrol eder.

        Bu kontrol her frame'de değil, yalnızca canlılık geçildiği anda 1 kez yapılır.
        Bu yüzden sistemi belirgin şekilde ağırlaştırmaz.
        """
        if target_item is None:
            return False

        if self.challenge_target_name is None:
            return False

        aligned = target_item.get("aligned")
        if aligned is None:
            return False

        query_feature = self.extract_fast_feature(aligned)

        target_gallery = None
        for gallery_item in self.named_gallery:
            if gallery_item.get("name") == self.challenge_target_name:
                target_gallery = gallery_item
                break

        if target_gallery is None:
            return False

        sim = self.match_against_gallery(query_feature, target_gallery.get("features", []))

        if sim is None:
            return False

        # Sağ panelde son kontrol skoru görülebilsin.
        self.matched_user_score = float(sim)

        if sim < self.CHALLENGE_RECHECK_THRESHOLD:
            self.status_text = (
                f"Canlilik hareketi algilandi ancak hedef kisi dogrulanamadi. "
                f"SIM={sim:.4f}"
            )
            self.status_time = time.time()
            return False

        return True

    # =========================================================
    # DEKORATIF LANDMARK / MESH
    # =========================================================
    def lerp_point(self, a, b, t):
        a = np.asarray(a, dtype=np.float32)
        b = np.asarray(b, dtype=np.float32)
        return ((1.0 - t) * a + t * b).astype(np.float32)

    def draw_decorative_mesh(self, frame, best_lmks, box):
        if not self.MESH_ENABLED:
            return

        x, y, w, h = box

        re = np.array(best_lmks[0], dtype=np.float32)
        le = np.array(best_lmks[1], dtype=np.float32)
        no = np.array(best_lmks[2], dtype=np.float32)
        rm = np.array(best_lmks[3], dtype=np.float32)
        lm = np.array(best_lmks[4], dtype=np.float32)

        eye_mid = (re + le) * 0.5
        mouth_mid = (rm + lm) * 0.5

        eye_vec = le - re
        eye_len = np.linalg.norm(eye_vec)
        if eye_len < 1e-6:
            return
        eye_dir = eye_vec / eye_len

        v_vec = mouth_mid - eye_mid
        v_len = np.linalg.norm(v_vec)
        if v_len < 1e-6:
            v_dir = np.array([0.0, 1.0], dtype=np.float32)
        else:
            v_dir = v_vec / v_len

        def clamp_pt(p):
            px = int(np.clip(p[0], 0, frame.shape[1] - 1))
            py = int(np.clip(p[1], 0, frame.shape[0] - 1))
            return (px, py)

        top = eye_mid - v_dir * (0.34 * h)
        top_right = eye_mid - eye_dir * (0.34 * w) - v_dir * (0.16 * h)
        top_left = eye_mid + eye_dir * (0.34 * w) - v_dir * (0.16 * h)
        mid_right = no - eye_dir * (0.48 * w) + v_dir * (0.04 * h)
        mid_left = no + eye_dir * (0.48 * w) + v_dir * (0.04 * h)
        low_right = mouth_mid - eye_dir * (0.30 * w) + v_dir * (0.18 * h)
        low_left = mouth_mid + eye_dir * (0.30 * w) + v_dir * (0.18 * h)
        chin = mouth_mid + v_dir * (0.28 * h)

        brow_mid = eye_mid - v_dir * (0.07 * h)
        nose_right = no - eye_dir * (0.08 * w)
        nose_left = no + eye_dir * (0.08 * w)
        mouth_low = mouth_mid + v_dir * (0.08 * h)

        cheek_inner_right = (re * 0.55 + rm * 0.45) - eye_dir * (0.05 * w)
        cheek_inner_left = (le * 0.55 + lm * 0.45) + eye_dir * (0.05 * w)

        pts = [
            re, le, no, rm, lm,
            top,
            top_right,
            top_left,
            mid_right,
            mid_left,
            low_right,
            low_left,
            chin,
            brow_mid,
            nose_right,
            nose_left,
            mouth_low,
            cheek_inner_right,
            cheek_inner_left
        ]

        edges = [
            (6, 5), (5, 7),
            (6, 8), (8, 10), (10, 12),
            (7, 9), (9, 11), (11, 12),
            (0, 13), (13, 1),
            (0, 17), (1, 18),
            (13, 2),
            (2, 14), (2, 15),
            (17, 14), (18, 15),
            (14, 3),
            (15, 4),
            (3, 16), (4, 16),
            (16, 12),
            (17, 10),
            (18, 11),
            (0, 6),
            (1, 7)
        ]

        overlay = frame.copy()

        for a, b in edges:
            cv.line(overlay, clamp_pt(pts[a]), clamp_pt(pts[b]), self.MESH_LINE_COLOR, self.MESH_LINE_THICKNESS, cv.LINE_AA)

        for i, p in enumerate(pts):
            halo_r = self.MESH_HALO_RADIUS
            if i >= 5:
                halo_r = max(3, self.MESH_HALO_RADIUS - 1)
            cv.circle(overlay, clamp_pt(p), halo_r, self.MESH_HALO_COLOR, -1, cv.LINE_AA)

        cv.addWeighted(overlay, self.MESH_ALPHA, frame, 1.0 - self.MESH_ALPHA, 0, frame)

        for i, p in enumerate(pts):
            r = self.MESH_POINT_RADIUS
            if i >= 5:
                r = max(2, self.MESH_POINT_RADIUS - 1)
            cv.circle(frame, clamp_pt(p), r, self.MESH_POINT_COLOR, -1, cv.LINE_AA)

    # =========================================================
    # CHALLENGE / CANLILIK
    # =========================================================
    def reset_challenge(self):
        self.current_challenge = self.CHALLENGE_NONE
        self.challenge_active = False
        self.challenge_ok = False
        self.challenge_deadline = 0.0
        self.challenge_baseline_yaw = 0.0
        self.challenge_freeze_until = 0.0
        self.challenge_target_name = None
        self.challenge_target_person_type = None
        self.challenge_target_person_type_label = None
        self.challenge_target_record_note = ""
        self.challenge_target_center = None
        self.challenge_target_box = None
        self.challenge_success_counter = 0

    def challenge_text(self):
        if self.challenge_ok:
            return "Canlılık: OK"
        if not self.challenge_active:
            return "Canlılık: Bekleniyor"
        if self.current_challenge == self.CHALLENGE_TURN_LEFT:
            return "Canlılık: Sola bakın"
        if self.current_challenge == self.CHALLENGE_TURN_RIGHT:
            return "Canlılık: Sağa bakın"
        return "Canlılık: ..."

    def start_random_challenge_for_result(self, result):
        yaw_like = result.get("yaw")
        if yaw_like is None:
            return False

        self.set_matched_from_result(result)

        self.challenge_target_name = result.get("name")
        self.challenge_target_person_type = result.get("person_type")
        self.challenge_target_person_type_label = result.get("person_type_label")
        self.challenge_target_record_note = result.get("record_note", "")
        self.challenge_target_center = result.get("center")
        self.challenge_target_box = result.get("box")
        self.challenge_target_lost_since = None

        self.current_challenge = random.choice([
            self.CHALLENGE_TURN_LEFT,
            self.CHALLENGE_TURN_RIGHT
        ])

        self.challenge_active = True
        self.challenge_ok = False
        self.challenge_deadline = time.time() + self.CHALLENGE_TIMEOUT_SEC
        self.challenge_baseline_yaw = yaw_like
        self.challenge_freeze_until = time.time() + self.CHALLENGE_FREEZE_SEC

        # Canlılık testi başladığında yönlendirmeyi hoparlörden söyle.
        self.play_challenge_prompt_async()

        return True

    def update_challenge_state(self, yaw_like):
        now = time.time()

        if not self.challenge_active:
            return self.challenge_ok, False

        if yaw_like is None:
            if now > self.challenge_deadline:
                self.reset_challenge()
                return False, True
            return self.challenge_ok, False

        if now > self.challenge_deadline:
            self.reset_challenge()
            return False, True

        yaw_delta = yaw_like - self.challenge_baseline_yaw

        success_now = False

        if self.current_challenge == self.CHALLENGE_TURN_LEFT:
            if yaw_delta <= -self.CHALLENGE_YAW_DELTA:
                success_now = True

        elif self.current_challenge == self.CHALLENGE_TURN_RIGHT:
            if yaw_delta >= self.CHALLENGE_YAW_DELTA:
                success_now = True

        if success_now:
            self.challenge_success_counter += 1
        else:
            self.challenge_success_counter = 0

        if self.challenge_success_counter >= self.CHALLENGE_SUCCESS_HOLD_FRAMES:
            self.challenge_ok = True
            self.challenge_active = False

        return self.challenge_ok, False

    # =========================================================
    # ENROLL
    # =========================================================
    def reset_enroll_session(self):
        self.enroll_samples = []
        self.enroll_counts = {
            self.POSE_FRONT: 0,
            self.POSE_RIGHT: 0,
            self.POSE_LEFT: 0,
        }
        self.last_enroll_capture_time = 0.0
        self.typed_name = ""
        self.name_warning_text = ""
        self.typed_gender = ""
        self.gender_warning_text = ""
        self.typed_email = ""
        self.email_warning_text = ""
        self.typed_person_type = ""
        self.person_type_warning_text = ""
        self.typed_record_note = ""
        self.record_note_warning_text = ""
        self.pending_username = ""
        self.last_spoken_enroll_pose = None
        self.enroll_pose_ready_time = 0.0
        self.enroll_done_audio_played = False
        self.last_enroll_guide_candidate_count = 0
        self.last_enroll_identity_score = None

    def current_needed_pose(self):
        if self.enroll_counts[self.POSE_FRONT] < self.ENROLL_TARGET_COUNT:
            return self.POSE_FRONT
        if self.enroll_counts[self.POSE_RIGHT] < self.ENROLL_TARGET_COUNT:
            return self.POSE_RIGHT
        if self.enroll_counts[self.POSE_LEFT] < self.ENROLL_TARGET_COUNT:
            return self.POSE_LEFT
        return None

    def enroll_completed(self):
        return (
            self.enroll_counts[self.POSE_FRONT] >= self.ENROLL_TARGET_COUNT and
            self.enroll_counts[self.POSE_RIGHT] >= self.ENROLL_TARGET_COUNT and
            self.enroll_counts[self.POSE_LEFT] >= self.ENROLL_TARGET_COUNT
        )

    def save_enroll_session(self, username):
        img_dir = self.user_images_dir(username)
        feat_dir = self.user_features_dir(username)

        pose_index = {
            self.POSE_FRONT: 0,
            self.POSE_RIGHT: 0,
            self.POSE_LEFT: 0,
        }

        for sample in self.enroll_samples:
            pose = sample["pose"]
            pose_index[pose] += 1
            idx = pose_index[pose]

            img_path = img_dir / f"{pose.lower()}_{idx:02d}.png"
            feat_path = feat_dir / f"{pose.lower()}_{idx:02d}.npy"

            cv.imwrite(str(img_path), sample["aligned_face"])
            np.save(str(feat_path), sample["feature"].astype(np.float32))

    # =========================================================
    # ACCESS / UYARI
    # =========================================================
    def prepare_matched_user_info(self, username):
        info = self.get_user_display_info(username)
        self.matched_user_info = info

        if info is None:
            self.matched_person_type = self.PERSON_TYPE_STAFF
            self.matched_person_type_label = "Personel"
            self.matched_record_note = ""
            return

        self.matched_person_type = info.get("person_type", self.PERSON_TYPE_STAFF)
        self.matched_person_type_label = info.get("person_type_label", self.person_type_label(self.matched_person_type))
        self.matched_record_note = info.get("record_note", "")

    def trigger_unlock(self):
        """
        Personel için canlılık başarılı olduktan sonra normal giriş:
        - GPIO/LED aktif olur
        - önce kısa onay sesi gelir
        - sonra hoş geldiniz sesi çalar
        - mail yok
        """
        self.lock_state = self.STATE_UNLOCKED
        self.unlock_until = time.time() + self.UNLOCK_DURATION_SEC
        self.alert_active = False
        self.reset_challenge()

        if self.matched_user_name is not None:
            self.prepare_matched_user_info(self.matched_user_name)
            self.play_success_then_welcome_async(self.matched_user_name)
            self.status_text = f"Personel tanindi: {self.matched_user_name}"
            self.status_time = time.time()

    def trigger_suspect_alert(self):
        """
        Şüpheli için canlılık başarılı olduktan sonra uyarı:
        - GPIO/LED kilit açma sinyali verilmez
        - lock_state LOCKED kalır
        - app_state ALERT olur
        - uyarı sesi çalar
        - PySide6 tarafında kırmızı panel/kamera çerçevesi aktif olur
        """
        self.lock_state = self.STATE_LOCKED
        self.alert_active = True
        self.alert_until = time.time() + self.ALERT_DURATION_SEC
        self.reset_challenge()

        if self.matched_user_name is not None:
            self.prepare_matched_user_info(self.matched_user_name)
            self.play_suspect_alert_async()
            self.status_text = f"UYARI: KAYITLI SUPHELI SAHIS ESLESMESI: {self.matched_user_name}"
            self.status_time = time.time()

        self.app_state = self.APP_ALERT
    def trigger_liveness_failed(self):
        """
        Canlılık testi başarısız olduğunda kısa süre kullanıcıya net bilgi verir.
        Süre dolunca sistem tekrar giriş/yüz tarama moduna döner.
        """
        self.lock_state = self.STATE_LOCKED
        self.alert_active = False

        self.status_text = "Canlılık doğrulaması başarısız. Lütfen tekrar deneyin."
        self.status_time = time.time()

        self.liveness_failed_text = "CANLILIK BASARISIZ"
        self.liveness_failed_until = time.time() + self.LIVENESS_FAIL_DURATION_SEC

        self.matched_user_name = None
        self.matched_user_score = None
        self.matched_person_type = None
        self.matched_person_type_label = None
        self.matched_record_note = ""
        self.matched_user_info = None
        self.pre_challenge_frame = None
        self.last_face_labels = []
        self.last_recognition_results = []

        self.reset_challenge()
        self.reset_score_smoothing()

        self.app_state = self.APP_LIVENESS_FAILED

    def update_lock_state(self):
        if self.lock_state == self.STATE_UNLOCKED and time.time() >= self.unlock_until:
            self.lock_state = self.STATE_LOCKED

        if self.alert_active and time.time() >= self.alert_until:
            self.alert_active = False
            if self.app_state == self.APP_ALERT:
                self.matched_user_name = None
                self.matched_user_score = None
                self.matched_person_type = None
                self.matched_person_type_label = None
                self.matched_record_note = ""
                self.matched_user_info = None
                self.pre_challenge_frame = None
                self.last_face_labels = []
                self.last_recognition_results = []
                self.reset_challenge()
                self.reset_score_smoothing()

                # Uyarı süresi bitince ana menüye değil,
                # otomatik tekrar giriş/yüz tarama moduna dön.
                self.app_state = self.APP_VERIFY_ALIGN

        if self.app_state == self.APP_LIVENESS_FAILED and time.time() >= self.liveness_failed_until:
            self.liveness_failed_text = ""
            self.app_state = self.APP_VERIFY_ALIGN

    def update_led(self):
        # Şüpheli kayıtta LED/kapı açma sinyali verilmez.
        if self.lock_state == self.STATE_UNLOCKED:
            GPIO.output(self.LED, GPIO.HIGH)
        else:
            GPIO.output(self.LED, GPIO.LOW)
            
    def access_state_text(self):
        """
        GUI tarafında gösterilecek erişim durumunu döndürür.
        İç sistemde LOCKED / UNLOCKED kalır, ekranda Türkçe ve demo diline uygun görünür.
        """

        if self.app_state == self.APP_ALERT or self.alert_active:
            return "Reddedildi"

        if self.app_state == self.APP_UNLOCKED or self.lock_state == self.STATE_UNLOCKED:
            return "Onaylandı"

        return "Beklemede"

    # =========================================================
    # GUI KONTROL FONKSİYONLARI
    # =========================================================
    def go_menu(self):
        self.app_state = self.APP_MENU
        self.alert_active = False

    def start_enroll(self):
        self.reset_enroll_session()
        self.app_state = self.APP_ENROLL_ALIGN

    def start_verify(self):
        self.matched_user_name = None
        self.matched_user_score = None
        self.matched_person_type = None
        self.matched_person_type_label = None
        self.matched_record_note = ""
        self.matched_user_info = None
        self.pre_challenge_frame = None
        self.alert_active = False
        self.last_face_labels = []
        self.last_recognition_results = []
        self.reset_challenge()
        self.reset_score_smoothing()
        self.named_gallery = self.load_named_gallery_from_disk()
        self.app_state = self.APP_VERIFY_ALIGN

    def show_users(self):
        self.app_state = self.APP_USER_LIST

    def toggle_debug(self):
        self.debug_window_open = not self.debug_window_open

    # =========================================================
    # YÜZ SEÇİMİ
    # =========================================================
    def select_primary_face_item(self, face_items):
        if not face_items:
            return None
        return max(face_items, key=lambda item: item.get("area", 0.0))

    # =========================================================
    # FRAME İŞLEME
    # =========================================================
    def process_frame(self):
        self.update_lock_state()
        self.update_led()

        ret, frame = self.cap.read()
        if not ret:
            return False, None

        if self.MIRROR_VIEW:
            frame = cv.flip(frame, 1)

        self.recognition_counter += 1
        do_recognition = (
            self.recognition_counter % max(1, self.RECOGNITION_INTERVAL) == 0
        )

        h, w = frame.shape[:2]
        self.detector.setInputSize((w, h))

        _, faces = self.detector.detect(frame)
        face_items = self.build_face_items(frame, faces)
        num_faces = len(face_items)

        self.last_num_faces = num_faces
        self.last_best_yaw = None
        self.last_face_aligned_ok = False
        self.last_pose_text = "-"

        primary_item = self.select_primary_face_item(face_items)
        best_lmks = None
        box = None
        face_aligned_ok = False
        aligned_sface = None
        best_yaw = None

        # Dekoratif mesh için ayrı hedef.
        # Kayıt ekranında primary_item kullanılır; giriş/canlılıkta tanınan hedefe bağlanır.
        mesh_lmks = None
        mesh_box = None

        if primary_item is not None:
            best_lmks = primary_item["lmks"]
            box = primary_item["box"]
            best_yaw = primary_item["yaw"]
            aligned_sface = primary_item["aligned"]

            x, y, w_box, h_box = box

            # Kayıt ekranında tek kişi zorunluluğu devam eder.
            # Giriş ekranında bu şart kullanılmaz.
            if aligned_sface is not None and w_box >= 80 and h_box >= 80 and num_faces == 1:
                face_aligned_ok = self.face_inside_guide(primary_item["face"], frame.shape)

            self.last_best_yaw = best_yaw
            self.last_face_aligned_ok = face_aligned_ok
            self.last_pose_text = self.classify_pose_from_yaw(best_yaw) if best_yaw is not None else "-"

            # Varsayılan olarak mesh en büyük / ana yüze çizilir.
            # Giriş ve canlılık aşamasında bu değer tanınan hedef yüzle değiştirilecek.
            mesh_lmks = best_lmks
            mesh_box = box

        # Kayıt ekranında artık "kamerada tek yüz" şartı yok.
        # Arkadan geçen yüzler yok sayılır; sadece kılavuz kutunun içindeki tek yüz hedef alınır.
        if self.app_state == self.APP_ENROLL_ALIGN:
            enroll_item = self.find_enroll_guide_face(face_items, frame.shape)
            if enroll_item is not None:
                best_lmks = enroll_item["lmks"]
                box = enroll_item["box"]
                best_yaw = enroll_item["yaw"]
                aligned_sface = enroll_item["aligned"]
                face_aligned_ok = True

                self.last_best_yaw = best_yaw
                self.last_face_aligned_ok = True
                self.last_pose_text = self.classify_pose_from_yaw(best_yaw) if best_yaw is not None else "-"

                # Kayıt ekranındaki dekoratif mesh de kayıt adayı olan yüzü takip eder.
                mesh_lmks = best_lmks
                mesh_box = box
            else:
                face_aligned_ok = False
                self.last_face_aligned_ok = False

        # =====================================================
        # ENROLL ALIGN
        # =====================================================
        if self.app_state == self.APP_ENROLL_ALIGN:
            need_pose = self.current_needed_pose()
            self.speak_enroll_pose_instruction(need_pose)

            prompt_wait_finished = time.time() >= self.enroll_pose_ready_time

            if (
                prompt_wait_finished and
                face_aligned_ok and
                aligned_sface is not None and
                best_yaw is not None and
                need_pose is not None
            ):
                current_pose = self.classify_pose_from_yaw(best_yaw)

                if current_pose == need_pose:
                    now = time.time()
                    if now - self.last_enroll_capture_time >= self.ENROLL_CAPTURE_DELAY_SEC:
                        feature = self.extract_robust_feature(aligned_sface)

                        # İlk pozdan sonra her fotoğrafta aynı kişi kontrolü yapılır.
                        # Böylece ÖN pozda bir kişi, SAĞ/SOL pozda başka kişi kayda karışamaz.
                        if self.enroll_same_person_ok(feature):
                            self.enroll_samples.append({
                                "pose": current_pose,
                                "aligned_face": aligned_sface.copy(),
                                "feature": feature.copy()
                            })

                            self.enroll_counts[current_pose] += 1
                            self.last_enroll_capture_time = now

                            self.status_text = f"{current_pose} kaydedildi"
                            self.status_time = time.time()

                            if self.enroll_completed():
                                if not self.enroll_done_audio_played:
                                    self.enroll_done_audio_played = True
                                    self.play_audio_file_async(self.enroll_photos_done_audio)

                                self.app_state = self.APP_ENROLL_NAME
                        else:
                            # Aynı kişi kontrolü başarısızsa sürekli art arda uyarı üretmesin.
                            self.last_enroll_capture_time = now

        # =====================================================
        # VERIFY ALIGN
        # =====================================================
        elif self.app_state == self.APP_VERIFY_ALIGN:

            # Giriş ekranında tek kişi şartı yok.
            # En az bir kullanılabilir yüz varsa tanıma aşamasına geçilir.
            usable_faces = [item for item in face_items if self.verify_face_usable(item)]
            if usable_faces:
                self.named_gallery = self.load_named_gallery_from_disk()
                self.matched_user_name = None
                self.matched_user_score = None
                self.matched_user_info = None
                self.pre_challenge_frame = None
                self.reset_challenge()
                self.reset_score_smoothing()
                self.app_state = self.APP_VERIFY_RECOGNIZE

        # =====================================================
        # VERIFY RECOGNIZE
        # =====================================================
        elif self.app_state == self.APP_VERIFY_RECOGNIZE:


            usable_faces = [item for item in face_items if self.verify_face_usable(item)]

            if not usable_faces:
                self.matched_user_name = None
                self.matched_user_score = None
                self.matched_user_info = None
                self.pre_challenge_frame = None
                self.last_face_labels = []
                self.reset_challenge()
                self.reset_score_smoothing()
                self.app_state = self.APP_VERIFY_ALIGN

            else:
                if do_recognition and len(self.named_gallery) > 0:
                    results = self.recognize_faces_in_items(face_items)
                    target = self.choose_challenge_target(results)

                    if target is not None:
                        self.set_matched_from_result(target)
                        self.pre_challenge_frame = frame.copy()

                        # Tanıma sonucu hangi yüz hedef seçildiyse,
                        # mesh ve pose bilgisini de aynı yüz üzerinden göster.
                        target_item_for_mesh = target.get("item")
                        if target_item_for_mesh is not None:
                            mesh_lmks = target_item_for_mesh.get("lmks")
                            mesh_box = target_item_for_mesh.get("box")

                            self.last_best_yaw = target_item_for_mesh.get("yaw")
                            self.last_pose_text = (
                                self.classify_pose_from_yaw(self.last_best_yaw)
                                if self.last_best_yaw is not None else "-"
                            )

                        started = self.start_random_challenge_for_result(target)
                        if started:
                            self.app_state = self.APP_VERIFY_CHALLENGE
                        else:
                            self.status_text = "Canlilik testi baslatilamadi. Tekrar deneyin."
                            self.status_time = time.time()
                    else:
                        self.status_text = "Eslesen kayit bulunamadi"
                        self.status_time = time.time()

        # =====================================================
        # VERIFY CHALLENGE
        # =====================================================
        elif self.app_state == self.APP_VERIFY_CHALLENGE:

            target_item = self.find_challenge_target_face(face_items)
            now = time.time()

            # Hedef yüz bulunamıyorsa hemen fail verme.
            # Kamera 1-2 frame yüzü kaçırabilir. 0.45 sn tolerans veriyoruz.
            if target_item is None:
                if self.challenge_target_lost_since is None:
                    self.challenge_target_lost_since = now

                lost_duration = now - self.challenge_target_lost_since

                if lost_duration >= self.CHALLENGE_TARGET_LOST_GRACE_SEC:
                    self.status_text = "Hedef yuz kayboldu. Canlilik basarisiz."
                    self.status_time = time.time()
                    self.trigger_liveness_failed()

            else:
                # Hedef tekrar bulunduysa kaybolma sayacını sıfırla.
                self.challenge_target_lost_since = None

                # Canlılıkta mesh, pose ve yaw kesinlikle hedef yüz üzerinden alınmalı.
                mesh_lmks = target_item.get("lmks")
                mesh_box = target_item.get("box")

                self.last_best_yaw = target_item.get("yaw")
                self.last_pose_text = (
                    self.classify_pose_from_yaw(self.last_best_yaw)
                    if self.last_best_yaw is not None else "-"
                )

                passed, timed_out = self.update_challenge_state(target_item.get("yaw"))

                if passed and self.matched_user_name is not None:
                    # Sağ/sol hareket doğru olsa bile, erişim vermeden önce
                    # hareketi yapan yüzün hâlâ aynı kayıtlı kişi olduğunu tekrar doğrula.
                    identity_ok = self.verify_challenge_target_identity(target_item)

                    if not identity_ok:
                        self.trigger_liveness_failed()
                    else:
                        if self.is_suspect_type(self.matched_person_type):
                            self.trigger_suspect_alert()
                        else:
                            self.app_state = self.APP_UNLOCKED
                            self.trigger_unlock()

                elif timed_out:
                    self.trigger_liveness_failed()

        # =====================================================
        # LIVENESS FAILED
        # =====================================================
        elif self.app_state == self.APP_LIVENESS_FAILED:
            # Başarısız mesajı PySide6 tarafında gösterilecek.
            # Kamera görüntüsüne OpenCV yazısı basmıyoruz.
            pass

        # =====================================================
        # UNLOCKED
        # =====================================================
        elif self.app_state == self.APP_UNLOCKED:

            if self.lock_state == self.STATE_LOCKED:
                self.matched_user_name = None
                self.matched_user_score = None
                self.matched_person_type = None
                self.matched_person_type_label = None
                self.matched_record_note = ""
                self.matched_user_info = None
                self.pre_challenge_frame = None
                self.last_face_labels = []
                self.last_recognition_results = []
                self.reset_challenge()
                self.reset_score_smoothing()

                # Giriş onayı bittikten sonra ana menüye değil,
                # tekrar yüz algılama / giriş tarama moduna dön.
                self.app_state = self.APP_VERIFY_ALIGN

        # =====================================================
        # ALERT
        # =====================================================
        elif self.app_state == self.APP_ALERT:
            # Şüpheli uyarısı PySide6 arayüzünde gösteriliyor.
            # Kamera görüntüsünün üstüne OpenCV ile ekstra kırmızı dikdörtgen/yazı basmıyoruz.
            pass

        # =====================================================
        # GÖRSEL ÇİZİMLER
        # =====================================================
        self.draw_last_face_labels(frame)

       # Challenge sırasında hedef kişinin üstünde sadece isim yazsın.
        if self.app_state == self.APP_VERIFY_CHALLENGE and self.challenge_target_box is not None:
            challenge_color = (0, 0, 255) if self.is_suspect_type(self.challenge_target_person_type) else (0, 200, 0)
            challenge_text = self.challenge_target_name or ""
            self.draw_face_label(frame, self.challenge_target_box, challenge_text, challenge_color)

        # Recognition ve state mantığı bittikten sonra mesh çiziliyor.
        # Kayıtta primary face kullanılır; giriş/canlılıkta tanınan/challenge hedef yüz kullanılır.
        if mesh_lmks is not None and mesh_box is not None:
            self.draw_decorative_mesh(frame, mesh_lmks, mesh_box)

        # =====================================================
        # FPS HESABI
        # =====================================================
        self.frame_count += 1
        elapsed = time.time() - self.fps_t0
        if elapsed >= 1.0:
            self.fps = self.frame_count / elapsed
            self.frame_count = 0
            self.fps_t0 = time.time()

        return True, frame

    def stop(self):
        if self.cap.isOpened():
            self.cap.release()
        GPIO.cleanup()
