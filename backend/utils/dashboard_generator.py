import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import openai
import json
from backend.utils.supabase_client import supabase
import re

# Get OpenAI API key from environment variables
openai.api_key = os.getenv("OPENAI_API_KEY")

def get_latest_model_name():
    """Get the latest OpenAI model name"""
    try:
        with open("latest_model_name.txt", "r") as f:
            return f.read().strip()
    except Exception:
        return "gpt-3.5-turbo"  # Default model

def generate_daily_dashboard():
    """
    Generates a dashboard with insights from the previous day's work orders
    """
    # Calculate yesterday's date
    yesterday = (datetime.now() - timedelta(days=1)).date().isoformat()
    today = datetime.now().date().isoformat()
    
    print(f"Generating dashboard for date range: {yesterday} to {today}")
    
    # Fetch work orders from yesterday
    yesterday_query = supabase.table("work_orders_history") \
        .select("*") \
        .gte("date_created", yesterday) \
        .lt("date_created", today) \
        .execute()
    
    # Fetch recently closed work orders
    closed_query = supabase.table("work_orders_history") \
        .select("*") \
        .eq("status", "Closed") \
        .gte("date_completed", yesterday) \
        .lt("date_completed", today) \
        .execute()
    
    # First, get the count of critical work orders FROM YESTERDAY ONLY
    critical_count_query = supabase.table("work_orders_history") \
        .select("count", count="exact") \
        .ilike("priority", "%critical%") \
        .gte("date_created", yesterday) \
        .lt("date_created", today) \
        .execute()
    
    # Extract the total count
    total_critical_count = 0
    if hasattr(critical_count_query, 'count'):
        total_critical_count = critical_count_query.count
    elif isinstance(critical_count_query.data, dict) and 'count' in critical_count_query.data:
        total_critical_count = critical_count_query.data['count']
    elif isinstance(critical_count_query.data, list) and len(critical_count_query.data) > 0 and 'count' in critical_count_query.data[0]:
        total_critical_count = critical_count_query.data[0]['count']
    
    # Then fetch critical work orders FROM YESTERDAY ONLY for display and analysis
    critical_query = supabase.table("work_orders_history") \
        .select("*") \
        .ilike("priority", "%critical%") \
        .gte("date_created", yesterday) \
        .lt("date_created", today) \
        .order("date_created", desc=True) \
        .limit(100) \
        .execute()
    
    # Convert to dataframes
    new_wo_df = pd.DataFrame(yesterday_query.data) if yesterday_query.data else pd.DataFrame()
    closed_wo_df = pd.DataFrame(closed_query.data) if closed_query.data else pd.DataFrame()
    critical_wo_df = pd.DataFrame(critical_query.data) if critical_query.data else pd.DataFrame()
    
    # Log the count information
    if total_critical_count > 0:
        print(f"Found {len(new_wo_df)} new work orders, {len(closed_wo_df)} closed work orders, and {total_critical_count} new critical work orders (analyzing {len(critical_wo_df)})")
    else:
        # If we couldn't get the total count, just use the length of the dataframe
        total_critical_count = len(critical_wo_df)
        print(f"Found {len(new_wo_df)} new work orders, {len(closed_wo_df)} closed work orders, and {len(critical_wo_df)} new critical work orders")
    
    # Generate dashboard content
    dashboard_content = f"# Work Orders Dashboard - {yesterday}\n\n"
    
    # Summary metrics
    dashboard_content += "## Summary Metrics\n\n"
    dashboard_content += f"- **New Work Orders:** {len(new_wo_df)}\n"
    dashboard_content += f"- **Closed Work Orders:** {len(closed_wo_df)}\n"
    
    # Show total count and note if it's limited
    if total_critical_count > len(critical_wo_df):
        dashboard_content += f"- **New Critical Work Orders:** {total_critical_count} (showing top {len(critical_wo_df)})\n\n"
    else:
        dashboard_content += f"- **New Critical Work Orders:** {total_critical_count}\n\n"
    
    # Store the chart data in JSON
    dashboard_content += "## Chart Data\n\n"
    dashboard_content += "```json\n"
    
    # Create a dictionary to store all our chart data
    chart_data = {
        "date_range": {
            "start": yesterday,
            "end": today
        },
        "total_records": len(new_wo_df),
        "sample_size": len(new_wo_df),
        "charts": {}
    }
    
    # Work Orders by Priority
    if not new_wo_df.empty and 'priority' in new_wo_df.columns:
        priority_counts = new_wo_df.groupby('priority').size().reset_index(name='count').to_dict('records')
        chart_data["charts"]["priority"] = {
            "title": "Work Orders by Priority (Yesterday)",
            "data": priority_counts
        }
    
    # Work Orders by Trade
    if not new_wo_df.empty and 'trade' in new_wo_df.columns:
        trade_counts = new_wo_df.groupby('trade').size().reset_index(name='count')
        trade_counts = trade_counts.sort_values('count', ascending=False).head(10).to_dict('records')
        chart_data["charts"]["trade"] = {
            "title": "Top 10 Trades with Work Orders (Yesterday)",
            "data": trade_counts
        }
    
    # Work Orders by Building
    if not new_wo_df.empty and 'building_name' in new_wo_df.columns:
        building_counts = new_wo_df.groupby('building_name').size().reset_index(name='count')
        building_counts = building_counts.sort_values('count', ascending=False).head(10).to_dict('records')
        chart_data["charts"]["building"] = {
            "title": "Top 10 Buildings with Work Orders (Yesterday)",
            "data": building_counts
        }
    
    # Status Distribution
    if not new_wo_df.empty and 'status' in new_wo_df.columns:
        status_counts = new_wo_df.groupby('status').size().reset_index(name='count').to_dict('records')
        chart_data["charts"]["status"] = {
            "title": "Work Orders by Status (Yesterday)",
            "data": status_counts
        }
    
    # Add the chart data to the dashboard content
    dashboard_content += json.dumps(chart_data, indent=2)
    dashboard_content += "\n```\n\n"
    
    # Generate insights using AI
    insights = generate_insights_from_data(new_wo_df, closed_wo_df, critical_wo_df, total_critical_count)
    dashboard_content += "## AI Insights\n\n"
    dashboard_content += insights
    
    # Add common topics analysis for daily dashboard too
    if not new_wo_df.empty and 'description' in new_wo_df.columns:
        dashboard_content += "\n## Common Work Order Topics\n\n"
        topics_analysis = analyze_work_order_topics(new_wo_df)
        dashboard_content += topics_analysis
    
    # Recent Critical Work Orders
    dashboard_content += "\n## Recent Critical Work Orders (Yesterday)\n\n"
    if not critical_wo_df.empty:
        # Take top 5 critical work orders
        recent_critical = critical_wo_df.sort_values('date_created', ascending=False).head(5)
        for _, wo in recent_critical.iterrows():
            dashboard_content += f"### WO #{wo.get('work_order', 'N/A')}\n"
            dashboard_content += f"**Building:** {wo.get('building_name', 'N/A')}\n"
            dashboard_content += f"**Description:** {wo.get('description', 'No description')}\n"
            dashboard_content += f"**Status:** {wo.get('status', 'Unknown')}\n\n"
    else:
        dashboard_content += "*No critical work orders found for yesterday.*\n\n"
    
    # Save the dashboard to a file for future reference
    save_dashboard_to_file(dashboard_content, yesterday)
    
    return dashboard_content

def generate_insights_from_data(new_wo_df, closed_wo_df, critical_wo_df, total_critical_count=None):
    """
    Uses OpenAI to generate insights from the work order data
    """
    # Prepare data summaries for OpenAI with more specific guidance
    insights_prompt = "Analyze this work order data from yesterday and provide 4-5 specific, actionable insights:\n\n"
    
    # Add more detailed data breakdowns
    if not new_wo_df.empty:
        insights_prompt += f"New Work Orders (Yesterday): {len(new_wo_df)}\n"
        
        # Add priority distribution with percentages
        if 'priority' in new_wo_df.columns:
            priority_counts = new_wo_df['priority'].value_counts()
            priority_pct = (priority_counts / priority_counts.sum() * 100).round(1)
            priority_data = {k: f"{v} ({priority_pct[k]}%)" for k, v in priority_counts.to_dict().items()}
            insights_prompt += f"Priority distribution: {priority_data}\n"
            
            # Add critical priority percentage
            critical_keys = [k for k in priority_counts.index if 'critical' in k.lower()]
            if critical_keys:
                critical_count = sum(priority_counts.get(k, 0) for k in critical_keys)
                critical_pct = (critical_count / priority_counts.sum() * 100) if priority_counts.sum() > 0 else 0
                if critical_pct > 0:
                    insights_prompt += f"Critical priority percentage: {critical_pct:.1f}%\n"
        
        # Add trade breakdown with more details
        if 'trade' in new_wo_df.columns:
            top_trades = new_wo_df['trade'].value_counts().head(5).to_dict()
            insights_prompt += f"Top trades: {top_trades}\n"
            
            # Compare to historical averages if available
            insights_prompt += "Note any trades that seem to have unusual volume compared to typical patterns.\n"
        
        # Add building breakdown with more details
        if 'building_name' in new_wo_df.columns:
            top_buildings = new_wo_df['building_name'].value_counts().head(5).to_dict()
            insights_prompt += f"Top buildings: {top_buildings}\n"
            
            # Add building-to-work order ratio
            unique_buildings = new_wo_df['building_name'].nunique()
            if unique_buildings > 0:
                insights_prompt += f"Work orders per building ratio: {len(new_wo_df)/unique_buildings:.1f} (across {unique_buildings} buildings)\n"
            
        # Add zone analysis if available
        if 'zone' in new_wo_df.columns:
            zone_counts = new_wo_df['zone'].value_counts().head(3).to_dict()
            insights_prompt += f"Top zones: {zone_counts}\n"
    
    # Add closed work order analysis
    if not closed_wo_df.empty:
        insights_prompt += f"\nClosed Work Orders (Yesterday): {len(closed_wo_df)}\n"
        
        # Add closure efficiency metrics
        if 'date_created' in closed_wo_df.columns and 'date_completed' in closed_wo_df.columns:
            try:
                # Calculate average time to close
                closed_wo_df['date_created'] = pd.to_datetime(closed_wo_df['date_created'])
                closed_wo_df['date_completed'] = pd.to_datetime(closed_wo_df['date_completed'])
                closed_wo_df['days_to_close'] = (closed_wo_df['date_completed'] - closed_wo_df['date_created']).dt.total_seconds() / 86400
                
                avg_days = closed_wo_df['days_to_close'].mean()
                median_days = closed_wo_df['days_to_close'].median()
                
                insights_prompt += f"Average days to close: {avg_days:.1f} days\n"
                insights_prompt += f"Median days to close: {median_days:.1f} days\n"
            except Exception as e:
                print(f"Error calculating closure metrics: {str(e)}")
        
        # Add trade closure rates
        if 'trade' in closed_wo_df.columns:
            closed_trades = closed_wo_df['trade'].value_counts().head(3).to_dict()
            insights_prompt += f"Top trades closing work orders: {closed_trades}\n"
    
    # Add critical work order analysis
    if not critical_wo_df.empty:
        # If we have the total count, use it
        if total_critical_count and total_critical_count > len(critical_wo_df):
            insights_prompt += f"\nNew Critical Work Orders (Yesterday): {total_critical_count} total (analyzing {len(critical_wo_df)})\n"
        else:
            insights_prompt += f"\nNew Critical Work Orders (Yesterday): {len(critical_wo_df)}\n"
            
        # Add status distribution for critical WOs
        if 'status' in critical_wo_df.columns:
            critical_status = critical_wo_df['status'].value_counts().to_dict()
            insights_prompt += f"Status of new critical work orders: {critical_status}\n"
            
            # Calculate percentage of critical WOs that are still open
            open_critical = sum(v for k, v in critical_status.items() if k != 'Closed')
            if sum(critical_status.values()) > 0:
                open_pct = (open_critical / sum(critical_status.values())) * 100
                insights_prompt += f"Percentage of critical WOs still open: {open_pct:.1f}%\n"
        
        # Add building and trade analysis for critical WOs
        if 'building_name' in critical_wo_df.columns:
            critical_buildings = critical_wo_df['building_name'].value_counts().head(3).to_dict()
            insights_prompt += f"Buildings with most critical WOs: {critical_buildings}\n"
        
        if 'trade' in critical_wo_df.columns:
            critical_trades = critical_wo_df['trade'].value_counts().head(3).to_dict()
            insights_prompt += f"Trades with most critical WOs: {critical_trades}\n"
    
    insights_prompt += "\nProvide the following in your response:"
    insights_prompt += "\n1. Highlight specific patterns, anomalies, or concerning trends"
    insights_prompt += "\n2. Compare open vs. closed work orders"
    insights_prompt += "\n3. Note any buildings, trades, or zones that need immediate attention"
    insights_prompt += "\n4. Suggest specific actions the facilities team should take"
    insights_prompt += "\n5. Highlight any efficiency issues or resource allocation concerns"
    insights_prompt += "\nFormat as concise bullet points that facility managers can act upon immediately."
    
    try:
        # Call OpenAI API to generate insights
        model_name = get_latest_model_name()
        response = openai.ChatCompletion.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are an expert facility management data analyst who provides specific, actionable insights. Use concrete numbers and percentages when possible. Avoid generic observations. Focus on what the data uniquely reveals about this specific day."},
                {"role": "user", "content": insights_prompt}
            ],
            temperature=0.4  # Lower temperature for more focused, less generic responses
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error generating AI insights: {str(e)}")
        return f"*Error generating AI insights: {str(e)}*\n\nPlease review the data manually for trends and patterns."

def save_dashboard_to_file(dashboard_content, date_str):
    """
    Saves the generated dashboard to a file for future reference
    """
    try:
        # Create dashboards directory if it doesn't exist
        dashboard_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboards")
        os.makedirs(dashboard_dir, exist_ok=True)
        
        # Save dashboard to file
        file_path = os.path.join(dashboard_dir, f"dashboard_{date_str}.md")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(dashboard_content)
            
        print(f"Dashboard saved to {file_path}")
        
    except Exception as e:
        print(f"Error saving dashboard to file: {str(e)}")

def get_latest_dashboard():
    """
    Returns the most recently generated dashboard
    """
    try:
        dashboard_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboards")
        if not os.path.exists(dashboard_dir):
            return None
            
        # Get list of dashboard files
        files = [os.path.join(dashboard_dir, f) for f in os.listdir(dashboard_dir) 
                 if f.startswith("dashboard_") and f.endswith(".md")]
        
        if not files:
            return None
            
        # Get most recent file
        latest_file = max(files, key=os.path.getmtime)
        
        # Read file content
        with open(latest_file, "r", encoding="utf-8") as f:
            return f.read()
            
    except Exception as e:
        print(f"Error getting latest dashboard: {str(e)}")
        return None

def generate_custom_dashboard(start_date=None,  description_keyword=None,  end_date=None, building_id=None, building_name=None, trade=None, zone=None):
    """
    Generates a custom dashboard with specific filters
    """
    # If no dates provided, default to last 7 days
    if not start_date:
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=7)
    elif not end_date:
        end_date = datetime.now().date()
    
    start_date_iso = start_date.isoformat() if isinstance(start_date, datetime) else start_date
    end_date_iso = end_date.isoformat() if isinstance(end_date, datetime) else end_date
    
    print(f"Generating custom dashboard for date range: {start_date_iso} to {end_date_iso}")
    
    # Build the filter description first
    filter_description = f"Date range: {start_date_iso} to {end_date_iso}"
    
    if building_id:
        filter_description += f" | Building ID: {building_id}"
    
    if building_name:
        filter_description += f" | Building: {building_name}"
    
    if trade:
        filter_description += f" | Trade: {trade}"
        
    if zone:
        filter_description += f" | Zone: {zone}"


    
    print(f"Filters: {filter_description}")
    
    # Get total count for accurate reporting
    count_query = supabase.table("work_orders_history").select("count", count="exact")
    
    # Apply date filter to count
    count_query = count_query.gte("date_created", start_date_iso).lt("date_created", end_date_iso)
    
    # Apply additional filters to count if provided
    if building_id:
        count_query = count_query.eq("building_id", str(building_id))
    
    if building_name:
        count_query = count_query.ilike("building_name", f"%{building_name}%")
    
    if trade:
        count_query = count_query.eq("trade", trade)
    
    if zone:
        count_query = count_query.eq("zone", zone)
        
    # Execute count query
    count_result = count_query.execute()
    
    # Extract total count
    total_count = 0
    if hasattr(count_result, 'count'):
        total_count = count_result.count
    elif isinstance(count_result.data, dict) and 'count' in count_result.data:
        total_count = count_result.data['count']
    elif isinstance(count_result.data, list) and len(count_result.data) > 0 and 'count' in count_result.data[0]:
        total_count = count_result.data[0]['count']
    
    print(f"Total count: {total_count}")
    
    # For chart generation, we'll process all records in batches if needed
    all_data = []
    batch_size = 1000  # Supabase recommended batch size
    max_records = min(10000, total_count)  # Cap at 10000 to avoid performance issues
    
    for offset in range(0, max_records, batch_size):
        # Build data query with the same filters
        query = supabase.table("work_orders_history").select("*")
        
        # Apply date filter
        query = query.gte("date_created", start_date_iso).lt("date_created", end_date_iso)
        
        # Apply additional filters if provided
        if building_id:
            query = query.eq("building_id", str(building_id))
        
        if building_name:
            query = query.ilike("building_name", f"%{building_name}%")
        
        if trade:
            query = query.eq("trade", trade)
            
        if zone:
            query = query.eq("zone", zone)

        if description_keyword:  # <-- add here
            query = query.ilike("description", f"%{description_keyword}%")

        
        # Apply pagination
        result = query.range(offset, offset + batch_size - 1).execute()
        
        if result.data:
            all_data.extend(result.data)
            print(f"Retrieved batch of {len(result.data)} records, total so far: {len(all_data)}")
        else:
            print("No more data")
            break  # No more data
        
        if len(all_data) >= max_records:
            print(f"Reached max records limit ({max_records})")
            break
    
    # Convert to dataframe
    df = pd.DataFrame(all_data) if all_data else pd.DataFrame()
    
    print(f"Final dataset: {len(df)} records out of {total_count} total")
    
    # Generate dashboard similar to daily dashboard but with custom filters
    dashboard_title = f"Custom Work Orders Dashboard"
    
    dashboard_content = f"# {dashboard_title}\n\n"
    dashboard_content += f"*{filter_description}*\n\n"
    
    # Summary metrics
    dashboard_content += "## Summary Metrics\n\n"
    
    if len(df) < total_count:
        dashboard_content += f"- **Total Work Orders:** {total_count} (analyzing {len(df)})\n"
    else:
        dashboard_content += f"- **Total Work Orders:** {len(df)}\n"
    
    if 'status' in df.columns:
        status_counts = df['status'].value_counts().to_dict()
        dashboard_content += f"- **Status Breakdown:** {status_counts}\n"
    
    if 'priority' in df.columns:
        priority_counts = df['priority'].value_counts().to_dict()
        dashboard_content += f"- **Priority Breakdown:** {priority_counts}\n"
    
    # Store the chart data in JSON format
    dashboard_content += "\n## Chart Data\n\n"
    dashboard_content += "```json\n"
    
    # Create a dictionary to store all our chart data
    chart_data = {
        "date_range": {
            "start": start_date_iso,
            "end": end_date_iso
        },
        "total_records": total_count,
        "sample_size": len(df),
        "charts": {}
    }
    
    # Work Orders by Priority
    if not df.empty and 'priority' in df.columns:
        priority_counts = df.groupby('priority').size().reset_index(name='count').to_dict('records')
        chart_data["charts"]["priority"] = {
            "title": f"Work Orders by Priority",
            "data": priority_counts
        }
    
    # Work Orders by Trade - only if trade filter is not applied
    if not df.empty and 'trade' in df.columns and not trade:
        trade_counts = df.groupby('trade').size().reset_index(name='count')
        trade_counts = trade_counts.sort_values('count', ascending=False).head(10).to_dict('records')
        chart_data["charts"]["trade"] = {
            "title": f"Top 10 Trades with Work Orders",
            "data": trade_counts
        }
    # If trade filter is applied, still show trade distribution if there are various trades matching the filter
    elif not df.empty and 'trade' in df.columns and trade:
        # Some trade fields might contain the trade name as part of a longer string
        if len(df['trade'].unique()) > 1:
            trade_counts = df.groupby('trade').size().reset_index(name='count')
            trade_counts = trade_counts.sort_values('count', ascending=False).head(10).to_dict('records')
            chart_data["charts"]["trade"] = {
                "title": f"Trade Distribution for {trade}",
                "data": trade_counts
            }
    
    # Work Orders by Building - only if building filter is not applied
    if not df.empty and 'building_name' in df.columns and not building_name and not building_id:
        building_counts = df.groupby('building_name').size().reset_index(name='count')
        building_counts = building_counts.sort_values('count', ascending=False).head(10).to_dict('records')
        chart_data["charts"]["building"] = {
            "title": f"Top 10 Buildings with Work Orders",
            "data": building_counts
        }
    # If building filter is applied, still show building distribution if there are various buildings matching the filter
    elif not df.empty and 'building_name' in df.columns and (building_name or building_id):
        if len(df['building_name'].unique()) > 1:
            building_counts = df.groupby('building_name').size().reset_index(name='count')
            building_counts = building_counts.sort_values('count', ascending=False).head(10).to_dict('records')
            chart_data["charts"]["building"] = {
                "title": f"Building Distribution for Filter",
                "data": building_counts
            }
    
    # Work Orders by Zone - only if zone filter is not applied
    if not df.empty and 'zone' in df.columns and not zone:
        zone_counts = df.groupby('zone').size().reset_index(name='count')
        zone_counts = zone_counts.sort_values('count', ascending=False).head(10).to_dict('records')
        chart_data["charts"]["zone"] = {
            "title": f"Top 10 Zones with Work Orders",
            "data": zone_counts
        }
    # If zone filter is applied, still show zone distribution if there are various zones matching the filter
    elif not df.empty and 'zone' in df.columns and zone:
        if len(df['zone'].unique()) > 1:
            zone_counts = df.groupby('zone').size().reset_index(name='count')
            zone_counts = zone_counts.sort_values('count', ascending=False).head(10).to_dict('records')
            chart_data["charts"]["zone"] = {
                "title": f"Zone Distribution for Filter",
                "data": zone_counts
            }
    
    # Status Distribution - always show this
    if not df.empty and 'status' in df.columns:
        status_counts = df.groupby('status').size().reset_index(name='count').to_dict('records')
        chart_data["charts"]["status"] = {
            "title": f"Work Orders by Status",
            "data": status_counts
        }
    
    # Add the chart data to the dashboard content
    dashboard_content += json.dumps(chart_data, indent=2)
    dashboard_content += "\n```\n\n"
    
    # Generate insights
    if not df.empty:
        insights = generate_custom_insights(df, start_date_iso, end_date_iso, building_id, building_name, trade, zone, total_count)
        dashboard_content += "\n## AI Insights\n\n"
        dashboard_content += insights
        
        # Extract common topics/issues from work order descriptions
        if 'description' in df.columns:
            dashboard_content += "\n## Common Work Order Topics\n\n"
            topics_analysis = analyze_work_order_topics(df)
            dashboard_content += topics_analysis
        
        # Add section for critical work orders if they exist in the dataset
        if 'priority' in df.columns:
            # Find critical work orders based on priority containing "critical" (case insensitive)
            critical_wo_df = df[df['priority'].str.contains('critical', case=False, na=False)]
            
            # Dedicated section for critical work orders
            dashboard_content += "\n## Critical Work Orders\n\n"
            
            if not critical_wo_df.empty:
                # Sort by date_created in descending order and take top 5
                recent_critical = critical_wo_df.sort_values('date_created', ascending=False).head(5)
                for _, wo in recent_critical.iterrows():
                    dashboard_content += f"### WO #{wo.get('work_order', 'N/A')}\n"
                    dashboard_content += f"**Building:** {wo.get('building_name', 'N/A')}\n"
                    dashboard_content += f"**Description:** {wo.get('description', 'No description')}\n"
                    dashboard_content += f"**Status:** {wo.get('status', 'Unknown')}\n\n"
                
                if len(critical_wo_df) > 5:
                    dashboard_content += f"*Showing 5 of {len(critical_wo_df)} critical work orders*\n\n"
            else:
                dashboard_content += "*No critical work orders found for the selected time period.*\n\n"
    
    return dashboard_content

def analyze_work_order_topics(df):
    """
    Analyzes work order descriptions to identify common topics and issues
    """
    if 'description' not in df.columns or df.empty:
        return "No work order description data available for analysis."
    
    # Prepare descriptions for analysis - drop missing values and lowercase
    descriptions = df['description'].dropna().str.lower()
    
    if descriptions.empty or len(descriptions) < 3:  # Lowered threshold to 3
        return "Not enough work order descriptions available for meaningful analysis."
    
    print(f"Analyzing {len(descriptions)} work order descriptions for common topics")
    
    # Define common topics/issues to look for - expanded keywords
    topics = {
        "elevator": ["elevator", "lift", "elevating", "escalator", "moving stairway", "conveyance"],
        "plumbing": ["plumbing", "leak", "water", "toilet", "sink", "faucet", "drain", "pipe", "flush", "shower", "bath", "flooding", "sprinkler"],
        "electrical": ["electrical", "light", "lighting", "power", "outlet", "bulb", "circuit", "breaker", "switch", "wiring", "electrical panel"],
        "hvac": ["hvac", "heating", "cooling", "air conditioning", "ac", "temperature", "thermostat", "ventilation", "furnace", "boiler", "heat", "cold", "fan"],
        "door/window": ["door", "window", "lock", "key", "handle", "hinge", "glass", "entrance", "exit", "doorway", "doorknob", "automatic door"],
        "cleaning": ["cleaning", "dirt", "dust", "garbage", "waste", "trash", "spill", "janitorial", "sanitize", "disinfect"],
        "furniture": ["furniture", "chair", "desk", "table", "cabinet", "drawer", "cubicle", "office furniture", "seating", "shelving", "workstation"],
        "safety": ["safety", "security", "hazard", "emergency", "fire", "alarm", "extinguisher", "sprinkler", "evacuation", "unsafe"],
        "structural": ["wall", "ceiling", "floor", "roof", "tile", "drywall", "concrete", "crack", "structure", "foundation", "leaking roof"],
        "exterior": ["parking", "lot", "sidewalk", "walkway", "landscaping", "exterior", "outside", "sign", "signage", "pavement", "asphalt"],
        "mechanical": ["mechanical", "equipment", "pump", "motor", "compressor", "engine", "machine", "belt", "bearing", "gear"],
        "general maintenance": ["maintenance", "repair", "fix", "install", "replace", "service", "check", "inspect", "assessment", "preventative"]
    }
    
    # Count occurrences of topics
    topic_counts = {topic: 0 for topic in topics}
    
    # Keep track of examples for each topic
    examples = {topic: [] for topic in topics}
    
    # Search for topics in descriptions
    for desc in descriptions:
        for topic, keywords in topics.items():
            for keyword in keywords:
                if keyword in desc:
                    topic_counts[topic] += 1
                    # Store an example (max 3 per topic)
                    if len(examples[topic]) < 3:
                        examples[topic].append(desc[:100] + "..." if len(desc) > 100 else desc)
                    break  # Only count each description once per topic
    
    # Filter out topics with zero occurrences
    topic_counts = {k: v for k, v in topic_counts.items() if v > 0}
    
    # Sort by frequency
    sorted_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)
    
    # Generate the topic analysis content
    result = ""
    
    # If keyword analysis didn't find anything with 2+ occurrences, try direct AI analysis
    if not sorted_topics or (len(sorted_topics) == 1 and sorted_topics[0][1] < 2):
        # Show the descriptions directly for small datasets
        if len(descriptions) < 10:
            result += "#### Work Order Descriptions\n\n"
            for i, desc in enumerate(descriptions.tolist()[:10], 1):
                result += f"{i}. {desc}\n\n"
            
            result += "Not enough data for automated topic analysis. The work order descriptions are shown above for manual review.\n\n"
            return result
        
        # For larger datasets, use AI to categorize
        try:
            print("Few topics found via keywords, attempting AI analysis...")
            # Prepare data for AI analysis
            sample_size = min(20, len(descriptions))
            sample_descriptions = descriptions.sample(sample_size).tolist()
            
            ai_prompt = (
                f"Analyze these {sample_size} work order descriptions and categorize them into 3-5 common themes or issue types:\n\n"
                + "\n".join([f"- {desc[:150]}..." if len(desc) > 150 else f"- {desc}" for desc in sample_descriptions[:15]])
                + ("\n- [Additional descriptions omitted for brevity]" if len(sample_descriptions) > 15 else "")
                + "\n\nIdentify the most common issue types and provide a brief summary of each category."
            )
            
            model_name = get_latest_model_name()
            response = openai.ChatCompletion.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are a facility management analyst who specializes in categorizing maintenance issues."},
                    {"role": "user", "content": ai_prompt}
                ]
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"Error generating topic categories with AI: {str(e)}")
            # If AI analysis fails, show a sample of descriptions
            result += "#### Sample Work Order Descriptions\n\n"
            for i, desc in enumerate(descriptions.sample(min(5, len(descriptions))).tolist(), 1):
                result += f"{i}. {desc}\n\n"
            
            result += "*No clear topic patterns identified. Consider reviewing these sample descriptions manually.*\n\n"
            return result
    
    # Calculate percentage
    total = len(descriptions)
    
    for topic, count in sorted_topics[:7]:  # Show top 7 topics
        percentage = (count / total) * 100
        result += f"### {topic.title()} Issues ({count} work orders, {percentage:.1f}%)\n\n"
        
        if examples[topic]:
            result += "**Example descriptions:**\n\n"
            for i, example in enumerate(examples[topic], 1):
                result += f"{i}. \"{example}\"\n"
            result += "\n"
    
    # Additional analysis using AI if we have enough data
    if len(descriptions) >= 15:  # Lowered threshold to 15
        try:
            # Prepare data for AI analysis - take a sample of descriptions
            sample_size = min(30, len(descriptions))  # Reduced sample size
            sample_descriptions = descriptions.sample(sample_size).tolist()
            
            ai_prompt = (
                f"Analyze these {sample_size} work order descriptions to identify specific trends, issues, and patterns:\n\n"
                + "\n".join([f"- {desc[:150]}..." if len(desc) > 150 else f"- {desc}" for desc in sample_descriptions[:10]])
                + "\n\n[Additional descriptions omitted for brevity]\n\n"
                + "Identify 3-4 key insights about the types of issues being reported, potential root causes, "
                + "and recommend specific maintenance actions. Focus on concrete observations unique to this dataset."
                + "Format your response as bullet points with actionable recommendations."
            )
            
            print("Calling OpenAI API for topic analysis...")
            model_name = get_latest_model_name()
            response = openai.ChatCompletion.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are a facility management expert who identifies specific patterns in maintenance requests and recommends actionable solutions. Avoid generic observations and focus on unique aspects of the data provided."},
                    {"role": "user", "content": ai_prompt}
                ],
                temperature=0.4
            )
            
            ai_analysis = response.choices[0].message.content.strip()
            result += "### AI Analysis of Common Issues\n\n"
            result += ai_analysis + "\n\n"
            print("AI topic analysis completed successfully")
            
        except Exception as e:
            print(f"Error generating AI topic analysis: {str(e)}")
            result += f"*AI analysis of trends unavailable: {str(e)}*\n\n"
    else:
        # For small datasets without AI analysis
        result += "### General Observations\n\n"
        result += "* The sample size is too small for detailed AI analysis.\n"
        result += f"* There are {len(descriptions)} work orders with descriptions available.\n"
        result += "* For more detailed insights, consider generating a dashboard with a wider date range.\n\n"
    
    return result

def generate_custom_insights(df, start_date, end_date, building_id=None, building_name=None, trade=None, zone=None, total_count=None):
    """
    Generates insights for a custom dashboard with more specific, actionable content
    """
    # Format dataframe information as a prompt with enhanced guidance
    insights_prompt = f"Generate 5 specific, data-driven insights from this facilities work order data:\n\n"
    insights_prompt += f"Date range: {start_date} to {end_date}\n"
    
    if total_count and total_count > len(df):
        insights_prompt += f"Total work orders: {total_count} (analyzing {len(df)})\n"
    else:
        insights_prompt += f"Total work orders: {len(df)}\n"
    
    # Add filter context
    filters_applied = []
    if building_id:
        filters_applied.append(f"Building ID: {building_id}")
    if building_name:
        filters_applied.append(f"Building name: {building_name}")
    if trade:
        filters_applied.append(f"Trade: {trade}")
    if zone:
        filters_applied.append(f"Zone: {zone}")
    
    if filters_applied:
        insights_prompt += f"Filters applied: {', '.join(filters_applied)}\n\n"
    
    # Add statistical summaries with more detail
    if 'priority' in df.columns:
        priority_counts = df['priority'].value_counts()
        if not priority_counts.empty:
            priority_pct = (priority_counts / priority_counts.sum() * 100).round(1)
            priority_data = {k: f"{v} ({priority_pct[k]}%)" for k, v in priority_counts.to_dict().items()}
            insights_prompt += f"Priority distribution: {priority_data}\n"
            
            # Calculate critical percentage
            critical_keys = [k for k in priority_counts.index if 'critical' in str(k).lower()]
            if critical_keys:
                critical_count = sum(priority_counts.get(k, 0) for k in critical_keys)
                if priority_counts.sum() > 0:
                    critical_pct = (critical_count / priority_counts.sum() * 100)
                    if critical_pct > 0:
                        insights_prompt += f"Critical priority percentage: {critical_pct:.1f}%\n"
    
    if 'status' in df.columns:
        status_counts = df['status'].value_counts()
        if not status_counts.empty:
            status_pct = (status_counts / status_counts.sum() * 100).round(1)
            status_data = {k: f"{v} ({status_pct[k]}%)" for k, v in status_counts.to_dict().items()}
            insights_prompt += f"Status distribution: {status_data}\n"
            
            # Calculate completion rate
            completed = status_counts.get('Closed', 0) + status_counts.get('Completed', 0)
            if status_counts.sum() > 0:
                completion_rate = (completed / status_counts.sum() * 100)
                insights_prompt += f"Work order completion rate: {completion_rate:.1f}%\n"
    
    # Add age analysis if date fields are available
    if 'date_created' in df.columns:
        try:
            df['date_created'] = pd.to_datetime(df['date_created'])
            current_date = pd.to_datetime('today')
            
            # Calculate age of open work orders
            if 'status' in df.columns:
                open_wo = df[df['status'] != 'Closed']
                if not open_wo.empty:
                    open_wo['age_days'] = (current_date - open_wo['date_created']).dt.total_seconds() / 86400
                    avg_age = open_wo['age_days'].mean()
                    median_age = open_wo['age_days'].median()
                    max_age = open_wo['age_days'].max()
                    
                    insights_prompt += f"Open work order age stats: Avg {avg_age:.1f} days, Median {median_age:.1f} days, Max {max_age:.1f} days\n"
                    
                    # Age distribution buckets
                    age_buckets = [
                        (open_wo['age_days'] <= 7).sum(),  # 0-7 days
                        ((open_wo['age_days'] > 7) & (open_wo['age_days'] <= 30)).sum(),  # 7-30 days
                        ((open_wo['age_days'] > 30) & (open_wo['age_days'] <= 90)).sum(),  # 30-90 days
                        (open_wo['age_days'] > 90).sum(),  # >90 days
                    ]
                    
                    insights_prompt += f"Age distribution: 0-7 days: {age_buckets[0]}, 7-30 days: {age_buckets[1]}, 30-90 days: {age_buckets[2]}, >90 days: {age_buckets[3]}\n"
        except Exception as e:
            print(f"Error calculating age metrics: {str(e)}")
    
    # Add trade analysis if not filtered by trade
    if 'trade' in df.columns and not trade:
        top_trades = df['trade'].value_counts().head(5).to_dict()
        insights_prompt += f"Top trades: {top_trades}\n"
        
        # Trade-specific metrics
        if 'status' in df.columns and len(df['trade'].unique()) > 1:
            try:
                trade_completion = df[df['status'] == 'Closed'].groupby('trade').size()
                trade_total = df.groupby('trade').size()
                # Only calculate rates for trades with data
                valid_trades = set(trade_completion.index).intersection(set(trade_total.index))
                if valid_trades:
                    trade_completion_rates = (trade_completion.loc[list(valid_trades)] / trade_total.loc[list(valid_trades)] * 100).fillna(0)
                    if not trade_completion_rates.empty:
                        top_completion_rates = trade_completion_rates.sort_values(ascending=False).head(3)
                        bottom_completion_rates = trade_completion_rates.sort_values().head(3)
                        
                        insights_prompt += f"Top 3 trades by completion rate: {top_completion_rates.to_dict()}\n"
                        insights_prompt += f"Bottom 3 trades by completion rate: {bottom_completion_rates.to_dict()}\n"
            except Exception as e:
                print(f"Error calculating trade completion rates: {str(e)}")
    
    # Add building analysis if not filtered by building
    if 'building_name' in df.columns and not building_id and not building_name:
        top_buildings = df['building_name'].value_counts().head(5).to_dict()
        insights_prompt += f"Top buildings: {top_buildings}\n"
        
        # Building efficiency metrics
        if 'status' in df.columns and len(df['building_name'].unique()) > 1:
            try:
                building_wo_counts = df.groupby('building_name').size()
                building_completion = df[df['status'] == 'Closed'].groupby('building_name').size()
                
                # Only calculate for buildings that have both data points
                common_buildings = set(building_wo_counts.index).intersection(set(building_completion.index))
                if common_buildings:
                    filtered_counts = building_wo_counts.loc[list(common_buildings)]
                    filtered_completions = building_completion.loc[list(common_buildings)]
                    building_completion_rates = (filtered_completions / filtered_counts * 100).fillna(0)
                    
                    # Identify buildings with high workload and low completion rates
                    if not building_completion_rates.empty and len(building_completion_rates) > 2:
                        high_volume_buildings = filtered_counts[filtered_counts > filtered_counts.median()].index
                        problem_buildings = building_completion_rates[building_completion_rates < 50].index
                        
                        high_volume_low_completion = set(high_volume_buildings).intersection(set(problem_buildings))
                        if high_volume_low_completion:
                            insights_prompt += f"Buildings with high volume and low completion rates: {list(high_volume_low_completion)[:3]}\n"
            except Exception as e:
                print(f"Error calculating building metrics: {str(e)}")
    
    # Add zone analysis if not filtered by zone
    if 'zone' in df.columns and not zone:
        top_zones = df['zone'].value_counts().head(5).to_dict()
        insights_prompt += f"Top zones: {top_zones}\n"
        
        # Zone metrics if available
        if 'priority' in df.columns and len(df['zone'].unique()) > 1 and 'zone' in df.columns:
            try:
                # Find rows with critical priority across all zones
                critical_mask = df['priority'].str.contains('critical', case=False, na=False)
                if critical_mask.any():
                    zone_critical_counts = df[critical_mask].groupby('zone').size()
                    zone_total_counts = df.groupby('zone').size()
                    
                    # Only calculate for zones with both data points
                    common_zones = set(zone_critical_counts.index).intersection(set(zone_total_counts.index))
                    if common_zones:
                        valid_critical = zone_critical_counts.loc[list(common_zones)]
                        valid_totals = zone_total_counts.loc[list(common_zones)]
                        zone_critical_rates = (valid_critical / valid_totals * 100).fillna(0)
                        
                        if not zone_critical_rates.empty:
                            highest_critical_zones = zone_critical_rates.sort_values(ascending=False).head(3)
                            insights_prompt += f"Zones with highest percentage of critical work orders: {highest_critical_zones.to_dict()}\n"
            except Exception as e:
                print(f"Error calculating zone metrics: {str(e)}")
    
    insights_prompt += "\nBased on this data, provide 5 specific insights that would be valuable to facilities managers:"
    insights_prompt += "\n1. Highlight specific patterns or trends that stand out in this dataset"
    insights_prompt += "\n2. Identify specific buildings, zones, or trades requiring immediate attention"
    insights_prompt += "\n3. Note any efficiency issues or resource allocation concerns"
    insights_prompt += "\n4. Compare metrics against expected benchmarks (e.g., completion rates, age of open WOs)"
    insights_prompt += "\n5. Recommend 2-3 specific, actionable steps for facilities management"
    insights_prompt += "\nUse concrete numbers, percentages, and specifics from the data. Avoid generic observations."
    
    try:
        # Call OpenAI API to generate insights with lower temperature for more focused results
        model_name = get_latest_model_name()
        response = openai.ChatCompletion.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are an expert facilities management consultant who provides specific, data-driven insights. Focus on patterns unique to this dataset, highlight anomalies, and provide actionable recommendations. Use concrete metrics and avoid generic advice."},
                {"role": "user", "content": insights_prompt}
            ],
            temperature=0.4  # Lower temperature for more focused insights
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"*Error generating AI insights: {str(e)}*"

if __name__ == "__main__":
    # When run directly, generate today's dashboard
    try:
        dashboard = generate_daily_dashboard()
        print("Dashboard generated successfully!")
        print(f"First 500 characters: {dashboard[:500]}...")
    except Exception as e:
        print(f"Error generating dashboard: {str(e)}")