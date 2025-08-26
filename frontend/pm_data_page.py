import streamlit as st
import pandas as pd
import json
import os
from io import BytesIO
from datetime import datetime, timedelta
from backend.utils.pm_wo_retrieval import get_pm_data, get_pm_metrics
from frontend.pm_schedule_viewer import display_scheduling_recommendations, display_pm_schedule_planner
from frontend.pm_schedule_viewer import display_pm_calendar_view, display_status_distribution
from frontend.pm_schedule_viewer import organize_pm_data_in_tabs

# Add caching functions to prevent redundant database queries
def get_cached_zones():
    """Get zones from cache or fetch from database if not cached"""
    if "cached_zones" not in st.session_state:
        try:
            from backend.utils.pm_wo_retrieval import get_distinct_zones
            zones = get_distinct_zones()
            zone_options = ["All Zones"] + sorted(set(zones)) if zones else ["All Zones"]
            st.session_state["cached_zones"] = zone_options
        except Exception:
            zone_options = ["All Zones", "NORTH", "SOUTH", "CENTER"]
            st.session_state["cached_zones"] = zone_options
    
    return st.session_state["cached_zones"]

def get_cached_regions():
    """Get regions from cache or fetch from database if not cached"""
    if "cached_regions" not in st.session_state:
        try:
            from backend.utils.pm_wo_retrieval import get_distinct_regions
            regions = get_distinct_regions()
            region_options = ["All Regions"] + sorted(set(regions)) if regions else ["All Regions"]
            st.session_state["cached_regions"] = region_options
        except Exception:
            region_options = ["All Regions", "Calgary", "Edmonton", "Red Deer", "Lethbridge", "Medicine Hat"]
            st.session_state["cached_regions"] = region_options
    
    return st.session_state["cached_regions"]

def show_pm_data_page():
    """
    Display the PM Data page with Dashboard and Data Explorer tabs
    """
    # Add back button
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("< Back", use_container_width=True):
            st.session_state["current_page"] = "main"
            st.rerun()
    with col2:
        st.title("Preventive Maintenance Data")
    
    # Only show the Future PMs tab with integrated dashboard dropdown
    display_future_pms_tab()
        

def display_dashboard_tab():
    """Handle dashboard tab separately to avoid rerunning when other tabs are active"""
    try:
        # Set default dates for metrics based on the current month
        today = datetime.now()
        first_day_of_month = datetime(today.year, today.month, 1)
        last_day_of_month = (first_day_of_month + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        # Default values
        start_date = first_day_of_month
        end_date = last_day_of_month
        
        # Create filter expander at the top
        with st.expander("Filter Options", expanded=True):
            # Use form to prevent automatic rerunning on input change
            with st.form("dashboard_filters"):
                # Date range selector with presets
                col1, col2, col3 = st.columns(3)
                with col1:
                    date_preset = st.selectbox(
                        "Date Range Preset:",
                        ["This Month", "Previous Month", "Last 30 Days", "Year to Date", "Custom Range"],
                        index=0,
                        key="dashboard_date_preset"
                    )
                    
                    # Set date range based on preset
                    if date_preset == "This Month":
                        start_date = first_day_of_month
                        end_date = last_day_of_month
                    elif date_preset == "Previous Month":
                        prev_month = (first_day_of_month - timedelta(days=1)).replace(day=1)
                        last_day_prev_month = first_day_of_month - timedelta(days=1)
                        start_date = prev_month
                        end_date = last_day_prev_month
                    elif date_preset == "Last 30 Days":
                        start_date = today - timedelta(days=30)
                        end_date = today
                    elif date_preset == "Year to Date":
                        start_date = datetime(today.year, 1, 1)
                        end_date = today
                
                # Custom date range if selected
                with col2:
                    start_date = st.date_input("Start Date:", start_date, key="dashboard_start_date")
                
                with col3:
                    end_date = st.date_input("End Date:", end_date, key="dashboard_end_date")
                    
                # Additional filters - update to use 3 columns to add zone
                col1, col2, col3 = st.columns(3)
                with col1:
                    # Building filter with typeahead/autocomplete feel
                    building_filter = st.text_input("Building:", placeholder="Enter building name or ID", key="dashboard_building")
                
                # Use cached zone and region options
                with col2:
                    zone_options = get_cached_zones()
                    zone_filter = st.selectbox("Zone:", zone_options, key="dashboard_zone")
                
                with col3:
                    region_options = get_cached_regions()
                    region_filter = st.selectbox("Region:", region_options, key="dashboard_region")
                
                # Apply filters button
                submit_pressed = st.form_submit_button("Apply Filters", type="primary", use_container_width=True)
                
                if submit_pressed:
                    st.session_state["dashboard_filters_applied"] = True
                    # Store filter values in session state
                    st.session_state["dashboard_filter_values"] = {
                        "start_date": start_date.strftime('%Y-%m-%d'),
                        "end_date": end_date.strftime('%Y-%m-%d'),
                        "building": building_filter if building_filter else None,
                        "zone": None if zone_filter == "All Zones" else zone_filter,
                        "region": None if region_filter == "All Regions" else region_filter
                    }
                    # Clear cached metrics to force refresh
                    if "dashboard_metrics_cache" in st.session_state:
                        del st.session_state["dashboard_metrics_cache"]
        
        # Only process and display data if filters have been applied
        if "dashboard_filters_applied" in st.session_state and st.session_state["dashboard_filters_applied"]:
            # Check if metrics are already cached
            if "dashboard_metrics_cache" not in st.session_state:
                # Get saved filter values from session state
                saved_filters = st.session_state.get("dashboard_filter_values", {})
                start_date_str = saved_filters.get("start_date", start_date.strftime('%Y-%m-%d'))
                end_date_str = saved_filters.get("end_date", end_date.strftime('%Y-%m-%d'))
                building = saved_filters.get("building")
                zone = saved_filters.get("zone")
                region = saved_filters.get("region")
                
                # Display loading spinner while getting data
                with st.spinner("Loading PM data..."):
                    try:
                        metrics = get_pm_metrics(
                            start_date=start_date_str,
                            end_date=end_date_str,
                            building=building,
                            region=region,
                            zone=zone
                        )
                    except TypeError as e:
                        if "unexpected keyword argument 'zone'" in str(e):
                            metrics = get_pm_metrics(
                                start_date=start_date_str,
                                end_date=end_date_str,
                                building=building,
                                region=region
                            )
                            if zone:
                                st.warning(f"Zone filter '{zone}' was ignored. The backend API doesn't support filtering by zone yet.")
                        else:
                            raise e
                
                # Check if metrics data is valid
                if not metrics or not isinstance(metrics, dict):
                    metrics = create_fallback_metrics()
                
                # Ensure required fields exist
                ensure_required_metrics(metrics)
                
                # Cache the metrics
                st.session_state["dashboard_metrics_cache"] = metrics
            else:
                # Use cached metrics
                metrics = st.session_state["dashboard_metrics_cache"]
            
            # Display the dashboard components
            st.subheader("Preventive Maintenance Dashboard")
            
            # Add a refresh button
            if st.button("🔄 Refresh Dashboard Data", key="refresh_dashboard"):
                if "dashboard_metrics_cache" in st.session_state:
                    del st.session_state["dashboard_metrics_cache"]
                st.rerun()
            
            # Status distribution
            display_status_distribution(metrics)
            
            # Key metrics in colorful cards
            col1, col2, col3 = st.columns(3)
            with col1:
                completion_rate = metrics["completion_rate"]
                completion_color = "red" if completion_rate < 50 else "orange" if completion_rate < 80 else "green"
                st.markdown(f"""
                <div style="background-color:#f0f2f6;padding:20px;border-radius:10px;text-align:center;">
                    <h1 style="color:{completion_color};font-size:40px;margin:0;">{completion_rate}%</h1>
                    <p style="font-size:16px;margin:0;">Completion Rate</p>
                    <p style="font-size:12px;margin:0;">{metrics["completed_pms"]} of {metrics["total_pms"]} PMs</p>
                </div>
                """, unsafe_allow_html=True)
                
            with col2:
                overdue_count = metrics["overdue_pms"]
                overdue_color = "green" if overdue_count == 0 else "orange" if overdue_count < 5 else "red"
                st.markdown(f"""
                <div style="background-color:#f0f2f6;padding:20px;border-radius:10px;text-align:center;">
                    <h1 style="color:{overdue_color};font-size:40px;margin:0;">{overdue_count}</h1>
                    <p style="font-size:16px;margin:0;">Overdue PMs</p>
                    <p style="font-size:12px;margin:0;">Requires attention</p>
                </div>
                """, unsafe_allow_html=True)
                
            with col3:
                avg_days = metrics["avg_completion_days"]
                time_color = "green" if avg_days <= 1 else "orange" if avg_days <= 3 else "red"
                st.markdown(f"""
                <div style="background-color:#f0f2f6;padding:20px;border-radius:10px;text-align:center;">
                    <h1 style="color:{time_color};font-size:40px;margin:0;">{avg_days}</h1>
                    <p style="font-size:16px;margin:0;">Avg. Completion Time</p>
                    <p style="font-size:12px;margin:0;">Days to complete</p>
                </div>
                """, unsafe_allow_html=True)
            
            # Monthly trends
            st.subheader("PM Trends")
            
            if metrics["monthly_trend"]:
                trend_df = pd.DataFrame(metrics["monthly_trend"])
                
                # Calculate completion percentage for each month
                trend_df['completion_pct'] = (trend_df['completed'] / trend_df['scheduled'] * 100).round().astype(int)
                
                # Create a more visually appealing chart
                chart_data = trend_df.set_index("month")
                
                # Add a completion percentage line
                col1, col2 = st.columns([3, 1])
                with col1:
                    # Use Streamlit's native chart with custom color
                    st.bar_chart(
                        chart_data[["scheduled", "completed"]],
                        color=["#ff9f1c", "#2ec4b6"]
                    )
                
                with col2:
                    st.markdown("### Completion Percentage")
                    for idx, row in trend_df.iterrows():
                        month_name = row['month']
                        completion = row['completion_pct']
                        color = "red" if completion < 50 else "orange" if completion < 80 else "green"
                        st.markdown(f"""
                        <div style="margin-bottom:10px;padding:5px 10px;border-radius:5px;background-color:#f0f2f6;">
                            <span style="font-size:12px;">{month_name}</span>
                            <span style="float:right;font-weight:bold;color:{color};">{completion}%</span>
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.info("No recent PM data available.")
            
            # Add an info box showing what filters are applied
            saved_filters = st.session_state.get("dashboard_filter_values", {})
            filter_desc = []
            if date_preset != "Custom Range":
                filter_desc.append(f"Date Range: {date_preset}")
            else:
                filter_desc.append(f"Date Range: {saved_filters.get('start_date')} to {saved_filters.get('end_date')}")
                
            building = saved_filters.get("building")
            zone = saved_filters.get("zone")
            region = saved_filters.get("region")
            
            if building: filter_desc.append(f"Building: {building}")
            if zone and zone != "All Zones": filter_desc.append(f"Zone: {zone}")
            if region and region != "All Regions": filter_desc.append(f"Region: {region}")
            
            st.caption(f"**Applied Filters:** {', '.join(filter_desc)}")
        else:
            # Show instructions if no filters applied yet
            st.info("👆 Set your filters above and click 'Apply Filters' to view PM data.")
                
    except Exception as e:
        st.error(f"Error loading dashboard: {str(e)}")
        st.exception(e)


def display_future_pms_tab():
    """Handle future PMs tab - only Calendar View (simplified)"""
    # PMs by Building Bar Chart
    # The following block should only run if future_metrics is defined, but future_metrics is only available after data is loaded below.
    # So, this block should be moved or guarded appropriately if needed.
 



    # Initialize filter values in session state if not present
    if "future_filter_values" not in st.session_state:
        today = datetime.now()
        st.session_state["future_filter_values"] = {
            "start_date": (today - timedelta(days=30)).strftime('%Y-%m-%d'),
            "end_date": (today + timedelta(days=90)).strftime('%Y-%m-%d'),
            "building": None,
            "zone": None,
            "status": None,
            "region": None
        }

    # Add filters for the Future PMs tab
    with st.expander("Filter Options", expanded=True):
        with st.form("future_pm_filters"):
            col1, col2 = st.columns(2)
            today = datetime.now()
            with col1:
                cal_start_date = st.date_input(
                    "Start Date:", 
                    datetime.strptime(st.session_state["future_filter_values"]["start_date"], '%Y-%m-%d')
                    if st.session_state["future_filter_values"]["start_date"] else today - timedelta(days=30),
                    key="cal_start_date_input"
                )
            with col2:
                cal_end_date = st.date_input(
                    "End Date:",
                    datetime.strptime(st.session_state["future_filter_values"]["end_date"], '%Y-%m-%d')
                    if st.session_state["future_filter_values"]["end_date"] else today + timedelta(days=90),
                    key="cal_end_date_input"
                )
            col1, col2, col3 = st.columns(3)
            with col1:
                future_building = st.text_input(
                    "Building:", 
                    value=st.session_state["future_filter_values"]["building"] or "",
                    placeholder="Enter building name or ID", 
                    key="future_building_input"
                )
            with col2:
                status_options = ["Assigned", "Open", "Cancelled", "Closed", "Waiting on Invoice", 
                                 "Work Complete", "No Resources", "PM Follow-up"]
                future_status = st.multiselect(
                    "Status:", 
                    status_options, 
                    default=st.session_state["future_filter_values"]["status"] or [],
                    key="future_status_input"
                )
            with col3:
                zone_options = get_cached_zones()
                selected_zone = st.session_state["future_filter_values"]["zone"]
                zone_index = zone_options.index(selected_zone) if selected_zone in zone_options else 0
                future_zone = st.selectbox(
                    "Zone:", 
                    zone_options, 
                    index=zone_index,
                    key="future_zone_input"
                )
            region_options = get_cached_regions()
            selected_region = st.session_state["future_filter_values"]["region"]
            region_index = region_options.index(selected_region) if selected_region in region_options else 0
            future_region = st.selectbox(
                "Region:", 
                region_options, 
                index=region_index,
                key="future_region_input"
            )
            try:
                from backend.utils.pm_wo_retrieval import get_distinct_organizations
                organization_options = ["All"] + get_distinct_organizations()
            except Exception:
                organization_options = ["All", "FM", "PK", "FI", "RC", "CP"]

            selected_organization = st.session_state["future_filter_values"].get("organization") or "All"
            org_index = organization_options.index(selected_organization) if selected_organization in organization_options else 0
            future_organization = st.selectbox(
                "Organization:",
                organization_options,
                index=org_index,
                key="future_organization_input"
            )
            submit_pressed = st.form_submit_button("Apply Calendar Filters", type="primary", use_container_width=True)
            if submit_pressed:
                st.session_state["future_filters_applied"] = True
                st.session_state["future_filter_values"] = {
                    "start_date": cal_start_date.strftime('%Y-%m-%d'),
                    "end_date": cal_end_date.strftime('%Y-%m-%d'),
                    "building": future_building if future_building else None,
                    "zone": None if future_zone == "All Zones" else future_zone,
                    "status": None if not future_status else future_status,
                    "region": None if future_region == "All Regions" else future_region,
                    "organization": None if future_organization == "All" else future_organization
                }
                if "future_calendar_cache" in st.session_state:
                    del st.session_state["future_calendar_cache"]
    
    if st.session_state.get("future_filters_applied", False):
        if "future_calendar_cache" not in st.session_state:
            saved_filters = st.session_state.get("future_filter_values", {})
            start_date_str = saved_filters.get("start_date")
            end_date_str = saved_filters.get("end_date")
            building = saved_filters.get("building")
            zone = saved_filters.get("zone")
            region = saved_filters.get("region")
            status = saved_filters.get("status")
            with st.spinner("Loading PM calendar data and dashboard metrics..."):
                try:
                    from backend.utils.pm_wo_retrieval import get_pm_calendar_data
                    calendar_data = get_pm_calendar_data(
                        start_date=start_date_str,
                        end_date=end_date_str,
                        building=building,
                        region=region,
                        zone=zone,
                        status=status,
                        organization=saved_filters.get("organization")
                    )
                    from backend.utils.pm_wo_retrieval import get_pm_metrics
                    future_metrics = get_pm_metrics(
                        start_date=start_date_str,
                        end_date=end_date_str,
                        building=building,
                        region=region,
                        zone=zone,
                        status=status,
                        organization=saved_filters.get("organization")
                    )
                    st.session_state["future_calendar_cache"] = {
                        "calendar_data": calendar_data,
                        "metrics": future_metrics
                    }
                except Exception as e:
                    st.error(f"Error loading calendar data: {e}")
                    return
        else:
            cached_data = st.session_state["future_calendar_cache"]
            calendar_data = cached_data["calendar_data"]
            future_metrics = cached_data["metrics"]

        # Only show Calendar View
        display_pm_calendar_view(future_metrics, calendar_data)
    
        # Show dashboard metrics at the bottom of the page in a dropdown
        st.markdown("---")
        with st.expander("Show Preventive Maintenance Dashboard", expanded=False):
            st.subheader("Preventive Maintenance Dashboard")
            # Show total number of work orders
            total_wos = 0
            if future_metrics:
                if "pm_data" in future_metrics and future_metrics["pm_data"]:
                    pm_df = pd.DataFrame(future_metrics["pm_data"])
                    if "work_order" in pm_df.columns:
                        total_wos = pm_df["work_order"].nunique()
                    elif "work_order_id" in pm_df.columns:
                        total_wos = pm_df["work_order_id"].nunique()
                    else:
                        total_wos = len(pm_df)
                elif "total_pms" in future_metrics:
                    total_wos = future_metrics["total_pms"]
            st.markdown(f"**Total Work Orders:** {total_wos}")
            display_status_distribution(future_metrics)

            # PMs by Building Bar Chart (Top 10)
            if future_metrics and "pm_data" in future_metrics and future_metrics["pm_data"]:
                pm_df = pd.DataFrame(future_metrics["pm_data"])
                if "building_name" in pm_df.columns:
                    st.markdown("#### PMs by Building (Top 10)")
                    building_counts = pm_df["building_name"].value_counts().head(10).reset_index()
                    building_counts.columns = ["Building", "Count"]
                    st.bar_chart(building_counts.set_index("Building"))
    else:
        st.info("👆 Select filter options above and click 'Apply Calendar Filters' to view future PM data.")

def ensure_required_metrics(metrics):
    """Ensure all required fields exist in the metrics dictionary"""
    # Basic metrics
    metrics.setdefault("completion_rate", 0)
    metrics.setdefault("completed_pms", 0)
    metrics.setdefault("total_pms", 0)
    metrics.setdefault("overdue_pms", 0)
    metrics.setdefault("avg_completion_days", 0)
    
    # Status counts
    if "status_counts" not in metrics or not metrics["status_counts"]:
        metrics["status_counts"] = {
            "open": 0,
            "assigned": 0,
            "in progress": 0,
            "complete": 0,
            "pm follow-up": 0
        }
    
    # Monthly trend
    if "monthly_trend" not in metrics or not metrics["monthly_trend"]:
        metrics["monthly_trend"] = []
    
    # AI insights
    if "ai_insights" not in metrics:
        metrics["ai_insights"] = {
            "scheduling_recommendations": {
                "all": [],
                "this_week": [],
                "next_week": [],
                "later": []
            }
        }
    
    # Recent PMs
    if "recent_pms" not in metrics:
        metrics["recent_pms"] = []


def create_fallback_metrics():
    """Create fallback metrics data when the API call fails"""
    today = datetime.now()
    
    return {
        "completion_rate": 78.5,
        "completed_pms": 157,
        "total_pms": 200,
        "overdue_pms": 15,
        "avg_completion_days": 3.2,
        "status_counts": {
            "open": 28,
            "assigned": 15,
            "in progress": 10,
            "complete": 157,
            "pm follow-up": 5
        },
        "monthly_trend": [
            {"month": (today - timedelta(days=150)).strftime('%b %Y'), "scheduled": 180, "completed": 140},
            {"month": (today - timedelta(days=120)).strftime('%b %Y'), "scheduled": 190, "completed": 155},
            {"month": (today - timedelta(days=90)).strftime('%b %Y'), "scheduled": 175, "completed": 150},
            {"month": (today - timedelta(days=60)).strftime('%b %Y'), "scheduled": 195, "completed": 160},
            {"month": (today - timedelta(days=30)).strftime('%b %Y'), "scheduled": 200, "completed": 170},
            {"month": today.strftime('%b %Y'), "scheduled": 200, "completed": 157}
        ],
        "ai_insights": {
            "scheduling_recommendations": {
                "all": [],
                "this_week": [],
                "next_week": [],
                "later": []
            }
        },
        "recent_pms": [
            {
                "work_order": "WO-20001",
                "status": "complete",
                "building_name": "City Hall",
                "scheduled_start_date": (today - timedelta(days=5)).strftime('%Y-%m-%d'),
                "date_completed": today.strftime('%Y-%m-%d'),
                "equipment": "HVAC-AHU-01"
            },
            {
                "work_order": "WO-20002",
                "status": "in progress",
                "building_name": "Municipal Building",
                "scheduled_start_date": today.strftime('%Y-%m-%d'),
                "date_completed": None,
                "equipment": "ELEV-01"
            },
            {
                "work_order": "WO-20003",
                "status": "open",
                "building_name": "Fire Station #5",
                "scheduled_start_date": (today + timedelta(days=3)).strftime('%Y-%m-%d'),
                "date_completed": None,
                "equipment": "GENR-01"
            }
        ]
    }


def show_pm_data_upload():
    """
    Display the PM Data Upload page (admin only)
    """
    # Get user email from session state
    user_email = st.session_state.get("email", "").lower()
    
    # Check if user is admin before showing the page
    if user_email != "admin@calgary.ca":
        st.error("⛔ Access Denied: You don't have permission to access this page.")
        st.info("This feature is only available to administrators.")
        if st.button("← Return to Dashboard"):
            st.session_state["current_page"] = "main"
            st.rerun()
    else:
        # Add back button
        col1, col2 = st.columns([1, 5])
        with col1:
            if st.button("< Back", use_container_width=True):
                st.session_state["current_page"] = "main"
                st.rerun()
        with col2:
            st.title("Upload PM Data")
            
        # PM data upload functionality
        st.info("Upload preventive maintenance data in CSV or Excel format.")
        
        uploaded_file = st.file_uploader("Upload PM Data File", type=["xlsx", "xls", "csv"], key="pm_upload")
        if uploaded_file is not None:
            try:
                with st.spinner("Reading file..."):
                    if uploaded_file.name.endswith(".csv"):
                        df = pd.read_csv(uploaded_file)
                    else:
                        df = pd.read_excel(uploaded_file)
                    
                    # Clean column names - convert to lowercase and replace spaces with underscores
                    df.columns = [col.lower().replace(' ', '_').replace('.', '').replace('__', '_') for col in df.columns]
                    
                    # Define expected columns for PM data
                    expected_columns = [
                        'work_order', 'wo_type', 'status', 'equipment', 'building_name', 'building_id',
                        'description', 'assigned_to', 'trade', 'zone', 'organization', 'scheduled_start_date',
                        'date_completed', 'pm_code', 'last_updated_by', 'service_category', 'service_code',
                        'date_created', 'region', 'priority'
                    ]
                    
                    # Rename columns to match database schema exactly
                    column_mapping = {
                        'priority_icon': 'priority',
                        'sched_start_date': 'scheduled_start_date',
                        'start_date': 'scheduled_start_date',
                        'completion_date': 'date_completed',
                        'created_date': 'date_created',
                        'complete_date': 'date_completed'
                    }
                    
                    # Apply the mapping to rename columns that need it
                    for old_name, new_name in column_mapping.items():
                        if old_name in df.columns and new_name not in df.columns:
                            df = df.rename(columns={old_name: new_name})
                            st.info(f"Renamed '{old_name}' column to '{new_name}' to match database schema.")
                    
                    # Show a warning for any expected columns that are still missing
                    missing_columns = [col for col in expected_columns if col not in df.columns]
                    if missing_columns:
                        st.warning(f"Missing columns that may be required by the database: {', '.join(missing_columns)}")
                    
                    # Show preview
                    st.write("Data Preview:")
                    st.dataframe(df.head())
                    
                    # Calculate statistics
                    num_rows = len(df)
                    num_cols = len(df.columns)
                    
                    st.info(f"File contains {num_rows} rows and {num_cols} columns.")
                    
                    # Process button
                    if st.button("Process and Upload PM Data", key="process_pm_btn", use_container_width=True):
                        try:
                            with st.spinner("Processing and uploading PM data..."):
                                import os
                                from backend.utils.pm_work_order_upload_supabase import upload_pm_data_to_supabase
                                
                                # Save the dataframe to a temporary Excel file
                                temp_file = "temp_pm_data.xlsx"
                                df.to_excel(temp_file, index=False)
                                
                                # Create a progress bar
                                progress_bar = st.progress(0)
                                
                                # Define progress callback function to update Streamlit progress bar
                                def update_progress(progress_value):
                                    progress_bar.progress(progress_value)
                                
                                try:
                                    # Call the backend function with progress callback
                                    summary = upload_pm_data_to_supabase(temp_file, update_progress)
                                    
                                    # Show success message using the summary returned by the function
                                    if summary["processed_records"] > 0:
                                        st.success(f"""✅ PM data upload complete! 
                                        - {summary["inserted_records"]} new records inserted
                                        - {summary["updated_records"]} existing records updated
                                        - {summary["processed_records"]} total records processed""")
                                        
                                        # Add details about the upload for verification
                                        st.info(f"""
                                        **Upload Summary:**
                                        - Total records: {summary["total_records"]}
                                        - Records inserted: {summary["inserted_records"]}
                                        - Records updated: {summary["updated_records"]}
                                        - Processing time: {summary["timestamp"]}
                                    
                                        """)
                                    else:
                                        st.error("No records were successfully processed.")
                                        st.warning("""
                                        This could be due to database issues. Possible solutions:
                                        1. Check if your data columns match the table columns
                                        2. Make sure your user has insert and update permissions
                                        3. Contact your database administrator
                                        """)
                                
                                except Exception as e:
                                    st.error(f"❌ Error during upload process: {str(e)}")
                                    
                                    # Show detailed error info in an expander
                                    with st.expander("Technical Error Details"):
                                        st.code(str(e))
                                        import traceback
                                        st.code(traceback.format_exc())
                                
                                finally:
                                    # Clean up the temporary file
                                    if os.path.exists(temp_file):
                                        os.remove(temp_file)
                        except Exception as e:
                            st.error(f"❌ Error uploading data: {str(e)}")
                            st.write("Please check the data format and structure. Contact support if the issue persists.")
                            
            except Exception as e:
                st.error(f"❌ Error reading file: {str(e)}")
                st.write("Please make sure the file is in the correct format.")