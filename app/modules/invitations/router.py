from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from .schemas import (
    InviteValidateRequest,
    InviteValidateResponse,
    WaitlistRequestCreate,
    InviteCreateRequest
)

from .service import (
    validate_invite_code,
    create_waitlist_entry,
    create_invite_code,
    list_invite_codes,
    list_invite_usages,
    list_waitlist
)
router = APIRouter(prefix="/v1/invitations", tags=["invitations"])


@router.post("/validate", response_model=InviteValidateResponse)
def validate_invite(payload: InviteValidateRequest, db: Session = Depends(get_db)):
    success, message = validate_invite_code(
        db,
        payload.code,
        payload.user_id,
        payload.phone,
    )
    return InviteValidateResponse(success=success, message=message)


@router.post("/waitlist")
def add_to_waitlist(payload: WaitlistRequestCreate, db: Session = Depends(get_db)):
    create_waitlist_entry(db, payload.phone, payload.name)
    return {"success": True}


@router.post("/admin/create")
def admin_create_invite(payload: InviteCreateRequest, db: Session = Depends(get_db)):
    invite = create_invite_code(db, payload.max_uses, payload.expires_at, payload.notes)
    return {
        "id": str(invite.id),
        "code": invite.code,
        "max_uses": invite.max_uses,
        "used_count": invite.used_count,
        "is_active": invite.is_active,
        "expires_at": invite.expires_at,
        "created_at": invite.created_at,
    }


@router.get("/admin/list")
def admin_list_invites(db: Session = Depends(get_db)):
    invites = list_invite_codes(db)
    return invites


@router.get("/admin/usages")
def admin_list_usages(db: Session = Depends(get_db)):
    return list_invite_usages(db)


@router.get("/admin/waitlist")
def admin_list_waitlist(db: Session = Depends(get_db)):
    return list_waitlist(db)
