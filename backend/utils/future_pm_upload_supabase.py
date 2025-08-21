import os
import sys
import pandas as pd
import numpy as np
import json
from datetime import datetime
from dotenv import load_dotenv

# Fix the import path issue
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Now try the import after fixing the path
try:
    from backend.utils.supabase_client import supabase
except ImportError:
    # Alternative: try local import if the file is in the same directory
    try:
        sys.path.append(current_dir)
        from supabase_client import supabase
    except ImportError:
        print("ERROR: Could not import supabase client. Please check that supabase_client.py exists.")
        print("It should be located at:", os.path.join(current_dir, "supabase_client.py"))
        exit(1)

import streamlit as st  # Added for Streamlit compatibility

# Load environment variables
load_dotenv()

# Custom JSON serializer to handle pandas Timestamp objects
class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (pd.Timestamp, datetime)):
            return obj.isoformat()
        return super().default(obj)

def upload_future_pm_to_supabase(excel_file_path: str, progress_callback=None):
    """
    Uploads preventive maintenance data from Excel file to Supabase future_pm table
    
    Args:
        excel_file_path: Path to the Excel file containing PM data
        progress_callback: Optional callback function to update UI progress (for Streamlit)
    
    Returns:
        dict: Summary of the upload operation including counts of records processed
    """
    print(f"Reading preventive maintenance data from Excel file: {excel_file_path}")
    
    # Read Excel file
    df = pd.read_excel(excel_file_path)
    
    # Clean column names - convert to lowercase and replace spaces with underscores
    df.columns = [col.lower().replace(' ', '_').replace('.', '').replace('__', '_') for col in df.columns]
    
    # Rename columns to match database schema
    column_mapping = {
        'select': 'selected',
        'work_order': 'work_order_id',
        'description': 'description',
        'status': 'status',
        'equipment': 'equipment',
        'equipment_description': 'equipment_description',
        'equipment_org': 'equipment_org',
        'pm': 'pm_code',
        'pm_type': 'pm_type',
        'maintenance_pattern': 'maintenance_pattern',
        'sequence': 'sequence',
        'scheduled_start_date': 'scheduled_start_date',
        'work_package': 'work_package',
        'wo_type': 'wo_type',
        'error_message': 'error_message'
    }
    
    # Rename columns based on the mapping
    df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})
    
    # Convert YES/NO to boolean for selected column
    if 'selected' in df.columns:
        df['selected'] = df['selected'].apply(lambda x: True if str(x).upper() == 'YES' else False)
    
    # Check for duplicates in the work_order_id column and keep only the last occurrence
    if 'work_order_id' in df.columns:
        duplicate_count = df.duplicated('work_order_id', keep=False).sum()
        if duplicate_count > 0:
            print(f"Found {duplicate_count} duplicate PM work order rows in the input file.")
            print("Keeping only the last occurrence of each duplicate work order.")
            df = df.drop_duplicates('work_order_id', keep='last')
    
    # Replace all NaN values with None for JSON compatibility
    df = df.replace({np.nan: None})
    
    # Convert date columns to proper format and then to ISO strings
    if 'scheduled_start_date' in df.columns:
        df['scheduled_start_date'] = pd.to_datetime(df['scheduled_start_date'], errors='coerce')
        # Convert timestamps to ISO format strings
        df['scheduled_start_date'] = df['scheduled_start_date'].apply(lambda x: x.isoformat() if pd.notna(x) else None)
    
    # Convert DataFrame to list of dictionaries
    records = df.to_dict('records')
    
    print(f"Found {len(records)} preventive maintenance records to process")
    
    # Process in batches
    batch_size = 100
    total_batches = (len(records) + batch_size - 1) // batch_size
    success_count = 0
    updated_count = 0
    inserted_count = 0
    
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
                
                # Convert work_order_id to string for consistency
                if key == 'work_order_id' and value is not None:
                    if isinstance(value, (int, float)) and not pd.isna(value):
                        if float(value).is_integer():
                            record[key] = str(int(value))
                        else:
                            record[key] = str(value)
                    elif isinstance(value, str) and value.endswith('.0'):
                        try:
                            record[key] = str(int(float(value)))
                        except (ValueError, TypeError):
                            pass
        
        print(f"Processing batch {batch_num} of {total_batches}...")
        
        try:
            # Get work order IDs from this batch
            work_orders_to_process = [r['work_order_id'] for r in batch if r.get('work_order_id') is not None]
            
            # Check which work orders already exist in the database
            existing_work_orders = set()
            if work_orders_to_process:
                try:
                    # Query in smaller sub-batches to avoid query length limits
                    check_batch_size = 50
                    for j in range(0, len(work_orders_to_process), check_batch_size):
                        check_batch = work_orders_to_process[j:j+check_batch_size]
                        query_result = supabase.table('future_pm').select('work_order_id').in_('work_order_id', check_batch).execute()
                        if hasattr(query_result, 'data'):
                            for item in query_result.data:
                                existing_work_orders.add(str(item['work_order_id']))
                except Exception as e:
                    print(f"Warning: Error checking existing work orders: {str(e)}. Will assume all are new.")
            
            # Delete existing records for these work orders
            if existing_work_orders:
                try:
                    # Delete in smaller sub-batches
                    delete_batch_size = 50
                    for j in range(0, len(existing_work_orders), delete_batch_size):
                        delete_batch = list(existing_work_orders)[j:j+delete_batch_size]
                        delete_result = supabase.table('future_pm').delete().in_('work_order_id', delete_batch).execute()
                        updated_count += len(delete_batch)
                except Exception as e:
                    print(f"Warning: Error deleting existing records: {str(e)}. Will attempt to insert anyway.")
            
            # Insert all records in this batch
            response = supabase.table('future_pm').insert(
                json.loads(json.dumps(batch, cls=JSONEncoder))
            ).execute()
            
            # Count inserts (new records) vs updates (deleted then inserted)
            new_inserts = len(batch) - len(existing_work_orders)
            inserted_count += new_inserts
            
            # Check for errors in the response
            if hasattr(response, 'error') and response.error:
                print(f"Error in batch {batch_num}: {response.error}")
            else:
                processed_count = len(response.data) if hasattr(response, 'data') else len(batch)
                print(f"Successfully processed batch {batch_num}: {processed_count} records")
                success_count += processed_count
                
            # Update progress if callback is provided
            if progress_callback:
                progress = min(1.0, (i + len(batch)) / len(records))
                progress_callback(progress)
                
        except Exception as e:
            print(f"Exception in batch {batch_num}: {str(e)}")
            
            # Debug information when an exception occurs
            print(f"Debugging batch {batch_num}:")
            for idx, record in enumerate(batch):
                if 'work_order_id' in record:
                    print(f"Record {idx}, work_order_id: {record['work_order_id']}, type: {type(record['work_order_id'])}")
    
    # Create summary of results
    summary = {
        "total_records": len(records),
        "processed_records": success_count,
        "inserted_records": inserted_count,
        "updated_records": updated_count,
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    print(f"Upload complete! Successfully processed {success_count} records.")
    print(f"  - {inserted_count} new records inserted")
    print(f"  - {updated_count} existing records updated")
    
    return summary

if __name__ == "__main__":
    # Use the specific Excel file name: PM.xlsx
    # Get the directory of the current script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    excel_file = os.path.join(current_dir, "PM.xlsx")
    
    # Check if the file exists
    if not os.path.exists(excel_file):
        print(f"ERROR: Excel file not found at {excel_file}")
        print("Please make sure 'PM.xlsx' is in the same directory as this script.")
        exit(1)
    
    try:
        # Upload preventive maintenance data
        upload_future_pm_to_supabase(excel_file)
        
    except Exception as e:
        print(f"Error during upload: {str(e)}")