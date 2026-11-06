from flask import Flask, render_template, request, redirect, session, flash, url_for
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import sqlite3
from db_layer import get_postgres_db
import re
import os
import secrets
import hashlib
import time
import smtplib
import ssl
from email.message import EmailMessage
import io
from uuid import uuid4
from pathlib import Path
from datetime import datetime, timedelta
from PIL import Image, UnidentifiedImageError
from course_data import PYTHON_COURSE
from python_final_data import PYTHON_FINAL
from javascript_final_data import JAVASCRIPT_FINAL

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "local-development-key")
app.config["MAX_CONTENT_LENGTH"] = 3 * 1024 * 1024
app.config["WTF_CSRF_ENABLED"] = True
app.config["WTF_CSRF_TIME_LIMIT"] = 3600

csrf = CSRFProtect(app)


# DEADY NEXUS - Oturum güvenliği
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("RENDER", "").lower() == "true",
)

# DEADY NEXUS - HTTP güvenlik başlıkları
@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=()"
    )

    if os.environ.get("RENDER", "").lower() == "true":
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000"
        )

    return response

DB_NAME = "academy.db"


def award_eligible_badges(db, user_id):
    db.execute("""
        INSERT OR IGNORE INTO user_badges (user_id, badge_id)
        SELECT ?, id FROM badges
        WHERE xp_required <= (
            SELECT xp FROM deady_users WHERE id = ?
        )
    """, (user_id, user_id))


def get_db():
    if os.environ.get("DATABASE_URL"):
        return get_postgres_db()

    db = sqlite3.connect(DB_NAME)
    db.row_factory = sqlite3.Row
    return db



def send_reset_email(recipient, reset_url):
    sender = os.environ.get("MAIL_USERNAME")
    password = os.environ.get("MAIL_APP_PASSWORD")

    if not sender or not password:
        raise RuntimeError("Gmail ortam değişkenleri ayarlanmamış.")

    message = EmailMessage()
    message["Subject"] = "DEADY SALVO - Şifre Yenileme"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(
        "Merhaba!\\n\\n"
        "DEADY SALVO hesabının şifresini yenilemek için bağlantıya tıkla:\\n"
        f"{reset_url}\\n\\n"
        "Bu bağlantı 30 dakika geçerlidir. "
        "Bu isteği sen yapmadıysan e-postayı dikkate alma."
    )

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(
        "smtp.gmail.com", 465, context=context, timeout=20
    ) as smtp:
        smtp.login(sender, password)
        smtp.send_message(message)



def send_verification_email(recipient, code):
    sender = os.environ.get("MAIL_USERNAME")
    password = os.environ.get("MAIL_APP_PASSWORD")

    if not sender or not password:
        raise RuntimeError("Gmail ortam değişkenleri ayarlanmamış.")

    message = EmailMessage()
    message["Subject"] = "DEADY NEXUS - E-posta Doğrulama"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(
        "DEADY NEXUS'a hoş geldin!\\n\\n"
        "E-posta doğrulama kodun: " + code + "\\n\\n"
        "Bu kod 5 dakika geçerlidir.\\n"
        "Kodu kimseyle paylaşma."
    )

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(
        "smtp.gmail.com", 465, context=context, timeout=20
    ) as smtp:
        smtp.login(sender, password)
        smtp.send_message(message)


def init_db():
    if os.environ.get("DATABASE_URL"):
        db = get_db()
        try:
            db.execute("""
                CREATE TABLE IF NOT EXISTS pending_email_verifications (
                    email TEXT PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    pending_membership TEXT,
                    code_hash TEXT NOT NULL,
                    expires_at BIGINT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_sent_at BIGINT NOT NULL
                )
            """)

            tables = [
                "deady_users", "users", "badges",
                "python_final_completions",
                "javascript_final_completions",
                "announcements", "password_reset_tokens",
                "coin_transactions", "private_messages",
                "user_badges"
            ]
            for table in tables:
                db.execute(f"SELECT 1 FROM {table} LIMIT 1")
            db.commit()
            print("Neon PostgreSQL tabloları doğrulandı.")
        finally:
            db.close()
        return

    db = get_db()

    db.execute("""
        CREATE TABLE IF NOT EXISTS pending_email_verifications (
            email TEXT PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            pending_membership TEXT,
            code_hash TEXT NOT NULL,
            expires_at INTEGER NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            last_sent_at INTEGER NOT NULL
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS deady_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL COLLATE NOCASE UNIQUE,
            password_hash TEXT NOT NULL,
            membership TEXT NOT NULL DEFAULT 'BAŞLANGIÇ',
            coins INTEGER NOT NULL DEFAULT 0,
            xp INTEGER NOT NULL DEFAULT 0,
            level INTEGER NOT NULL DEFAULT 1,
            last_daily_reward TEXT,
            profile_photo TEXT,
            email TEXT
        )
    """)

    columns = {
        row["name"]
        for row in db.execute("PRAGMA table_info(deady_users)").fetchall()
    }

    migrations = {
        "email": "TEXT",
        "coins": "INTEGER NOT NULL DEFAULT 0",
        "xp": "INTEGER NOT NULL DEFAULT 0",
        "level": "INTEGER NOT NULL DEFAULT 1",
        "last_daily_reward": "TEXT",
        "profile_photo": "TEXT",
        "pending_membership": "TEXT"
    }

    for column, definition in migrations.items():
        if column not in columns:
            db.execute(
                f"ALTER TABLE deady_users ADD COLUMN {column} {definition}"
            )

    db.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_deady_users_email
        ON deady_users(email COLLATE NOCASE)
        WHERE email IS NOT NULL AND email != ''
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS python_final_completions (
            user_id INTEGER PRIMARY KEY,
            score INTEGER NOT NULL,
            correct_answers INTEGER NOT NULL,
            completed_at TEXT NOT NULL
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS javascript_final_completions (
            user_id INTEGER PRIMARY KEY,
            score INTEGER NOT NULL,
            correct_answers INTEGER NOT NULL,
            completed_at TEXT NOT NULL
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS badges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            icon TEXT NOT NULL,
            xp_required INTEGER NOT NULL DEFAULT 0
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS user_badges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            badge_id INTEGER NOT NULL,
            earned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, badge_id),
            FOREIGN KEY(user_id) REFERENCES deady_users(id),
            FOREIGN KEY(badge_id) REFERENCES badges(id)
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS private_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            is_read INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(sender_id) REFERENCES deady_users(id),
            FOREIGN KEY(receiver_id) REFERENCES deady_users(id)
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            token_hash TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            expires_at TEXT NOT NULL,
            used_at TEXT,
            FOREIGN KEY(user_id) REFERENCES deady_users(id)
        )
    """)

    db.commit()
    db.close()


def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect("/login")

        admin_username = os.environ.get("ADMIN_USERNAME")

        if session.get("username") != admin_username:
            return "Bu sayfaya erişim yetkin yok!", 403

        return func(*args, **kwargs)
    return wrapper


def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Önce giriş yapmalısın.")
            return redirect("/login")
        return func(*args, **kwargs)
    return wrapper


courses = {
    "python": {
        "title": "🐍 Python Eğitimi",
        "description": "Sıfırdan Python programlamayı öğren!",
        "lessons": [
            ("Python'a Giriş", "Python nedir? İlk kodumuzu yazalım.", 'print("Merhaba DEADY SALVO!")'),
            ("Değişkenler", "Değişkenler veri saklamak için kullanılır.", 'isim = "Enes"\nyas = 20\nprint(isim)\nprint(yas)'),
            ("Sayılarla İşlemler", "Toplama, çıkarma, çarpma ve bölme.", 'a = 10\nb = 5\nprint(a + b)\nprint(a * b)'),
            ("If ve Else", "Koşullara göre işlem yapmayı öğren.", 'yas = 18\nif yas >= 18:\n    print("Giriş serbest")\nelse:\n    print("Giriş yasak")'),
            ("For ve While Döngüleri", "Tekrarlanan işlemleri otomatikleştir.", 'for i in range(5):\n    print(i)'),
            ("Fonksiyonlar", "Kendi komutlarımızı oluşturalım.", 'def selamla(isim):\n    print("Merhaba", isim)\n\nselamla("Enes")'),
            ("Random Modülü", "Rastgele sayılar ve seçimler yap.", 'import random\n\nsayi = random.randint(1, 100)\nprint(sayi)'),
            ("Random İsim Seçici", "Listeden rastgele isim seç.", 'import random\n\nisimler = ["Enes", "Ali", "Mehmet"]\nprint(random.choice(isimler))'),
            ("Rastgele Şifre", "Rastgele karakterlerle şifre oluştur.", 'import random\nimport string\n\nkarakterler = string.ascii_letters + string.digits\nsifre = "".join(random.choice(karakterler) for _ in range(12))\nprint(sifre)')
        ]
    },
    "web": {
        "title": "🌐 Web Tasarım Eğitimi",
        "description": "HTML, CSS ve JavaScript öğren!",
        "lessons": [
            ("HTML Başlangıç", "Web sayfasının temel yapısı.", '<h1>Merhaba Dünya</h1>\n<p>İlk web sayfam.</p>'),
            ("HTML Bağlantılar", "Sayfalara bağlantı ekle.", '<a href="https://example.com">Siteye git</a>'),
            ("CSS Başlangıç", "Sayfanın görünümünü değiştir.", 'body {\n    background: black;\n    color: white;\n}'),
            ("CSS Renkler", "Yazı ve arka plan renklerini ayarla.", 'h1 {\n    color: purple;\n}'),
            ("JavaScript Başlangıç", "JavaScript ile ekrana mesaj yaz.", 'console.log("Merhaba DEADY!")'),
            ("JavaScript Değişkenler", "let ve const kullanımını öğren.", 'let isim = "Enes";\nconst yas = 20;\nconsole.log(isim);'),
            ("JavaScript Fonksiyonlar", "Kendi fonksiyonunu oluştur.", 'function selamla() {\n    alert("Merhaba!");\n}\n\nselamla();'),
            ("JavaScript Random", "Rastgele sayı üret.", 'let sayi = Math.floor(Math.random() * 100) + 1;\nconsole.log(sayi);')
        ]
    },

}

courses["python"] = PYTHON_COURSE

@app.route("/python-final", methods=["GET", "POST"])
@login_required
def python_final():
    db = get_db()
    user_id = session["user_id"]
    completed = db.execute(
        "SELECT score, correct_answers FROM python_final_completions WHERE user_id = ?",
        (user_id,)
    ).fetchone()

    result = None

    if request.method == "POST":
        correct = 0
        blank = 0

        for i, question in enumerate(PYTHON_FINAL):
            answer = request.form.get(f"q{i}")

            if answer is None or answer == "":
                blank += 1
                continue

            try:
                if int(answer) == question["answer"]:
                    correct += 1
            except (ValueError, TypeError):
                pass

        wrong = len(PYTHON_FINAL) - correct - blank
        score = round(correct * 100 / len(PYTHON_FINAL))
        passed = correct >= 21
        rewarded = False

        if passed and completed is None:
            try:
                db.execute("BEGIN IMMEDIATE")
                db.execute("""
                    INSERT INTO python_final_completions
                    (user_id, score, correct_answers, completed_at)
                    VALUES (?, ?, ?, ?)
                """, (user_id, score, correct, datetime.now().isoformat(timespec="seconds")))

                user = db.execute(
                    "SELECT xp FROM deady_users WHERE id = ?", (user_id,)
                ).fetchone()

                if user is None:
                    raise ValueError("Kullanıcı bulunamadı.")

                new_xp = user["xp"] + 100
                new_level = (new_xp // 100) + 1

                db.execute("""
                    UPDATE deady_users
                    SET coins = coins + 50, xp = ?, level = ?
                    WHERE id = ?
                """, (new_xp, new_level, user_id))

                db.execute("""
                    INSERT INTO coin_transactions (user_id, amount, reason)
                    VALUES (?, 50, ?)
                """, (user_id, "Python final sınavı ödülü"))

                award_eligible_badges(db, user_id)
                db.commit()
                rewarded = True
                completed = {"score": score, "correct_answers": correct}
            except Exception:
                db.rollback()
                db.close()
                raise

        elif passed:
            db.commit()
        else:
            db.commit()

        result = {
            "correct": correct,
            "wrong": wrong,
            "blank": blank,
            "score": score,
            "passed": passed,
            "rewarded": rewarded,
            "already_rewarded": passed and not rewarded
        }

    db.close()
    return render_template(
        "python_final.html",
        questions=PYTHON_FINAL,
        result=result,
        completed=completed
    )





@app.route("/javascript-final", methods=["GET", "POST"])
@login_required
def javascript_final():
    db = get_db()
    user_id = session["user_id"]

    completed = db.execute(
        "SELECT score, correct_answers FROM javascript_final_completions WHERE user_id = ?",
        (user_id,)
    ).fetchone()

    result = None

    if request.method == "POST":
        correct = 0
        blank = 0

        for i, question in enumerate(JAVASCRIPT_FINAL):
            answer = request.form.get(f"q{i}")

            if answer is None or answer == "":
                blank += 1
                continue

            try:
                if int(answer) == question["answer"]:
                    correct += 1
            except (ValueError, TypeError):
                pass

        wrong = len(JAVASCRIPT_FINAL) - correct - blank
        score = round(correct * 100 / len(JAVASCRIPT_FINAL))
        passed = correct >= 21
        rewarded = False

        if passed and completed is None:
            try:
                db.execute("BEGIN IMMEDIATE")

                db.execute("""
                    INSERT INTO javascript_final_completions
                    (user_id, score, correct_answers, completed_at)
                    VALUES (?, ?, ?, ?)
                """, (
                    user_id,
                    score,
                    correct,
                    datetime.now().isoformat(timespec="seconds")
                ))

                user = db.execute(
                    "SELECT xp FROM deady_users WHERE id = ?",
                    (user_id,)
                ).fetchone()

                if user is None:
                    raise ValueError("Kullanıcı bulunamadı.")

                new_xp = user["xp"] + 100
                new_level = (new_xp // 100) + 1

                db.execute("""
                    UPDATE deady_users
                    SET coins = coins + 50, xp = ?, level = ?
                    WHERE id = ?
                """, (new_xp, new_level, user_id))

                db.execute("""
                    INSERT INTO coin_transactions (user_id, amount, reason)
                    VALUES (?, 50, ?)
                """, (user_id, "JavaScript final sınavı ödülü"))

                award_eligible_badges(db, user_id)
                db.commit()

                rewarded = True
                completed = {
                    "score": score,
                    "correct_answers": correct
                }

            except Exception:
                db.rollback()
                db.close()
                raise

        result = {
            "correct": correct,
            "wrong": wrong,
            "blank": blank,
            "score": score,
            "passed": passed,
            "rewarded": rewarded,
            "already_rewarded": passed and not rewarded
        }

    db.close()

    return render_template(
        "javascript_final.html",
        questions=JAVASCRIPT_FINAL,
        result=result,
        completed=completed
    )


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()

        db = get_db()
        try:
            user = db.execute(
                "SELECT id, email FROM deady_users WHERE email = ? COLLATE NOCASE",
                (email,)
            ).fetchone()

            if user and user["email"]:
                token = secrets.token_urlsafe(32)
                token_hash = hashlib.sha256(token.encode()).hexdigest()
                now = datetime.now()
                expires = (now + timedelta(minutes=30)).isoformat(
                    timespec="seconds"
                )

                db.execute(
                    "DELETE FROM password_reset_tokens WHERE user_id = ?",
                    (user["id"],)
                )
                db.execute(
                    """INSERT INTO password_reset_tokens
                       (token_hash, user_id, expires_at)
                       VALUES (?, ?, ?)""",
                    (token_hash, user["id"], expires)
                )
                db.commit()

                base_url = os.environ.get("APP_BASE_URL", "").rstrip("/")
                if base_url:
                    reset_url = (
                        base_url + url_for("reset_password", token=token)
                    )
                else:
                    reset_url = url_for(
                        "reset_password", token=token, _external=True
                    )

                try:
                    send_reset_email(user["email"], reset_url)
                except Exception:
                    db.execute(
                        "DELETE FROM password_reset_tokens WHERE token_hash = ?",
                        (token_hash,)
                    )
                    db.commit()
        finally:
            db.close()

        flash(
            "Bu e-posta kayıtlıysa şifre yenileme bağlantısı gönderilecektir."
        )
        return redirect("/forgot-password")

    return render_template("forgot_password.html")


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    now = datetime.now().isoformat(timespec="seconds")

    db = get_db()
    try:
        reset_record = db.execute(
            """SELECT user_id FROM password_reset_tokens
               WHERE token_hash = ? AND used_at IS NULL
               AND expires_at > ?""",
            (token_hash, now)
        ).fetchone()

        if not reset_record:
            flash("Bağlantı geçersiz veya süresi dolmuş.")
            return redirect("/forgot-password")

        if request.method == "POST":
            password = request.form.get("password", "")
            confirm = request.form.get("confirm_password", "")

            if len(password) < 8:
                flash("Şifre en az 8 karakter olmalı.")
                return redirect(request.path)

            if password != confirm:
                flash("Şifreler eşleşmiyor.")
                return redirect(request.path)

            db.execute(
                "UPDATE deady_users SET password_hash = ? WHERE id = ?",
                (generate_password_hash(password), reset_record["user_id"])
            )
            db.execute(
                """UPDATE password_reset_tokens SET used_at = ?
                   WHERE user_id = ? AND used_at IS NULL""",
                (now, reset_record["user_id"])
            )
            db.commit()
            flash("Şifren başarıyla yenilendi. Giriş yapabilirsin.")
            return redirect("/login")

        return render_template("reset_password.html")
    finally:
        db.close()


@app.route("/")
def home():
    return render_template("index.html")



@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        selected = request.form.get("membership", "BAŞLANGIÇ").strip().upper()

        allowed_packages = {"BAŞLANGIÇ", "GÜMÜŞ", "ALTIN", "ELMAS", "EFSANE"}

        if selected not in allowed_packages:
            flash("Geçersiz üyelik paketi.")
            return redirect("/register")

        if not re.fullmatch(r"[A-Za-z0-9_]{3,20}", username):
            flash("Kullanıcı adı 3-20 karakter olmalı.")
            return redirect("/register")

        if not re.fullmatch(r"[^@\s]+@[^@\s.]+(?:\.[^@\s.]+)+", email):
            flash("Geçerli bir e-posta adresi gir.")
            return redirect("/register")

        if len(password) < 8:
            flash("Şifre en az 8 karakter olmalı.")
            return redirect("/register")

        db = get_db()
        try:
            existing = db.execute(
                "SELECT id FROM deady_users WHERE username = ? OR email = ?",
                (username, email)
            ).fetchone()

            if existing:
                flash("Bu kullanıcı adı veya e-posta zaten kullanılıyor.")
                return redirect("/register")

            pending = db.execute(
                "SELECT email, username, last_sent_at FROM pending_email_verifications WHERE email = ? OR username = ?",
                (email, username)
            ).fetchone()

            now = int(time.time())

            if pending:
                same_account = (
                    pending["email"].lower() == email
                    and pending["username"].lower() == username.lower()
                )

                if not same_account:
                    flash("Bu kullanıcı adı veya e-posta başka bir bekleyen kayıtta kullanılıyor.")
                    return redirect("/register")

                if now - int(pending["last_sent_at"]) < 60:
                    session["pending_verification_email"] = email
                    flash("Doğrulama kodu zaten gönderildi. E-postanı kontrol et.")
                    return redirect("/verify-email")

                db.execute(
                    "DELETE FROM pending_email_verifications WHERE email = ?",
                    (email,)
                )

            code = f"{secrets.randbelow(1000000):06d}"
            code_hash = hashlib.sha256(
                (app.secret_key + code).encode()
            ).hexdigest()

            db.execute(
                """INSERT INTO pending_email_verifications
                (email, username, password_hash, pending_membership,
                 code_hash, expires_at, attempts, last_sent_at)
                VALUES (?, ?, ?, ?, ?, ?, 0, ?)""",
                (
                    email,
                    username,
                    generate_password_hash(password),
                    None if selected == "BAŞLANGIÇ" else selected,
                    code_hash,
                    now + 300,
                    now
                )
            )
            db.commit()

            try:
                send_verification_email(email, code)
            except Exception:
                db.execute(
                    "DELETE FROM pending_email_verifications WHERE email = ?",
                    (email,)
                )
                db.commit()
                flash("E-posta gönderilemedi. E-posta ayarlarını kontrol et.")
                return redirect("/register")

            session["pending_verification_email"] = email
            flash("6 haneli doğrulama kodu e-posta adresine gönderildi.")
            return redirect("/verify-email")

        except sqlite3.IntegrityError:
            db.rollback()
            flash("Bu kullanıcı adı veya e-posta zaten kullanılıyor.")
            return redirect("/register")
        finally:
            db.close()

    selected = request.args.get("paket", "BAŞLANGIÇ").strip().upper()
    allowed = {"BAŞLANGIÇ", "GÜMÜŞ", "ALTIN", "ELMAS", "EFSANE"}
    if selected not in allowed:
        selected = "BAŞLANGIÇ"

    return render_template("register.html", selected_package=selected)


@app.route("/verify-email", methods=["GET", "POST"])
def verify_email():
    email = session.get("pending_verification_email")

    if not email:
        flash("Önce kayıt işlemini başlatmalısın.")
        return redirect("/register")

    db = get_db()

    try:
        pending = db.execute(
            "SELECT * FROM pending_email_verifications WHERE email = ?",
            (email,)
        ).fetchone()

        if not pending:
            session.pop("pending_verification_email", None)
            flash("Bekleyen doğrulama kaydı bulunamadı. Yeniden kayıt ol.")
            return redirect("/register")

        now = int(time.time())

        if request.method == "POST":
            action = request.form.get("action", "verify")

            if action == "resend":
                if now - int(pending["last_sent_at"]) < 60:
                    flash("Yeni kod istemeden önce 60 saniye beklemelisin.")
                    return redirect("/verify-email")

                code = f"{secrets.randbelow(1000000):06d}"
                code_hash = hashlib.sha256(
                    (app.secret_key + code).encode()
                ).hexdigest()

                try:
                    send_verification_email(email, code)
                except Exception:
                    flash("E-posta gönderilemedi. Biraz sonra tekrar dene.")
                    return redirect("/verify-email")

                db.execute(
                    """UPDATE pending_email_verifications
                    SET code_hash = ?, expires_at = ?, attempts = 0, last_sent_at = ?
                    WHERE email = ?""",
                    (code_hash, now + 300, now, email)
                )
                db.commit()
                flash("Yeni doğrulama kodu gönderildi. Kod 5 dakika geçerlidir.")
                return redirect("/verify-email")

            if now > int(pending["expires_at"]):
                db.execute(
                    "DELETE FROM pending_email_verifications WHERE email = ?",
                    (email,)
                )
                db.commit()
                session.pop("pending_verification_email", None)
                flash("Kodun süresi doldu. Lütfen yeniden kayıt ol.")
                return redirect("/register")

            if int(pending["attempts"]) >= 5:
                db.execute(
                    "DELETE FROM pending_email_verifications WHERE email = ?",
                    (email,)
                )
                db.commit()
                session.pop("pending_verification_email", None)
                flash("Çok fazla hatalı deneme yaptın. Yeniden kayıt ol.")
                return redirect("/register")

            submitted_code = request.form.get("code", "").strip()

            if not re.fullmatch(r"\d{6}", submitted_code):
                flash("6 haneli doğrulama kodunu gir.")
                return redirect("/verify-email")

            submitted_hash = hashlib.sha256(
                (app.secret_key + submitted_code).encode()
            ).hexdigest()

            if not secrets.compare_digest(submitted_hash, pending["code_hash"]):
                attempts = int(pending["attempts"]) + 1

                if attempts >= 5:
                    db.execute(
                        "DELETE FROM pending_email_verifications WHERE email = ?",
                        (email,)
                    )
                    db.commit()
                    session.pop("pending_verification_email", None)
                    flash("5 hatalı deneme yaptın. Yeniden kayıt ol.")
                    return redirect("/register")

                db.execute(
                    "UPDATE pending_email_verifications SET attempts = ? WHERE email = ?",
                    (attempts, email)
                )
                db.commit()
                flash(f"Doğrulama kodu hatalı. Kalan deneme hakkı: {5 - attempts}")
                return redirect("/verify-email")

            try:
                db.execute(
                    """INSERT INTO deady_users
                    (username, email, password_hash, pending_membership)
                    VALUES (?, ?, ?, ?)""",
                    (
                        pending["username"],
                        pending["email"],
                        pending["password_hash"],
                        pending["pending_membership"]
                    )
                )
                db.commit()

                user = db.execute(
                    "SELECT id, username FROM deady_users WHERE username = ?",
                    (pending["username"],)
                ).fetchone()

                award_eligible_badges(db, user["id"])

                db.execute(
                    "DELETE FROM pending_email_verifications WHERE email = ?",
                    (email,)
                )
                db.commit()

                session.clear()
                session["user_id"] = user["id"]
                session["username"] = user["username"]

                flash("E-posta doğrulandı. Hesabın başarıyla oluşturuldu!")
                return redirect("/dashboard")

            except sqlite3.IntegrityError:
                db.rollback()
                db.execute(
                    "DELETE FROM pending_email_verifications WHERE email = ?",
                    (email,)
                )
                db.commit()
                session.pop("pending_verification_email", None)
                flash("Bu kullanıcı adı veya e-posta zaten kullanılıyor.")
                return redirect("/register")

        return render_template("verify_email.html", email=email)

    finally:
        db.close()


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        db = get_db()
        try:
            user = db.execute(
                "SELECT * FROM deady_users WHERE username = ?",
                (username,)
            ).fetchone()
        finally:
            db.close()

        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            flash("Başarıyla giriş yaptın!")
            return redirect("/dashboard")

        flash("Kullanıcı adı veya şifre hatalı.")

    return render_template("login.html")


@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    try:
        user = db.execute(
            "SELECT username, membership, coins, xp, level, last_daily_reward, profile_photo "
            "FROM deady_users WHERE id = ?",
            (session["user_id"],)
        ).fetchone()

        if user is not None:
            db.execute("""
                INSERT OR IGNORE INTO user_badges (user_id, badge_id)
                SELECT ?, id FROM badges
                WHERE xp_required <= (
                    SELECT xp FROM deady_users WHERE id = ?
                )
            """, (session["user_id"], session["user_id"]))

            earned_badges = db.execute("""
                SELECT b.name, b.description, b.icon
                FROM user_badges ub
                JOIN badges b ON b.id = ub.badge_id
                WHERE ub.user_id = ?
                ORDER BY ub.earned_at DESC
            """, (session["user_id"],)).fetchall()

            db.commit()
        else:
            earned_badges = []

        announcements = db.execute("""
            SELECT id, title, content, created_at
            FROM announcements
            ORDER BY id DESC
            LIMIT 10
        """).fetchall()

        unread_messages = db.execute(
            "SELECT COUNT(*) FROM private_messages WHERE receiver_id = ? AND is_read = 0",
            (session["user_id"],)
        ).fetchone()[0]

    finally:
        db.close()

    if user is None:
        session.clear()
        return redirect("/login")

    today = datetime.now().date().isoformat()

    return render_template(
        "dashboard.html",
        username=user["username"],
        earned_badges=earned_badges,
        profile_photo=user["profile_photo"],
        membership=user["membership"],
        coins=user["coins"],
        xp=user["xp"],
        level=user["level"],
        xp_progress=user["xp"] % 100,
        xp_to_next=100 - (user["xp"] % 100),
        daily_claimed=(user["last_daily_reward"] == today),
        announcements=announcements,
        unread_messages=unread_messages
    )


@app.route("/daily-reward", methods=["POST"])
@login_required
def daily_reward():
    today = datetime.now().date().isoformat()
    db = get_db()

    try:
        db.execute("BEGIN IMMEDIATE")

        user = db.execute(
            "SELECT coins, xp, last_daily_reward FROM deady_users WHERE id = ?",
            (session["user_id"],)
        ).fetchone()

        if user is None:
            db.rollback()
            session.clear()
            return redirect("/login")

        if user["last_daily_reward"] == today:
            db.rollback()
            flash("Günlük ödülünü bugün zaten aldın.")
            return redirect("/dashboard")

        new_xp = user["xp"] + 25
        new_level = (new_xp // 100) + 1

        db.execute(
            """UPDATE deady_users
               SET coins = coins + 10,
                   xp = ?,
                   level = ?,
                   last_daily_reward = ?
               WHERE id = ?""",
            (new_xp, new_level, today, session["user_id"])
        )

        db.execute(
            """INSERT INTO coin_transactions (user_id, amount, reason)
               VALUES (?, 10, ?)""",
            (session["user_id"], "Günlük giriş ödülü")
        )

        award_eligible_badges(db, session["user_id"])
        db.commit()
        flash("Tebrikler! 10 DEADY COINS ve 25 XP kazandın.")

    except Exception:
        db.rollback()
        app.logger.exception("Günlük ödül işlemi başarısız.")
        flash("Ödül alınırken bir hata oluştu.")
    finally:
        db.close()

    return redirect("/dashboard")



@app.route("/upload-profile-photo", methods=["POST"])
@login_required
def upload_profile_photo():
    uploaded = request.files.get("photo")

    if not uploaded or not uploaded.filename:
        flash("Önce bir fotoğraf seçmelisin.")
        return redirect("/profile")

    data = uploaded.read(3 * 1024 * 1024 + 1)

    if not data or len(data) > 3 * 1024 * 1024:
        flash("Fotoğraf en fazla 3 MB olabilir.")
        return redirect("/profile")

    try:
        Image.MAX_IMAGE_PIXELS = 20_000_000

        with Image.open(io.BytesIO(data)) as image:
            if image.format not in ("JPEG", "PNG", "WEBP"):
                raise ValueError("Desteklenmeyen fotoğraf formatı.")
            image.verify()

        with Image.open(io.BytesIO(data)) as image:
            image.load()
            image.thumbnail((1000, 1000))

            image_format = image.format
            extension = {
                "JPEG": "jpg",
                "PNG": "png",
                "WEBP": "webp"
            }[image_format]

            if image_format == "JPEG":
                image = image.convert("RGB")
            elif image_format == "PNG" and image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGBA")

            folder = Path(app.static_folder) / "uploads" / "profiles"
            folder.mkdir(parents=True, exist_ok=True)

            filename = f"{uuid4().hex}.{extension}"
            destination = folder / filename

            save_options = {"optimize": True}
            if image_format == "JPEG":
                save_options["quality"] = 88

            image.save(destination, format=image_format, **save_options)

        relative_path = f"uploads/profiles/{filename}"

        db = get_db()
        try:
            old = db.execute(
                "SELECT profile_photo FROM deady_users WHERE id = ?",
                (session["user_id"],)
            ).fetchone()

            db.execute(
                "UPDATE deady_users SET profile_photo = ? WHERE id = ?",
                (relative_path, session["user_id"])
            )
            db.commit()

            old_photo = old["profile_photo"] if old else None

        except Exception:
            db.rollback()
            destination.unlink(missing_ok=True)
            raise
        finally:
            db.close()

        if old_photo and old_photo.startswith("uploads/profiles/"):
            old_path = (Path(app.static_folder) / old_photo).resolve()
            safe_folder = (Path(app.static_folder) / "uploads" / "profiles").resolve()

            if old_path.parent == safe_folder and old_path != destination.resolve():
                old_path.unlink(missing_ok=True)

        flash("Profil fotoğrafın başarıyla güncellendi!")

    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        flash("Geçerli bir JPG, PNG veya WebP fotoğrafı seçmelisin.")
    except Exception:
        app.logger.exception("Profil fotoğrafı yüklenemedi.")
        flash("Fotoğraf yüklenirken bir hata oluştu.")

    return redirect("/profile")

@app.route("/profile")
@login_required
def profile():
    db = get_db()
    try:
        user = db.execute(
            """SELECT id, username, membership, coins, xp, level, profile_photo
               FROM deady_users WHERE id = ?""",
            (session["user_id"],)
        ).fetchone()

        if user is None:
            session.clear()
            return redirect("/login")

        transactions = db.execute(
            """SELECT amount, reason, created_at
               FROM coin_transactions
               WHERE user_id = ?
               ORDER BY id DESC LIMIT 10""",
            (session["user_id"],)
        ).fetchall()

        badges = db.execute("""
            SELECT b.name, b.description, b.icon, ub.earned_at
            FROM user_badges ub
            JOIN badges b ON b.id = ub.badge_id
            WHERE ub.user_id = ?
            ORDER BY ub.earned_at DESC
        """, (session["user_id"],)).fetchall()

        python_exam = db.execute("""
            SELECT score, correct_answers, completed_at
            FROM python_final_completions
            WHERE user_id = ?
        """, (session["user_id"],)).fetchone()

        javascript_exam = db.execute("""
            SELECT score, correct_answers, completed_at
            FROM javascript_final_completions
            WHERE user_id = ?
        """, (session["user_id"],)).fetchone()

    finally:
        db.close()

    xp_progress = user["xp"] % 100
    xp_to_next = 100 - xp_progress

    return render_template(
        "profile.html",
        user=user,
        deady_id=f"DS-{user['id']:06d}",
        transactions=transactions,
        badges=badges,
        python_exam=python_exam,
        javascript_exam=javascript_exam,
        xp_progress=xp_progress,
        xp_to_next=xp_to_next
    )


@app.route("/course/<course_id>")
@login_required
def course_page(course_id):
    course = courses.get(course_id)
    if course is None:
        return "Ders bulunamadı.", 404
    return render_template("course.html", course=course)


@app.route("/html-baslangic")
@login_required
def html_baslangic():
    return render_template("html_baslangic.html")



@app.route("/messages", methods=["GET", "POST"])
@login_required
def messages():
    db = get_db()
    admin_username = os.environ.get("ADMIN_USERNAME")
    is_admin = bool(admin_username and session.get("username") == admin_username)

    admin_user = db.execute(
        "SELECT id FROM deady_users WHERE username = ?",
        (admin_username,)
    ).fetchone() if admin_username else None

    if not admin_user:
        db.close()
        return "Admin hesabı bulunamadı.", 403

    admin_id = admin_user["id"]
    selected_id = None

    if is_admin:
        students = db.execute(
            "SELECT id, username FROM deady_users WHERE id != ? ORDER BY username",
            (admin_id,)
        ).fetchall()
        selected_id = request.args.get("user", type=int)
        if request.method == "POST":
            selected_id = request.form.get("receiver_id", type=int)
    else:
        students = []
        selected_id = admin_id

    if request.method == "POST":
        content = request.form.get("content", "").strip()

        if is_admin:
            receiver_id = selected_id
        else:
            receiver_id = admin_id

        valid_receiver = db.execute(
            "SELECT id FROM deady_users WHERE id = ?",
            (receiver_id,)
        ).fetchone() if receiver_id else None

        if content and len(content) <= 2000 and valid_receiver:
            db.execute(
                "INSERT INTO private_messages (sender_id, receiver_id, content) VALUES (?, ?, ?)",
                (session["user_id"], receiver_id, content)
            )
            db.commit()
            db.close()
            if is_admin:
                return redirect(url_for("messages", user=receiver_id))
            return redirect(url_for("messages"))

        flash("Mesaj boş olamaz veya alıcı seçilmelidir.")
        db.close()
        return redirect(url_for("messages"))

    if is_admin and selected_id:
        db.execute(
            "UPDATE private_messages SET is_read = 1 WHERE sender_id = ? AND receiver_id = ?",
            (selected_id, admin_id)
        )
        db.commit()
        conversation = db.execute("""
            SELECT m.*, s.username AS sender_name, r.username AS receiver_name
            FROM private_messages m
            JOIN deady_users s ON s.id = m.sender_id
            JOIN deady_users r ON r.id = m.receiver_id
            WHERE (m.sender_id = ? AND m.receiver_id = ?)
               OR (m.sender_id = ? AND m.receiver_id = ?)
            ORDER BY m.id ASC
        """, (selected_id, admin_id, admin_id, selected_id)).fetchall()
    elif not is_admin:
        db.execute(
            "UPDATE private_messages SET is_read = 1 WHERE sender_id = ? AND receiver_id = ?",
            (admin_id, session["user_id"])
        )
        db.commit()
        conversation = db.execute("""
            SELECT m.*, s.username AS sender_name, r.username AS receiver_name
            FROM private_messages m
            JOIN deady_users s ON s.id = m.sender_id
            JOIN deady_users r ON r.id = m.receiver_id
            WHERE (m.sender_id = ? AND m.receiver_id = ?)
               OR (m.sender_id = ? AND m.receiver_id = ?)
            ORDER BY m.id ASC
        """, (admin_id, session["user_id"], session["user_id"], admin_id)).fetchall()
    else:
        conversation = []

    unread = db.execute(
        "SELECT COUNT(*) FROM private_messages WHERE receiver_id = ? AND is_read = 0",
        (session["user_id"],)
    ).fetchone()[0]

    db.close()
    return render_template(
        "messages.html",
        is_admin=is_admin,
        students=students,
        selected_id=selected_id,
        conversation=conversation,
        unread=unread
    )


@app.route("/logout")
def logout():
    session.clear()
    flash("Çıkış yaptın.")
    return redirect("/")



@app.route("/admin", methods=["GET", "POST"])
@admin_required
def admin():
    db = get_db()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()

        if title and content:
            db.execute(
                "INSERT INTO announcements (title, content) VALUES (?, ?)",
                (title, content)
            )
            db.commit()
            flash("Duyuru yayınlandı!")
        else:
            flash("Başlık ve içerik boş bırakılamaz.")
        db.close()
        return redirect("/admin")

    users = db.execute("""
        SELECT id, username, membership, pending_membership,
               coins, xp, level FROM deady_users ORDER BY id DESC
    """).fetchall()

    stats = db.execute("""
        SELECT COUNT(*) AS total_users,
        COALESCE(SUM(xp), 0) AS total_xp,
        COALESCE(SUM(coins), 0) AS total_coins,
        COALESCE(SUM(CASE WHEN pending_membership IS NOT NULL
        AND pending_membership != '' THEN 1 ELSE 0 END), 0) AS pending_count
        FROM deady_users
    """).fetchone()

    membership_counts = db.execute("""
        SELECT membership, COUNT(*) AS total
        FROM deady_users GROUP BY membership
    """).fetchall()

    announcements = db.execute("""
        SELECT id, title, content, created_at
        FROM announcements ORDER BY id DESC
    """).fetchall()

    unread_messages = db.execute(
        "SELECT COUNT(*) FROM private_messages WHERE receiver_id = ? AND is_read = 0",
        (session["user_id"],)
    ).fetchone()[0]

    db.close()

    return render_template(
        "admin.html", users=users,
        total_users=stats["total_users"],
        total_xp=stats["total_xp"],
        total_coins=stats["total_coins"],
        pending_count=stats["pending_count"],
        membership_counts=membership_counts,
        announcements=announcements,
        unread_messages=unread_messages
    )


@app.route("/admin/announcement/<int:announcement_id>/delete", methods=["POST"])
@admin_required
def delete_announcement(announcement_id):
    db = get_db()
    db.execute("DELETE FROM announcements WHERE id = ?", (announcement_id,))
    db.commit()
    db.close()
    flash("Duyuru silindi.")
    return redirect("/admin")



@app.route("/admin/membership/<int:user_id>/<action>", methods=["POST"])
@admin_required
def admin_membership_action(user_id, action):
    db = get_db()
    try:
        user = db.execute(
            "SELECT pending_membership FROM deady_users WHERE id = ?",
            (user_id,)
        ).fetchone()

        if user is None or not user["pending_membership"]:
            flash("Bekleyen başvuru bulunamadı.")
        elif action == "approve":
            db.execute("""
                UPDATE deady_users
                SET membership = ?, pending_membership = NULL
                WHERE id = ?
            """, (user["pending_membership"], user_id))
            db.commit()
            flash("Üyelik başvurusu onaylandı.")
        elif action == "reject":
            db.execute("""
                UPDATE deady_users
                SET pending_membership = NULL
                WHERE id = ?
            """, (user_id,))
            db.commit()
            flash("Üyelik başvurusu reddedildi.")
        else:
            flash("Geçersiz işlem.")
    finally:
        db.close()

    return redirect("/admin")


@app.route("/admin/member/<int:user_id>/update", methods=["POST"])
@admin_required
def admin_update_member(user_id):
    db = get_db()
    try:
        user = db.execute(
            "SELECT id, username, membership, coins, xp FROM deady_users WHERE id = ?",
            (user_id,)
        ).fetchone()

        if user is None:
            flash("Üye bulunamadı.")
            return redirect("/admin")

        try:
            xp_change = int(request.form.get("xp_change", "0"))
            coin_change = int(request.form.get("coin_change", "0"))
        except (TypeError, ValueError):
            flash("XP ve coin alanlarına geçerli sayı gir.")
            return redirect("/admin")

        if abs(xp_change) > 100000 or abs(coin_change) > 100000:
            flash("İşlem limiti 100.000.")
            return redirect("/admin")

        new_xp = user["xp"] + xp_change
        new_coins = user["coins"] + coin_change

        if new_xp < 0 or new_coins < 0:
            flash("XP veya coin bakiyesi sıfırın altına inemez.")
            return redirect("/admin")

        membership = request.form.get(
            "membership", user["membership"] or "BAŞLANGIÇ"
        ).strip().upper()

        allowed_packages = {
            "BAŞLANGIÇ", "GÜMÜŞ", "ALTIN", "ELMAS", "EFSANE"
        }

        if membership not in allowed_packages:
            flash("Geçersiz üyelik paketi.")
            return redirect("/admin")

        new_level = (new_xp // 100) + 1

        db.execute("""
            UPDATE deady_users
            SET xp = ?, level = ?, coins = ?, membership = ?
            WHERE id = ?
        """, (new_xp, new_level, new_coins, membership, user_id))

        if coin_change != 0:
            db.execute("""
                INSERT INTO coin_transactions (user_id, amount, reason)
                VALUES (?, ?, ?)
            """, (
                user_id,
                coin_change,
                "Yönetici tarafından düzenlendi"
            ))

        if xp_change > 0:
            award_eligible_badges(db, user_id)

        db.commit()
        flash(f"{user['username']} hesabı güncellendi.")

    except Exception:
        db.rollback()
        app.logger.exception("Yönetici üye güncelleme hatası.")
        flash("İşlem sırasında hata oluştu.")
    finally:
        db.close()

    return redirect("/admin")

init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
