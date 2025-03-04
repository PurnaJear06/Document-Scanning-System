import sqlite3
from werkzeug.security import generate_password_hash

# Database connection
DB_FILE = "database.db"

def insert_admin():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Hash the password
    admin_username = "admin"
    admin_password = "admin123"  # Change this to a secure password
    hashed_password = generate_password_hash(admin_password)

    try:
        # Insert admin user
        cursor.execute("""
            INSERT INTO users (username, password, credits, is_admin)
            VALUES (?, ?, ?, ?)
        """, (admin_username, hashed_password, 9999, 1))
        
        conn.commit()
        print("Admin user inserted successfully!")
    except sqlite3.IntegrityError:
        print("Admin user already exists!")
    finally:
        conn.close()

if __name__ == "__main__":
    insert_admin()
