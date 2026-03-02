from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime


def ensure_app_user(db: Session, user_id: str, phone: str | None):
    db.execute(
        text("""
            insert into public.app_users (user_id, phone)
            values (:uid, :phone)
            on conflict (user_id)
            do update set phone = coalesce(:phone, public.app_users.phone)
        """),
        {"uid": user_id, "phone": phone},
    )
    db.commit()


def set_user_age(db: Session, user_id: str, age: int):
    if age < 18:
        return False

    db.execute(
        text("""
            update public.app_users
            set age_int = :age,
                age_set_at = now()
            where user_id = :uid
        """),
        {"uid": user_id, "age": age},
    )
    db.commit()
    return True
