from datetime import date, timedelta
from db import get_db

SCHEDULE = [
    # Джампинг
    ("jumping", 0, "10:00", 15),
    ("jumping", 0, "19:30", 15),
    ("jumping", 2, "10:00", 15),
    ("jumping", 4, "10:00", 15),
    ("jumping", 4, "19:30", 15),

    # Жиротопка
    ("fatburn", 2, "19:30", None),
    ("fatburn", 5, "13:00", None),
]

def generate_week_schedule():
    conn = get_db()
    cur = conn.cursor()

    today = date.today()
    monday = today - timedelta(days=today.weekday())

    for training_type, weekday, time_str, limit_count in SCHEDULE:
        training_date = monday + timedelta(days=weekday)

        cur.execute(
            """
            INSERT INTO trainings (type, date, time, limit_count)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (training_type, training_date, time_str, limit_count)
        )

    conn.commit()
    cur.close()
    conn.close()
