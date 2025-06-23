# filepath: c:\Users\apatwary\OneDrive - The City of Calgary\PM-team-chatbot\backend\utils\ai_chat.py
import openai
import os
import re
import pandas as pd
from datetime import datetime, timedelta
from backend.utils.supabase_client import supabase
# Import dashboard functions
from .dashboard_generator import (
    generate_daily_dashboard,
    get_latest_dashboard,
    generate_custom_dashboard
)
openai.api_key = os.getenv("OPENAI_API_KEY")

def get_latest_model_name():
    try:
        with open("latest_model_name.txt", "r") as f:
            return f.read().strip()
    except Exception:
        return "gpt-3.5-turbo"

def suggest_pm_names(partial_name: str, limit=5):
    query = supabase.table("dictionary") \
        .select("pm_name") \
        .ilike("pm_name", f"%{partial_name}%") \
        .limit(limit) \
        .execute()
    if query.data:
        # Remove duplicates and empty names
        names = list({row["pm_name"] for row in query.data if row["pm_name"]})
        return names
    return []

def get_work_order_info(work_order_number):
    """
    Retrieves information about a specific work order by its number
    """
    query = supabase.table("work_orders_history") \
        .select("*") \
        .eq("work_order", str(work_order_number)) \
        .execute()
    
    if query.data and len(query.data) > 0:
        return query.data[0]
    return None

def get_building_work_orders(building_id=None, building_name=None, limit=20):
    """
    Retrieves recent work orders for a specific building by ID or name
    """
    query = supabase.table("work_orders_history").select("*")
    
    if building_id:
        query = query.eq("building_id", str(building_id))
    elif building_name:
        query = query.ilike("building_name", f"%{building_name}%")
    
    result = query.order("date_created", desc=True).limit(limit).execute()
    
    if result.data and len(result.data) > 0:
        return result.data
    return []

def get_critical_work_orders(limit=10):
    """
    Retrieves critical priority work orders
    """
    query = supabase.table("work_orders_history") \
        .select("*") \
        .ilike("priority", "%critical%") \
        .order("date_created", desc=True) \
        .limit(limit) \
        .execute()
    
    if query.data and len(query.data) > 0:
        return query.data
    return []

def get_pm_tasks(search_term: str, search_pm_code=True, search_pm_name=True):
    # Try pm_code first if allowed
    if search_pm_code:
        query = supabase.table("dictionary") \
            .select("pm_code, pm_name, sequence, description") \
            .ilike("pm_code", f"%{search_term}%") \
            .execute()
        if query.data and len(query.data) > 0:
            return query.data
    # Try pm_name if allowed
    if search_pm_name:
        query = supabase.table("dictionary") \
            .select("pm_code, pm_name, sequence, description") \
            .ilike("pm_name", f"%{search_term}%") \
            .execute()
        if query.data and len(query.data) > 0:
            return query.data
    return []

def ask_gpt(question, context=""):
    question_lower = question.lower()
    
    # NEW CODE: Handle work order summary requests specifically
    if any(phrase in question_lower for phrase in [
        "summary of yesterday", "yesterday's work order", "summary of work orders",
        "yesterday's summary", "work orders from yesterday", "yesterday work order summary"
    ]):
        try:
            # Generate the dashboard with yesterday's data
            dashboard = generate_daily_dashboard()
            
            # Extract the summary section for chat display
            summary_match = re.search(r"## Summary Metrics\n\n(.*?)(?=##|\Z)", dashboard, re.DOTALL)
            if summary_match:
                summary = "# Summary of Yesterday's Work Orders\n\n" + summary_match.group(1)
                
                # Add AI insights if available
                insights_match = re.search(r"## AI Insights\n\n(.*?)(?=##|\Z)", dashboard, re.DOTALL)
                if insights_match:
                    summary += "\n\n## Key Insights\n\n" + insights_match.group(1)
                
                # Add critical work orders if available
                critical_match = re.search(r"## Recent Critical Work Orders\n\n(.*?)(?=##|\Z)", dashboard, re.DOTALL)
                if critical_match:
                    summary += "\n\n## Critical Work Orders\n\n" + critical_match.group(1)
                
                return summary
            
            return "I generated a dashboard for yesterday's work orders, but couldn't extract the summary. Try asking for the full dashboard."
        except Exception as e:
            return f"I encountered an error trying to generate the work order summary: {str(e)}"
    
    # DASHBOARD FUNCTIONALITY - Just the entry points
    # Check for dashboard generation request
    if any(phrase in question_lower for phrase in [
        "generate dashboard", "create dashboard", "show dashboard", "daily dashboard",
        "yesterday's dashboard", "work order dashboard"
    ]):
        # Check if asking for latest existing dashboard or generating new one
        if "latest" in question_lower or "recent" in question_lower:
            latest_dashboard = get_latest_dashboard()
            if latest_dashboard:
                return latest_dashboard
        # Otherwise generate a new dashboard
        return generate_daily_dashboard()
    
    # Check for custom dashboard requests
    if any(phrase in question_lower for phrase in [
        "custom dashboard", "specific dashboard", "filtered dashboard"
    ]):
        # Extract date ranges if provided
        start_date = None
        end_date = None
        building_id = None
        trade = None
        
        # Simple parsing logic - could be expanded with better NLP
        if "last week" in question_lower:
            start_date = (datetime.now() - timedelta(days=7)).date().isoformat()
        elif "last month" in question_lower:
            start_date = (datetime.now() - timedelta(days=30)).date().isoformat()
            
        # Extract building ID if mentioned
        building_match = re.search(r"building\s*(?:id)?\s*[#:]?\s*(\d+)", question_lower)
        if building_match:
            building_id = building_match.group(1)
            
        # Extract trade if mentioned
        trade_patterns = ["electric", "plumbing", "mechanical", "hvac", "carpentry"]
        for pattern in trade_patterns:
            if pattern in question_lower:
                trade = pattern.upper()
                break
                
        return generate_custom_dashboard(start_date, end_date, building_id, trade)
    
    # WORK ORDER QUERIES
    # Check for work order related queries
    if re.search(r"work\s*order\s*(?:number)?\s*[#:]?\s*(\d+)", question_lower):
        # Extract work order number
        wo_match = re.search(r"work\s*order\s*(?:number)?\s*[#:]?\s*(\d+)", question_lower)
        if wo_match:
            work_order_number = wo_match.group(1)
            work_order = get_work_order_info(work_order_number)
            
            if work_order:
                # Format the response
                response_text = f"**Work Order #{work_order['work_order']}**\n\n"
                response_text += f"**Status:** {work_order.get('status', 'Unknown')}\n"
                response_text += f"**Priority:** {work_order.get('priority', 'Not specified')}\n"
                response_text += f"**Building:** {work_order.get('building_name', 'Not specified')}\n"
                response_text += f"**Equipment:** {work_order.get('equipment', 'Not specified')}\n"
                response_text += f"**Description:** {work_order.get('description', 'No description')}\n"
                
                if work_order.get('scheduled_start_date'):
                    response_text += f"**Scheduled Start:** {work_order['scheduled_start_date']}\n"
                
                if work_order.get('date_completed'):
                    response_text += f"**Completed:** {work_order['date_completed']}\n"
                
                response_text += f"**Type:** {work_order.get('wo_type', 'Not specified')}\n"
                response_text += f"**Trade:** {work_order.get('trade', 'Not specified')}\n"
                return response_text
            else:
                return f"I couldn't find any information for Work Order #{work_order_number}."
    
    # Check for building-related work order queries
    elif any(kw in question_lower for kw in ["building work orders", "work orders for building"]):
        building_id_match = re.search(r"building\s*(?:id|number)?\s*[#:]?\s*(\d+)", question_lower)
        building_name_match = re.search(r"building\s*(?:name)?\s*[:]?\s*[\"']?([^\"']+?)[\"']?(?:\s|$)", question_lower)
        
        building_id = building_id_match.group(1) if building_id_match else None
        building_name = building_name_match.group(1).strip() if building_name_match else None
        
        if building_id or building_name:
            work_orders = get_building_work_orders(building_id, building_name)
            
            if work_orders:
                if building_name:
                    response_text = f"**Recent Work Orders for Building: {building_name}**\n\n"
                else:
                    response_text = f"**Recent Work Orders for Building ID: {building_id}**\n\n"
                
                for i, wo in enumerate(work_orders[:10], 1):  # Limit to first 10
                    response_text += f"{i}. **WO #{wo['work_order']}** - {wo.get('status', 'Unknown')}\n"
                    response_text += f"   {wo.get('description', 'No description')[:100]}...\n"
                    response_text += f"   Priority: {wo.get('priority', 'Not specified')}\n\n"
                
                if len(work_orders) > 10:
                    response_text += f"\n*Showing 10 of {len(work_orders)} work orders.*"
                
                return response_text
            else:
                if building_name:
                    return f"I couldn't find any work orders for building named '{building_name}'."
                else:
                    return f"I couldn't find any work orders for building ID {building_id}."
    
    # Check for critical work orders query
    elif "critical work orders" in question_lower or "high priority work orders" in question_lower:
        critical_wos = get_critical_work_orders()
        
        if critical_wos:
            response_text = "**Critical Priority Work Orders**\n\n"
            
            for i, wo in enumerate(critical_wos, 1):
                response_text += f"{i}. **WO #{wo['work_order']}** - {wo.get('building_name', 'Unknown location')}\n"
                response_text += f"   {wo.get('description', 'No description')[:100]}...\n"
                response_text += f"   Status: {wo.get('status', 'Unknown')}\n\n"
            
            return response_text
        else:
            return "I couldn't find any critical priority work orders at this time."

    # PM CODE QUERIES
    if (("what" in question_lower or "list" in question_lower or "show" in question_lower) and 
        ("pm code" in question_lower or "pm codes" in question_lower or "task plan" in question_lower)):
        
        # Extract equipment name from the question
        equipment = None
        for keyword in ["for ", "of ", "related to "]:
            if keyword in question_lower:
                equipment = question_lower.split(keyword, 1)[1].strip().rstrip("?")
                break
        
        if equipment:
            # Search for PM codes in dictionary where pm_name contains the equipment
            query = supabase.table("dictionary") \
                .select("pm_code, pm_name") \
                .ilike("pm_name", f"%{equipment}%") \
                .execute()
            
            results = {}
            if query.data:
                # Get unique pm_code and pm_name pairs
                for row in query.data:
                    if row["pm_code"] not in results:
                        results[row["pm_code"]] = row["pm_name"]
            
            if results:
                response_text = f"**PM Codes for {equipment.title()}:**\n\n"
                for code, name in results.items():
                    response_text += f"- **{code}**: {name}\n"
                return response_text
            else:
                # Try searching in description if no results in pm_name
                query = supabase.table("dictionary") \
                    .select("pm_code, pm_name, description") \
                    .ilike("description", f"%{equipment}%") \
                    .execute()
                
                if query.data:
                    results = {}
                    for row in query.data:
                        if row["pm_code"] not in results:
                            results[row["pm_code"]] = row["pm_name"]
                    
                    if results:
                        response_text = f"**PM Codes for {equipment.title()}:**\n\n"
                        for code, name in results.items():
                            response_text += f"- **{code}**: {name}\n"
                        return response_text
                
                return f"No PM codes found for '{equipment}' in the database."
    
    pm_match = re.search(r"([A-Z]+[-]\w+[-]\d{2})", question)
    if pm_match:
        search_term = pm_match.group(1)
        tasks = get_pm_tasks(search_term, search_pm_code=True, search_pm_name=True)
        label = "PM Code"
    else:
        # Search both pm_code and pm_name for the user's input
        search_term = question.strip()
        tasks = get_pm_tasks(search_term, search_pm_code=True, search_pm_name=True)
        label = "PM Name or Code"

    if tasks and len(tasks) > 0:
        df = pd.DataFrame(tasks)
        df = df.sort_values("sequence")
        pm_code = df.iloc[0]['pm_code']
        pm_name = df.iloc[0]['pm_name']
        table_md = df[["sequence", "description"]].to_markdown(index=False)
        response_text = (
            f"**PM Code:** {pm_code}\n\n"
            f"**PM Name:** {pm_name}\n\n"
            "**Tasks:**\n"
            f"{table_md}"
        )
        return response_text
    
    # FALLBACK TO GPT
    # If not found, continue with code/gen AI as fallback
    # Remove the plain "code" keyword from triggering code snippet output.
    question_lower = question.lower()
    needs_code = any(kw in question_lower for kw in [
        "visualize", "chart", "graph", "plot", "draw", "bar chart", "line chart", "heatmap", "generate code"
    ])
    
    # Add work order data to context for the AI
    work_orders_context = "The system includes work order data with these fields:\n"
    work_orders_context += "- work_order: unique identifier for the work order\n"
    work_orders_context += "- status: current status (Open, Closed, In Progress, etc.)\n"
    work_orders_context += "- priority: priority level (Critical, High, Medium, Low)\n"
    work_orders_context += "- building_name: name of the building\n"
    work_orders_context += "- building_id: unique identifier for the building\n"
    work_orders_context += "- description: description of the work needed\n"
    work_orders_context += "- equipment: equipment involved\n"
    work_orders_context += "- scheduled_start_date: when work is scheduled to start\n"
    work_orders_context += "- date_completed: when work was completed\n"
    work_orders_context += "- trade: trade responsible for the work\n\n"
    
    context = work_orders_context + context
    
    if needs_code:
        prompt = (
            'You are a Streamlit data assistant.\n'
            'When answering, provide a complete Python code snippet that includes all necessary imports:\n'
            '```python\nimport streamlit as st\nimport pandas as pd\nimport plotly.express as px\n```\n\n'
            'For all visualizations, use Plotly and display figures using `st.plotly_chart(fig, key="unique_key")`.\n'
            'Do NOT use matplotlib or seaborn.\n'
            'IMPORTANT: Do NOT read any data from local files. Assume the uploaded data is already loaded '
            'into a pandas DataFrame called `df`.\n\n'
            f'Context (including Data Dictionary):\n{context}\n\n'
            f'User question: {question}\nAnswer:\n'
            'Provide the code wrapped in triple backticks with python, like:\n'
            '```python\n...code...\n```'
        )
    else:
        prompt = (
            'You are a helpful Streamlit chatbot assistant.\n'
            'You may assume the user has uploaded data already loaded into a DataFrame called `df`.\n'
            'Please review the provided context—including the Data Dictionary below—to answer the user\'s question.\n\n'
            f'Context (including Data Dictionary):\n{context}\n\n'
            f'User question: {question}\nAnswer:'
        )
    model_name = get_latest_model_name()
    response = openai.ChatCompletion.create(
        model=model_name,
        messages=[
            {"role": "system", "content": "You are a helpful assistant for data analysis in Streamlit."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content.strip()