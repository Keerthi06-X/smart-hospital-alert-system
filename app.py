import os
import random
import sqlite3
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template_string, request, redirect, url_for

app = Flask(__name__)
DB_PATH = Path(__file__).parent / "mews_monitor.db"

AVPU_OPTIONS = ["Alert", "Verbal", "Pain", "Unresponsive"]
RISK_LOW = "Low"
RISK_MEDIUM = "Medium"
RISK_CRITICAL = "Critical"

BOUNDS = {
    "heart_rate": (20, 250),
    "resp_rate": (4, 60),
    "systolic_bp": (50, 250),
    "temperature": (32.0, 42.0),
}

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
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
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_readings_bed_time ON readings (bed_id, recorded_at DESC)")
    conn.commit()
    conn.close()

def insert_reading(record):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO readings (bed_id, heart_rate, resp_rate, systolic_bp, temperature, avpu, mews_score, risk_level, recorded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (record["bed_id"], record["heart_rate"], record["resp_rate"], record["systolic_bp"], record["temperature"], record["avpu"], record["mews_score"], record["risk_level"], record["recorded_at"])
    )
    conn.commit()
    conn.close()

def fetch_latest_per_bed():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT r1.bed_id, r1.heart_rate, r1.resp_rate, r1.systolic_bp, r1.temperature, r1.avpu, r1.mews_score, r1.risk_level, r1.recorded_at
        FROM readings r1
        INNER JOIN (
            SELECT bed_id, MAX(recorded_at) as max_time
            FROM readings
            GROUP BY bed_id
        ) r2 ON r1.bed_id = r2.bed_id AND r1.recorded_at = r2.max_time
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return rows

def calculate_mews(heart_rate, resp_rate, systolic_bp, temperature, avpu):
    total = 0
    if resp_rate >= 30: total += 3
    elif resp_rate >= 21: total += 2
    elif resp_rate >= 15: total += 1
    
    if heart_rate >= 130: total += 3
    elif heart_rate >= 111: total += 2
    elif heart_rate >= 101: total += 1

    if systolic_bp <= 70: total += 3
    elif systolic_bp <= 80: total += 2
    elif systolic_bp <= 100: total += 1

    if temperature >= 39.0: total += 2
    elif temperature >= 38.5: total += 1

    avpu_map = {"Alert": 0, "Verbal": 1, "Pain": 2, "Unresponsive": 3}
    total += avpu_map.get(avpu, 0)
    
    if total >= 7: risk = RISK_CRITICAL
    elif total >= 5: risk = RISK_MEDIUM
    else: risk = RISK_LOW
    return total, risk

def process_reading(bed_id, heart_rate, resp_rate, systolic_bp, temperature, avpu):
    score, risk = calculate_mews(heart_rate, resp_rate, systolic_bp, temperature, avpu)
    return {
        "bed_id": bed_id.strip().upper(), "heart_rate": heart_rate, "resp_rate": resp_rate,
        "systolic_bp": systolic_bp, "temperature": round(temperature, 1), "avpu": avpu,
        "mews_score": score, "risk_level": risk, "recorded_at": datetime.now().isoformat(),
    }

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Smart Hospital MEWS Dashboard</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    <style>
        .risk-Critical { background-color: #f8d7da !important; color: #842029; font-weight: bold; }
        .risk-Medium { background-color: #fff3cd !important; color: #664d03; }
        .risk-Low { background-color: #d1e7dd !important; color: #0f5132; }
    </style>
</head>
<body class="bg-light">
    <div class="container my-5">
        <h1 class="mb-4 text-center">🏥 Smart Hospital Patient Alert System</h1>
        
        <div class="row">
            <!-- Left Ingestion Panel -->
            <div class="col-md-4">
                <div class="card p-4 shadow-sm mb-4">
                    <h4 class="card-title text-primary mb-3">Vitals Ingestion Stage</h4>
                    <form action="/add" method="POST">
                        <div class="mb-3">
                            <label class="form-label">Bed ID</label>
                            <input type="text" name="bed_id" class="form-control" placeholder="e.g. ICU-04" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Heart Rate (bpm)</label>
                            <input type="number" name="heart_rate" class="form-control" value="72" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Respiratory Rate</label>
                            <input type="number" name="resp_rate" class="form-control" value="16" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Systolic BP (mmHg)</label>
                            <input type="number" name="systolic_bp" class="form-control" value="120" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Temperature (°C)</label>
                            <input type="number" step="0.1" name="temperature" class="form-control" value="37.0" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">AVPU Status</label>
                            <select name="avpu" class="form-select">
                                {% for opt in avpu_opts %}
                                <option value="{{ opt }}">{{ opt }}</option>
                                {% endfor %}
                            </select>
                        </div>
                        <button type="submit" class="btn btn-primary w-100">Submit Vitals Entry</button>
                    </form>
                    <form action="/drift" method="POST" class="mt-3">
                        <button type="submit" class="btn btn-outline-secondary w-100">🔄 Trigger Ward Simulation Drift</button>
                    </form>
                </div>
            </div>
            
            <!-- Right Grid View -->
            <div class="col-md-8">
                <div class="card p-4 shadow-sm">
                    <h4 class="card-title text-success mb-3">Live Triage Matrix Grid View</h4>
                    <div class="table-responsive">
                        <table class="table table-bordered align-middle">
                            <thead class="table-dark">
                                <tr>
                                    <th>Bed ID</th>
                                    <th>HR</th>
                                    <th>RR</th>
                                    <th>BP</th>
                                    <th>Temp</th>
                                    <th>AVPU</th>
                                    <th>MEWS</th>
                                    <th>Triage Level</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% if not beds %}
                                <tr><td colspan="8" class="text-center text-muted">No active patient beds tracked yet.</td></tr>
                                {% endif %}
                                {% for b in beds %}
                                <tr class="risk-{{ b[7] }}">
                                    <td>{{ b[0] }}</td>
                                    <td>{{ b[1] }}</td>
                                    <td>{{ b[2] }}</td>
                                    <td>{{ b[3] }}</td>
                                    <td>{{ b[4] }}°C</td>
                                    <td>{{ b[5] }}</td>
                                    <td>{{ b[6] }}</td>
                                    <td>{{ '🚨 ' if b[7] == 'Critical' }}{{ b[7] }}</td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

@app.route("/")
def home():
    beds = fetch_latest_per_bed()
    beds.sort(key=lambda x: (0 if x[7] == RISK_CRITICAL else 1, -x[6]))
    return render_template_string(HTML_TEMPLATE, beds=beds, avpu_opts=AVPU_OPTIONS)

@app.route("/add", methods=["POST"])
def add_reading():
    bed_id = request.form.get("bed_id")
    hr = int(request.form.get("heart_rate"))
    rr = int(request.form.get("resp_rate"))
    sbp = int(request.form.get("systolic_bp"))
    temp = float(request.form.get("temperature"))
    avpu = request.form.get("avpu")
    
    insert_reading(process_reading(bed_id, hr, rr, sbp, temp, avpu))
    return redirect(url_for("home"))

@app.route("/drift", methods=["POST"])
def drift_readings():
    latest = fetch_latest_per_bed()
    for row in latest:
        hr = max(BOUNDS["heart_rate"][0], min(BOUNDS["heart_rate"][1], int(row[1] + random.randint(-6, 6))))
        rr = max(BOUNDS["resp_rate"][0], min(BOUNDS["resp_rate"][1], int(row[2] + random.randint(-3, 3))))
        sbp = max(BOUNDS["systolic_bp"][0], min(BOUNDS["systolic_bp"][1], int(row[3] + random.randint(-10, 10))))
        temp = max(BOUNDS["temperature"][0], min(BOUNDS["temperature"][1], round(row[4] + random.uniform(-0.4, 0.4), 1)))
        insert_reading(process_reading(row[0], hr, rr, sbp, temp, row[5]))
    return redirect(url_for("home"))

if __name__ == "__main__":
    init_db()
    if not fetch_latest_per_bed():
        insert_reading(process_reading("ICU-01", 72, 14, 120, 36.8, "Alert"))
        insert_reading(process_reading("WARD-04", 115, 22, 95, 38.6, "Verbal"))
        insert_reading(process_reading("ICU-03", 138, 32, 62, 39.4, "Unresponsive"))
        
    app.run(debug=True, port=5000)