import os
from supabase import create_client, Client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# Delete all future PMs (selected == False) with scheduled_start_date before today
response = (
    supabase.table("pm_all")
    .delete()
    .eq("selected", False)
    .lt("scheduled_start_date", "today")
    .execute()
)
print(f"Deleted {len(response.data)} old future PMs")