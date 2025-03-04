from flask import Flask, render_template, request, redirect, url_for, session
import os
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "supersecretkey"

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Database connection
def get_db_connection():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn

# Create tables
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        credits INTEGER DEFAULT 20,
        is_admin INTEGER DEFAULT 0
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS credit_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        requested_credits INTEGER NOT NULL,
        status TEXT DEFAULT 'pending'
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        uploaded_by TEXT NOT NULL
    )""")

    conn.commit()
    conn.close()

init_db()

# User Registration
@app.route("/auth/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", 
                           (username, hashed_password))
            conn.commit()
            conn.close()
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            return "Username already exists"

    return render_template("register.html")

# User Login
# def get_db_connection():
#     conn = sqlite3.connect("database.db")
#     conn.row_factory = sqlite3.Row  # This makes rows behave like dictionaries
#     return conn
@app.route("/auth/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()
        user = dict(user) if user else None

        if user and check_password_hash(user["password"], password):
            session["username"] = username
            session["is_admin"] = user["is_admin"]
            print(session)
            return redirect(url_for("dashboard"))
        return "Invalid credentials"

    return render_template("login.html")

# User Logout
@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect(url_for("login"))

# Dashboard
@app.route("/dashboard")
def dashboard():
    if "username" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username, credits, is_admin FROM users WHERE username = ?", (session["username"],))
    user = cursor.fetchone()
    conn.close()

    if user is None:
        return redirect(url_for("login"))

    # Check if the user is admin
    if user["is_admin"]:
        return render_template("admin_dashboard.html", username=user["username"], credits=user["credits"])

    return render_template("dashboard.html", username=user["username"], credits=user["credits"])


# Request Credits
@app.route("/request_credits", methods=["POST"])
def request_credits():
    if "username" not in session:
        return redirect(url_for("login"))

    username = session["username"]
    requested_credits = int(request.form["credits"])

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO credit_requests (username, requested_credits) VALUES (?, ?)", 
                   (username, requested_credits))
    conn.commit()
    conn.close()

    return redirect(url_for("dashboard"))

# Admin Panel for Credit Requests
@app.route("/admin/credit_requests")
def admin_credit_requests():
    if "username" not in session or session.get("is_admin") != 1:
        return "Access Denied"

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM credit_requests")
    credit_requests = cursor.fetchall()
    conn.close()

    return render_template("admin_credit_requests.html", credit_requests=credit_requests)

# Approve Credit Request
@app.route("/approve_credit/<int:request_id>")
def approve_credit(request_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE credit_requests SET status = 'approved' WHERE id = ?", (request_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_credit_requests'))

# Deny Credit Request
@app.route("/deny_credit/<int:request_id>")
def deny_credit(request_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE credit_requests SET status = 'denied' WHERE id = ?", (request_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_credit_requests'))


# Upload & Scan Document
@app.route("/scan", methods=["POST"])
def scan_document():
    if "username" not in session:
        return redirect(url_for("login"))

    username = session["username"]
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT credits FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()

    if user["credits"] <= 0:
        return "No credits left! Request more from admin."

    uploaded_file = request.files["file"]
    if uploaded_file.filename == "":
        return "No file selected!"

    file_path = os.path.join(UPLOAD_FOLDER, uploaded_file.filename)
    uploaded_file.save(file_path)

    cursor.execute("INSERT INTO documents (filename, uploaded_by) VALUES (?, ?)", 
                   (uploaded_file.filename, username))
    cursor.execute("UPDATE users SET credits = credits - 1 WHERE username = ?", (username,))
    conn.commit()
    conn.close()

    # Check for similar documents
    similar_docs = find_similar_documents(file_path)

    if similar_docs:
        return f"File uploaded! Matching documents found: {', '.join(similar_docs)}"
    else:
        return "File uploaded! No matching documents found."

# Find Similar Documents
def find_similar_documents(new_doc_path):
    """Simple text-based matching using word overlap."""
    with open(new_doc_path, "r") as f:
        new_doc_text = f.read().lower()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT filename FROM documents")
    existing_docs = cursor.fetchall()
    conn.close()

    matching_docs = []
    for doc in existing_docs:
        doc_path = os.path.join(UPLOAD_FOLDER, doc["filename"])
        if os.path.exists(doc_path):
            with open(doc_path, "r") as existing_doc:
                existing_text = existing_doc.read().lower()
                common_words = set(new_doc_text.split()) & set(existing_text.split())

                if len(common_words) > 5:  # If 5 or more words match, consider similar
                    matching_docs.append(doc["filename"])

    return matching_docs
@app.route("/")
def home():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)