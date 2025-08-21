import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from io import BytesIO
import json

from backend.utils.pm_wo_retrieval import get_distinct_organizations

def organize_pm_data_in_tabs(metrics):
    tabs = st.tabs(["📊 Dashboard", "📅 Future PMs", "🔍 Data Explorer"])
    dashboard_tab = tabs[0]
    future_tab = tabs[1]
    explorer_tab = tabs[2]

    with dashboard_tab:
        st.header("Preventive Maintenance Dashboard")
        display_status_distribution(metrics)
        display_key_metrics(metrics)
        display_recent_pms(metrics)

    with future_tab:
        st.header("Future Preventive Maintenance")
        overview_tab, building_tab, type_tab, calendar_tab, planner_tab = st.tabs([
            "Overview", "By Building", "By Type", "Calendar", "Planner"
        ])
        with overview_tab:
            display_scheduling_recommendations(metrics)
        with building_tab:
            display_pm_by_building(metrics)
        with type_tab:
            display_pm_by_type(metrics)
        with calendar_tab:
            display_pm_calendar_view(metrics)
        with planner_tab:
            display_pm_schedule_planner(metrics)

    with explorer_tab:
        st.header("PM Data Explorer")
        display_pm_data_explorer(metrics)

def display_key_metrics(metrics):
    completion_rate = metrics.get("completion_rate", 0)
    overdue_count = metrics.get("overdue_count", 0)
    avg_completion_time = metrics.get("avg_completion_time", 0)
    total_pms = 0
    completed_pms = 0

    if "pm_data" in metrics:
        total_pms = len(metrics["pm_data"])
        if "status_counts" in metrics:
            completed_pms = metrics["status_counts"].get("complete", 0)
            if not overdue_count and "open" in metrics["status_counts"]:
                overdue_count = metrics["status_counts"]["open"]

    completion_percentage = (completed_pms / total_pms * 100) if total_pms > 0 else 0

    st.markdown("### Key Performance Metrics")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            "Completion Rate",
            f"{completion_percentage:.1f}%",
            delta=None,
            help="Percentage of PMs completed out of total scheduled"
        )
        st.caption(f"{completed_pms} of {total_pms} PMs")
    with col2:
        st.metric(
            "Overdue PMs",
            f"{overdue_count}",
            delta=None,
            delta_color="inverse",
            help="Number of PMs that are past their due date"
        )
        st.caption("Requires attention")
    with col3:
        st.metric(
            "Avg. Completion Time",
            f"{avg_completion_time}",
            delta=None,
            help="Average days to complete a PM"
        )
        st.caption("Days to complete")

    st.markdown("### PM Trends")
    if "monthly_data" in metrics:
        try:
            monthly_df = pd.DataFrame(metrics["monthly_data"])
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=monthly_df["month"],
                y=monthly_df["scheduled"],
                name="Scheduled PMs",
                marker_color='#90caf9'
            ))
            fig.add_trace(go.Bar(
                x=monthly_df["month"],
                y=monthly_df["completed"],
                name="Completed PMs",
                marker_color='#81c784'
            ))
            monthly_df["completion_pct"] = (monthly_df["completed"] / monthly_df["scheduled"] * 100).round(1)
            fig.add_trace(go.Scatter(
                x=monthly_df["month"],
                y=monthly_df["completion_pct"],
                name="Completion %",
                mode="lines+markers",
                yaxis="y2",
                line=dict(color='#f44336', width=3),
                marker=dict(size=8)
            ))
            fig.update_layout(
                title="Monthly Scheduled vs. Completed PMs",
                xaxis=dict(title="Month"),
                yaxis=dict(title="Number of PMs"),
                yaxis2=dict(
                    title="Completion %",
                    overlaying="y",
                    side="right",
                    showgrid=False,
                    range=[0, 100]
                ),
                legend=dict(x=0.01, y=0.99),
                barmode="group",
                height=350
            )
            st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.warning(f"Could not display trend chart: {str(e)}")
    else:
        st.markdown("#### Completion Percentage")
        months = ["2025-01", "2025-02", "2025-03", "2025-04", "2025-05", "2025-06", "2025-07"]
        completion = [0, 0, 0, 0, 0, 0, 0]
        completion_df = pd.DataFrame({"Month": months, "Completion %": completion})
        st.dataframe(
            completion_df,
            column_config={
                "Month": "Month",
                "Completion %": st.column_config.ProgressColumn(
                    "Completion %",
                    format="%d%%",
                    min_value=0,
                    max_value=100
                )
            },
            hide_index=True
        )

def get_status_color(status):
    status_colors = {
        "closed": "#4CAF50",
        "work complete": "#4CAF50",
        "waiting on invoice": "#8BC34A",
        "assigned": "#2196F3",
        "open": "#03A9F4",
        "pm follow-up": "#FF9800",
        "cancelled": "#9E9E9E",
        "no resources": "#673AB7",
        "waiting for po": "#FFC107",
        "waiting for parts": "#FFC107",
        "suppress": "#9C27B0",
        "due today": "#FF9800",
        "past_due": "#F44336",
        "due_today": "#FF9800",
        "upcoming": "#01070C"
    }
    if status:
        status_lower = status.lower()
        if status_lower in status_colors:
            return status_colors[status_lower]
    return "#01070C"

def display_pm_by_building(metrics):
    if "ai_insights" not in metrics or "scheduling_recommendations" not in metrics["ai_insights"]:
        st.info("No building-specific PM data available.")
        return
    sched_recs = metrics["ai_insights"]["scheduling_recommendations"]
    if not sched_recs or "all" not in sched_recs or not sched_recs["all"]:
        st.info("No upcoming PMs to schedule by building.")
        return
    st.subheader("📍 PMs by Building")
    try:
        all_pms = pd.DataFrame(sched_recs["all"])
        buildings = all_pms["building"].unique().tolist()
        building_counts = all_pms.groupby("building").size().reset_index(name="count")
        building_counts = building_counts.sort_values("count", ascending=False)
        fig = px.bar(
            building_counts,
            y="building",
            x="count",
            orientation="h",
            labels={"building": "Building", "count": "Number of PMs"},
            title="Number of Upcoming PMs by Building",
            color="count",
            color_continuous_scale="Viridis",
        )
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)
        if len(buildings) > 0:
            col1, col2 = st.columns([3, 1])
            with col1:
                selected_building = st.selectbox(
                    "Select a building to view details:",
                    options=building_counts["building"].tolist()
                )
            with col2:
                st.metric("PMs Count", len(all_pms[all_pms["building"] == selected_building]))
            building_pms = all_pms[all_pms["building"] == selected_building]
            building_pms = building_pms.sort_values("days_until_due")
            st.markdown(f"### {selected_building}")
            col1, col2, col3 = st.columns(3)
            urgent_count = len(building_pms[building_pms["days_until_due"] <= 2])
            upcoming_count = len(building_pms[(building_pms["days_until_due"] > 2) & (building_pms["days_until_due"] <= 7)])
            later_count = len(building_pms[building_pms["days_until_due"] > 7])
            with col1:
                st.markdown(f"<div style='background-color:#ffcdd2;padding:10px;border-radius:5px;text-align:center;'><h3>🔴<br>{urgent_count}</h3><p>Urgent (0-2 days)</p></div>", unsafe_allow_html=True)
            with col2:
                st.markdown(f"<div style='background-color:#fff9c4;padding:10px;border-radius:5px;text-align:center;'><h3>🟡<br>{upcoming_count}</h3><p>This Week (3-7 days)</p></div>", unsafe_allow_html=True)
            with col3:
                st.markdown(f"<div style='background-color:#c8e6c9;padding:10px;border-radius:5px;text-align:center;'><h3>🟢<br>{later_count}</h3><p>Later (8+ days)</p></div>", unsafe_allow_html=True)
            st.dataframe(
                building_pms[["equipment", "scheduled_date", "days_until_due"]],
                column_config={
                    "equipment": "Equipment",
                    "scheduled_date": "Scheduled Date",
                    "days_until_due": st.column_config.NumberColumn(
                        "Days Until Due",
                        format="%d",
                        help="Number of days until the PM is due"
                    )
                },
                use_container_width=True,
                hide_index=True
            )
    except Exception as e:
        st.error(f"Error displaying PMs by building: {str(e)}")

def display_pm_by_type(metrics):
    if "ai_insights" not in metrics or "scheduling_recommendations" not in metrics["ai_insights"]:
        st.info("No PM type data available.")
        return
    sched_recs = metrics["ai_insights"]["scheduling_recommendations"]
    if not sched_recs or "all" not in sched_recs or not sched_recs["all"]:
        st.info("No upcoming PMs to schedule by type.")
        return
    st.subheader("🔧 PMs by Type")
    try:
        all_pms = pd.DataFrame(sched_recs["all"])
        if "equipment" in all_pms.columns:
            all_pms["pm_type"] = all_pms["equipment"].apply(
                lambda x: x.split("-")[1] if isinstance(x, str) and len(x.split("-")) > 1 else "OTHER"
            )
        else:
            all_pms["pm_type"] = "UNKNOWN"
        pm_type_counts = all_pms.groupby("pm_type").size().reset_index(name="count")
        pm_type_counts = pm_type_counts.sort_values("count", ascending=False)
        col1, col2 = st.columns([2, 1])
        with col1:
            fig = px.pie(
                pm_type_counts,
                values="count",
                names="pm_type",
                title="Distribution of PM Types",
                hole=0.4
            )
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.markdown("### PM Counts by Type")
            for _, row in pm_type_counts.iterrows():
                pm_type = row["pm_type"]
                count = row["count"]
                st.markdown(f"""
                <div style="padding:8px;margin-bottom:5px;background-color:#f0f2f6;border-radius:5px;">
                    <span style="font-weight:bold;">{pm_type}</span>
                    <span style="float:right;">{count}</span>
                </div>
                """, unsafe_allow_html=True)
        selected_type = st.selectbox(
            "Select a PM type to view details:",
            options=pm_type_counts["pm_type"].tolist()
        )
        type_pms = all_pms[all_pms["pm_type"] == selected_type]
        type_pms = type_pms.sort_values("days_until_due")
        st.markdown(f"### {selected_type} PMs")
        st.metric("Total PMs", len(type_pms))
        urgency_tabs = st.tabs(["All", "Urgent (0-2 days)", "This Week (3-7 days)", "Later (8+ days)"])
        with urgency_tabs[0]:
            if not type_pms.empty:
                st.dataframe(
                    type_pms[["building", "equipment", "scheduled_date", "days_until_due"]],
                    column_config={
                        "building": "Building",
                        "equipment": "Equipment",
                        "scheduled_date": "Scheduled Date",
                        "days_until_due": st.column_config.NumberColumn(
                            "Days Until Due",
                            format="%d",
                            help="Number of days until the PM is due"
                        )
                    },
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info(f"No {selected_type} PMs found.")
        with urgency_tabs[1]:
            urgent_pms = type_pms[type_pms["days_until_due"] <= 2]
            if not urgent_pms.empty:
                st.dataframe(
                    urgent_pms[["building", "equipment", "scheduled_date", "days_until_due"]],
                    column_config={
                        "building": "Building",
                        "equipment": "Equipment",
                        "scheduled_date": "Scheduled Date",
                        "days_until_due": st.column_config.NumberColumn(
                            "Days Until Due",
                            format="%d",
                            help="Number of days until the PM is due"
                        )
                    },
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info(f"No urgent {selected_type} PMs (due within 2 days).")
        with urgency_tabs[2]:
            upcoming_pms = type_pms[(type_pms["days_until_due"] > 2) & (type_pms["days_until_due"] <= 7)]
            if not upcoming_pms.empty:
                st.dataframe(
                    upcoming_pms[["building", "equipment", "scheduled_date", "days_until_due"]],
                    column_config={
                        "building": "Building",
                        "equipment": "Equipment",
                        "scheduled_date": "Scheduled Date",
                        "days_until_due": st.column_config.NumberColumn(
                            "Days Until Due",
                            format="%d",
                            help="Number of days until the PM is due"
                        )
                    },
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info(f"No {selected_type} PMs due this week (3-7 days).")
        with urgency_tabs[3]:
            later_pms = type_pms[type_pms["days_until_due"] > 7]
            if not later_pms.empty:
                st.dataframe(
                    later_pms[["building", "equipment", "scheduled_date", "days_until_due"]],
                    column_config={
                        "building": "Building",
                        "equipment": "Equipment",
                        "scheduled_date": "Scheduled Date",
                        "days_until_due": st.column_config.NumberColumn(
                            "Days Until Due",
                            format="%d",
                            help="Number of days until the PM is due"
                        )
                    },
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info(f"No {selected_type} PMs due later (8+ days).")
    except Exception as e:
        st.error(f"Error displaying PMs by type: {str(e)}")

def display_recent_pms(metrics):
    if "recent_pms" not in metrics or not metrics["recent_pms"]:
        if "pm_data" in metrics and metrics["pm_data"]:
            recent_pms = metrics["pm_data"][:10]
        else:
            st.info("No recent PM data available.")
            return
    else:
        recent_pms = metrics["recent_pms"]
    st.subheader("Recent PM Work Orders")
    try:
        recent_df = pd.DataFrame(recent_pms)
        date_cols = ['scheduled_start_date', 'date_completed', 'date_created']
        for col in date_cols:
            if col in recent_df.columns:
                recent_df[col] = pd.to_datetime(recent_df[col]).dt.strftime('%Y-%m-%d')
        if 'status' in recent_df.columns:
            def get_status_indicator(status):
                status = str(status).lower()
                if 'complete' in status:
                    return "✅ " + status
                elif 'progress' in status:
                    return "🔄 " + status
                elif 'schedule' in status:
                    return "📅 " + status
                elif 'overdue' in status:
                    return "⚠️ " + status
                else:
                    return status
            recent_df['status_display'] = recent_df['status'].apply(get_status_indicator)
        else:
            recent_df['status_display'] = "Unknown"
        display_cols = ['work_order', 'status_display', 'building_name', 'scheduled_start_date', 'equipment']
        display_cols = [col for col in display_cols if col in recent_df.columns]
        column_config = {
            'work_order': 'Work Order',
            'status_display': 'Status',
            'building_name': 'Building',
            'scheduled_start_date': 'Scheduled Date',
            'equipment': 'Equipment'
        }
        st.dataframe(
            recent_df[display_cols],
            use_container_width=True,
            column_config={col: column_config.get(col, col) for col in display_cols},
            hide_index=True
        )
        st.markdown("View all PM records →")
    except Exception as e:
        st.error(f"Error displaying recent PMs: {str(e)}")

def display_pm_data_explorer(metrics):
    if "pm_data" not in metrics or not metrics["pm_data"]:
        st.info("No detailed PM data available for exploration.")
        return
    try:
        pm_df = pd.DataFrame(metrics["pm_data"])
        date_cols = ['scheduled_start_date', 'date_completed', 'date_created']
        for col in date_cols:
            if col in pm_df.columns:
                pm_df[col] = pd.to_datetime(pm_df[col])
        st.markdown("### Filter PM Data")
        col1, col2, col3 = st.columns(3)
        statuses = ["All"] + sorted(pm_df["status"].unique().tolist()) if "status" in pm_df.columns else ["All"]
        buildings = ["All"] + sorted(pm_df["building_name"].unique().tolist()) if "building_name" in pm_df.columns else ["All"]
        organizations = ["All", "FM", "PK", "FI", "RC", "CP"]
        with col1:
            filter_status = st.selectbox("Status:", statuses)
        with col2:
            filter_building = st.selectbox("Building:", buildings)
        with col3:  # Add a new column for the organization filter
            filter_organization = st.selectbox("Organization:", organizations)

        filtered_df = pm_df.copy()
        if filter_status != "All" and "status" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["status"] == filter_status]
        if filter_building != "All" and "building_name" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["building_name"] == filter_building]
        if filter_organization != "All" and "organization" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["organization"] == filter_organization]
        col1, col2 = st.columns(2)
        with col1:
            min_date = pm_df["scheduled_start_date"].min() if "scheduled_start_date" in pm_df.columns else datetime.now() - timedelta(days=30)
            max_date = pm_df["scheduled_start_date"].max() if "scheduled_start_date" in pm_df.columns else datetime.now() + timedelta(days=30)
            start_date = st.date_input("From:", min_date, key="explorer_start")
        with col2:
            end_date = st.date_input("To:", max_date, key="explorer_end")
        if "scheduled_start_date" in filtered_df.columns:
            filtered_df = filtered_df[
                (filtered_df["scheduled_start_date"].dt.date >= start_date) & 
                (filtered_df["scheduled_start_date"].dt.date <= end_date)
            ]
        for col in date_cols:
            if col in filtered_df.columns:
                filtered_df[col] = filtered_df[col].dt.strftime('%Y-%m-%d')
        st.markdown(f"### Showing {len(filtered_df)} PM Records")
        display_cols = [
            'work_order', 'status', 'building_name', 'scheduled_start_date', 
            'date_completed', 'equipment', 'description'
        ]
        display_cols = [col for col in display_cols if col in filtered_df.columns]
        st.dataframe(
            filtered_df[display_cols],
            use_container_width=True,
            column_config={
                'work_order': st.column_config.TextColumn('Work Order'),
                'status': st.column_config.TextColumn('Status'),
                'building_name': st.column_config.TextColumn('Building'),
                'scheduled_start_date': st.column_config.TextColumn('Scheduled Date'),
                'date_completed': st.column_config.TextColumn('Completed Date'),
                'equipment': st.column_config.TextColumn('Equipment'),
                'description': st.column_config.TextColumn('Description')
            }
        )
        col1, col2 = st.columns(2)
        with col1:
            csv_data = filtered_df[display_cols].to_csv(index=False).encode('utf-8')
            st.download_button(
                "Download as CSV",
                csv_data,
                file_name=f"pm_data_export_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        with col2:
            try:
                excel_buffer = BytesIO()
                with pd.ExcelWriter(excel_buffer, engine="xlsxwriter") as writer:
                    filtered_df[display_cols].to_excel(writer, index=False, sheet_name="PM Data")
                excel_data = excel_buffer.getvalue()
                st.download_button(
                    "Download as Excel",
                    excel_data,
                    file_name=f"pm_data_export_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            except Exception as e:
                st.warning(f"Excel export not available: {str(e)}")
    except Exception as e:
        st.error(f"Error in data explorer: {str(e)}")

def display_scheduling_recommendations(metrics):
    if "ai_insights" not in metrics or "scheduling_recommendations" not in metrics["ai_insights"]:
        st.info("No scheduling recommendations available. Please check your data or filters.")
        return
    sched_recs = metrics["ai_insights"]["scheduling_recommendations"]
    if not sched_recs or "all" not in sched_recs or not sched_recs["all"]:
        st.info("No upcoming PMs to schedule in the selected timeframe.")
        return
    st.subheader("📅 Upcoming PMs Overview")
    this_week_count = len(sched_recs.get("this_week", []))
    next_week_count = len(sched_recs.get("next_week", []))
    later_count = len(sched_recs.get("later", []))
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("This Week", this_week_count, delta=None)
    with col2:
        st.metric("Next Week", next_week_count, delta=None)
    with col3:
        st.metric("Later", later_count, delta=None)
    tab1, tab2, tab3 = st.tabs(["This Week", "Next Week", "Later"])
    with tab1:
        if sched_recs.get("this_week"):
            for i, rec in enumerate(sched_recs["this_week"]):
                col1, col2 = st.columns([1, 3])
                with col1:
                    days = rec.get("days_until_due", 0)
                    if days <= 1:
                        st.markdown(f"<div style='background-color:#ffcdd2;padding:10px;border-radius:5px;text-align:center;'><h3>🔴<br>{days} day{'s' if days != 1 else ''}</h3></div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div style='background-color:#ffecb3;padding:10px;border-radius:5px;text-align:center;'><h3>🟠<br>{days} days</h3></div>", unsafe_allow_html=True)
                with col2:
                    st.markdown(f"""
                    **{rec['equipment']}**  
                    📍 {rec['building']}  
                    📅 Due: {rec.get('scheduled_date', 'Not specified')}
                    """)
                st.markdown("---")
        else:
            st.info("No PMs to schedule this week")
    with tab2:
        if sched_recs.get("next_week"):
            for rec in sched_recs["next_week"]:
                col1, col2 = st.columns([1, 3])
                with col1:
                    days = rec.get("days_until_due", 0)
                    st.markdown(f"<div style='background-color:#fff9c4;padding:10px;border-radius:5px;text-align:center;'><h3>🟡<br>{days} days</h3></div>", unsafe_allow_html=True)
                with col2:
                    st.markdown(f"""
                    **{rec['equipment']}**  
                    📍 {rec['building']}  
                    📅 Due: {rec.get('scheduled_date', 'Not specified')}
                    """)
                st.markdown("---")
        else:
            st.info("No PMs to schedule next week")
    with tab3:
        if sched_recs.get("later"):
            for rec in sched_recs["later"]:
                col1, col2 = st.columns([1, 3])
                with col1:
                    days = rec.get("days_until_due", 0)
                    st.markdown(f"<div style='background-color:#c8e6c9;padding:10px;border-radius:5px;text-align:center;'><h3>🟢<br>{days} days</h3></div>", unsafe_allow_html=True)
                with col2:
                    st.markdown(f"""
                    **{rec['equipment']}**  
                    📍 {rec['building']}  
                    📅 Due: {rec.get('scheduled_date', 'Not specified')}
                    """)
                st.markdown("---")
        else:
            st.info("No PMs to schedule beyond next week")

def display_pm_schedule_planner(metrics):
    if "ai_insights" not in metrics or "scheduling_recommendations" not in metrics["ai_insights"]:
        st.info("No PM scheduling data available for planning.")
        return
    sched_recs = metrics["ai_insights"]["scheduling_recommendations"]
    if not sched_recs or "all" not in sched_recs or not sched_recs["all"]:
        st.info("No upcoming PMs to schedule in the planner.")
        return
    st.subheader("📋 PM Scheduling Planner")
    st.markdown("Select PMs to add to your schedule")
    try:
        all_pms = pd.DataFrame(sched_recs["all"])
        buildings = all_pms["building"].unique().tolist()
        building_tabs = st.tabs(buildings)
        selected_pms = {}
        for i, building in enumerate(buildings):
            with building_tabs[i]:
                building_pms = all_pms[all_pms["building"] == building]
                building_pms = building_pms.sort_values("days_until_due")
                st.markdown(f"#### {len(building_pms)} PMs at {building}")
                with st.form(f"building_form_{i}"):
                    for _, rec in building_pms.iterrows():
                        pm_id = rec.get("pm_id", f"unknown_{i}")
                        due_days = rec.get("days_until_due", "?")
                        icon = "🔴" if due_days <= 2 else "🟠" if due_days <= 5 else "🟡"
                        selected_pms[pm_id] = st.checkbox(
                            f"{icon} {rec['equipment']} - Due in {due_days} days",
                            key=f"pm_{pm_id}"
                        )
                    submit = st.form_submit_button("Schedule Selected PMs", use_container_width=True)
                    if submit:
                        selected_ids = [pm_id for pm_id, selected in selected_pms.items() if selected]
                        if selected_ids:
                            st.success(f"Added {len(selected_ids)} PMs to your schedule")
                            st.markdown("#### PMs added to schedule:")
                            for pm_id in selected_ids:
                                for _, rec in building_pms.iterrows():
                                    if rec.get("pm_id") == pm_id:
                                        st.markdown(f"✅ {rec['equipment']}")
                        else:
                            st.warning("No PMs selected")
        st.markdown("### Download Schedule Report")
        csv_data = all_pms.to_csv(index=False).encode('utf-8')
        st.download_button(
            "Download PM Schedule as CSV",
            csv_data,
            file_name=f"pm_schedule_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    except Exception as e:
        st.error(f"Error in schedule planner: {str(e)}")

def display_pm_calendar_view(metrics, calendar_data=None):
    import json
    import streamlit.components.v1 as components
    from datetime import datetime, timedelta
    import pandas as pd
    import time

    cache_buster = int(time.time())
    st.write(f"<div style='display:none' id='cache-bust-{cache_buster}'></div>", unsafe_allow_html=True)
    if st.button("🔄 Refresh Calendar"):
        st.rerun()
    st.subheader("📆 PM Calendar View")

    # Prepare calendar_data if not provided
    if not calendar_data:
        calendar_data = {
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
        if "ai_insights" in metrics and "scheduling_recommendations" in metrics["ai_insights"]:
            sched_recs = metrics["ai_insights"]["scheduling_recommendations"]
            if sched_recs and "all" in sched_recs and sched_recs["all"]:
                today = datetime.now()
                for rec in sched_recs["all"]:
                    # --- Apply filters ---
                    org = rec.get("organization", "")
                    if organization != "All" and org != organization:
                        continue
                    rec_building = rec.get("building_name", "") or rec.get("building", "")
                    if building and building.lower() not in str(rec_building).lower():
                        continue
                    rec_status = rec.get("status", "")
                    if status != "All" and rec_status != status:
                        continue
                    rec_zone = rec.get("zone", "")
                    if zone != "All Zones" and rec_zone != zone:
                        continue
                    rec_region = rec.get("region", "")
                    if region != "All Regions" and rec_region != region:
                        continue
                    date_created = rec.get("date_created")
                    if not date_created:
                        continue
                    date_created_obj = pd.to_datetime(date_created)
                    if date_created_obj.date() < start_date or date_created_obj.date() > end_date:
                        continue
                    days_from_today = (date_created_obj - today).days
                    is_past_due = days_from_today < 0
                    is_today = days_from_today == 0
                    is_future = days_from_today > 0
                    detailed_status = rec.get("status", "")
                    if not detailed_status:
                        if is_past_due:
                            detailed_status = "past_due"
                        elif is_today:
                            detailed_status = "due_today"
                        else:
                            detailed_status = "upcoming"
                    color = get_status_color(detailed_status)
                    textColor = "#000000" if detailed_status.lower() in [
                        "waiting on invoice", "waiting for po", "waiting for parts", "open", "due today"
                    ] else "#FFFFFF"
                    equipment_display = rec.get('equipment', '')
                    desc = rec.get('description', '')

                    event = {
                        "id": str(rec.get("id", "")),
                        "title": f"{desc} @ {rec.get('building_name', 'Building')}",
                        "start": date_created,
                        "color": color,
                        "textColor": textColor,
                        "extendedProps": {
                            "status": detailed_status,
                            "building": rec.get("building_name", ""),
                            "equipment": equipment_display,
                            "work_order": rec.get("work_order_id", "") if rec.get("work_order_id") else "",
                            "description": desc,
                            "organization": org,
                            "zone": rec_zone,
                            "region": rec_region,
                            "days_from_today": days_from_today,
                            "is_past_due": is_past_due,
                            "is_today": is_today,
                            "is_future": is_future,
                            "is_completed": detailed_status.lower() in ["work complete", "closed"]
                        }
                    }
                    if is_past_due:
                        calendar_data["past_due"].append(event)
                    elif is_future or is_today:
                        calendar_data["future"].append(event)
                    calendar_data["events"].append(event)
                calendar_data["stats"] = {
                    "total": len(calendar_data["events"]),
                    "past_due": len(calendar_data["past_due"]),
                    "today": sum(1 for e in calendar_data["events"] if e["extendedProps"]["is_today"]),
                    "future": sum(1 for e in calendar_data["events"] if e["extendedProps"]["is_future"]),
                    "completed": sum(1 for e in calendar_data["events"] if e["extendedProps"]["is_completed"])
                }
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total PMs", calendar_data["stats"].get("total", 0))
    st.markdown("### Status Color Legend")
    status_colors = {
        "Assigned": get_status_color("assigned"),
        "Open": get_status_color("open"),
        "Cancelled": get_status_color("cancelled"),
        "Closed": get_status_color("closed"),
        "Waiting on Invoice": get_status_color("waiting on invoice"),
        "Work Complete": get_status_color("work complete"),
        "No Resources": get_status_color("no resources"),
        "PM Follow-up": get_status_color("pm follow-up"),
        "Upcoming": get_status_color("upcoming"),
    }
    legend_cols = st.columns(len(status_colors))
    for i, (status, color) in enumerate(status_colors.items()):
        with legend_cols[i]:
            st.markdown(f"""
            <div style="display:flex;align-items:center;">
                <div style="width:15px;height:15px;background-color:{color};margin-right:5px;"></div>
                <div>{status}</div>
            </div>
            """, unsafe_allow_html=True)
    events = calendar_data.get("events", [])
    if not events:
        st.info("No PM data available for calendar view. Try adjusting your filters or date range.")
        return
    def json_serializer(obj):
        if isinstance(obj, (datetime, timedelta)):
            return str(obj)
        elif hasattr(obj, '__dict__'):
            return {k: v for k, v in obj.__dict__.items() if not k.startswith('_')}
        elif isinstance(obj, bool):
            return bool(obj)
        elif isinstance(obj, (int, float)):
            return obj
        else:
            return str(obj)
    safe_events = []
    for event in events:
        safe_event = {}
        for k, v in event.items():
            if k == 'extendedProps':
                safe_event[k] = {}
                for prop_k, prop_v in event[k].items():
                    if isinstance(prop_v, bool):
                        safe_event[k][prop_k] = bool(prop_v)
                    elif isinstance(prop_v, (int, float)):
                        safe_event[k][prop_k] = prop_v
                    else:
                        safe_event[k][prop_k] = str(prop_v) if prop_v is not None else ""
            else:
                safe_event[k] = v
        safe_events.append(safe_event)
    events_json = json.dumps(safe_events, default=json_serializer)
    default_view = "dayGridMonth"
    # Try to get the user's selected start date from Streamlit session state
    initial_date = None
    try:
        if "future_filter_values" in st.session_state:
            initial_date = st.session_state["future_filter_values"].get("start_date")
        elif "dashboard_filter_values" in st.session_state:
            initial_date = st.session_state["dashboard_filter_values"].get("start_date")
        if initial_date:
            # Ensure it's in YYYY-MM-DD format
            from datetime import datetime
            initial_date = str(initial_date)
            # If it's a datetime/date object, convert to string
            if not isinstance(initial_date, str):
                initial_date = initial_date.strftime('%Y-%m-%d')
    except Exception:
        initial_date = None
    calendar_html = f"""
        <!DOCTYPE html>
        <html data-version="{cache_buster}">
        <head>
            <meta charset='utf-8' />
            <link href='https://cdn.jsdelivr.net/npm/fullcalendar@5.11.3/main.min.css?v={cache_buster}' rel='stylesheet' />
            <script src='https://cdn.jsdelivr.net/npm/fullcalendar@5.11.3/main.min.js?v={cache_buster}'></script>
            <style>
                body {{
                    font-family: Arial, Helvetica, sans-serif;
                    margin: 0;
                    padding: 0;
                }}
                #calendar {{
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 0px;
                    height: 650px;
                }}
                .fc-view-harness {{
                    height: 600px !important;
                    min-height: 600px !important;
                    overflow: auto !important;
                }}
                .fc-daygrid-body {{
                    height: auto !important;
                    overflow-y: scroll !important;
                }}
                .fc-daygrid-day-frame {{
                    height: auto !important;
                }}
                .fc-timegrid-body {{
                    overflow-y: auto !important;
                }}
                .fc-scroller-liquid-absolute {{
                    position: relative !important;
                    overflow: auto !important;
                }}
                .fc-event {{
                    cursor: pointer;
                    border-radius: 3px;
                    border: none;
                    padding: 2px 5px;
                    font-size: 12px;
                    margin-bottom: 2px;
                }}
                .fc-toolbar-title {{
                    font-size: 1.5em !important;
                    font-weight: bold;
                }}
                .event-tooltip {{
                    position: absolute;
                    z-index: 1000;
                    padding: 10px;
                    background-color: white;
                    border: 1px solid #ddd;
                    box-shadow: 0 0 10px rgba(0,0,0,0.1);
                    border-radius: 5px;
                    max-width: 300px;
                }}
                .fc-list-event-title a {{
                    font-weight: bold;
                }}
            </style>
    </head>
    <body>
        <div id='calendar'></div>
        <script>
        document.addEventListener('DOMContentLoaded', function() {{
            let events = [];
            try {{
                events = {events_json};
            }} catch (e) {{
                console.error('Error parsing events:', e);
            }}
            var calendarEl = document.getElementById('calendar');
            var tooltipInstance = null;
            var calendar = new FullCalendar.Calendar(calendarEl, {{
                initialView: '{default_view}',
                {f"initialDate: '{initial_date}'," if initial_date else ""}
                headerToolbar: {{
                    left: 'prev,next today',
                    center: 'title',
                    right: 'dayGridMonth,timeGridWeek,timeGridDay,listMonth'
                }},
                events: events,
                eventTimeFormat: {{
                    hour: 'numeric',
                    minute: '2-digit',
                    meridiem: 'short'
                }},
                height: 650,
                contentHeight: 'auto',
                scrollTime: '08:00:00',
                handleWindowResize: true,
                expandRows: false,
                dayMaxEvents: 5,
                stickyHeaderDates: true,
                eventDidMount: function(info) {{
                    info.el.addEventListener('mouseover', function() {{
                        if (tooltipInstance) {{
                            tooltipInstance.remove();
                            tooltipInstance = null;
                        }}
                        let tooltip = document.createElement('div');
                        tooltip.className = 'event-tooltip';
                        let props = info.event.extendedProps || {{}};
                        let tooltipContent = `<div style="font-weight:bold;margin-bottom:5px;font-size:14px;">${{info.event.title}}</div>`;
                        tooltipContent += `<div style="margin:3px 0"><b>Status:</b> ${{props.status || 'Not specified'}}</div>`;
                        tooltipContent += `<div style="margin:3px 0"><b>Building:</b> ${{props.building || 'Not specified'}}</div>`;
                        if (props.work_order) {{
                            tooltipContent += `<div style="margin:3px 0"><b>Work Order:</b> ${{props.work_order}}</div>`;
                        }}
                        if (props.description) {{
                            tooltipContent += `<hr style="margin:5px 0"><b>Description:</b><br>${{props.description}}`;
                        }}
                        tooltip.innerHTML = tooltipContent;
                        
                        // Add tooltip to body to calculate its dimensions
                        tooltip.style.visibility = 'hidden';
                        document.body.appendChild(tooltip);
                        
                        // Get dimensions
                        const tooltipHeight = tooltip.offsetHeight;
                        const tooltipWidth = tooltip.offsetWidth;
                        const rect = info.el.getBoundingClientRect();
                        const viewportHeight = window.innerHeight;
                        const viewportWidth = window.innerWidth;
                        
                        // Calculate positions
                        let top, left;
                        
                        // Check if tooltip would extend beyond bottom of viewport
                        if (rect.bottom + tooltipHeight + 10 > viewportHeight) {{
                            // Position above the event
                            top = rect.top + window.scrollY - tooltipHeight - 10;
                        }} else {{
                            // Position below the event
                            top = rect.bottom + window.scrollY + 10;
                        }}
                        
                        // Check horizontal positioning
                        if (rect.left + tooltipWidth > viewportWidth) {{
                            // Align with right edge of viewport
                            left = viewportWidth - tooltipWidth - 10;
                        }} else {{
                            // Align with left edge of event
                            left = rect.left + window.scrollX;
                        }}
                        
                        // Apply calculated position
                        tooltip.style.top = top + 'px';
                        tooltip.style.left = left + 'px';
                        tooltip.style.visibility = 'visible';
                        tooltip.style.zIndex = '9999'; // Ensure high z-index
                        
                        tooltipInstance = tooltip;
                    }});
                    info.el.addEventListener('mouseout', function() {{
                        if (tooltipInstance) {{
                            tooltipInstance.remove();
                            tooltipInstance = null;
                        }}
                    }});
                }}
            }});
            calendar.render();
        }});
        </script>
    </body>
    </html>
    """
    try:
        import streamlit.components.v1 as components
        components.html(calendar_html, height=700)
    except Exception as e:
        st.error(f"Error rendering calendar: {str(e)}")
    with st.expander("List View of Calendar Events", expanded=False):
        if events:
            events_df = pd.DataFrame([
                {
                    "Title": e["title"],
                    "Date": e["start"],
                    "Status": e["extendedProps"].get("status", ""),
                    "Building": e["extendedProps"].get("building", ""),
                    "Work Order": e["extendedProps"].get("work_order", "")
                } for e in events
            ])
            col1, col2 = st.columns(2)
            with col1:
                sort_by = st.selectbox("Sort by:", ["Date", "Building", "Status"])
            with col2:
                ascending = st.checkbox("Ascending", value=True)
            events_df = events_df.sort_values(sort_by, ascending=ascending)
            st.dataframe(events_df, use_container_width=True)
            csv_data = events_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "Download as CSV",
                csv_data,
                file_name=f"pm_events_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        else:
            st.info("No calendar events to display.")

def display_status_distribution(metrics):
    if "status_counts" not in metrics or not metrics["status_counts"]:
        return
    st.subheader("PM Status Distribution")
    try:
        status_df = pd.DataFrame({
            "Status": list(metrics["status_counts"].keys()),
            "Count": list(metrics["status_counts"].values())
        })
        status_df = status_df.sort_values("Count", ascending=False)
        if status_df["Count"].sum() > 0:
            status_df["Percentage"] = (status_df["Count"] / status_df["Count"].sum() * 100).round(1).astype(str) + "%"
        else:
            status_df["Percentage"] = "0.0%"
        col1, col2 = st.columns([2, 1])
        with col1:
            try:
                fig = px.pie(
                    status_df,
                    values='Count',
                    names='Status',
                    title='PM Status Distribution',
                    color_discrete_sequence=px.colors.qualitative.Pastel,
                    hole=0.3
                )
                fig.update_traces(textposition='inside', textinfo='percent+label')
                fig.update_layout(margin=dict(l=20, r=20, t=30, b=20), height=300)
                st.plotly_chart(fig, use_container_width=True)
            except ImportError:
                st.bar_chart(status_df.set_index("Status")["Count"])
        with col2:
            st.markdown("#### Status Breakdown")
            for _, row in status_df.iterrows():
                if row["Count"] > 0:
                    st.markdown(f"""
                    <div style="padding:8px;margin-bottom:5px;background-color:#f0f2f6;border-radius:5px;">
                        <span style="font-weight:bold;">{row['Status']}</span>
                        <span style="float:right;">{row['Count']} ({row['Percentage']})</span>
                    </div>
                    """, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Error displaying status distribution: {e}")