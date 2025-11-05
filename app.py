from flask import Flask, render_template, request, redirect, url_for, session, flash
import os
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd
import matplotlib
matplotlib.use('Agg')   # IMPORTANTISSIMO: backend headless per server
import matplotlib.pyplot as plt
import uuid

app = Flask(__name__)
app.secret_key = "metti_qui_una_chiave_lunga_e_randomica_!@#"

DB_NAME = "database.db"
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# inizializza db se non esiste
def init_db():
    if not os.path.exists(DB_NAME):
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("""
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL
                )
            """)
            conn.commit()

def get_user_by_email(email):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT id, email, password FROM users WHERE email = ?", (email,))
        return c.fetchone()

@app.route("/")
def index():
    return render_template("index.html", user=session.get("user"))

# ---- REGISTER: renderizzo la pagina anche in caso di errore (non redirect) ----
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if len(password) < 6:
            error = "La password deve avere almeno 6 caratteri."
            return render_template("register.html", error=error, email=email)

        if get_user_by_email(email):
            error = "Email già registrata!"
            return render_template("register.html", error=error, email=email)

        hashed = generate_password_hash(password)
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, hashed))
            conn.commit()

        flash("Registrazione completata! Effettua il login.")
        return redirect(url_for("login"))

    return render_template("register.html", email="")

# ---- LOGIN: se fallisce ri-renderizzo template con email preservata ----
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        row = get_user_by_email(email)
        if not row:
            error = "Utente non trovato. Registrati prima!"
            return render_template("login.html", error=error, email=email)

        hashed = row[2]
        if not check_password_hash(hashed, password):
            error = "Password errata!"
            return render_template("login.html", error=error, email=email)

        session["user"] = email
        flash("Accesso effettuato!")
        return redirect(url_for("index"))

    return render_template("login.html", email="")

@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("Logout effettuato.")
    return redirect(url_for("login"))

# ---- UPLOAD: accetta GET (form) e POST (file) ----
@app.route("/upload", methods=["GET", "POST"])
def upload():
    if "user" not in session:
        flash("Devi accedere per caricare un file!")
        return redirect(url_for("login"))

    if request.method == "POST":
        if "file" not in request.files:
            flash("Nessun file caricato.")
            return redirect(url_for("upload"))

        file = request.files["file"]
        if file.filename == "":
            flash("Nessun file selezionato.")
            return redirect(url_for("upload"))

        if not file.filename.lower().endswith(".csv"):
            flash("Carica solo file CSV.")
            return redirect(url_for("upload"))

        filepath = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
        file.save(filepath)

        try:
            df = pd.read_csv(filepath)
        except Exception as e:
            flash(f"Errore nel parsing del CSV: {e}")
            return redirect(url_for("upload"))

        stats_html = df.describe(include='all').to_html(classes="table table-striped table-bordered", border=0)

        # Genero la cartella static se non esiste
        os.makedirs("static", exist_ok=True)

        charts = []  # lista dei grafici generati

        # 1️⃣ Istogramma
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        if len(numeric_cols) > 0:
            plt.figure(figsize=(5, 4))
            df[numeric_cols[0]].hist(color="skyblue", edgecolor="black")
            plt.title(f"Istogramma: {numeric_cols[0]}")
            plt.tight_layout()
            hist_path = os.path.join("static", "hist.png")
            plt.savefig(hist_path)
            plt.close()
            charts.append(("Istogramma", hist_path))

        # 2️⃣ Scatter plot
        if len(numeric_cols) >= 2:
            plt.figure(figsize=(5, 4))
            plt.scatter(df[numeric_cols[0]], df[numeric_cols[1]], color="tomato", alpha=0.7)
            plt.title(f"Scatter: {numeric_cols[0]} vs {numeric_cols[1]}")
            plt.xlabel(numeric_cols[0])
            plt.ylabel(numeric_cols[1])
            plt.tight_layout()
            scatter_path = os.path.join("static", "scatter.png")
            plt.savefig(scatter_path)
            plt.close()
            charts.append(("Scatter Plot", scatter_path))

        # 3️⃣ Grafico a barre per colonna categorica
        cat_cols = df.select_dtypes(include=['object']).columns.tolist()
        if len(cat_cols) > 0:
            col = cat_cols[0]
            counts = df[col].value_counts().head(10)
            plt.figure(figsize=(5, 4))
            counts.plot(kind='bar', color='orange', edgecolor='black')
            plt.title(f"Top categorie: {col}")
            plt.tight_layout()
            bar_path = os.path.join("static", "bar.png")
            plt.savefig(bar_path)
            plt.close()
            charts.append(("Grafico a Barre", bar_path))

        return render_template("result.html", stats=stats_html, charts=charts, user=session.get("user"))

    return render_template("upload.html", user=session.get("user"))

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
