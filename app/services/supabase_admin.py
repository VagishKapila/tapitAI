import os
from supabase import create_client, Client

_SUPABASE: Client | None = None

def supabase_admin() -> Client:
    global _SUPABASE
    if _SUPABASE is not None:
        return _SUPABASE

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")

    _SUPABASE = create_client(url, key)
    return _SUPABASE
