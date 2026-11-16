
from flask import Flask, render_template, request, redirect, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import time

app = Flask(__name__)
app.secret_key = "deady-salvo-gelistirme-anahtari"

requests_log = {}

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    return render_template("register.html")

@app.route("/ai")
def ai_page():
    return render_template("ai.html")

@app.route("/ask-ai", methods=["POST"])
def ask_ai():
    return {
        "error": "AI özelliği şu anda kapalı."
    }, 503

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

