import sqlite3

DB_PATH = "disaster_alerts.db"

def get_db():
    """Open a SQLite connection with safe defaults.

    Pragmas applied on every connection:
    - WAL journal mode: safe concurrent reads/writes, no corruption on crash.
    - foreign_keys=ON : enforce referential integrity (off by default in SQLite).
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def create_tables():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            location_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message TEXT NOT NULL,
            risk_level TEXT NOT NULL,
            latitude REAL,
            longitude REAL,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            location_name TEXT,
            risk_score REAL NOT NULL,
            risk_level TEXT NOT NULL,
            weather_data TEXT,
            predicted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS community_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            hazard_type TEXT NOT NULL,
            description TEXT NOT NULL,
            reporter_name TEXT DEFAULT 'Anonymous',
            severity TEXT DEFAULT 'MODERATE',
            status TEXT DEFAULT 'active',
            reported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
