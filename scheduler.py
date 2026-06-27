# ========================================
# SCHEDULER BMKG - VERSI SATU FILE
# ========================================

import sys
import os
import time
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import psycopg2
import requests


# ========================================
# KONFIGURASI
# ========================================

BASE_URL = "https://api.bmkg.go.id/publik/prakiraan-cuaca"
ADM4 = "12.17.08.2021"

DB_CONFIG = {
    "host": "localhost",
    "database": "bmkg_db",
    "user": "bmkg_user",
    "password": "postgres"
}


# ========================================
# DATABASE CONNECTION
# ========================================

def get_connection():
    """Membuat koneksi ke database PostgreSQL"""
    return psycopg2.connect(**DB_CONFIG)


# ========================================
# BMKG API CLIENT
# ========================================

def fetch_bmkg_data():
    """
    Mengambil data cuaca dari API BMKG
    
    Returns:
        dict: Data cuaca dalam format JSON
    """
    url = f"{BASE_URL}?adm4={ADM4}"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.json()


# ========================================
# WEATHER DATA PROCESSING
# ========================================

def parse_time(value):
    """Parse waktu dari string ISO format ke datetime"""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", ""))
    except:
        return None


def save_wilayah(lokasi):
    """Menyimpan data wilayah ke database"""
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO wilayah (
                adm4, provinsi, kota, kecamatan, desa,
                latitude, longitude
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (adm4) DO NOTHING
        """, (
            lokasi.get("adm4"),
            lokasi.get("provinsi"),
            lokasi.get("kotkab"),
            lokasi.get("kecamatan"),
            lokasi.get("desa"),
            lokasi.get("lat"),
            lokasi.get("lon")
        ))

        conn.commit()

    except Exception as e:
        print("Wilayah insert error:", e)
        conn.rollback()

    finally:
        cur.close()
        conn.close()


def flatten_bmkg_data(json_data):
    """Flatten data BMKG menjadi list"""
    weather_data = json_data["data"][0]["cuaca"]

    flat = []
    for day in weather_data:
        flat.extend(day)

    return flat


def save_to_db(flat_data):
    """
    Menyimpan data cuaca ke database
    
    Args:
        flat_data (list): List data cuaca yang sudah flatten
    
    Returns:
        int: Jumlah record yang berhasil diinsert
    """
    conn = get_connection()
    cur = conn.cursor()

    inserted = 0

    for item in flat_data:
        try:
            tp = float(item.get("tp", 0) or 0)
            label_hujan = 1 if tp > 0 else 0

            cur.execute("""
                INSERT INTO weather_forecast (
                    adm4,
                    forecast_time,
                    analysis_date,
                    suhu,
                    kelembapan,
                    kecepatan_angin,
                    arah_angin,
                    cuaca,
                    jarak_pandang,
                    tutupan_awan,
                    label_hujan
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (adm4, forecast_time) DO NOTHING
            """, (
                ADM4,
                parse_time(item.get("local_datetime")),
                parse_time(item.get("analysis_date")),
                float(item.get("t", 0) or 0),
                float(item.get("hu", 0) or 0),
                float(item.get("ws", 0) or 0),
                item.get("wd"),
                item.get("weather_desc"),
                item.get("vs_text"),
                float(item.get("tcc", 0) or 0),
                label_hujan
            ))

            if cur.rowcount > 0:
                inserted += 1

        except Exception as e:
            print("Insert error:", e)
            conn.rollback()
            continue

    conn.commit()
    cur.close()
    conn.close()

    return inserted


# ========================================
# SCHEDULER LOG
# ========================================

def log(status, message, start_time=None):
    """Mencatat log scheduler ke database"""
    try:
        conn = get_connection()
        cur = conn.cursor()

        duration = None
        if start_time:
            duration = (datetime.now() - start_time).total_seconds()

        cur.execute("""
            INSERT INTO scheduler_log (run_time, status, message, duration_seconds)
            VALUES (%s, %s, %s, %s)
        """, (
            datetime.now(),
            status,
            message,
            duration
        ))

        conn.commit()
        cur.close()
        conn.close()

    except Exception as e:
        print("LOG ERROR:", e)


# ========================================
# JOB SCHEDULER
# ========================================

def job():
    """Job utama untuk fetch dan save data BMKG"""
    start_time = datetime.now()
    print("Running scheduler:", start_time)

    try:
        json_data = fetch_bmkg_data()

        if not json_data or "data" not in json_data:
            raise Exception("Invalid BMKG response")

        lokasi = json_data["data"][0]["lokasi"]
        save_wilayah(lokasi)

        flat_data = flatten_bmkg_data(json_data)
        inserted = save_to_db(flat_data)

        log("SUCCESS", f"Inserted {inserted} records", start_time)
        print("Success: Inserted", inserted, "records")

    except Exception as e:
        log("FAILED", str(e))
        print("JOB ERROR:", e)


# ========================================
# MAIN - START SCHEDULER
# ========================================

scheduler = BackgroundScheduler()
scheduler.add_job(job, 'cron', minute=0)
scheduler.start()

print("Scheduler started...")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Shutting down scheduler...")
    scheduler.shutdown()
    print("Scheduler stopped.")