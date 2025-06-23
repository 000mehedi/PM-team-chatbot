import os
import pandas as pd
import numpy as np
import json
from datetime import datetime
from dotenv import load_dotenv
# Import supabase client from your module
from supabase_client import supabase

# Load environment variables
load_dotenv()

# Custom JSON serializer to handle pandas Timestamp objects
class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (pd.Timestamp, datetime)):
            return obj.isoformat()
        return super().default(obj)

def upload_work_orders_to_supabase(excel_file_path: str):
    """
    Uploads work order data from Excel file to Supabase work_orders_history table
    """
    print(f"Reading data from Excel file: {excel_file_path}")
    
    # Read Excel file
    df = pd.read_excel(excel_file_path)
    
    # Clean column names - convert to lowercase and replace spaces with underscores
    df.columns = [col.lower().replace(' ', '_').replace('.', '').replace('__', '_') for col in df.columns]
    
    # Rename columns to match database schema
    column_mapping = {
        'priority_icon': 'priority',
        'work_order': 'work_order',
        'wo_type': 'wo_type',
        'status': 'status',
        'equipment': 'equipment',
        'building_name': 'building_name',
        'building_id': 'building_id',
        'description': 'description',
        'assigned_to': 'assigned_to',
        'trade': 'trade',
        'zone': 'zone',
        'organization': 'organization',
        'sched_start_date': 'scheduled_start_date',
        'date_completed': 'date_completed',
        'pm_code': 'pm_code',
        'last_updated_by': 'last_updated_by',
        'service_category': 'service_category',
        'service_code': 'service_code',
        'date_created': 'date_created',
        'region': 'region'
    }
    
    # Rename columns based on the mapping
    df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})
    
    # Replace all NaN values with None for JSON compatibility
    df = df.replace({np.nan: None})
    
    # Convert date columns to proper format and then to ISO strings
    date_columns = ['scheduled_start_date', 'date_completed', 'date_created']
    for col in date_columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
            # Convert timestamps to ISO format strings
            df[col] = df[col].apply(lambda x: x.isoformat() if pd.notna(x) else None)
    
    # Convert DataFrame to list of dictionaries
    records = df.to_dict('records')
    
    print(f"Found {len(records)} work order records to process")
    
    # Process in batches
    batch_size = 100
    total_batches = (len(records) + batch_size - 1) // batch_size
    success_count = 0
    
    for i in range(0, len(records), batch_size):
        batch = records[i:i+batch_size]
        batch_num = i // batch_size + 1
        
        # Additional cleaning for each batch
        for record in batch:
            for key, value in list(record.items()):
                # Convert any remaining Timestamp objects to strings
                if isinstance(value, (pd.Timestamp, datetime)):
                    record[key] = value.isoformat()
                # Convert NaN values to None
                elif isinstance(value, float) and np.isnan(value):
                    record[key] = None
                
                # Convert strings that look like floats to integers for specific fields
                if key in ['work_order', 'building_id'] and isinstance(value, str) and value.endswith('.0'):
                    try:
                        record[key] = int(float(value))
                    except (ValueError, TypeError):
                        # If conversion fails, keep the original value
                        pass
                
                # Also check for float values that should be integers
                if key in ['work_order', 'building_id'] and isinstance(value, float) and value.is_integer():
                    record[key] = int(value)
        
        print(f"Processing batch {batch_num} of {total_batches}...")
        
        try:
            # Two-step process: First delete existing records with these work_order values
            work_orders_to_update = [r['work_order'] for r in batch if r.get('work_order') is not None]
            
            if work_orders_to_update:
                # Delete in smaller sub-batches to avoid query length limits
                delete_batch_size = 50
                for j in range(0, len(work_orders_to_update), delete_batch_size):
                    delete_batch = work_orders_to_update[j:j+delete_batch_size]
                    try:
                        # Delete existing records for these work orders
                        supabase.table('work_orders_history').delete().in_('work_order', delete_batch).execute()
                    except Exception as e:
                        print(f"Warning: Error deleting existing records: {str(e)}")
            
            # Then insert the new records
            response = supabase.table('work_orders_history').insert(
                json.loads(json.dumps(batch, cls=JSONEncoder))
            ).execute()
            
            # Check for errors in the response
            if hasattr(response, 'error') and response.error:
                print(f"Error in batch {batch_num}: {response.error}")
            else:
                processed_count = len(response.data) if hasattr(response, 'data') else len(batch)
                print(f"Successfully processed batch {batch_num}: {processed_count} records")
                success_count += processed_count
                
        except Exception as e:
            print(f"Exception in batch {batch_num}: {str(e)}")
            
            # Debug information when an exception occurs
            print(f"Debugging batch {batch_num}:")
            for idx, record in enumerate(batch):
                if 'work_order' in record:
                    print(f"Record {idx}, work_order: {record['work_order']}, type: {type(record['work_order'])}")
                if 'building_id' in record:
                    print(f"Record {idx}, building_id: {record['building_id']}, type: {type(record['building_id'])}")
    
    print(f"Upload complete! Successfully processed {success_count} records.")

if __name__ == "__main__":
    # Use the specific Excel file name: Work.xlsx
    # Get the directory of the current script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    excel_file = os.path.join(current_dir, "Work.xlsx")
    
    # Check if the file exists
    if not os.path.exists(excel_file):
        print(f"ERROR: Excel file not found at {excel_file}")
        print("Please make sure 'Work.xlsx' is in the same directory as this script.")
        exit(1)
    
    try:
        # Upload work order data
        upload_work_orders_to_supabase(excel_file)
        
    except Exception as e:
        print(f"Error during upload: {str(e)}")