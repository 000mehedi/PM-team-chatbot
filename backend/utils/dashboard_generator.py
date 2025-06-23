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
    # Prepare data summaries for OpenAI
    insights_prompt = "Generate 3-5 key insights from the following work order data from yesterday:\n\n"
    
    if not new_wo_df.empty:
        insights_prompt += f"New Work Orders (Yesterday): {len(new_wo_df)}\n"
        if 'priority' in new_wo_df.columns:
            priority_counts = new_wo_df['priority'].value_counts().to_dict()
            insights_prompt += f"Priority distribution: {priority_counts}\n"
        if 'trade' in new_wo_df.columns:
            top_trades = new_wo_df['trade'].value_counts().head(5).to_dict()
            insights_prompt += f"Top trades: {top_trades}\n"
        if 'building_name' in new_wo_df.columns:
            top_buildings = new_wo_df['building_name'].value_counts().head(5).to_dict()
            insights_prompt += f"Top buildings: {top_buildings}\n"
    
    if not closed_wo_df.empty:
        insights_prompt += f"\nClosed Work Orders (Yesterday): {len(closed_wo_df)}\n"
        if 'trade' in closed_wo_df.columns:
            closed_trades = closed_wo_df['trade'].value_counts().head(5).to_dict()
            insights_prompt += f"Top trades closing work orders: {closed_trades}\n"
    
    if not critical_wo_df.empty:
        # If we have the total count, use it
        if total_critical_count and total_critical_count > len(critical_wo_df):
            insights_prompt += f"\nNew Critical Work Orders (Yesterday): {total_critical_count} total (analyzing {len(critical_wo_df)})\n"
        else:
            insights_prompt += f"\nNew Critical Work Orders (Yesterday): {len(critical_wo_df)}\n"
            
        if 'status' in critical_wo_df.columns:
            critical_status = critical_wo_df['status'].value_counts().to_dict()
            insights_prompt += f"Status of new critical work orders: {critical_status}\n"
    
    insights_prompt += "\nProvide concise, actionable insights that help facility managers prioritize work. Format as bullet points."
    
    try:
        # Call OpenAI API to generate insights
        model_name = get_latest_model_name()
        response = openai.ChatCompletion.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are a facility management data analyst who provides clear, concise insights."},
                {"role": "user", "content": insights_prompt}
            ]
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

def generate_custom_dashboard(start_date=None, end_date=None, building_id=None, building_name=None, trade=None):
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
        insights = generate_custom_insights(df, start_date_iso, end_date_iso, building_id, building_name, trade, total_count)
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
                f"Analyze these {sample_size} work order descriptions to identify common themes, issues, and patterns:\n\n"
                + "\n".join([f"- {desc[:150]}..." if len(desc) > 150 else f"- {desc}" for desc in sample_descriptions[:10]])
                + "\n\n[Additional descriptions omitted for brevity]\n\n"
                + "Identify 3-4 key insights about the types of issues being reported, potential root causes, "
                + "or maintenance trends. Format your response as bullet points."
            )
            
            print("Calling OpenAI API for topic analysis...")
            model_name = get_latest_model_name()
            response = openai.ChatCompletion.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are a facility management analyst who specializes in identifying patterns in work order data."},
                    {"role": "user", "content": ai_prompt}
                ]
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
def generate_custom_insights(df, start_date, end_date, building_id=None, building_name=None, trade=None, total_count=None):
    """
    Generates insights for a custom dashboard
    """
    # Format dataframe information as a prompt
    insights_prompt = f"Generate 3-5 key insights from work order data with the following characteristics:\n\n"
    insights_prompt += f"Date range: {start_date} to {end_date}\n"
    
    if total_count and total_count > len(df):
        insights_prompt += f"Total work orders: {total_count} (analyzing {len(df)})\n"
    else:
        insights_prompt += f"Total work orders: {len(df)}\n"
    
    if building_id:
        insights_prompt += f"Building ID filter: {building_id}\n"
    
    if building_name:
        insights_prompt += f"Building name filter: {building_name}\n"
    
    if trade:
        insights_prompt += f"Trade filter: {trade}\n"
    
    # Add statistical summaries
    if 'priority' in df.columns:
        priority_counts = df['priority'].value_counts().to_dict()
        insights_prompt += f"Priority distribution: {priority_counts}\n"
    
    if 'status' in df.columns:
        status_counts = df['status'].value_counts().to_dict()
        insights_prompt += f"Status distribution: {status_counts}\n"
    
    if 'trade' in df.columns and not trade:
        top_trades = df['trade'].value_counts().head(5).to_dict()
        insights_prompt += f"Top trades: {top_trades}\n"
    
    if 'building_name' in df.columns and not building_id and not building_name:
        top_buildings = df['building_name'].value_counts().head(5).to_dict()
        insights_prompt += f"Top buildings: {top_buildings}\n"
    
    insights_prompt += "\nProvide concise, actionable insights focused on trends, anomalies, and recommendations."
    insights_prompt += "\nFormat as bullet points for readability."
    
    try:
        # Call OpenAI API to generate insights
        model_name = get_latest_model_name()
        response = openai.ChatCompletion.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are a facility management data analyst who provides clear, concise insights."},
                {"role": "user", "content": insights_prompt}
            ]
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