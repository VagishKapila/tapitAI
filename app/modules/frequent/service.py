from sqlalchemy.orm import Session
from datetime import datetime
import uuid


def register_visit(db: Session, user_id: str, lat: float, lng: float):
    """
    Store simple visit session.
    """

    visit = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "lat": lat,
        "lng": lng,
        "start_ts": datetime.utcnow(),
        "end_ts": datetime.utcnow(),
        "duration_sec": 0,
    }

    db.execute(
        """
        INSERT INTO user_location_sessions
        (id, user_id, lat, lng, start_ts, end_ts, duration_sec)
        VALUES (:id, :user_id, :lat, :lng, :start_ts, :end_ts, :duration_sec)
        """,
        visit,
    )

    db.commit()


def get_frequent_feed(db: Session, user_id: str):
    """
    Return frequent users + nearby users
    """

    frequents = db.execute(
        """
        SELECT candidate_user_id, encounter_count
        FROM user_frequents
        WHERE user_id = :user_id
        AND dismissed = false
        ORDER BY encounter_count DESC
        LIMIT 2
        """,
        {"user_id": user_id},
    ).fetchall()

    return frequents
