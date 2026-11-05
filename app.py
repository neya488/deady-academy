from flask import Flask, render_template, request, redirect, session, flash, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import sqlite3
import re
import os
import secrets
import hashlib
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

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "local-development-key")
app.config["MAX_CONTENT_LENGTH"] = 3 * 1024 * 1024

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


def init_db():
    db = get_db()

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
            db.execute(
                "INSERT INTO deady_users (username, email, password_hash, pending_membership) VALUES (?, ?, ?, ?)",
                (
                    username,
                    email,
                    generate_password_hash(password),
                    None if selected == "BAŞLANGIÇ" else selected
                )
            )
            db.commit()

            user = db.execute(
                "SELECT id, username FROM deady_users WHERE username = ?",
                (username,)
            ).fetchone()

            award_eligible_badges(db, user["id"])
            db.commit()

            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            flash("Hesabın başarıyla oluşturuldu!")
            return redirect("/dashboard")

        except sqlite3.IntegrityError:
            flash("Bu kullanıcı adı veya e-posta zaten kullanılıyor.")
            return redirect("/register")
        finally:
            db.close()

    selected = request.args.get("paket", "BAŞLANGIÇ").strip().upper()
    allowed = {"BAŞLANGIÇ", "GÜMÜŞ", "ALTIN", "ELMAS", "EFSANE"}
    if selected not in allowed:
        selected = "BAŞLANGIÇ"

    return render_template("register.html", selected_package=selected)


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
        daily_claimed=(user["last_daily_reward"] == today)
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
    finally:
        db.close()

    return render_template(
        "profile.html",
        user=user,
        deady_id=f"DS-{user['id']:06d}",
        transactions=transactions
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


@app.route("/logout")
def logout():
    session.clear()
    flash("Çıkış yaptın.")
    return redirect("/")


@app.route("/admin")
@admin_required
def admin():
    db = get_db()

    users = db.execute("""
        SELECT id, username, membership, pending_membership,
               coins, xp, level
        FROM deady_users
        ORDER BY id DESC
    """).fetchall()

    stats = db.execute("""
        SELECT
            COUNT(*) AS total_users,
            COALESCE(SUM(xp), 0) AS total_xp,
            COALESCE(SUM(coins), 0) AS total_coins,
            COALESCE(SUM(
                CASE WHEN pending_membership IS NOT NULL
                AND pending_membership != '' THEN 1 ELSE 0 END
            ), 0) AS pending_count
        FROM deady_users
    """).fetchone()

    membership_counts = db.execute("""
        SELECT membership, COUNT(*) AS total
        FROM deady_users
        GROUP BY membership
    """).fetchall()

    db.close()

    return render_template(
        "admin.html",
        users=users,
        total_users=stats["total_users"],
        total_xp=stats["total_xp"],
        total_coins=stats["total_coins"],
        pending_count=stats["pending_count"],
        membership_counts=membership_counts
    )

init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
