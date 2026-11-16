from pathlib import Path

p = Path("app.py")
old = p.read_text()

start = old.find("courses = {")
end = old.find('\n\n\n@app.route("/")', start)

if start == -1 or end == -1:
    print("Kurs bölümü bulunamadı. Dosyaya dokunulmadı.")
    raise SystemExit

prefix = old[:start]
courses = old[start:end]

routes = '''

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
    app.run(host="0.0.0.0", port=5000, debug=True)
'''

p.write_text(prefix + courses + routes)
print("Dosya yeniden oluşturuldu.")
