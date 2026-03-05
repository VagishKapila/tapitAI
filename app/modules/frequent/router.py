from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db

router = APIRouter(prefix="/v1/frequent", tags=["frequent"])


@router.get("/feed")
def get_frequent_feed(user_id: str, db: Session = Depends(get_db)):

    rows = db.execute(
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

    return {"frequents": rows}
