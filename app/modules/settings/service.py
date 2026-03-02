from __future__ import annotations

import json
from sqlalchemy.orm import Session
from sqlalchemy import text


# ------------------------------------------------------------
# Table A: public.profiles  (basic profile: gender, interested_in, etc.)
# PK: id (supabase user id)
# ------------------------------------------------------------
def ensure_profiles_row_exists(db: Session, user_id: str):
    existing = db.execute(
        text("select id from public.profiles where id = :uid"),
        {"uid": user_id},
    ).first()

    if not existing:
        db.execute(
            text("""
                insert into public.profiles (id, created_at, updated_at)
                values (:uid, now(), now())
            """),
            {"uid": user_id},
        )
        db.commit()


# ------------------------------------------------------------
# Table B: public.profile  (extended onboarding: height, intent, etc.)
# PK: user_id (supabase user id)
# ------------------------------------------------------------
def ensure_profile_row_exists(db: Session, user_id: str):
    existing = db.execute(
        text("select user_id from public.profile where user_id = :uid"),
        {"uid": user_id},
    ).first()

    if not existing:
        db.execute(
            text("""
                insert into public.profile (user_id, updated_at)
                values (:uid, now())
            """),
            {"uid": user_id},
        )
        db.commit()


def ensure_settings_exists(db: Session, user_id: str):
    existing = db.execute(
        text("select user_id from public.user_settings where user_id = :uid"),
        {"uid": user_id},
    ).first()

    if not existing:
        db.execute(
            text("""
                insert into public.user_settings (user_id)
                values (:uid)
            """),
            {"uid": user_id},
        )
        db.commit()


def get_full_settings(db: Session, user_id: str):
    # Make sure rows exist everywhere
    ensure_profiles_row_exists(db, user_id)
    ensure_profile_row_exists(db, user_id)
    ensure_settings_exists(db, user_id)

    basic = db.execute(
        text("select * from public.profiles where id = :uid"),
        {"uid": user_id},
    ).mappings().first()

    extended = db.execute(
        text("select * from public.profile where user_id = :uid"),
        {"uid": user_id},
    ).mappings().first()

    settings = db.execute(
        text("select * from public.user_settings where user_id = :uid"),
        {"uid": user_id},
    ).mappings().first()

    # Merge basic + extended into ONE profile payload for the app
    merged_profile = {}
    if basic:
        merged_profile.update(dict(basic))
    if extended:
        merged_profile.update(dict(extended))

    return {
        "profile": merged_profile,
        "settings": dict(settings) if settings else {},
    }


def update_profile(db: Session, user_id: str, data: dict):
    # Ensure both rows exist
    ensure_profiles_row_exists(db, user_id)
    ensure_profile_row_exists(db, user_id)

    # ----------------------------
    # Update public.profiles (basic)
    # ----------------------------
    db.execute(
        text("""
            update public.profiles
            set
                display_name   = coalesce(:display_name, display_name),
                bio            = coalesce(:bio, bio),
                gender         = coalesce(:gender, gender),
                interested_in  = coalesce(:interested_in, interested_in),
                date_of_birth  = coalesce(:date_of_birth, date_of_birth),
                updated_at     = now()
            where id = :uid
        """),
        {
            "uid": user_id,
            "display_name": data.get("display_name"),
            "bio": data.get("bio"),
            "gender": data.get("gender"),
            "interested_in": data.get("interested_in"),
            "date_of_birth": data.get("date_of_birth"),
        },
    )

    # ----------------------------
    # Update public.profile (extended onboarding)
    # ----------------------------
    # If these are json/jsonb columns, passing JSON strings is safest.
    height_prefs = data.get("height_preferences")
    lifestyle_tags = data.get("lifestyle_tags")

    db.execute(
        text("""
            update public.profile
            set
                height_inches       = coalesce(:height_inches, height_inches),
                height_preferences  = coalesce(:height_preferences::jsonb, height_preferences),
                intent              = coalesce(:intent, intent),
                wingman_style       = coalesce(:wingman_style, wingman_style),
                lifestyle_tags      = coalesce(:lifestyle_tags::jsonb, lifestyle_tags),
                note_text           = coalesce(:note_text, note_text),
                updated_at          = now()
            where user_id = :uid
        """),
        {
            "uid": user_id,
            "height_inches": data.get("height_inches"),
            "height_preferences": json.dumps(height_prefs) if height_prefs is not None else None,
            "intent": data.get("intent"),
            "wingman_style": data.get("wingman_style"),
            "lifestyle_tags": json.dumps(lifestyle_tags) if lifestyle_tags is not None else None,
            "note_text": data.get("note_text"),
        },
    )

    db.commit()


def update_settings(db: Session, user_id: str, data: dict):
    ensure_settings_exists(db, user_id)

    db.execute(
        text("""
            update public.user_settings
            set
                ai_tone = coalesce(:ai_tone, ai_tone),
                auto_nudge = coalesce(:auto_nudge, auto_nudge),
                notify_new_match = coalesce(:notify_new_match, notify_new_match),
                notify_new_message = coalesce(:notify_new_message, notify_new_message),
                notify_daily_reveal = coalesce(:notify_daily_reveal, notify_daily_reveal),
                delayed_response_enabled = coalesce(:delayed_response_enabled, delayed_response_enabled),
                delayed_response_minutes = coalesce(:delayed_response_minutes, delayed_response_minutes),
                updated_at = now()
            where user_id = :uid
        """),
        {
            "uid": user_id,
            "ai_tone": data.get("ai_tone"),
            "auto_nudge": data.get("auto_nudge"),
            "notify_new_match": data.get("notify_new_match"),
            "notify_new_message": data.get("notify_new_message"),
            "notify_daily_reveal": data.get("notify_daily_reveal"),
            "delayed_response_enabled": data.get("delayed_response_enabled"),
            "delayed_response_minutes": data.get("delayed_response_minutes"),
        },
    )
    db.commit()