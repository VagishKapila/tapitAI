from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.session import get_db
from app.core.admin.deps import require_admin

router = APIRouter(prefix="/v1/admin", tags=["admin"])


@router.get("/overview")
def admin_overview(
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    total_users = db.execute(
        text("select count(*) from public.app_users")
    ).scalar()

    invite_verified = db.execute(
        text("select count(*) from public.app_users where invite_verified = true")
    ).scalar()

    total_reports = db.execute(
        text("select count(*) from public.reports")
    ).scalar()

    active_presence = db.execute(
        text("""
            select count(*) 
            from public.presence
            where last_seen_at > now() - interval '2 minutes'
        """)
    ).scalar()

    return {
        "total_users": total_users,
        "invite_verified_users": invite_verified,
        "reports_total": total_reports,
        "active_users_now": active_presence,
    }


@router.get("/invite-codes")
def list_invites(
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    rows = db.execute(
        text("""
            select code, used_count, max_uses, is_active, expires_at
            from public.invite_codes
            order by created_at desc
        """)
    ).mappings().all()

    return rows


@router.get("/reports")
def list_reports(
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    rows = db.execute(
        text("""
            select id, reporter_user_id, reported_user_id, reason, created_at
            from public.reports
            order by created_at desc
            limit 100
        """)
    ).mappings().all()

    return rows
