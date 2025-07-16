import os
import pandas as pd
import numpy as np
import json
from datetime import datetime
from dotenv import load_dotenv
# Import supabase client from your module
from backend.utils.supabase_client import supabase
import streamlit as st  # Added for Streamlit compatibility

# Load environment variables
load_dotenv()

# Custom JSON serializer to handle pandas Timestamp objects
class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (pd.Timestamp, datetime)):
            return obj.isoformat()
        return super().default(obj)

def upload_work_orders_to_supabase(excel_file_path: str, progress_callback=None):
    """
    Uploads work order data from Excel file to Supabase work_orders_history table
    
    Args:
        excel_file_path: Path to the Excel file containing work order data
        progress_callback: Optional callback function to update UI progress (for Streamlit)
    
    Returns:
        dict: Summary of the upload operation including counts of records processed
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
    
    # Check for duplicates in the work_order column and keep only the last occurrence
    if 'work_order' in df.columns:
        duplicate_count = df.duplicated('work_order', keep=False).sum()
        if duplicate_count > 0:
            print(f"Found {duplicate_count} duplicate work order rows in the input file.")
            print("Keeping only the last occurrence of each duplicate work order.")
            df = df.drop_duplicates('work_order', keep='last')
    
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
                
                # Convert work_order and building_id to strings for consistency
                if key in ['work_order', 'building_id'] and value is not None:
                    # Handle integer-like floats (e.g. 123.0)
                    if isinstance(value, (int, float)) and not pd.isna(value):
                        if float(value).is_integer():
                            record[key] = str(int(value))
                        else:
                            record[key] = str(value)
                    # Handle strings that look like floats (e.g. "123.0")
                    elif isinstance(value, str) and value.endswith('.0'):
                        try:
                            record[key] = str(int(float(value)))
                        except (ValueError, TypeError):
                            pass
        
        print(f"Processing batch {batch_num} of {total_batches}...")
        
        try:
            # Get work order IDs from this batch
            work_orders_to_process = [r['work_order'] for r in batch if r.get('work_order') is not None]
            
            # Check which work orders already exist in the database
            existing_work_orders = set()
            if work_orders_to_process:
                try:
                    # Query in smaller sub-batches to avoid query length limits
                    check_batch_size = 50
                    for j in range(0, len(work_orders_to_process), check_batch_size):
                        check_batch = work_orders_to_process[j:j+check_batch_size]
                        query_result = supabase.table('work_orders_history').select('work_order').in_('work_order', check_batch).execute()
                        if hasattr(query_result, 'data'):
                            for item in query_result.data:
                                existing_work_orders.add(str(item['work_order']))
                except Exception as e:
                    print(f"Warning: Error checking existing work orders: {str(e)}. Will assume all are new.")
            
            # Delete existing records for these work orders
            if existing_work_orders:
                try:
                    # Delete in smaller sub-batches
                    delete_batch_size = 50
                    for j in range(0, len(existing_work_orders), delete_batch_size):
                        delete_batch = list(existing_work_orders)[j:j+delete_batch_size]
                        delete_result = supabase.table('work_orders_history').delete().in_('work_order', delete_batch).execute()
                        updated_count += len(delete_batch)
                except Exception as e:
                    print(f"Warning: Error deleting existing records: {str(e)}. Will attempt to insert anyway.")
            
            # Insert all records in this batch
            response = supabase.table('work_orders_history').insert(
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
                if 'work_order' in record:
                    print(f"Record {idx}, work_order: {record['work_order']}, type: {type(record['work_order'])}")
                if 'building_id' in record:
                    print(f"Record {idx}, building_id: {record['building_id']}, type: {type(record['building_id'])}")
    
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