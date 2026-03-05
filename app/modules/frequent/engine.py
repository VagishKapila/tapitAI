from sqlalchemy.orm import Session
from app.db.session import SessionLocal
import uuid
import math


DIST_THRESHOLD = 0.005  # ~0.5 mile approx


def distance(lat1, lon1, lat2, lon2):
    return math.sqrt((lat1 - lat2) ** 2 + (lon1 - lon2) ** 2)


def run_frequency_engine():

    db: Session = SessionLocal()

    users = db.execute(
        """
        SELECT user_id, lat, lng, last_seen_at
        FROM presence
        WHERE discoverable = true
        """
    ).fetchall()

    pairs = {}

    for i in range(len(users)):
        a = users[i]

        for j in range(i + 1, len(users)):
            b = users[j]

            if str(a.user_id) == str(b.user_id):
                continue

            d = distance(a.lat, a.lng, b.lat, b.lng)

            if d < DIST_THRESHOLD:
                key = tuple(sorted([str(a.user_id), str(b.user_id)]))
                pairs[key] = pairs.get(key, 0) + 1

    for (user_a, user_b), count in pairs.items():

        if count < 2:
            continue

        db.execute(
            """
            INSERT INTO user_frequents
            (id, user_id, candidate_user_id, encounter_count, first_seen_at, last_seen_at)
            VALUES (:id, :user_a, :user_b, :count, now(), now())
            ON CONFLICT DO NOTHING
            """,
            {
                "id": str(uuid.uuid4()),
                "user_a": user_a,
                "user_b": user_b,
                "count": count,
            },
        )

    db.commit()
