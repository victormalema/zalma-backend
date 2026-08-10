from supabase import create_client, Client
from config import Config

_supabase_client = None


def get_supabase() -> Client:
    """
    Returns a shared Supabase client using the service_role key.
    RLS is enabled with zero policies on every table, so this key is
    the only way in -- which is exactly the point: only this backend
    can read/write, never the browser directly.
    """
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = create_client(
            Config.SUPABASE_URL, Config.SUPABASE_SERVICE_KEY
        )
    return _supabase_client
