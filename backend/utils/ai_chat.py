import openai
import os
import re
import pandas as pd
import base64
from datetime import datetime, timedelta
from backend.utils.supabase_client import supabase
from frontend.guidance_section import get_guidance_results, get_best_practices_results

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
        names = list({row["pm_name"] for row in query.data if row["pm_name"]})
        return names
    return []

def get_work_order_info(work_order_number):
    query = supabase.table("work_orders_history") \
        .select("*") \
        .eq("work_order", str(work_order_number)) \
        .execute()
    if query.data and len(query.data) > 0:
        return query.data[0]
    return None

def get_building_work_orders(building_id=None, building_name=None, limit=20):
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
    if search_pm_code:
        query = supabase.table("dictionary") \
            .select("pm_code, pm_name, sequence, description") \
            .ilike("pm_code", f"%{search_term}%") \
            .execute()
        if query.data and len(query.data) > 0:
            return query.data
    if search_pm_name:
        query = supabase.table("dictionary") \
            .select("pm_code, pm_name, sequence, description") \
            .ilike("pm_name", f"%{search_term}%") \
            .execute()
        if query.data and len(query.data) > 0:
            return query.data
    return []

def get_pm_work_orders(start_date=None, end_date=None, building=None, zone=None, region=None, status=None, limit=10):
    """
    Retrieves PM work orders based on filters
    """
    try:
        query = supabase.table("pm_work_orders").select("*")
        # Apply filters
        if start_date:
            query = query.gte('scheduled_start_date', start_date)
        if end_date:
            query = query.lte('scheduled_start_date', end_date)
        if building:
            # Use case-insensitive exact match for building name
            query = query.ilike('building_name', building)
        if zone and zone != "All Zones":
            query = query.eq('zone', zone)
        if region and region != "All Regions":
            query = query.eq('region', region)
        if status:
            query = query.eq('status', status)
        result = query.order('scheduled_start_date', desc=True).limit(limit).execute()
        if result.data and len(result.data) > 0:
            return result.data
        return []
    except Exception as e:
        print(f"Error getting PM work orders: {str(e)}")
        return []

def get_overdue_pm_work_orders(limit=10):
    today = datetime.now().strftime('%Y-%m-%d')
    try:
        query = supabase.table("pm_work_orders") \
            .select("*") \
            .lt('scheduled_start_date', today) \
            .not_.like('status', '%Complete%') \
            .not_.like('status', '%Closed%') \
            .order('scheduled_start_date') \
            .limit(limit) \
            .execute()
        if query.data and len(query.data) > 0:
            return query.data
        return []
    except Exception as e:
        print(f"Error getting overdue PMs: {str(e)}")
        return []

def get_pm_metrics_summary(building=None, zone=None, region=None):
    try:
        query = supabase.table("pm_work_orders").select("status, count", count="exact")
        if building:
            query = query.ilike('building_name', building)
        if zone and zone != "All Zones":
            query = query.eq('zone', zone)
        if region and region != "All Regions":
            query = query.eq('region', region)
        result = query.execute()
        completed_query = query.like('status', '%Complete%').execute()
        total = result.count if hasattr(result, 'count') else 0
        completed = completed_query.count if hasattr(completed_query, 'count') else 0
        completion_rate = round((completed / total) * 100) if total > 0 else 0
        return {
            "total_pms": total,
            "completed_pms": completed,
            "completion_rate": completion_rate
        }
    except Exception as e:
        print(f"Error getting PM metrics: {str(e)}")
        return {
            "total_pms": 0,
            "completed_pms": 0,
            "completion_rate": 0
        }

def search_process_maps(query, limit=3):
    """Search process maps based on keywords"""
    try:
        # First search by title (most relevant)
        title_query = supabase.table("process_maps") \
            .select("*") \
            .ilike("title", f"%{query}%") \
            .limit(limit) \
            .execute()
            
        results = title_query.data
        
        # If we don't have enough results, search by description
        if len(results) < limit:
            desc_query = supabase.table("process_maps") \
                .select("*") \
                .ilike("description", f"%{query}%") \
                .not_.in_("id", [item["id"] for item in results]) \
                .limit(limit - len(results)) \
                .execute()
            
            results.extend(desc_query.data)
            
        # If we still don't have enough, search by category
        if len(results) < limit:
            cat_query = supabase.table("process_maps") \
                .select("*") \
                .ilike("category", f"%{query}%") \
                .not_.in_("id", [item["id"] for item in results]) \
                .limit(limit - len(results)) \
                .execute()
                
            results.extend(cat_query.data)
            
        return results
    except Exception as e:
        print(f"Error searching process maps: {str(e)}")
        return []

def get_process_map_by_id(map_id):
    """Get a specific process map by ID"""
    try:
        response = supabase.table("process_maps").select("*").eq("id", map_id).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        print(f"Error fetching process map by ID: {e}")
        return None
    
GUIDANCE_KEYWORDS = ["regulation", "bylaw", "code", "legal requirement"]
BEST_PRACTICE_KEYWORDS = ["best practice", "oem manual", "manual", "procedure", "recommendation", "standard", "maintenance tip"]

def ask_gpt(question, context=""):
    question_lower = question.lower()
        # Guidance/Regulation queries
    if any(kw in question_lower for kw in GUIDANCE_KEYWORDS):
        results = get_guidance_results(question_lower, limit=3)
        if results:
            response = "**Here are relevant regulations/bylaws:**\n\n"
            for r in results:
                response += f"- **{r['Equipment']}** ({r['Regulation/Code']}): {r['Reference']}\n"
            response += "\nFor more, visit the Regulations & Bylaws section."
            return response

    # Best practices queries
    if any(kw in question_lower for kw in BEST_PRACTICE_KEYWORDS):
        results = get_best_practices_results(question_lower, limit=3)
        if results:
            response = "**Here are some best practices from trusted sources:**\n\n"
            for r in results:
                response += f"- [{r['title']}]({r['link']}) ({r['domain']})\n"
            response += "\nFor more, visit the Best Practices section."
            return response

    
    # PROCESS MAPS QUERIES - Moved to top priority and enhanced
    if any(phrase in question_lower for phrase in [
        "process map", "workflow", "procedure", "flow chart", "diagram",
        "process diagram", "work order flow", "steps for", "process for",
        "how do i", "how to", "procedure for", "what's the process",
        "show me process", "get process", "find process", "display process",
        "need the process", "want the process"
    ]):
        search_terms = question_lower
        
        # Extract the specific terms from the request
        for phrase in ["process map for", "workflow for", "procedure for", "steps for", 
                       "how do i", "how to", "what's the process for", "show me process for",
                       "show me the", "display the", "open the", "view the", 
                       "can you show me", "i want to see", "pull up the", "find the",
                       "get the", "process for"]:
            if phrase in question_lower:
                search_terms = question_lower.split(phrase, 1)[1].strip()
                break
        
        # Clean up search terms
        for term in ["process map", "workflow", "procedure", "diagram", "please", "thanks", "?"]:
            search_terms = search_terms.replace(term, "").strip()
        
        # Search for relevant process maps
        results = search_process_maps(search_terms)
        
        if results:
            # Always return the structured response with PDFs for process map queries
            return {
                "type": "process_maps",
                "message": f"Here are the process maps related to your query:",
                "results": results
            }
        else:
            # If no results, still return a structured response but with empty results
            return {
                "type": "process_maps",
                "message": f"I couldn't find any process maps related to '{search_terms}'. Please try different keywords or check with your administrator.",
                "results": []
            }
    
    # Handle work order summary requests
    if any(phrase in question_lower for phrase in [
        "summary of yesterday", "yesterday's work order", "summary of work orders",
        "yesterday's summary", "work orders from yesterday", "yesterday work order summary"
    ]):
        try:
            dashboard = generate_daily_dashboard()
            summary_match = re.search(r"## Summary Metrics\n\n(.*?)(?=##|\Z)", dashboard, re.DOTALL)
            if summary_match:
                summary = "# Summary of Yesterday's Work Orders\n\n" + summary_match.group(1)
                insights_match = re.search(r"## AI Insights\n\n(.*?)(?=##|\Z)", dashboard, re.DOTALL)
                if insights_match:
                    summary += "\n\n## Key Insights\n\n" + insights_match.group(1)
                critical_match = re.search(r"## Recent Critical Work Orders\n\n(.*?)(?=##|\Z)", dashboard, re.DOTALL)
                if critical_match:
                    summary += "\n\n## Critical Work Orders\n\n" + critical_match.group(1)
                return summary
            return "I generated a dashboard for yesterday's work orders, but couldn't extract the summary. Try asking for the full dashboard."
        except Exception as e:
            return f"I encountered an error trying to generate the work order summary: {str(e)}"

    # Dashboard functionality
    if any(phrase in question_lower for phrase in [
        "generate dashboard", "create dashboard", "show dashboard", "daily dashboard",
        "yesterday's dashboard", "work order dashboard"
    ]):
        if "latest" in question_lower or "recent" in question_lower:
            latest_dashboard = get_latest_dashboard()
            if latest_dashboard:
                return latest_dashboard
        return generate_daily_dashboard()

    # Custom dashboard requests
    if any(phrase in question_lower for phrase in [
        "custom dashboard", "specific dashboard", "filtered dashboard"
    ]):
        start_date = None
        end_date = None
        building_id = None
        trade = None
        if "last week" in question_lower:
            start_date = (datetime.now() - timedelta(days=7)).date().isoformat()
        elif "last month" in question_lower:
            start_date = (datetime.now() - timedelta(days=30)).date().isoformat()
        building_match = re.search(r"building\s*(?:id)?\s*[#:]?\s*(\d+)", question_lower)
        if building_match:
            building_id = building_match.group(1)
        trade_patterns = ["electric", "plumbing", "mechanical", "hvac", "carpentry"]
        for pattern in trade_patterns:
            if pattern in question_lower:
                trade = pattern.upper()
                break
        return generate_custom_dashboard(start_date, end_date, building_id, trade)

    # Work order queries
    if re.search(r"work\s*order\s*(?:number)?\s*[#:]?\s*(\d+)", question_lower):
        wo_match = re.search(r"work\s*order\s*(?:number)?\s*[#:]?\s*(\d+)", question_lower)
        if wo_match:
            work_order_number = wo_match.group(1)
            work_order = get_work_order_info(work_order_number)
            if work_order:
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
                for i, wo in enumerate(work_orders[:10], 1):
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
        equipment = None
        for keyword in ["for ", "of ", "related to "]:
            if keyword in question_lower:
                equipment = question_lower.split(keyword, 1)[1].strip().rstrip("?")
                break
        if equipment:
            query = supabase.table("dictionary") \
                .select("pm_code, pm_name") \
                .ilike("pm_name", f"%{equipment}%") \
                .execute()
            results = {}
            if query.data:
                for row in query.data:
                    if row["pm_code"] not in results:
                        results[row["pm_code"]] = row["pm_name"]
            if results:
                response_text = f"**PM Codes for {equipment.title()}:**\n\n"
                for code, name in results.items():
                    response_text += f"- **{code}**: {name}\n"
                return response_text
            else:
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

    # PM WORK ORDER QUERIES - NEW SECTION WITH EXPANDED PHRASES
    if any(phrase in question_lower for phrase in [
        "preventive maintenance", "pm work order", "pm schedule", 
        "maintenance schedule", "maintenance plan", "maintenance task", 
        "scheduled maintenance", "equipment maintenance", "list maintenance",
        "show maintenance", "maintenance for", "maintenance at"
    ]):
        building = None
        zone = None
        region = None
        status = None
        # Building alias mapping for more accurate results
        building_aliases = {
            "municipal building": "Municipal Building",
            "city hall": "Historic City Hall",
            # Add more aliases as needed
        }
        building_match = re.search(r"building\s*(?:name)?\s*[:]?\s*[\"']?([^\"']+?)[\"']?(?:\s|$)", question_lower)
        if building_match:
            building = building_match.group(1).strip()
            if building.lower() in building_aliases:
                building = building_aliases[building.lower()]
        zone_match = re.search(r"zone\s*(?:name)?\s*[:]?\s*[\"']?([^\"']+?)[\"']?(?:\s|$)", question_lower)
        if zone_match:
            zone = zone_match.group(1).strip().upper()
        region_match = re.search(r"region\s*(?:name)?\s*[:]?\s*[\"']?([^\"']+?)[\"']?(?:\s|$)", question_lower)
        if region_match:
            region = region_match.group(1).strip()
        if "overdue" in question_lower or "past due" in question_lower:
            overdue_pms = get_overdue_pm_work_orders(limit=15)
            if overdue_pms:
                response_text = f"**Overdue Preventive Maintenance Work Orders**\n\n"
                for i, pm in enumerate(overdue_pms, 1):
                    scheduled_date = pm.get('scheduled_start_date', 'Unknown date')
                    if isinstance(scheduled_date, str) and len(scheduled_date) > 10:
                        scheduled_date = scheduled_date[:10]
                    response_text += f"{i}. **PM #{pm.get('work_order', 'Unknown')}** - {pm.get('building_name', 'Unknown location')}\n"
                    response_text += f"   Equipment: {pm.get('equipment', 'Unknown')}\n"
                    response_text += f"   Scheduled: {scheduled_date} (OVERDUE)\n"
                    response_text += f"   Status: {pm.get('status', 'Unknown')}\n\n"
                return response_text
            else:
                return "I couldn't find any overdue PM work orders at this time."
        elif "upcoming" in question_lower or "scheduled" in question_lower or "future" in question_lower:
            today = datetime.now().strftime('%Y-%m-%d')
            future = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
            upcoming_pms = get_pm_work_orders(start_date=today, end_date=future, 
                                              building=building, zone=zone, region=region, limit=15)
            if upcoming_pms:
                response_text = f"**Upcoming Preventive Maintenance Work Orders"
                if building:
                    response_text += f" for {building}"
                if zone:
                    response_text += f" in {zone} Zone"
                response_text += "**\n\n"
                for i, pm in enumerate(upcoming_pms, 1):
                    scheduled_date = pm.get('scheduled_start_date', 'Unknown date')
                    if isinstance(scheduled_date, str) and len(scheduled_date) > 10:
                        scheduled_date = scheduled_date[:10]
                    response_text += f"{i}. **PM #{pm.get('work_order', 'Unknown')}** - {scheduled_date}\n"
                    response_text += f"   Building: {pm.get('building_name', 'Unknown location')}\n"
                    response_text += f"   Equipment: {pm.get('equipment', 'Unknown')}\n"
                    response_text += f"   Trade: {pm.get('trade', 'Unknown')}\n\n"
                return response_text
            else:
                return "I couldn't find any upcoming PM work orders matching your criteria."
        elif "metrics" in question_lower or "completion rate" in question_lower or "summary" in question_lower:
            metrics = get_pm_metrics_summary(building=building, zone=zone, region=region)
            response_text = f"**Preventive Maintenance Metrics"
            if building:
                response_text += f" for {building}"
            if zone:
                response_text += f" in {zone} Zone"
            response_text += "**\n\n"
            response_text += f"• Total PMs: {metrics['total_pms']}\n"
            response_text += f"• Completed PMs: {metrics['completed_pms']}\n"
            response_text += f"• Completion Rate: {metrics['completion_rate']}%\n"
            return response_text
        else:
            recent_pms = get_pm_work_orders(building=building, zone=zone, region=region, limit=10)
            if recent_pms:
                response_text = f"**Recent Preventive Maintenance Work Orders"
                if building:
                    response_text += f" for {building}"
                if zone:
                    response_text += f" in {zone} Zone"
                response_text += "**\n\n"
                for i, pm in enumerate(recent_pms, 1):
                    scheduled_date = pm.get('scheduled_start_date', 'Unknown date')
                    if isinstance(scheduled_date, str) and len(scheduled_date) > 10:
                        scheduled_date = scheduled_date[:10]
                    response_text += f"{i}. **PM #{pm.get('work_order', 'Unknown')}** - {pm.get('status', 'Unknown')}\n"
                    response_text += f"   Building: {pm.get('building_name', 'Unknown location')}\n"
                    response_text += f"   Equipment: {pm.get('equipment', 'Unknown')}\n"
                    response_text += f"   Scheduled: {scheduled_date}\n\n"
                response_text += (
                    "\nRegular preventive maintenance helps reduce unexpected breakdowns and extends equipment life. "
                    "If you notice repeated maintenance for the same equipment, it may indicate underlying issues such as aging assets, improper usage, or environmental factors. "
                    "Consider reviewing maintenance history, scheduling more frequent inspections, or consulting with specialists to address recurring problems. "
                    "Proactive planning and communication with your maintenance team can help ensure all tasks are completed efficiently and on schedule."
                )
                return response_text
            else:
                all_buildings_query = supabase.table("pm_work_orders").select("building_name").execute()
                building_names = sorted({row["building_name"] for row in all_buildings_query.data if row.get("building_name")})
                suggestion = ""
                if building and building_names:
                    suggestion = f"\nAvailable building names include: {', '.join(building_names[:10])}..."
                return f"I couldn't find any PM work orders matching your criteria.{suggestion} If you have concerns about missing maintenance, consider reviewing your scheduling process or contacting your PM coordinator for further assistance."

    needs_code = any(kw in question_lower for kw in [
        "visualize", "chart", "graph", "plot", "draw", "bar chart", "line chart", "heatmap", "generate code"
    ])

    work_orders_context = (
        "The system includes two main data types:\n\n"
        "1. WORK ORDERS with these fields:\n"
        "- work_order: unique identifier for the work order\n"
        "- status: current status (Open, Closed, In Progress, etc.)\n"
        "- priority: priority level (Critical, High, Medium, Low)\n"
        "- building_name: name of the building\n"
        "- building_id: unique identifier for the building\n"
        "- description: description of the work needed\n"
        "- equipment: equipment involved\n"
        "- scheduled_start_date: when work is scheduled to start\n"
        "- date_completed: when work was completed\n"
        "- trade: trade responsible for the work\n\n"
        "2. PREVENTIVE MAINTENANCE (PM) WORK ORDERS with these fields:\n"
        "- work_order: unique identifier for the PM work order\n"
        "- status: current status (Open, Closed, Complete, etc.)\n"
        "- building_name: name of the building\n"
        "- zone: geographic zone (NORTH, SOUTH, CENTER)\n"
        "- region: region name\n"
        "- equipment: equipment being maintained\n"
        "- description: description of the maintenance task\n"
        "- scheduled_start_date: when maintenance is scheduled\n"
        "- date_completed: when maintenance was completed\n"
        "- trade: trade responsible for the maintenance\n"
        "- pm_code: code identifying the type of PM\n\n"
        "3. PROCESS MAPS with these fields:\n"
        "- title: name of the process map\n"
        "- category: category the process map belongs to\n"
        "- description: detailed description of what the process map covers\n"
        "- file_data: the actual PDF content\n\n"
    )

    # --- Context Limiting Logic ---
    # Only add the large context if code/data analysis is needed
    if needs_code:
        context = work_orders_context + context
        # Truncate context if too long
        if isinstance(context, str) and len(context) > 3000:
            context = context[:3000] + "\n...[truncated]..."
    else:
        # For plain Q&A, keep context minimal
        if isinstance(context, str) and len(context) > 1000:
            context = context[:1000] + "\n...[truncated]..."
        # Do NOT add the large work_orders_context for simple Q&A

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
            'You are a helpful maintenance and facilities management assistant with deep expertise in preventive maintenance and troubleshooting.\n'
            'When answering, provide not only the requested information, but also explain possible causes, contributing factors, and offer practical solutions or recommendations.\n'
            'If the user asks about an issue, describe why it might occur and how to address or prevent it.\n'
            'DO NOT provide code examples unless specifically asked for code.\n'
            'DO NOT assume data is in a DataFrame unless the user specifically asks for data analysis.\n'
            'When discussing maintenance schedules, work orders, or equipment, use plain language and include actionable advice.\n\n'
            f'Context (including Data Dictionary):\n{context}\n\n'
            f'User question: {question}\n'
            'Your response should:\n'
            '- Explain the underlying causes or reasons for the issue or request\n'
            '- Offer practical solutions, recommendations, or next steps\n'
            '- Be clear, conversational, and helpful\n'
            'Answer:'
        )
    # Force use of gpt-3.5-turbo for speed, set max_tokens and temperature for faster, more focused responses
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful maintenance assistant for facilities management. Always explain causes and provide solutions or recommendations, not just direct answers. Do not provide code unless requested."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=512,
        temperature=0.3,
        response_format={"type": "text"}
    )
    return response.choices[0].message.content.strip()