import os
from datetime import datetime
from supabase import create_client

def get_supabase_client():
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")
    return create_client(supabase_url, supabase_key)

def remove_past_future_pms_with_null_selected():
    supabase = get_supabase_client()
    today_str = datetime.now().strftime('%Y-%m-%d')
    response = supabase.table('pm_all').delete().leq('scheduled_start_date', today_str).is_('selected', None).execute()
    deleted_count = len(response.data) if hasattr(response, 'data') and response.data else 0
    print(f"Deleted {deleted_count} PMs scheduled before {today_str} with selected=NULL.")
    
if __name__ == "__main__":
    remove_past_future_pms_with_null_selected()