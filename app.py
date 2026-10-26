import os
import sqlite3
from functools import wraps

from flask import (Flask, g, render_template, request,
                   redirect, url_for, session, flash)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-key")

DATABASE = "tracker.db"
STATUSES = ["Applied", "Interview", "Offer", "Rejected"]


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(error):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    with app.open_resource("schema.sql") as f:
        db.executescript(f.read().decode("utf8"))


with app.app_context():
    init_db()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        user = get_db().execute(
            "SELECT id FROM users WHERE id = ?", (session["user_id"],)
        ).fetchone()
        if user is None:
            session.clear()
            flash("Please log in again.", "info")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        if not username or not password:
            flash("Username and password are required.", "danger")
        elif len(password) < 6:
            flash("Password must be at least 6 characters.", "danger")
        else:
            db = get_db()
            try:
                db.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username, generate_password_hash(password)),
                )
                db.commit()
                flash("Account created. Please log in.", "success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("Username already taken.", "danger")

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()

        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Wrong username or password.", "danger")
        else:
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("home"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def home():
    db = get_db()
    status_filter = request.args.get("status", "")

    # Counts for the cards at the top (always for ALL of this user's applications)
    rows = db.execute(
        "SELECT status, COUNT(*) AS total FROM applications "
        "WHERE user_id = ? GROUP BY status",
        (session["user_id"],),
    ).fetchall()
    counts = {s: 0 for s in STATUSES}
    for r in rows:
        counts[r["status"]] = r["total"]
    total = sum(counts.values())

    # List, optionally filtered by status
    if status_filter in STATUSES:
        applications = db.execute(
            "SELECT * FROM applications WHERE user_id = ? AND status = ? "
            "ORDER BY id DESC",
            (session["user_id"], status_filter),
        ).fetchall()
    else:
        status_filter = ""
        applications = db.execute(
            "SELECT * FROM applications WHERE user_id = ? ORDER BY id DESC",
            (session["user_id"],),
        ).fetchall()

    return render_template(
        "dashboard.html",
        applications=applications,
        counts=counts,
        total=total,
        statuses=STATUSES,
        status_filter=status_filter,
    )


@app.route("/add", methods=["GET", "POST"])
@login_required
def add():
    if request.method == "POST":
        company = request.form["company"].strip()
        role = request.form["role"].strip()
        status = request.form["status"]
        applied_date = request.form["applied_date"]
        notes = request.form["notes"].strip()

        if not company or not role:
            flash("Company and role are required.", "danger")
        elif status not in STATUSES:
            flash("Invalid status.", "danger")
        else:
            db = get_db()
            db.execute(
                "INSERT INTO applications "
                "(user_id, company, role, status, applied_date, notes) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (session["user_id"], company, role, status, applied_date, notes),
            )
            db.commit()
            flash("Application added.", "success")
            return redirect(url_for("home"))

    return render_template("form.html", statuses=STATUSES, application=None)


@app.route("/edit/<int:app_id>", methods=["GET", "POST"])
@login_required
def edit(app_id):
    db = get_db()
    application = db.execute(
        "SELECT * FROM applications WHERE id = ? AND user_id = ?",
        (app_id, session["user_id"]),
    ).fetchone()

    if application is None:
        flash("Application not found.", "danger")
        return redirect(url_for("home"))

    if request.method == "POST":
        company = request.form["company"].strip()
        role = request.form["role"].strip()
        status = request.form["status"]
        applied_date = request.form["applied_date"]
        notes = request.form["notes"].strip()

        if not company or not role:
            flash("Company and role are required.", "danger")
        elif status not in STATUSES:
            flash("Invalid status.", "danger")
        else:
            db.execute(
                "UPDATE applications "
                "SET company = ?, role = ?, status = ?, applied_date = ?, notes = ? "
                "WHERE id = ? AND user_id = ?",
                (company, role, status, applied_date, notes,
                 app_id, session["user_id"]),
            )
            db.commit()
            flash("Application updated.", "success")
            return redirect(url_for("home"))

    return render_template("form.html", statuses=STATUSES, application=application)


@app.route("/delete/<int:app_id>", methods=["POST"])
@login_required
def delete(app_id):
    db = get_db()
    db.execute(
        "DELETE FROM applications WHERE id = ? AND user_id = ?",
        (app_id, session["user_id"]),
    )
    db.commit()
    flash("Application deleted.", "info")
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)