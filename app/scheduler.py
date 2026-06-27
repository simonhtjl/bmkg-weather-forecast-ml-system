from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime

from app.bmkg_client import fetch_bmkg_data
from app.weather_ingestion import save_to_db, flatten_bmkg_data, save_wilayah
from app.database import get_connection


scheduler = BackgroundScheduler()


def log(status, message, start_time=None):
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


def job():
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

    except Exception as e:
        log("FAILED", str(e))
        print("JOB ERROR:", e)

scheduler.add_job(job, 'cron', minute=0) 

print("Scheduler started...")
scheduler.start()