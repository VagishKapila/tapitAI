from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
import secrets

from .models import InviteCode, InviteUsage, WaitlistRequest


def validate_invite_code(db: Session, code: str, user_id: str, phone: str | None):
    invite = db.query(InviteCode).filter(InviteCode.code == code).first()

    if not invite:
        return False, "Invalid invite code."

    if not invite.is_active:
        return False, "Invite code is inactive."

    if invite.expires_at and invite.expires_at < datetime.utcnow():
        return False, "Invite code has expired."

    if invite.used_count >= invite.max_uses:
        return False, "Invite code usage limit reached."

    # increment usage
    invite.used_count += 1

    usage = InviteUsage(
        invite_code_id=invite.id,
        user_id=user_id,
        phone=phone,
    )

    db.add(usage)

    # 🔥 Update local app_users mirror
    db.execute(
        text("""
            update public.app_users
            set invite_verified = true,
                invite_verified_at = now(),
                invite_code_used = :code
            where user_id = :uid
        """),
        {"uid": user_id, "code": code},
    )

    db.commit()

    return True, "Invite code accepted."


def create_waitlist_entry(db: Session, phone: str, name: str | None):
    entry = WaitlistRequest(phone=phone, name=name)
    db.add(entry)
    db.commit()
    return entry


def generate_invite_code():
    return secrets.token_hex(4).upper()


def create_invite_code(db: Session, max_uses: int, expires_at: str | None, notes: str | None):
    code = generate_invite_code()

    invite = InviteCode(
        code=code,
        max_uses=max_uses,
        expires_at=datetime.fromisoformat(expires_at) if expires_at else None,
        notes=notes,
    )

    db.add(invite)
    db.commit()
    db.refresh(invite)

    return invite


def list_invite_codes(db: Session):
    return db.query(InviteCode).order_by(InviteCode.created_at.desc()).all()


def list_invite_usages(db: Session):
    return db.query(InviteUsage).order_by(InviteUsage.used_at.desc()).all()


def list_waitlist(db: Session):
    return db.query(WaitlistRequest).order_by(WaitlistRequest.requested_at.desc()).all()