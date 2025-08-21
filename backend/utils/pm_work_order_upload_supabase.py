import os
import pandas as pd
import numpy as np
import json
from datetime import datetime
import time
from supabase import create_client

# Custom JSON serializer to handle pandas Timestamp objects
class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (pd.Timestamp, datetime)):
            return obj.isoformat()
        return super().default(obj)

def upload_pm_data_to_supabase(file_path, progress_callback=None):

    """
    Uploads PM work order data to Supabase from an Excel or CSV file
    
    Args:
        file_path (str): Path to the Excel or CSV file
        progress_callback (callable): Function to call with progress updates (0-1)
        
    Returns:
        dict: Summary of the upload process
    """
    # Initialize counters for summary
    summary = {
        "total_records": 0,
        "processed_records": 0,
        "inserted_records": 0,
        "updated_records": 0,
        "error_records": 0,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    print(f"Reading data from file: {file_path}")
    start_time = time.time()

    try:
        # Read the file based on extension
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)

        print(f"Loaded {len(df)} records from file")

        # Initialize Supabase client
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_KEY")

        if not supabase_url or not supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY environment variables must be set")

        supabase = create_client(supabase_url, supabase_key)
        print("Connected to Supabase")

        # Delete WOs where selected is FALSE and scheduled_start_date is before today
        try:
            today_str = datetime.now().date().isoformat()
            delete_result = supabase.table('pm_all') \
                .delete() \
                .eq('selected', False) \
                .lt('scheduled_start_date', today_str) \
                .execute()
            if hasattr(delete_result, 'data') and delete_result.data:
                print(f"Deleted {len(delete_result.data)} old unselected work orders from pm_all.")
        except Exception as e:
            print(f"Warning: Could not delete old unselected work orders: {str(e)}")
            
        # Clean column names - convert to lowercase and replace spaces with underscores
        df.columns = [col.lower().replace(' ', '_').replace('.', '').replace('__', '_') for col in df.columns]
        
        # Handle column name variations
        column_mapping = {
            'work_order': 'work_order_id',
            'sched_start_date': 'scheduled_start_date',
            'start_date': 'scheduled_start_date',
            'completion_date': 'date_completed',
            'created_date': 'date_created',
            'complete_date': 'date_completed'
        }
        
        # Rename columns if needed
        for old_name, new_name in column_mapping.items():
            if old_name in df.columns and new_name not in df.columns:
                df = df.rename(columns={old_name: new_name})

        # Remove 'priority' column if it exists
        if 'priority' in df.columns:
            df = df.drop(columns=['priority'])
        
        # Replace NaN values with None for proper JSON serialization
        df = df.replace({np.nan: None})
        
        # Convert date columns to proper datetime format and then to strings
        date_columns = ['scheduled_start_date', 'date_completed', 'date_created']
        for col in date_columns:
            if col in df.columns:
                print(f"Processing date column: {col}")
                df[col] = pd.to_datetime(df[col], errors='coerce')
                # Convert timestamps to ISO format strings
                df[col] = df[col].apply(lambda x: x.isoformat() if pd.notna(x) else None)
                
        # Initialize Supabase client
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_KEY")
        
        if not supabase_url or not supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY environment variables must be set")
            
        supabase = create_client(supabase_url, supabase_key)
        print("Connected to Supabase")
        
        # Convert DataFrame to list of dictionaries
        records = df.to_dict('records')
        
        # Process in batches
        batch_size = 100
        total_records = len(records)
        summary["total_records"] = total_records
        total_batches = (total_records + batch_size - 1) // batch_size
        
        print(f"Processing {total_records} records in {total_batches} batches (batch size: {batch_size})")
        
        for i in range(0, total_records, batch_size):
            batch = records[i:i+batch_size]
            batch_num = i // batch_size + 1
            batch_end = min(i + batch_size, total_records)
            
            print(f"Processing batch {batch_num}/{total_batches} (records {i+1}-{batch_end})...")
            
            # Additional cleaning for each batch
            for record in batch:
                for key, value in list(record.items()):
                    # Convert any remaining Timestamp objects to strings
                    if isinstance(value, (pd.Timestamp, datetime)):
                        record[key] = value.isoformat()
                    # Convert NaN values to None
                    elif isinstance(value, float) and np.isnan(value):
                        record[key] = None
                    # Convert work_order_id and building_id to strings for consistency
                    if key in ['work_order_id', 'building_id'] and value is not None:
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
                            query_result = supabase.table('pm_all').select('work_order_id').in_('work_order_id', check_batch).execute()
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
                            delete_result = supabase.table('pm_all').delete().in_('work_order_id', delete_batch).execute()
                            summary["updated_records"] += len(delete_batch)
                    except Exception as e:
                        print(f"Warning: Error deleting existing records: {str(e)}. Will attempt to insert anyway.")
                # Insert all records in this batch
                response = supabase.table('pm_all').insert(
                    json.loads(json.dumps(batch, cls=JSONEncoder))
                ).execute()
                # Count inserts (new records) vs updates (deleted then inserted)
                new_inserts = len(batch) - len(existing_work_orders)
                summary["inserted_records"] += new_inserts
                summary["processed_records"] += len(batch)
                # Check for errors in the response
                if hasattr(response, 'error') and response.error:
                    print(f"Error in batch {batch_num}: {response.error}")
                else:
                    print(f"Successfully processed batch {batch_num}: {len(batch)} records")
                # Update progress if callback is provided
                if progress_callback:
                    progress = min(1.0, batch_end / total_records)
                    progress_callback(progress)
                    
            except Exception as e:
                summary["error_records"] += len(batch)
                summary["processed_records"] -= len(batch)
                print(f"Exception in batch {batch_num}: {str(e)}")
                
                # Debug information when an exception occurs
                print(f"Debugging batch {batch_num}:")
                for idx, record in enumerate(batch[:5]):  # Show just first 5 records for debugging
                    if 'work_order_id' in record:
                        print(f"Record {idx}, work_order_id: {record['work_order_id']}, type: {type(record['work_order_id'])}")
        
        elapsed_time = time.time() - start_time
        print(f"Upload complete in {elapsed_time:.2f} seconds!")
        print(f"  - {summary['inserted_records']} new records inserted")
        print(f"  - {summary['updated_records']} existing records updated")
        print(f"  - {summary['error_records']} records with errors")
            
        return summary
        
    except Exception as e:
        print(f"Error uploading PM data: {str(e)}")
        raise