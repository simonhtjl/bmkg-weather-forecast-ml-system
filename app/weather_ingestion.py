from datetime import datetime
from database import get_connection
from config import ADM4


# =========================
# PARSE TIME SAFETY
# =========================
def parse_time(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", ""))
    except:
        return None


# =========================
# SAVE WEATHER DATA
# =========================
def save_to_db(flat_data):
    conn = get_connection()
    cur = conn.cursor()

    inserted = 0

    for item in flat_data:
        try:
            # ======================
            # LABEL HUJAN (ML TARGET)
            # ======================
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
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
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


# =========================
# SAVE WILAYAH
# =========================
def save_wilayah(lokasi):
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO wilayah (
                adm4, provinsi, kota, kecamatan, desa,
                latitude, longitude
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s)
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


# =========================
# FLATTEN BMKG DATA
# =========================
def flatten_bmkg_data(json_data):
    weather_data = json_data["data"][0]["cuaca"]

    flat = []
    for day in weather_data:
        flat.extend(day)

    return flat