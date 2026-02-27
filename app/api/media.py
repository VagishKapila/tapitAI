from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from sqlalchemy import text
import uuid
import os
import httpx

from app.db import get_db

router = APIRouter(prefix="/v1", tags=["media"])

UPLOAD_DIR = "static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# 🔐 Validate Supabase JWT and extract user_id
async def _get_user_from_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing auth token")

    token = authorization.split(" ")[1]

    supabase_url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{supabase_url}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {token}",
                "apikey": service_key,
            },
        )

        if resp.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid token")

        user = resp.json()
        return user["id"]


def _detect_media_type(file: UploadFile) -> str:
    if file.content_type:
        if file.content_type.startswith("video"):
            return "video"
        if file.content_type.startswith("image"):
            return "image"
    return "image"  # fallback


@router.post("/media/upload")
async def upload_media(
    file: UploadFile = File(...),
    order_index: int = 0,
    make_primary: bool = False,   # 👈 explicit control
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
):
    user_id = await _get_user_from_token(authorization)

    media_id = str(uuid.uuid4())

    ext = file.filename.split(".")[-1].lower()
    filename = f"{media_id}.{ext}"

    media_type = _detect_media_type(file)

    file_path = f"/uploads/{filename}"
    full_path = os.path.join(UPLOAD_DIR, filename)

    with open(full_path, "wb") as buffer:
        buffer.write(await file.read())

    is_primary_bool = False

    # 👇 ONLY images can be primary
    if media_type == "image":

        if make_primary:
            # Remove primary from all other images
            db.execute(
                text("""
                    update public.media_item
                    set is_primary = false
                    where user_id = :user_id
                      and media_type = 'image'
                """),
                {"user_id": user_id},
            )
            is_primary_bool = True

        else:
            # If no primary exists, auto-make this first image primary
            existing_primary = db.execute(
                text("""
                    select id from public.media_item
                    where user_id = :user_id
                      and media_type = 'image'
                      and is_primary = true
                    limit 1
                """),
                {"user_id": user_id},
            ).fetchone()

            if not existing_primary:
                is_primary_bool = True

    db.execute(
        text("""
            insert into public.media_item (
                id,
                user_id,
                media_type,
                order_index,
                is_primary,
                file_path
            )
            values (
                :id,
                :user_id,
                :media_type,
                :order_index,
                :is_primary,
                :file_path
            )
        """),
        {
            "id": media_id,
            "user_id": user_id,
            "media_type": media_type,
            "order_index": order_index,
            "is_primary": is_primary_bool,
            "file_path": file_path,
        },
    )

    db.commit()

    return {
        "id": media_id,
        "file_path": file_path,
        "media_type": media_type,
        "is_primary": is_primary_bool,
    }

    # ---------------------------------------------------
    # DEV DEBUG: See who backend thinks you are
    # ---------------------------------------------------
    @router.get("/media/debug-user")
    async def debug_user(
        authorization: str | None = Header(None),
    ):
        user_id = await _get_user_from_token(authorization)
        return {"user_id": user_id}
