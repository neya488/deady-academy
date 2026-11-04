from flask import Flask, render_template, request, redirect, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import sqlite3
import re
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "local-development-key")

DB_NAME = "academy.db"


def get_db():
    db = sqlite3.connect(DB_NAME)
    db.row_factory = sqlite3.Row
    return db


def init_db():
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS deady_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL COLLATE NOCASE UNIQUE,
            password_hash TEXT NOT NULL,
            membership TEXT NOT NULL DEFAULT 'BAŞLANGIÇ'
        )
    """)
    db.commit()
    db.close()


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
    "ai": {
        "title": "🤖 Yapay Zekâ Eğitimi",
        "description": "Yapay zekânın temel mantığını keşfet!",
        "lessons": [
            ("Yapay Zekâ Nedir?", "Yapay zekânın ne olduğunu öğren.", 'Yapay zekâ, verilerden öğrenebilen sistemler geliştirme alanıdır.'),
            ("Makine Öğrenmesi", "Bilgisayarların verilerden öğrenme mantığı.", 'Veri → Öğrenme → Tahmin'),
            ("Python ve Yapay Zekâ", "Python ile yapay zekâ projelerine giriş.", 'print("Yapay zekâ öğreniyorum!")')
        ]
    }
}

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not re.fullmatch(r"[A-Za-z0-9_]{3,20}", username):
            flash("Kullanıcı adı 3-20 karakter olmalı.")
            return redirect("/register")

        if len(password) < 8:
            flash("Şifre en az 8 karakter olmalı.")
            return redirect("/register")

        db = get_db()
        try:
            db.execute(
                "INSERT INTO deady_users (username, password_hash) VALUES (?, ?)",
                (username, generate_password_hash(password))
            )
            db.commit()
            user = db.execute(
                "SELECT id, username FROM deady_users WHERE username = ?",
                (username,)
            ).fetchone()

            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            flash("Hesabın başarıyla oluşturuldu!")
            return redirect("/dashboard")

        except sqlite3.IntegrityError:
            flash("Bu kullanıcı adı zaten kullanılıyor.")
            return redirect("/register")
        finally:
            db.close()

    return render_template("register.html")


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
    return render_template(
        "dashboard.html",
        username=session["username"]
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


@app.route("/ai")
@login_required
def ai_page():
    return render_template("ai.html")


@app.route("/ask-ai", methods=["POST"])
@login_required
def ask_ai():
    return {"error": "AI özelliği henüz etkinleştirilmedi."}, 503


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
