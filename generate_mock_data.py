import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "mews_monitor.db"

def seed_sample_data():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bed_id TEXT NOT NULL,
            heart_rate INTEGER NOT NULL,
            resp_rate INTEGER NOT NULL,
            systolic_bp INTEGER NOT NULL,
            temperature REAL NOT NULL,
            avpu TEXT NOT NULL,
            mews_score INTEGER NOT NULL,
            risk_level TEXT NOT NULL,
            recorded_at TEXT NOT NULL
        )
    """)
    
    # Sample records matching our triage dashboard expectations
    samples = [
        ("ICU-01", 72, 14, 120, 36.8, "Alert", 0, "Low", datetime.now().isoformat()),
        ("WARD-04", 115, 22, 95, 38.6, "Verbal", 5, "Medium", datetime.now().isoformat()),
        ("ICU-03", 138, 32, 62, 39.4, "Unresponsive", 14, "Critical", datetime.now().isoformat()),
        ("WARD-12", 80, 16, 118, 37.0, "Alert", 0, "Low", datetime.now().isoformat())
    ]
    cursor.executemany("""
        INSERT INTO readings (bed_id, heart_rate, resp_rate, systolic_bp, temperature, avpu, mews_score, risk_level, recorded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, samples)
    
    conn.commit()
    conn.close()
    print("Database successfully seeded with baseline clinical evaluation records!")

if __name__ == "__main__":
    seed_sample_data()
