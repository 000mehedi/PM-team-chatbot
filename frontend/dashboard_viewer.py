import streamlit as st
import pandas as pd
import plotly.express as px
import re
import os
import json
from datetime import datetime, timedelta
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.utils.dashboard_generator import generate_daily_dashboard, get_latest_dashboard, generate_custom_dashboard
from backend.utils.supabase_client import supabase

def get_business_day_dashboard():
    today = datetime.now().date()
    weekday = today.weekday()
    if weekday == 0:
        business_day = today - timedelta(days=3)
    elif weekday == 6:
        business_day = today - timedelta(days=2)
    elif weekday == 5:
        business_day = today - timedelta(days=1)
    else:
        business_day = today - timedelta(days=1)
    os.environ["DASHBOARD_DATE"] = business_day.isoformat()
    try:
        dashboard = generate_daily_dashboard()
        if re.search(r"# Work Orders Dashboard - \d{4}-\d{2}-\d{2}", dashboard):
            dashboard = re.sub(
                r"# Work Orders Dashboard - \d{4}-\d{2}-\d{2}",
                f"# Work Orders Dashboard - {business_day.isoformat()}",
                dashboard
            )
        else:
            dashboard = dashboard.replace("# Work Orders Dashboard", f"# Work Orders Dashboard - {business_day.isoformat()}")
        return dashboard, business_day
    except Exception as e:
        st.error(f"Error in business day dashboard: {str(e)}")
        return generate_daily_dashboard(), today

@st.cache_data(ttl=3600)
def get_common_trades():
    try:
        query = supabase.table("work_orders_history") \
            .select("trade") \
            .not_.is_("trade", "null") \
            .execute()
        if query.data:
            trades = set()
            for row in query.data:
                if row.get("trade") and row["trade"].strip():
                    trades.add(row["trade"].strip())
            trades_list = sorted(list(trades))
            final_list = ["All Trades"] + trades_list
            return final_list
    except Exception as e:
        print(f"Error getting trade options: {str(e)}")
    return ["All Trades"]

@st.cache_data(ttl=3600)
def get_common_zones():
    try:
        query = supabase.table("work_orders_history") \
            .select("zone") \
            .not_.is_("zone", "null") \
            .execute()
        if query.data:
            zones = set()
            for row in query.data:
                if row.get("zone") and row["zone"].strip():
                    zones.add(row["zone"].strip())
            zones_list = sorted(list(zones))
            final_list = ["All Zones"] + zones_list
            return final_list
    except Exception as e:
        print(f"Error getting zone options: {str(e)}")
    return ["All Zones"]

def extract_chart_data(dashboard_content):
    try:
        match = re.search(r"## Chart Data\n\n```json\n(.*?)\n```", dashboard_content, re.DOTALL)
        if match:
            chart_data = json.loads(match.group(1))
            return chart_data
        return None
    except Exception as e:
        st.error(f"Error extracting chart data: {str(e)}")
        return None

def display_dashboard_page(generate_new=False):
    col1, col2 = st.columns([6, 1])
    with col1:
        st.title("Work Orders Dashboard")
    with col2:
        if st.button("Return to Chat"):
            st.session_state["current_page"] = "chat"
            st.rerun()

    st.markdown("### Dashboard Options")
    dashboard_action = st.radio(
        "Select action:",
        ["Daily Dashboard", "Custom Dashboard", "Load Latest"],
        horizontal=True,
        key="dashboard_action_main"
    )

    if dashboard_action == "Daily Dashboard":
        if st.button("Generate Daily Dashboard", key="generate_daily_dashboard_main"):
            with st.spinner("Generating new dashboard..."):
                try:
                    new_dashboard, business_day = get_business_day_dashboard()
                    st.session_state['current_dashboard'] = new_dashboard
                    st.success(f"New dashboard generated for {business_day.strftime('%Y-%m-%d')}!")
                except Exception as e:
                    st.error(f"Error: {str(e)}")

    elif dashboard_action == "Custom Dashboard":
        st.subheader("Custom Filters")
        date_type = st.radio(
            "Date selection:",
            ["Quick ranges", "Custom range"],
            key="date_type_main"
        )
        start_date = None
        end_date = None
        if date_type == "Quick ranges":
            date_option = st.radio(
                "Select range:",
                ["Last 7 days", "Last 30 days", "Current month", "Previous month", "Today", "Yesterday"],
                key="date_option_main"
            )
            today = datetime.now().date()
            if date_option == "Last 7 days":
                end_date = today
                start_date = end_date - timedelta(days=7)
            elif date_option == "Last 30 days":
                end_date = today
                start_date = end_date - timedelta(days=30)
            elif date_option == "Current month":
                start_date = datetime(today.year, today.month, 1).date()
                if today.month == 12:
                    end_date = datetime(today.year + 1, 1, 1).date()
                else:
                    end_date = datetime(today.year, today.month + 1, 1).date()
            elif date_option == "Previous month":
                if today.month == 1:
                    start_date = datetime(today.year - 1, 12, 1).date()
                else:
                    start_date = datetime(today.year, today.month - 1, 1).date()
                end_date = datetime(today.year, today.month, 1).date()
            elif date_option == "Today":
                start_date = today
                end_date = today + timedelta(days=1)
                st.info(f"This will show data for today ({today.strftime('%Y-%m-%d')}) only")
            else:
                yesterday = today - timedelta(days=1)
                start_date = yesterday
                end_date = today
                st.info(f"This will show data for yesterday ({yesterday.strftime('%Y-%m-%d')}) only")
        else:
            col1, col2 = st.columns(2)
            with col1:
                start_date = st.date_input("Start date (inclusive)", datetime.now().date() - timedelta(days=7), key="custom_start_date_main")
            with col2:
                end_date_display = st.date_input("End date (inclusive)", datetime.now().date(), key="custom_end_date_main")
            if start_date == end_date_display:
                end_date = start_date + timedelta(days=1)
                st.info(f"This will show data for {start_date.strftime('%Y-%m-%d')} only (from 00:00 to 23:59)")
            else:
                end_date = end_date_display + timedelta(days=1)
                st.info(f"This will show data from {start_date.strftime('%Y-%m-%d')} 00:00 to {end_date_display.strftime('%Y-%m-%d')} 23:59")

        building_name = st.text_input("Building name (optional)", key="building_name_main")
        filter_col1, filter_col2 = st.columns(2)
        with filter_col1:
            trade_options = get_common_trades()
            trade_filter = st.selectbox("Filter by trade", trade_options, key="trade_filter_main")
            trade = None if trade_filter == "All Trades" else trade_filter
        with filter_col2:
            zone_options = get_common_zones()
            zone_filter = st.selectbox("Filter by zone", zone_options, key="zone_filter_main")
            zone = None if zone_filter == "All Zones" else zone_filter

        # --- Description Keyword Filter ---
        description_keyword = st.text_input(
            "Keyword in work order description (optional)",
            key="description_keyword_main",
            help="Enter a keyword to filter work orders by their description. Example: hot tub"
        )

        if st.button("Generate Custom Dashboard", key="generate_custom_dashboard_main"):
            with st.spinner("Generating custom dashboard..."):
                try:
                    custom_dashboard = generate_custom_dashboard(
                        start_date=start_date.isoformat(),
                        end_date=end_date.isoformat(),
                        building_name=building_name if building_name else None,
                        trade=trade,
                        zone=zone,
                        description_keyword=description_keyword if description_keyword else None
                    )
                    st.session_state['current_dashboard'] = custom_dashboard
                    st.success("Custom dashboard generated!")
                except Exception as e:
                    st.error(f"Error: {str(e)}")

    else:
        if st.button("Load Latest Dashboard", key="load_latest_dashboard_main"):
            with st.spinner("Loading latest dashboard..."):
                latest = get_latest_dashboard()
                if latest:
                    st.session_state['current_dashboard'] = latest
                    st.success("Dashboard loaded!")
                else:
                    st.error("No saved dashboards found")

    # --- Main content area - display dashboard ---
    if 'current_dashboard' in st.session_state:
        dashboard_content = st.session_state['current_dashboard']

        title_match = re.search(r"# (.*?)\n", dashboard_content)
        if title_match:
            st.header(title_match.group(1))

        summary_match = re.search(r"## Summary Metrics\n\n(.*?)(?=##|\Z)", dashboard_content, re.DOTALL)
        if summary_match:
            st.subheader("Summary Metrics")
            summary_content = summary_match.group(1)

            total_wo_match = re.search(r"\*\*Total Work Orders:\*\* (\d+)", summary_content)
            new_wo_match = re.search(r"\*\*New Work Orders:\*\* (\d+)", summary_content)
            closed_wo_match = re.search(r"\*\*Closed Work Orders:\*\* (\d+)", summary_content)
            critical_wo_match = re.search(r"\*\*(?:New )?Critical Work Orders:\*\* (\d+)", summary_content)

            metric_cols = st.columns(4)
            if total_wo_match:
                with metric_cols[0]:
                    st.metric("Total Work Orders", total_wo_match.group(1))
            elif new_wo_match:
                with metric_cols[0]:
                    st.metric("New Work Orders", new_wo_match.group(1))
            if closed_wo_match:
                with metric_cols[1]:
                    st.metric("Closed Work Orders", closed_wo_match.group(1))
            if critical_wo_match:
                with metric_cols[2]:
                    st.metric("Critical Work Orders", critical_wo_match.group(1))

            st.write("---")

            with st.expander("Status Breakdown", expanded=True):
                status_match = re.search(r"\*\*Status Breakdown:\*\* \{(.*?)\}", summary_content)
                if status_match:
                    status_str = status_match.group(1)
                    status_pairs = status_str.split(", ")
                    status_data = []
                    for pair in status_pairs:
                        if ': ' in pair:
                            key, value = pair.split(': ')
                            key = key.strip("'")
                            value = int(value)
                            status_data.append({"Status": key, "Count": value})
                    if status_data:
                        status_df = pd.DataFrame(status_data)
                        status_df = status_df.sort_values("Count", ascending=False)
                        fig = px.bar(
                            status_df,
                            x="Status",
                            y="Count",
                            text="Count",
                            color="Status",
                            color_discrete_sequence=px.colors.qualitative.Pastel1
                        )
                        fig.update_layout(
                            height=400,
                            xaxis_title=None,
                            yaxis_title="Number of Work Orders"
                        )
                        fig.update_traces(textposition='outside')
                        st.plotly_chart(fig, use_container_width=True)

            with st.expander("Priority Breakdown", expanded=True):
                priority_match = re.search(r"\*\*Priority Breakdown:\*\* \{(.*?)\}", summary_content)
                if priority_match:
                    priority_str = priority_match.group(1)
                    priority_pairs = priority_str.split(", ")
                    priority_data = []
                    for pair in priority_pairs:
                        if ': ' in pair:
                            key, value = pair.split(': ')
                            key = key.strip("'")
                            value = int(value)
                            priority_num = 5
                            if key.startswith('0'):
                                priority_num = 0
                            elif key.startswith('1'):
                                priority_num = 1
                            elif key.startswith('2'):
                                priority_num = 2
                            elif key.startswith('3'):
                                priority_num = 3
                            elif key.startswith('4'):
                                priority_num = 4
                            display_name = key
                            if '@' in key:
                                display_name = key.split('@')[0].strip()
                            priority_data.append({
                                "Priority": display_name,
                                "Count": value,
                                "Sort": priority_num,
                                "Full": key
                            })
                    if priority_data:
                        priority_df = pd.DataFrame(priority_data)
                        priority_df = priority_df.sort_values("Sort")
                        colors = {
                            0: "#FF0000",
                            1: "#FF4500",
                            2: "#FFA500",
                            3: "#FFFF00",
                            4: "#00BFFF",
                            5: "#808080"
                        }
                        fig = px.bar(
                            priority_df,
                            x="Priority",
                            y="Count",
                            text="Count",
                            color="Sort",
                            color_discrete_map=colors,
                            custom_data=["Full"]
                        )
                        fig.update_layout(
                            height=400,
                            xaxis_title=None,
                            yaxis_title="Number of Work Orders",
                            coloraxis_showscale=False,
                            showlegend=False
                        )
                        fig.update_traces(
                            hovertemplate="<b>%{x}</b><br>Count: %{y}<br>Full: %{customdata[0]}",
                            textposition='outside'
                        )
                        st.plotly_chart(fig, use_container_width=True)

            other_metrics = re.sub(r"\*\*(?:Total|New) Work Orders:\*\*.*?\n", "", summary_content)
            other_metrics = re.sub(r"\*\*Closed Work Orders:\*\*.*?\n", "", other_metrics)
            other_metrics = re.sub(r"\*\*(?:New )?Critical Work Orders:\*\*.*?\n", "", other_metrics)
            other_metrics = re.sub(r"\*\*Status Breakdown:\*\*.*?\n", "", other_metrics)
            other_metrics = re.sub(r"\*\*Priority Breakdown:\*\*.*?\n", "", other_metrics)
            if other_metrics.strip():
                st.markdown(other_metrics)
            st.write("---")

        st.subheader("Charts")
        chart_data = extract_chart_data(dashboard_content)
        if chart_data and "charts" in chart_data:
            if "total_records" in chart_data and "sample_size" in chart_data:
                total_records = chart_data["total_records"]
                sample_size = chart_data["sample_size"]
                if total_records > sample_size:
                    st.warning(f"⚠️ Charts represent a sample of {sample_size} records out of {total_records} total records.")
            tabs = []
            chart_types = []
            if "priority" in chart_data["charts"]:
                tabs.append("Priority")
                chart_types.append("priority")
            if "trade" in chart_data["charts"]:
                tabs.append("Trade")
                chart_types.append("trade")
            if "building" in chart_data["charts"]:
                tabs.append("Building")
                chart_types.append("building")
            if "status" in chart_data["charts"]:
                tabs.append("Status")
                chart_types.append("status")
            if tabs:
                tab_objects = st.tabs(tabs)
                for i, tab in enumerate(tab_objects):
                    chart_type = chart_types[i]
                    chart_info = chart_data["charts"][chart_type]
                    with tab:
                        if chart_type == "priority":
                            df = pd.DataFrame(chart_info["data"])
                            fig = px.pie(
                                df,
                                values='count',
                                names='priority',
                                title=chart_info["title"],
                                color_discrete_sequence=px.colors.qualitative.Plotly
                            )
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            df = pd.DataFrame(chart_info["data"])
                            field_name = "trade" if chart_type == "trade" else "building_name" if chart_type == "building" else "status"
                            fig = px.bar(
                                df,
                                x=field_name,
                                y='count',
                                title=chart_info["title"],
                                color='count',
                                color_continuous_scale='Viridis'
                            )
                            if chart_type == "building":
                                fig.update_layout(xaxis_title='Building', yaxis_title='Number of Work Orders')
                                fig.update_xaxes(tickangle=45)
                            else:
                                fig.update_layout(xaxis_title=field_name.capitalize(), yaxis_title='Number of Work Orders')
                            st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No chart data available in the dashboard.")
        else:
            st.warning("Chart data not found in dashboard. Generating charts from database...")
            date_match = re.search(r"Dashboard - (\d{4}-\d{2}-\d{2})", dashboard_content)
            custom_match = re.search(r"Date range: (\d{4}-\d{2}-\d{2}) to (\d{4}-\d{2}-\d{2})", dashboard_content)
            if date_match:
                yesterday = date_match.group(1)
                today = (datetime.strptime(yesterday, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
                data_query = supabase.table("work_orders_history") \
                    .select("*") \
                    .gte("date_created", yesterday) \
                    .lt("date_created", today) \
                    .execute()
                df = pd.DataFrame(data_query.data) if data_query.data else pd.DataFrame()
            elif custom_match:
                start_date = custom_match.group(1)
                end_date = custom_match.group(2)
                data_query = supabase.table("work_orders_history") \
                    .select("*") \
                    .gte("date_created", start_date) \
                    .lt("date_created", end_date) \
                    .limit(1000) \
                    .execute()
                df = pd.DataFrame(data_query.data) if data_query.data else pd.DataFrame()
                if len(df) == 1000:
                    st.warning("⚠️ Showing charts for a sample of 1000 records. Generate a new dashboard for more accurate charts.")
            else:
                st.error("Could not determine dashboard date range. Please generate a new dashboard.")
                df = pd.DataFrame()
            if not df.empty:
                tabs = st.tabs(["Priority", "Trade", "Building", "Status"])
                with tabs[0]:
                    if 'priority' in df.columns:
                        priority_counts = df.groupby('priority').size().reset_index(name='count')
                        fig = px.pie(
                            priority_counts,
                            values='count',
                            names='priority',
                            title="Work Orders by Priority",
                            color_discrete_sequence=px.colors.qualitative.Plotly
                        )
                        st.plotly_chart(fig, use_container_width=True)
                with tabs[1]:
                    if 'trade' in df.columns:
                        trade_counts = df.groupby('trade').size().reset_index(name='count')
                        trade_counts = trade_counts.sort_values('count', ascending=False).head(10)
                        fig = px.bar(
                            trade_counts,
                            x='trade',
                            y='count',
                            title="Top 10 Trades with Work Orders",
                            color='count',
                            color_continuous_scale='Viridis'
                        )
                        fig.update_layout(xaxis_title='Trade', yaxis_title='Number of Work Orders')
                        st.plotly_chart(fig, use_container_width=True)
                with tabs[2]:
                    if 'building_name' in df.columns:
                        building_counts = df.groupby('building_name').size().reset_index(name='count')
                        building_counts = building_counts.sort_values('count', ascending=False).head(10)
                        fig = px.bar(
                            building_counts,
                            x='building_name',
                            y='count',
                            title="Top 10 Buildings with Work Orders",
                            color='count',
                            color_continuous_scale='Viridis'
                        )
                        fig.update_layout(xaxis_title='Building', yaxis_title='Number of Work Orders')
                        fig.update_xaxes(tickangle=45)
                        st.plotly_chart(fig, use_container_width=True)
                with tabs[3]:
                    if 'status' in df.columns:
                        status_counts = df.groupby('status').size().reset_index(name='count')
                        fig = px.bar(
                            status_counts,
                            x='status',
                            y='count',
                            title="Work Orders by Status",
                            color='count',
                            color_continuous_scale='Viridis'
                        )
                        fig.update_layout(xaxis_title='Status', yaxis_title='Number of Work Orders')
                        st.plotly_chart(fig, use_container_width=True)
            else:
                st.error("Could not retrieve work order data for the dashboard date range.")

        insights_match = re.search(r"## AI Insights\n\n(.*?)(?=##|\Z)", dashboard_content, re.DOTALL)
        if insights_match:
            st.subheader("AI Insights")
            st.markdown(insights_match.group(1))

        topics_match = re.search(r"## Common Work Order Topics\n\n([\s\S]*?)(?=\n##|\Z)", dashboard_content)
        if topics_match:
            st.subheader("Common Work Order Topics")
            topics_content = topics_match.group(1).strip()
            st.markdown(topics_content)

        critical_match = re.search(r"## (?:Recent )?Critical Work Orders.*?\n\n(.*?)(?=##|\Z)", dashboard_content, re.DOTALL)
        if critical_match:
            st.subheader("Critical Work Orders")
            critical_content = critical_match.group(1).strip()
            if "No critical" in critical_content or "*No critical" in critical_content:
                st.info("No critical work orders found for the selected time period.")
            else:
                st.markdown(critical_content)
                date_match = re.search(r"Dashboard - (\d{4}-\d{2}-\d{2})", dashboard_content)
                if date_match:
                    yesterday = date_match.group(1)
                    today = (datetime.strptime(yesterday, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
                    critical_query = supabase.table("work_orders_history") \
                        .select("*") \
                        .ilike("priority", "%critical%") \
                        .gte("date_created", yesterday) \
                        .lt("date_created", today) \
                        .order("date_created", desc=True) \
                        .limit(100) \
                        .execute()
                    critical_wo_df = pd.DataFrame(critical_query.data) if critical_query.data else pd.DataFrame()
                    if not critical_wo_df.empty:
                        st.subheader("Critical Work Orders (from database)")
                        display_cols = ["work_order", "building_name", "description", "status"]
                        display_df = critical_wo_df[display_cols] if all(col in critical_wo_df.columns for col in display_cols) else critical_wo_df
                        st.dataframe(display_df, use_container_width=True)
                custom_match = re.search(r"Date range: (\d{4}-\d{2}-\d{2}) to (\d{4}-\d{2}-\d{2})", dashboard_content)
                if custom_match and not date_match:
                    start_date = custom_match.group(1)
                    end_date = custom_match.group(2)
                    building_filter = None
                    trade_filter = None
                    zone_filter = None
                    building_match = re.search(r"Building: ([^|]+)", dashboard_content)
                    if building_match:
                        building_filter = building_match.group(1).strip()
                    trade_match = re.search(r"Trade: ([^|]+?)(?:\||$)", dashboard_content)
                    if trade_match:
                        trade_filter = trade_match.group(1).strip()
                    zone_match = re.search(r"Zone: ([^|]+?)(?:\||$)", dashboard_content)
                    if zone_match:
                        zone_filter = zone_match.group(1).strip()
                    critical_query = supabase.table("work_orders_history") \
                        .select("*") \
                        .ilike("priority", "%critical%") \
                        .gte("date_created", start_date) \
                        .lt("date_created", end_date)
                    if building_filter:
                        critical_query = critical_query.ilike("building_name", f"%{building_filter}%")
                    if trade_filter:
                        critical_query = critical_query.eq("trade", trade_filter)
                    if zone_filter:
                        critical_query = critical_query.eq("zone", zone_filter)
                    critical_result = critical_query.order("date_created", desc=True).limit(100).execute()
                    critical_wo_df = pd.DataFrame(critical_result.data) if critical_result.data else pd.DataFrame()
                    if not critical_wo_df.empty:
                        st.subheader("Critical Work Orders (from database)")
                        display_cols = ["work_order", "building_name", "description", "status", "date_created"]
                        display_df = critical_wo_df[display_cols] if all(col in critical_wo_df.columns for col in display_cols) else critical_wo_df
                        st.dataframe(display_df, use_container_width=True)
    else:
        with st.spinner("Generating initial dashboard..."):
            try:
                dashboard_content, business_day = get_business_day_dashboard()
                st.session_state['current_dashboard'] = dashboard_content
                st.success(f"Dashboard generated for {business_day.strftime('%Y-%m-%d')}!")
                st.rerun()
            except Exception as e:
                st.error(f"Error generating dashboard: {str(e)}")
                st.info("Please use the dashboard options above to generate a dashboard.")