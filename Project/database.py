import mysql.connector
from mysql.connector import Error
from tkinter import messagebox
from datetime import datetime


DB_CONFIG = {
    "host": "localhost",
    "user": "root",          # change if needed
    "password": "nishant@7979",   # change if needed
    "database": "hospital_db",
    "raise_on_warnings": True,
    "autocommit": False
}

# Database helpers
def get_db_connection():
    """
    Return a new MySQL connection or None if connection fails.
    (We create short-lived connections to avoid global-state problems.)
    """
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except Error as e:
        messagebox.showerror("Database Error", f"Could not connect to MySQL:\n{e}")
        return None


def ensure_database_exists():
    """Create the database if it doesn't exist yet."""
    tmp_conf = DB_CONFIG.copy()
    tmp_conf.pop("database", None)
    try:
        tmp = mysql.connector.connect(**tmp_conf)
        cur = tmp.cursor()
        cur.execute(
            f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']} "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
        )
        tmp.commit()
        cur.close()
        tmp.close()
    except Error as e:
        raise



# Initialize Database & Load Data

def init_db(wards, patients, patient_names):
    """
    Create tables if not exist and load ward/patient data into memory lists/dicts.
    wards: dict to fill with ward_name -> {"capacity": int, "occupied": int}
    patients: list to fill with {"id": int, "name": str, "ward": str}
    patient_names: sorted list of name_key strings used for bisect ordering
    """
    try:
        ensure_database_exists()
    except Exception as e:
        messagebox.showerror("DB Init Error", f"Failed to ensure database exists:\n{e}")
        return

    conn = get_db_connection()
    if not conn:
        return

    cur = None
    try:
        cur = conn.cursor()

        # Create tables
        cur.execute("""
        CREATE TABLE IF NOT EXISTS wards (
            ward_name VARCHAR(100) PRIMARY KEY,
            capacity INT NOT NULL,
            occupied INT NOT NULL DEFAULT 0
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            name_key VARCHAR(255) NOT NULL,
            ward_name VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (ward_name) REFERENCES wards(ward_name) ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # Insert default wards if empty
        cur.execute("SELECT COUNT(*) FROM wards;")
        (count,) = cur.fetchone()
        if count == 0:
            defaults = [
                ("ICU", 5, 2),
                ("General Ward", 10, 4),
                ("Emergency", 6, 3),
                ("Maternity", 6, 1),
            ]
            cur.executemany(
                "INSERT INTO wards (ward_name, capacity, occupied) VALUES (%s, %s, %s)",
                defaults
            )
            conn.commit()

        # Load wards
        cur.execute("SELECT ward_name, capacity, occupied FROM wards ORDER BY ward_name;")
        wards.clear()
        for ward_name, capacity, occupied in cur.fetchall():
            wards[ward_name] = {"capacity": capacity, "occupied": occupied}

        # Load patients ordered by name_key
        cur.execute("SELECT id, name, name_key, ward_name FROM patients ORDER BY name_key, id;")
        patients.clear()
        patient_names.clear()
        for pid, name, name_key, ward_name in cur.fetchall():
            patients.append({"id": pid, "name": name, "ward": ward_name})
            patient_names.append(name_key)

        print("[OK] Loaded data from MySQL successfully.")

    except Error as e:
        messagebox.showerror("DB Init Error", str(e))
    finally:
        if cur:
            cur.close()
        if conn and conn.is_connected():
            conn.close()


def add_patient_to_db(name, name_key, ward_name):
    """
    Insert a new patient and increment occupied count for the ward.
    name_key should be normalized by the GUI (e.g., lowercase with underscores).
    Returns inserted row id on success, None on failure.
    """
    if not (name and name_key and ward_name):
        messagebox.showwarning("DB Insert", "Missing name, name_key or ward_name.")
        return None

    conn = get_db_connection()
    if not conn:
        return None

    cur = None
    try:
        cur = conn.cursor()

        # Acquire ward row for update
        cur.execute("SELECT ward_name, capacity, occupied FROM wards WHERE ward_name = %s FOR UPDATE", (ward_name,))
        row = cur.fetchone()
        if not row:
            messagebox.showerror("DB Insert Error", f"Ward '{ward_name}' not found in DB.")
            conn.rollback()
            return None

        _, capacity, occupied = row
        if occupied >= capacity:
            messagebox.showerror("No Beds", f"No beds available in ward '{ward_name}'.")
            conn.rollback()
            return None

        # Insert patient and update occupied count
        cur.execute(
            "INSERT INTO patients (name, name_key, ward_name) VALUES (%s, %s, %s)",
            (name, name_key, ward_name)
        )
        last_id = cur.lastrowid

        cur.execute(
            "UPDATE wards SET occupied = occupied + 1 WHERE ward_name = %s",
            (ward_name,)
        )

        conn.commit()
        print(f"[DB] Added patient '{name}' (id={last_id}) to '{ward_name}'")
        return last_id

    except Error as e:
        conn.rollback()
        messagebox.showerror("DB Insert Error", str(e))
        return None
    finally:
        if cur:
            cur.close()
        if conn and conn.is_connected():
            conn.close()

def discharge_patient_from_db(name_key):
    """
    Delete one patient matching name_key (the earliest inserted)
    and decrement occupied count for the ward.
    Returns True if a patient was removed, False otherwise.
    """
    if not name_key:
        messagebox.showwarning("DB Delete", "name_key is required.")
        return False

    conn = get_db_connection()
    if not conn:
        return False

    cur = None
    try:
        cur = conn.cursor()

        # Find the earliest patient with this name_key
        cur.execute(
            "SELECT id, ward_name FROM patients WHERE name_key = %s ORDER BY created_at, id LIMIT 1 FOR UPDATE",
            (name_key,)
        )
        row = cur.fetchone()
        if not row:
            print(f"[DB] No patient found with name_key '{name_key}'")
            conn.rollback()
            return False

        patient_id, ward = row

        # Delete patient
        cur.execute("DELETE FROM patients WHERE id = %s", (patient_id,))

        # Decrement occupied count safely
        if ward:
            cur.execute("UPDATE wards SET occupied = GREATEST(0, occupied - 1) WHERE ward_name = %s", (ward,))

        conn.commit()
        print(f"[DB] Discharged patient id={patient_id} (name_key='{name_key}') from '{ward}'")
        return True

    except Error as e:
        conn.rollback()
        messagebox.showerror("DB Delete Error", str(e))
        return False
    finally:
        if cur:
            cur.close()
        if conn and conn.is_connected():
            conn.close()
