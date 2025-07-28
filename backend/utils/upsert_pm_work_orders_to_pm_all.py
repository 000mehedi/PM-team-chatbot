import os
from supabase import create_client

def get_supabase_client():
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")
    return create_client(supabase_url, supabase_key)

def upsert_pm_work_orders_to_pm_all():
    supabase = get_supabase_client()
    # Fetch all work orders
    response = supabase.table('pm_work_orders').select('*').execute()
    work_orders = response.data if response.data else []

    for wo in work_orders:
        # Upsert each work order into pm_all
        # You must have a unique constraint on work_order_id in pm_all
        supabase.table('pm_all').upsert([{
            "selected": True,
            "work_order_id": wo.get("work_order"),
            "wo_type": wo.get("wo_type"),
            "status": wo.get("status"),
            "equipment": wo.get("equipment"),
            "building_name": wo.get("building_name"),
            "building_id": wo.get("building_id"),
            "description": wo.get("description"),
            "assigned_to": wo.get("assigned_to"),
            "trade": wo.get("trade"),
            "zone": wo.get("zone"),
            "organization": wo.get("organization"),
            "scheduled_start_date": wo.get("scheduled_start_date"),
            "date_completed": wo.get("date_completed"),
            "pm_code": wo.get("pm_code"),
            "last_updated_by": wo.get("last_updated_by"),
            "service_category": wo.get("service_category"),
            "service_code": wo.get("service_code"),
            "date_created": wo.get("date_created"),
            "region": wo.get("region")
        }], on_conflict="work_order_id").execute()

if __name__ == "__main__":
    upsert_pm_work_orders_to_pm_all()