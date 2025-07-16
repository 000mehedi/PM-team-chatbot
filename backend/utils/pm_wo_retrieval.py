import os
from supabase import create_client
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

from frontend.pm_schedule_viewer import get_status_color
def get_supabase_client():
    """Returns a configured Supabase client"""
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY environment variables must be set")
        
    return create_client(supabase_url, supabase_key)

def get_distinct_statuses():
    """
    Get a list of distinct status values from the database
    
    Returns:
        list: List of unique status values
    """
    try:
        print("Retrieving distinct status values...")
        # Connect to Supabase
        supabase = get_supabase_client()
        print("Supabase connection created successfully")
        
        # Query distinct status values
        response = supabase.table('pm_work_orders').select('status').execute()
        print(f"Query response received: {len(response.data)} rows")
        
        # Extract unique statuses, removing None/empty values
        statuses = set()
        for record in response.data:
            status_value = record.get('status')
            if status_value:
                statuses.add(status_value)
                print(f"Found status: {status_value}")
        
        result = sorted(list(statuses))
        print(f"Returning {len(result)} distinct statuses: {result}")
        return result
    except Exception as e:
        print(f"Error retrieving statuses: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return []
def get_building_info(building_id_or_name):
    """
    Get zone and region information for a specific building
    
    Args:
        building_id_or_name (str): Building ID or name to search for
        
    Returns:
        dict: Dictionary with building information including zone and region
    """
    try:
        # Connect to Supabase
        supabase = get_supabase_client()
        
        # Try to search by ID first
        if building_id_or_name and (building_id_or_name.strip().isdigit() or 
                                     (building_id_or_name.strip().startswith('B') and 
                                      building_id_or_name.strip()[1:].isdigit())):
            # It looks like a building ID
            building_id = building_id_or_name.strip()
            response = supabase.table("pm_work_orders").select("building_name, zone, region").eq("building_id", building_id).limit(1).execute()
            
            if response.data:
                return response.data[0]
        
        # If no results or not an ID, try by name
        response = supabase.table("pm_work_orders").select("building_name, zone, region").ilike("building_name", f"%{building_id_or_name}%").limit(1).execute()
        
        if response.data:
            return response.data[0]
            
        # If still no results, try getting any record with this ID in any field
        if building_id_or_name:
            # Try building_id as a partial match
            response = supabase.table("pm_work_orders").select("building_name, zone, region").ilike("building_id", f"%{building_id_or_name}%").limit(1).execute()
            if response.data:
                return response.data[0]
                
        # No results found
        return {"building_name": None, "zone": None, "region": None}
        
    except Exception as e:
        print(f"Error getting building info: {str(e)}")
        return {"building_name": None, "zone": None, "region": None}

def get_distinct_zones():
    """
    Get a list of all distinct zones in the pm_work_orders table
    """
    try:
        print("Attempting to retrieve distinct zones from database...")
        # Connect to your Supabase client
        supabase = get_supabase_client()
        print(f"Supabase client created successfully: {supabase is not None}")
        
        # Query distinct zones
        print("Executing zone query...")
        response = supabase.table("pm_work_orders").select("zone").execute()

        # Extract unique non-null zone values
        zones = set()
        for item in response.data:
            if item.get("zone"):  # Only add non-null zones
                zones.add(item["zone"])
                
        print(f"Found {len(zones)} distinct zones in database: {zones}")
        return list(zones)
    except Exception as e:
        print(f"Error getting distinct zones: {e}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return []

def get_distinct_regions():
    """
    Get a list of all distinct regions in the pm_work_orders table
    """
    try:
        # Connect to your Supabase database
        supabase = get_supabase_client()
        
        # Query distinct regions
        response = supabase.table("pm_work_orders").select("region").execute()
        
        # Extract unique non-null region values
        regions = set()
        for item in response.data:
            if item.get("region"):  # Only add non-null regions
                regions.add(item["region"])
                
        return list(regions)
    except Exception as e:
        print(f"Error getting distinct regions: {e}")
        return []

def get_pm_data(start_date=None, end_date=None, status=None, building=None, 
                trade=None, region=None, zone=None, frequency=None, limit=10000):
    """
    Retrieves PM data based on filters
    
    Args:
        start_date (str): Start date for filtering (YYYY-MM-DD)
        end_date (str): End date for filtering (YYYY-MM-DD)
        status (str): Work order status filter
        building (str): Building name or ID filter
        trade (str): Trade filter
        region (str): Region filter
        zone (str): Zone filter
        frequency (str): PM frequency filter (maps to service_category)
        limit (int): Maximum number of records to return (default 10000)
        
    Returns:
        pd.DataFrame: DataFrame containing filtered PM work orders
    """
    try:
        supabase = get_supabase_client()
        
        # Start the query
        query = supabase.table('pm_work_orders').select('*')
        
        # Apply date filters - check scheduled_start_date is within range
        # Also check if dates are provided
        if start_date:
            # Use a range query with gte (greater than or equal)
            query = query.gte('date_created', start_date)
            
        if end_date:
            # Use a range query with lte (less than or equal)
            # Add 1 day to include the end date fully
            next_day = (datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
            query = query.lt('date_created', next_day)
            
        # Apply other filters
        if status and status != "All":
            query = query.eq('status', status)
            
        # Replace the current building filter code (around line 110-117) with this:
        if building:
            # Check if it's a building ID or a building name
            if building.strip().isdigit() or (building.strip().startswith('B') and building.strip()[1:].isdigit()):
                # It's a numeric ID - need to handle both numeric IDs and string IDs
                building_id = building.strip()
                # Try both exact match on building_id field and partial match if the ID is embedded in the field
                query = query.or_(f"building_id.eq.{building_id},building_id.ilike.%{building_id}%")
                print(f"Searching by building ID: {building_id}")
            else:
                # It's more likely a building name - search with partial matching
                query = query.ilike('building_name', f'%{building}%')
                print(f"Searching by building name: {building}")
                    
        if trade and trade != "All":
            query = query.eq('trade', trade)
            
        if region and region != "All":
            query = query.eq('region', region)
            
        if zone and zone != "All":
            query = query.eq('zone', zone)
            
        if frequency and frequency != "All":
            # Map frequency to appropriate service_category values
            query = query.eq('service_category', frequency)
        
        # Execute the query with a limit (or unlimited if limit is 0)
        print(f"Executing PM data query with filters: start_date={start_date}, end_date={end_date}, status={status}, building={building}, zone={zone}")
        
        if limit <= 0:
            # For unlimited retrieval, use pagination to get all records
            # Supabase has a default limit of 1000 per request
            all_data = []
            page_size = 1000
            page = 0
            
            while True:
                # Fetch a page of data
                page_response = query.order('scheduled_start_date', desc=True).range(page * page_size, (page + 1) * page_size - 1).execute()
                
                if not page_response.data:
                    # No more data, break the loop
                    break
                    
                all_data.extend(page_response.data)
                print(f"Retrieved page {page + 1} with {len(page_response.data)} records")
                
                if len(page_response.data) < page_size:
                    # Not a full page, means we've reached the end
                    break
                    
                # Move to next page
                page += 1
            
            print(f"Retrieved a total of {len(all_data)} PM work orders")
            
            # Convert to DataFrame
            if all_data:
                df = pd.DataFrame(all_data)
                
                # Debug: Print date range of results
                if 'scheduled_start_date' in df.columns and not df.empty:
                    df['scheduled_start_date'] = pd.to_datetime(df['scheduled_start_date'])
                    min_date = df['scheduled_start_date'].min()
                    max_date = df['scheduled_start_date'].max()
                    print(f"Date range in results: {min_date} to {max_date}")
                
                return df
            else:
                print("No PM work orders found with the specified filters")
                return pd.DataFrame()
        else:
            # Limited retrieval (original code)
            response = query.order('scheduled_start_date', desc=True).limit(limit).execute()
            
            # Convert to DataFrame
            if response.data:
                print(f"Retrieved {len(response.data)} PM work orders")
                df = pd.DataFrame(response.data)
                
                # Debug: Print date range of results
                if 'scheduled_start_date' in df.columns and not df.empty:
                    df['scheduled_start_date'] = pd.to_datetime(df['scheduled_start_date'])
                    min_date = df['scheduled_start_date'].min()
                    max_date = df['scheduled_start_date'].max()
                    print(f"Date range in results: {min_date} to {max_date}")
                
                return df
            else:
                print("No PM work orders found with the specified filters")
                return pd.DataFrame()
            
    except Exception as e:
        print(f"Error retrieving PM data: {str(e)}")
        raise

def get_monthly_trend(df):
    """Get monthly trend data with all status types"""
    if 'scheduled_start_date' not in df.columns or df.empty:
        return []
        
    # Add month column
    df['month'] = df['scheduled_start_date'].dt.strftime('%Y-%m')
    
    # Get total counts by month
    monthly_counts = df.groupby('month').size().reset_index(name='total')
    
    # Get counts by status for each month
    if 'status_lower' in df.columns:
        # Get unique statuses
        all_statuses = df['status_lower'].unique()
        
        # Create a DataFrame for each status
        status_dfs = []
        for status in all_statuses:
            status_df = df[df['status_lower'] == status]
            status_counts = status_df.groupby('month').size().reset_index(name=f"status_{status}")
            status_dfs.append(status_counts)
        
        # Start with the total counts
        monthly_trend = monthly_counts
        
        # Merge in each status
        for status_df in status_dfs:
            monthly_trend = pd.merge(monthly_trend, status_df, on='month', how='left')
        
        # Fill NaN values with 0 and convert to int
        for col in monthly_trend.columns:
            if col != 'month':
                monthly_trend[col] = monthly_trend[col].fillna(0).astype(int)
                
        # Keep the legacy 'completed' column for backward compatibility
        completed_statuses = ['completed', 'closed', 'finish', 'finished']
        completed_cols = [f"status_{s}" for s in completed_statuses if f"status_{s}" in monthly_trend.columns]
        
        if completed_cols:
            monthly_trend['completed'] = monthly_trend[completed_cols].sum(axis=1)
        else:
            monthly_trend['completed'] = 0
            
        # Add 'scheduled' column for backward compatibility (total - completed)
        monthly_trend['scheduled'] = monthly_trend['total']
        
        # Convert to list of dicts for the frontend
        return monthly_trend.to_dict('records')
    else:
        # Fallback to old method if status_lower is not available
        # Count completed PMs per month
        monthly_completed = df.groupby('month').size().reset_index(name='scheduled')
        return monthly_completed.to_dict('records')

def detect_pm_anomalies(df):
    """Detect anomalies in PM data"""
    anomalies = []
    
    try:
        if not df.empty and len(df) > 50:
            # Check for unusual completion times
            if 'completion_time' in df.columns:
                # Use IQR method to find outliers
                Q1 = df['completion_time'].quantile(0.25)
                Q3 = df['completion_time'].quantile(0.75)
                IQR = Q3 - Q1
                
                # Define bounds for outliers
                lower_bound = Q1 - 1.5 * IQR
                upper_bound = Q3 + 1.5 * IQR
                
                # Find outliers
                outliers = df[(df['completion_time'] < lower_bound) | (df['completion_time'] > upper_bound)]
                
                if len(outliers) > 0:
                    # Group by equipment to find patterns
                    equipment_anomalies = outliers.groupby('equipment').size().reset_index(name='count')
                    equipment_anomalies = equipment_anomalies.sort_values('count', ascending=False).head(5)
                    
                    for _, row in equipment_anomalies.iterrows():
                        anomalies.append({
                            "type": "completion_time",
                            "equipment": row['equipment'],
                            "count": int(row['count']),
                            "message": f"Unusual completion times for {row['equipment']}"
                        })
            
            # Check for buildings with declining completion rates
            if 'building_name' in df.columns and 'scheduled_start_date' in df.columns and 'status_lower' in df.columns:
                df['month_year'] = df['scheduled_start_date'].dt.strftime('%Y-%m')
                building_completion = df.groupby(['building_name', 'month_year']).apply(
                    lambda x: len(x[x['status_lower'].isin(['completed', 'closed', 'finish', 'finished'])]) / len(x) * 100
                    if len(x) > 0 else 0
                ).reset_index(name='completion_rate')
                
                # Find buildings with consistently declining rates
                for building in building_completion['building_name'].unique():
                    building_data = building_completion[building_completion['building_name'] == building].sort_values('month_year')
                    
                    if len(building_data) >= 3:
                        rates = building_data['completion_rate'].tolist()
                        if rates[-1] < rates[-2] < rates[-3]:
                            anomalies.append({
                                "type": "declining_performance",
                                "building": building,
                                "current_rate": rates[-1],
                                "message": f"Consistently declining completion rates at {building}"
                            })
    except Exception as e:
        print(f"Error in anomaly detection: {str(e)}")
        
    return anomalies

# Add this new function after get_scheduling_recommendations
def get_pm_calendar_data(start_date=None, end_date=None, building=None, region=None, zone=None, status=None):
    """
    Get PM data formatted for calendar views, separating past due and future PMs
    
    Args:
        start_date (str): Start date for filtering (YYYY-MM-DD)
        end_date (str): End date for filtering (YYYY-MM-DD)
        building (str): Building filter
        region (str): Region filter
        zone (str): Zone filter
        status (list or str): Status filter, can be a single status or list of statuses
        
    Returns:
        dict: Dictionary containing calendar-formatted events and statistics
    """
    try:
        today = datetime.now()
        
        # Default to current month + next 2 months if no dates provided
        if not start_date:
            start_date = (today - timedelta(days=30)).strftime('%Y-%m-%d')
        if not end_date:
            # Default to 3 months from today
            end_date = (today + timedelta(days=90)).strftime('%Y-%m-%d')
            
        # Get PM data for the date range - handle status properly
        if status:
            # For multi-select case (status is a list)
            if isinstance(status, list) and status:
                # Use the get_pm_data function's custom query logic
                # We'll build a custom filter for the status list
                df = get_pm_data(
                    start_date=start_date, 
                    end_date=end_date, 
                    building=building, 
                    region=region, 
                    zone=zone,
                    # Don't pass status here - we'll handle multiple statuses below
                    limit=0
                )
                
                # Filter by the list of statuses after getting the data
                if not df.empty:
                    # Convert all to lowercase for case-insensitive comparison
                    df['status_lower'] = df['status'].astype(str).str.lower()
                    status_lower = [s.lower() for s in status]
                    df = df[df['status_lower'].isin(status_lower)]
            else:
                # Single status case (backward compatibility)
                df = get_pm_data(
                    start_date=start_date, 
                    end_date=end_date, 
                    building=building, 
                    region=region, 
                    zone=zone,
                    status=status,
                    limit=0
                )
        else:
            # No status filter
            df = get_pm_data(
                start_date=start_date, 
                end_date=end_date, 
                building=building, 
                region=region, 
                zone=zone,
                limit=0
            )
        
        if df.empty:
            return {
                "events": [],
                "past_due": [],
                "future": [],
                "stats": {
                    "total": 0,
                    "past_due": 0,
                    "today": 0,
                    "future": 0,
                    "completed": 0
                }
            }
            
        # Create status_lower for filtering if it doesn't exist
        if 'status_lower' not in df.columns and 'status' in df.columns:
            df['status_lower'] = df['status'].astype(str).str.lower()
        
        # Convert dates to datetime if needed
        df['scheduled_start_date'] = pd.to_datetime(df['scheduled_start_date'])
        
        # Ensure date_created is available and in datetime format
        if 'date_created' not in df.columns:
            # If date_created is not available, fall back to scheduled_start_date
            df['date_created'] = df['scheduled_start_date']
        else:
            df['date_created'] = pd.to_datetime(df['date_created'])
            
        if 'date_completed' in df.columns:
            df['date_completed'] = pd.to_datetime(df['date_completed'])
        
        # Split into past due, today, and future PMs - using date_created instead
        completed_mask = df['status_lower'].isin(['completed', 'closed', 'finish', 'finished', 'work complete']) if 'status_lower' in df.columns else pd.Series(False, index=df.index)
        past_due_mask = (df['date_created'] < today) & ~completed_mask
        today_mask = (df['date_created'].dt.date == today.date()) & ~completed_mask
        future_mask = (df['date_created'] > today) & ~completed_mask
        
        # Create calendar events for all PMs
        calendar_events = []
        past_due_events = []
        future_events = []
        
        # Count statistics
        stats = {
            "total": len(df),
            "past_due": sum(past_due_mask),
            "today": sum(today_mask),
            "future": sum(future_mask),
            "completed": sum(completed_mask)
        }
        
        for _, row in df.iterrows():
            # Determine if past due, today, or future
            is_past_due = past_due_mask.iloc[_] if isinstance(_, int) and _ < len(past_due_mask) else False
            is_today = today_mask.iloc[_] if isinstance(_, int) and _ < len(today_mask) else False
            is_future = future_mask.iloc[_] if isinstance(_, int) and _ < len(future_mask) else False
            is_completed = completed_mask.iloc[_] if isinstance(_, int) and _ < len(completed_mask) else False
            
            # Get status from row
            status_value = row.get('status', '')
            
            # Use the get_status_color function to determine color based on status
            color = get_status_color(status_value)
            
            # Determine text color based on status for better contrast
            status_lower = str(status_value).lower()
            if status_lower in ["waiting on invoice", "waiting for po", "waiting for parts", "open", "due today"]:
                textColor = "#000000"  # Black text for light backgrounds
            else:
                textColor = "#FFFFFF"  # White text for dark backgrounds
                
            # Calculate days from today - using date_created instead
            days_from_today = (row['date_created'] - today).days
            days_label = f"{abs(days_from_today)} days {'overdue' if days_from_today < 0 else 'from now'}"
            if days_from_today == 0:
                days_label = "Today"
                
            # Create event title
            equipment = row.get('equipment', 'Equipment')
            building = row.get('building_name', 'Building')
            description = row.get('description', 'Description')
            
            title = f"{description} @ {building}"
            
            # Create description with details
            description_parts = []
            
            # Add important fields to description
            important_fields = [
              
                ('Building', building),
                ('Equipment', equipment),
                ('Status', status_value),
                ('Scheduled Date', row.get('scheduled_start_date').strftime('%Y-%m-%d') if isinstance(row.get('scheduled_start_date'), pd.Timestamp) else row.get('scheduled_start_date', '')),
                ('Trade', row.get('trade', '')),
                ('Service Category', row.get('service_category', '')),
                ('Description', row.get('description', '')),
               
            ]
            
            for label, value in important_fields:
                if value and str(value).strip():
                    description_parts.append(f"<b>{label}:</b> {value}<br>")
                    
            description = "".join(description_parts)
            
            # Create the calendar event - using date_created instead
            event = {
                "title": title,
                "start": row['date_created'].strftime('%Y-%m-%d'),
                "color": color,
                "textColor": textColor,
                "extendedProps": {
                    "status": status_value,
                    "building": building,
                    "equipment": equipment,
                    "description": description,
                    "trade": row.get('trade', ''),
                    "service_category": row.get('service_category', ''),
                    "work_order": row.get('work_order', ''),
                    "days_from_today": days_from_today,
                    "is_past_due": is_past_due,
                    "is_today": is_today,
                    "is_future": is_future,
                    "is_completed": is_completed
                }
            }
            
            # Add to appropriate lists
            calendar_events.append(event)
            
            if is_past_due:
                past_due_events.append(event)
            elif is_future or is_today:
                future_events.append(event)
            
        return {
            "events": calendar_events,
            "past_due": past_due_events,
            "future": future_events,
            "stats": stats
        }
        
    except Exception as e:
        print(f"Error creating PM calendar data: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return {
            "events": [],
            "past_due": [],
            "future": [],
            "stats": {
                "total": 0,
                "past_due": 0,
                "today": 0,
                "future": 0,
                "completed": 0
            },
            "error": str(e)
        }
def get_resource_recommendations(df):
    """Generate resource allocation recommendations"""
    recommendations = []
    
    try:
        if not df.empty:
            # Find trades with high workload
            if 'trade' in df.columns:
                trade_workload = df.groupby('trade').size().reset_index(name='count')
                trade_workload = trade_workload.sort_values('count', ascending=False)
                
                # Calculate average PMs per trade
                avg_workload = trade_workload['count'].mean()
                
                # Find trades with much higher than average workload
                high_workload_trades = trade_workload[trade_workload['count'] > avg_workload * 1.5]
                
                for _, row in high_workload_trades.iterrows():
                    recommendations.append({
                        "type": "resource_allocation",
                        "trade": row['trade'],
                        "current_workload": int(row['count']),
                        "avg_workload": int(avg_workload),
                        "message": f"Consider additional resources for {row['trade']} team"
                    })
            
            # Find buildings with high PM backlog
            if 'building_name' in df.columns and 'status_lower' in df.columns:
                building_status = df.groupby(['building_name', 'status_lower']).size().reset_index(name='count')
                
                for building in building_status['building_name'].unique():
                    building_data = building_status[building_status['building_name'] == building]
                    
                    overdue = building_data[building_data['status_lower'].isin(['overdue', 'late', 'delayed'])]
                    overdue_count = overdue['count'].sum() if not overdue.empty else 0
                    
                    if overdue_count >= 10:
                        recommendations.append({
                            "type": "backlog_reduction",
                            "building": building,
                            "overdue_count": int(overdue_count),
                            "message": f"High backlog at {building} - consider focused maintenance event"
                        })
    except Exception as e:
        print(f"Error generating recommendations: {str(e)}")
        
    return recommendations

def generate_smart_alerts(df):
    """Generate smart alerts based on PM data patterns"""
    alerts = []
    
    try:
        if not df.empty:
            # Alert for buildings with high priority overdue PMs
            if 'priority' in df.columns and 'status_lower' in df.columns and 'building_name' in df.columns:
                # Convert priority to string if it's not already
                df['priority'] = df['priority'].astype(str)
                
                high_priority = df[
                    (df['priority'].str.lower().isin(['critical', 'high', '1', '2'])) & 
                    (~df['status_lower'].isin(['completed', 'closed', 'finish', 'finished']))
                ]
                
                building_alerts = high_priority.groupby('building_name').size().reset_index(name='count')
                building_alerts = building_alerts.sort_values('count', ascending=False)
                
                for _, row in building_alerts.iterrows():
                    if row['count'] > 0:
                        alerts.append({
                            "severity": "high" if row['count'] > 5 else "medium",
                            "building": row['building_name'],
                            "count": int(row['count']),
                            "message": f"{row['count']} high-priority PMs need attention at {row['building_name']}"
                        })
            
            # Alert for equipment with repeated maintenance
            if 'equipment' in df.columns:
                # Look for equipment with multiple PMs in the time period
                equipment_count = df.groupby('equipment').size().reset_index(name='count')
                frequent_maintenance = equipment_count[equipment_count['count'] > 3]  # Threshold for "frequent"
                
                for _, row in frequent_maintenance.head(5).iterrows():
                    alerts.append({
                        "severity": "medium",
                        "equipment": row['equipment'],
                        "count": int(row['count']),
                        "message": f"{row['equipment']} has required {row['count']} maintenance visits - consider inspection"
                    })
    except Exception as e:
        print(f"Error generating alerts: {str(e)}")
    
    return alerts

def forecast_pm_workload(df, periods=3):
    """Forecast future PM workload using time series analysis"""
    forecast_results = {}
    
    try:
        if not df.empty and 'scheduled_start_date' in df.columns and len(df) > 60:
            # Try using Prophet if available
            try:
                from prophet import Prophet
                has_prophet = True
            except ImportError:
                has_prophet = False
            
            if has_prophet:
                # Prepare data for Prophet
                df['date'] = pd.to_datetime(df['scheduled_start_date'])
                ts_data = df.groupby(df['date'].dt.strftime('%Y-%m-%d')).size().reset_index()
                ts_data.columns = ['ds', 'y']
                ts_data['ds'] = pd.to_datetime(ts_data['ds'])
                
                # Create and fit the model
                model = Prophet(daily_seasonality=False, yearly_seasonality=True)
                model.fit(ts_data)
                
                # Make future dataframe and forecast
                future = model.make_future_dataframe(periods=periods, freq='M')
                forecast = model.predict(future)
                
                # Extract results
                forecast_results = {
                    "forecast_dates": forecast['ds'].tail(periods).dt.strftime('%Y-%m').tolist(),
                    "forecast_values": forecast['yhat'].tail(periods).round().astype(int).tolist(),
                    "forecast_lower": forecast['yhat_lower'].tail(periods).round().astype(int).tolist(),
                    "forecast_upper": forecast['yhat_upper'].tail(periods).round().astype(int).tolist(),
                    "method": "prophet"
                }
            else:
                # Fall back to simple moving average if Prophet isn't installed
                df['month'] = df['scheduled_start_date'].dt.strftime('%Y-%m')
                monthly_counts = df.groupby('month').size()
                
                # Calculate 3-month moving average
                if len(monthly_counts) >= 3:
                    avg = monthly_counts.rolling(window=3, min_periods=1).mean()
                    last_avg = avg.iloc[-1]
                else:
                    last_avg = monthly_counts.mean()
                
                # Simple forecast based on last average
                last_month = pd.to_datetime(monthly_counts.index[-1] if not monthly_counts.empty else datetime.now().strftime('%Y-%m'))
                forecast_months = [(last_month + pd.DateOffset(months=i)).strftime('%Y-%m') for i in range(1, periods+1)]
                
                forecast_results = {
                    "forecast_dates": forecast_months,
                    "forecast_values": [round(last_avg)] * periods,
                    "method": "moving_average"
                }
        else:
            forecast_results = {"status": "insufficient data for forecast"}
    except Exception as e:
        print(f"Error forecasting PM workload: {str(e)}")
        forecast_results = {"error": str(e)}
        
    return forecast_results

def get_scheduling_recommendations(df, look_ahead_days=30):
    """
    Generate intelligent recommendations for which PMs to schedule next
    with predictions for optimal scheduling days (e.g., Thursdays)
    
    Args:
        df: DataFrame containing PM work orders
        look_ahead_days: Number of days to look ahead for scheduling
        
    Returns:
        dict: Dictionary containing scheduling recommendations
    """
    recommendations = []
    
    try:
        if df.empty:
            return {"this_week": [], "next_week": [], "later": [], "all": []}
            
        # Make sure we have the required columns
        required_cols = ['scheduled_start_date', 'status', 'building_name', 'equipment']
        if not all(col in df.columns for col in required_cols):
            return {"this_week": [], "next_week": [], "later": [], "all": []}
            
        today = datetime.now()
        future_date = today + timedelta(days=look_ahead_days)
        
        # Create a status_lower column if it doesn't exist
        if 'status_lower' not in df.columns:
            df['status_lower'] = df['status'].astype(str).str.lower()
        
        # Filter to get upcoming PMs not yet scheduled or in progress
        upcoming_mask = (
            (df['scheduled_start_date'] >= today) & 
            (df['scheduled_start_date'] <= future_date) & 
            (~df['status_lower'].isin(['scheduled', 'in progress', 'completed', 'closed', 'finish', 'finished']))
        )
        
        upcoming_pms = df[upcoming_mask].copy()
        
        if upcoming_pms.empty:
            return {"this_week": [], "next_week": [], "later": [], "all": []}
            
        # Convert priority to numeric for sorting (higher is more important)
        priority_map = {
            'critical': 5,
            'high': 4,
            'medium': 3,
            'normal': 2,
            'low': 1
        }
        
        # Handle numeric priorities (1, 2, 3, etc.)
        for i, val in enumerate(['1', '2', '3', '4', '5']):
            priority_map[val] = 5 - i
            
        # Apply the priority mapping, defaulting to 2 (normal) if priority not in the map
        if 'priority' in upcoming_pms.columns:
            upcoming_pms['priority_num'] = upcoming_pms['priority'].astype(str).str.lower().map(
                lambda x: next((priority_map[key] for key in priority_map if key in x.lower()), 2)
            )
        else:
            upcoming_pms['priority_num'] = 2  # Default to normal priority
        
        # Calculate a scheduling score based on multiple factors
        
        # 1. Days until scheduled date (closer dates get higher score)
        upcoming_pms['days_until'] = (upcoming_pms['scheduled_start_date'] - today).dt.days
        max_days = upcoming_pms['days_until'].max() if not upcoming_pms.empty else 1
        upcoming_pms['date_score'] = 1 - (upcoming_pms['days_until'] / max_days if max_days > 0 else 0)
        
        # 2. Priority score (normalized to 0-1)
        upcoming_pms['priority_score'] = (upcoming_pms['priority_num'] - 1) / 4  # Normalize to 0-1
        
        # 3. Equipment criticality (if available)
        if 'equipment_criticality' in upcoming_pms.columns:
            # Normalize equipment criticality to 0-1 scale
            criticality_map = {'critical': 1.0, 'high': 0.75, 'medium': 0.5, 'low': 0.25}
            upcoming_pms['criticality_score'] = upcoming_pms['equipment_criticality'].str.lower().map(
                lambda x: next((criticality_map[key] for key in criticality_map if key in x.lower()), 0.5)
            )
        else:
            upcoming_pms['criticality_score'] = 0.5  # Default mid-value
            
        # 4. Building occupancy factor (if available)
        if 'building_occupancy' in upcoming_pms.columns:
            upcoming_pms['occupancy_score'] = upcoming_pms['building_occupancy'] / 100
        else:
            upcoming_pms['occupancy_score'] = 0.5  # Default mid-value
        
        # 5. Historical PM delay factor - check if this building or equipment has overdue PMs
        if 'building_name' in upcoming_pms.columns:
            # Calculate average delay by building
            buildings_with_overdue = df[(df['scheduled_start_date'] < today) & 
                                      (~df['status_lower'].isin(['completed', 'closed', 'finish', 'finished']))]['building_name'].unique()
            
            upcoming_pms['delay_risk_score'] = upcoming_pms['building_name'].apply(
                lambda x: 0.8 if x in buildings_with_overdue else 0.2
            )
        else:
            upcoming_pms['delay_risk_score'] = 0.5  # Default mid-value
            
        # Calculate final scheduling score
        # Weight factors according to importance
        upcoming_pms['scheduling_score'] = (
            0.35 * upcoming_pms['priority_score'] +  # Priority is most important
            0.25 * upcoming_pms['date_score'] +      # Due date is next most important
            0.15 * upcoming_pms['criticality_score'] +
            0.10 * upcoming_pms['occupancy_score'] +
            0.15 * upcoming_pms['delay_risk_score']
        )
        
        # Sort by scheduling score (descending)
        upcoming_pms = upcoming_pms.sort_values('scheduling_score', ascending=False)
        
        # Get the top recommendations
        top_pms = upcoming_pms.head(30)  # Increased to get more recommendations
        
        # Helper function to find the next Thursday
        def get_next_thursday(from_date):
            # Get days until next Thursday (where Thursday = 3 in Python's weekday() function)
            days_ahead = (3 - from_date.weekday()) % 7
            if days_ahead == 0:  # It's already Thursday
                if from_date.hour >= 17:  # If it's past work hours
                    days_ahead = 7  # Schedule for next Thursday
            next_thursday = from_date + timedelta(days=days_ahead)
            return next_thursday.replace(hour=9, minute=0, second=0, microsecond=0)
        
        # Helper function to find last Thursday of month
        def get_last_thursday_of_month(date):
            # Move to the first day of next month
            if date.month == 12:
                first_of_next_month = datetime(date.year + 1, 1, 1)
            else:
                first_of_next_month = datetime(date.year, date.month + 1, 1)
            
            # Go back to the last day of current month
            last_day = first_of_next_month - timedelta(days=1)
            
            # Find the last Thursday of the month
            days_to_subtract = (last_day.weekday() - 3) % 7
            if days_to_subtract == 0:
                last_thursday = last_day
            else:
                last_thursday = last_day - timedelta(days=days_to_subtract)
                if last_thursday.weekday() != 3:  # Not a Thursday
                    last_thursday = last_thursday - timedelta(days=7)  # Go back a week
            
            return last_thursday.replace(hour=9, minute=0, second=0, microsecond=0)
        
        # Format recommendations
        for _, row in top_pms.iterrows():
            days_until = int(row['days_until'])
            due_text = f"{days_until} days" if days_until > 0 else "Today"
            priority_text = "Normal"
            if 'priority' in row:
                priority_val = row['priority_num'] if 'priority_num' in row else 2
                priority_text = next((k.capitalize() for k, v in priority_map.items() if v == priority_val), "Normal")
            
            pm_id = str(row.get('pm_id', row.get('id', row.name)))
            
            # Determine frequency based on patterns in the data or specific columns
            frequency = "Unknown"
            if 'service_category' in row:
                # Use actual frequency if it exists
                frequency = str(row['service_category'])
            elif 'frequency' in row:
                frequency = str(row['frequency'])
            else:
                # Try to infer frequency from description or equipment name
                desc = str(row.get('description', '')).lower() + " " + str(row.get('equipment', '')).lower()
                if any(term in desc for term in ['weekly', 'week', '7 day']):
                    frequency = "Weekly"
                elif any(term in desc for term in ['monthly', 'month', '30 day']):
                    frequency = "Monthly"
                elif any(term in desc for term in ['quarterly', 'quarter', '90 day', '3 month']):
                    frequency = "Quarterly"
                elif any(term in desc for term in ['semi-annual', 'semi annual', '6 month', 'biannual']):
                    frequency = "Semi-Annual"
                elif any(term in desc for term in ['annual', 'yearly', 'year', '12 month', '365 day']):
                    frequency = "Annual"
            
            # Generate recommended schedule date based on frequency
            if frequency.lower() in ['weekly', 'week', '7 day']:
                # Weekly PMs are scheduled on Thursdays
                recommended_date = get_next_thursday(today)
                schedule_reason = "Weekly PMs scheduled on Thursdays"
            elif frequency.lower() in ['monthly', 'month', '30 day']:
                # Monthly PMs are scheduled on last Thursday of month
                recommended_date = get_last_thursday_of_month(today)
                schedule_reason = "Monthly PMs scheduled on last Thursday of month"
            else:
                # Default to next Thursday for other frequencies
                recommended_date = get_next_thursday(today)
                schedule_reason = "Recommended for next available scheduling day (Thursday)"
            
            # Create recommendation
            recommendations.append({
                "pm_id": pm_id,
                "equipment": row['equipment'],
                "building": row['building_name'],
                "priority": priority_text,
                "frequency": frequency,
                "scheduled_date": row['scheduled_start_date'].strftime('%Y-%m-%d'),
                "days_until_due": days_until,
                "scheduling_score": round(row['scheduling_score'] * 100),
                "recommended_date": recommended_date.strftime('%Y-%m-%d'),
                "recommended_day": recommended_date.strftime('%A'),
                "schedule_reason": schedule_reason,
                "message": f"Schedule {row['equipment']} PM at {row['building_name']} - Due in {due_text}"
            })
            
        # Group recommendations by week for easier planning
        this_week = []
        next_week = []
        later = []
        
        # Get the end date of this week (next Sunday)
        this_week_end = today + timedelta(days=(6 - today.weekday()))
        next_week_end = this_week_end + timedelta(days=7)
        
        for rec in recommendations:
            due_date = datetime.strptime(rec['scheduled_date'], '%Y-%m-%d')
            if due_date <= this_week_end:
                this_week.append(rec)
            elif due_date <= next_week_end:
                next_week.append(rec)
            else:
                later.append(rec)
                
        return {
            "this_week": this_week,
            "next_week": next_week,
            "later": later,
            "all": recommendations
        }
        
    except Exception as e:
        print(f"Error generating scheduling recommendations: {str(e)}")
        return {"error": str(e), "this_week": [], "next_week": [], "later": [], "all": []}
    
def get_pm_metrics(start_date=None, end_date=None, building=None, region=None, zone=None):
    """
    Calculates PM completion metrics
    
    Args:
        start_date (str): Start date for metrics calculation
        end_date (str): End date for metrics calculation
        building (str): Building filter
        region (str): Region filter
        zone (str): Zone filter
        
    Returns:
        dict: Dictionary containing PM metrics and AI-powered insights
    """
    try:
        # Default to last 30 days if no dates provided
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
            
        # Get filtered data - use unlimited records for accurate metrics
        df = get_pm_data(start_date=start_date, end_date=end_date, 
                         building=building, region=region, zone=zone, limit=0)
        
        if df.empty:
            return {
                "total_pms": 0,
                "completed_pms": 0,
                "completion_rate": 0,
                "overdue_pms": 0,
                "avg_completion_days": 0,
                "monthly_trend": [],
                "status_counts": {},
                "ai_insights": {"status": "no data available"}
            }
        
        # Calculate metrics
        total_pms = len(df)
        
        # Count completed PMs (case-insensitive check for completed/closed/finished)
        status_col = 'status' if 'status' in df.columns else 'Status'
        if status_col in df.columns:
            # Convert status to lowercase for consistent comparison
            df['status_lower'] = df[status_col].astype(str).str.lower()
            completed_pms = len(df[df['status_lower'].isin(['completed', 'closed', 'finish', 'finished'])])
            
            # Count all status types
            status_counts = df.groupby('status_lower').size().to_dict()
        else:
            completed_pms = 0
            status_counts = {}
        
        # Calculate completion rate
        completion_rate = round((completed_pms / total_pms) * 100) if total_pms > 0 else 0
        
        # Count overdue PMs (scheduled date in past but not completed)
        current_date = datetime.now()
        
        # Make sure we have datetime objects for comparison
        if 'scheduled_start_date' in df.columns:
            df['scheduled_start_date'] = pd.to_datetime(df['scheduled_start_date'])
            
            # Create overdue mask - check if scheduled date is in the past and status is not completed
            overdue_mask = (
                (df['scheduled_start_date'] < current_date) & 
                (~df['status_lower'].isin(['completed', 'closed', 'finish', 'finished']))
            )
            overdue_pms = len(df[overdue_mask])
        else:
            overdue_pms = 0
        
        # Calculate average completion time in days
        avg_completion_days = 0
        if 'date_completed' in df.columns:
            # Convert to datetime
            df['date_completed'] = pd.to_datetime(df['date_completed'])
            
            # Filter only completed PMs with valid dates
            completed_df = df[
                (~df['date_completed'].isna()) & 
                (~df['scheduled_start_date'].isna()) &
                (df['status_lower'].isin(['completed', 'closed', 'finish', 'finished']))
            ]
            
            if not completed_df.empty:
                # Calculate completion time
                completed_df['completion_time'] = (
                    completed_df['date_completed'] - 
                    completed_df['scheduled_start_date']
                ).dt.days
                
                # Calculate mean - handle negative values (completed before scheduled)
                avg_completion_days = round(completed_df['completion_time'].abs().mean())
        
        # Get monthly trend data with all status types
        trend_data = get_monthly_trend(df)
        
        # Generate AI insights
        ai_insights = {}
        
        # 1. Predictive maintenance forecasting
        try:
            if not df.empty and 'scheduled_start_date' in df.columns and len(df) > 30:
                # Calculate completion rate trends over time
                df['week'] = df['scheduled_start_date'].dt.isocalendar().week
                weekly_completion = df.groupby('week').apply(
                    lambda x: len(x[x['status_lower'].isin(['completed', 'closed', 'finish', 'finished'])]) / len(x) * 100
                    if len(x) > 0 else 0
                ).reset_index(name='weekly_rate')
                
                # Simple trend analysis - is completion rate improving or declining?
                if len(weekly_completion) > 2:
                    try:
                        from scipy import stats
                        has_scipy = True
                    except ImportError:
                        has_scipy = False
                        
                    if has_scipy:
                        # Linear regression to find trend
                        x = weekly_completion['week'].values
                        y = weekly_completion['weekly_rate'].values
                        slope, _, r_value, p_value, _ = stats.linregress(x, y)
                        
                        # Predict next week's completion rate
                        next_week = x[-1] + 1
                        predicted_rate = slope * next_week + y[0] - (slope * x[0])
                        predicted_rate = max(0, min(100, predicted_rate))  # Keep between 0-100%
                        
                        # Determine trend direction
                        if slope > 0 and p_value < 0.1:
                            trend = "improving"
                        elif slope < 0 and p_value < 0.1:
                            trend = "declining"
                        else:
                            trend = "stable"
                    else:
                        # Simple trend calculation without scipy
                        y = weekly_completion['weekly_rate'].values
                        if len(y) > 2:
                            slope = (y[-1] - y[0]) / (len(y) - 1)
                            
                            predicted_rate = y[-1] + slope
                            predicted_rate = max(0, min(100, predicted_rate))
                            
                            if slope > 0.5:
                                trend = "improving"
                            elif slope < -0.5:
                                trend = "declining"
                            else:
                                trend = "stable"
                        else:
                            trend = "stable"
                            predicted_rate = y[-1] if len(y) > 0 else completion_rate
                            
                    # Predict workload for next month based on historical data
                    current_month = datetime.now().month
                    next_month = (current_month % 12) + 1
                    prev_year_same_month = df[df['scheduled_start_date'].dt.month == next_month]
                    
                    if not prev_year_same_month.empty:
                        predicted_workload = len(prev_year_same_month)
                    else:
                        predicted_workload = round(total_pms * 1.1)  # 10% increase as default prediction
                    
                    # Add predictions to the results
                    ai_insights["completion_trend"] = trend
                    ai_insights["predicted_next_rate"] = round(predicted_rate, 1)
                    ai_insights["predicted_workload"] = predicted_workload
                    if has_scipy:
                        ai_insights["confidence"] = abs(r_value) if not np.isnan(r_value) else 0.5
                else:
                    ai_insights["status"] = "insufficient data for trend prediction"
            else:
                ai_insights["status"] = "insufficient data for predictions"
        except Exception as e:
            print(f"Error generating trend predictions: {str(e)}")
            ai_insights["trend_error"] = str(e)
            
        # 2. Add anomaly detection
        try:
            anomalies = detect_pm_anomalies(df)
            ai_insights["anomalies"] = anomalies
        except Exception as e:
            print(f"Error detecting anomalies: {str(e)}")
            ai_insights["anomalies_error"] = str(e)
            
        # 3. Add resource recommendations
        try:
            recommendations = get_resource_recommendations(df)
            ai_insights["recommendations"] = recommendations
        except Exception as e:
            print(f"Error generating recommendations: {str(e)}")
            ai_insights["recommendations_error"] = str(e)
            
        # 4. Add smart alerts
        try:
            alerts = generate_smart_alerts(df)
            ai_insights["alerts"] = alerts
        except Exception as e:
            print(f"Error generating alerts: {str(e)}")
            ai_insights["alerts_error"] = str(e)
            
        # 5. Add workload forecast
        try:
            forecast = forecast_pm_workload(df)
            ai_insights["workload_forecast"] = forecast
        except Exception as e:
            print(f"Error forecasting workload: {str(e)}")
            ai_insights["forecast_error"] = str(e)
            
        # 6. Add scheduling recommendations
        try:
            # Get data for the next 60 days for scheduling purposes
            future_end_date = (datetime.now() + timedelta(days=60)).strftime('%Y-%m-%d')
            future_df = get_pm_data(start_date=datetime.now().strftime('%Y-%m-%d'), 
                                   end_date=future_end_date, building=building, region=region, zone=zone, limit=0)
            
            scheduling_recs = get_scheduling_recommendations(future_df, look_ahead_days=60)
            ai_insights["scheduling_recommendations"] = scheduling_recs
        except Exception as e:
            print(f"Error generating scheduling recommendations: {str(e)}")
            ai_insights["scheduling_error"] = str(e)
        
        # Return all metrics and AI insights
        return {
            "total_pms": int(total_pms),
            "completed_pms": int(completed_pms),
            "completion_rate": int(completion_rate),
            "overdue_pms": int(overdue_pms),
            "avg_completion_days": int(avg_completion_days),
            "monthly_trend": trend_data,
            "status_counts": status_counts,
            "ai_insights": ai_insights
        }
        
    except Exception as e:
        print(f"Error calculating PM metrics: {str(e)}")
        return {
            "error": str(e),
            "total_pms": 0,
            "completed_pms": 0,
            "completion_rate": 0,
            "overdue_pms": 0,
            "avg_completion_days": 0,
            "monthly_trend": [],
            "status_counts": {},
            "ai_insights": {"error": str(e)}
        }