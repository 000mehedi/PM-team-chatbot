import streamlit as st
import pandas as pd
from io import BytesIO, StringIO
import sys, os
from datetime import datetime, timedelta
import numpy as np
import json

# Import custom modules and styles
from styles import inject_styles
from auth import auth_sidebar
from sidebar import chat_sessions_sidebar, full_sidebar
from chat import chat_interface, load_dictionary_corpus
from sidebar_sections import show_faqs, show_definitions, show_forms_and_docs, show_user_feedback, show_session_analytics, show_dictionary_lookup, show_dashboard
from manual_lookup import show_manual_lookup
from frontend.dashboard_viewer import display_dashboard_page
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from admin_upload import show_admin_upload
from backend.utils.pm_wo_retrieval import get_pm_data, get_pm_metrics
from backend.utils.pm_work_order_upload_supabase import upload_pm_data_to_supabase
from pm_schedule_viewer import display_scheduling_recommendations, display_pm_schedule_planner, display_pm_calendar_view, display_status_distribution
from pm_schedule_viewer import organize_pm_data_in_tabs

from pm_data_page import show_pm_data_page, show_pm_data_upload
# Initialize session state for page navigation
if "current_page" not in st.session_state:
    st.session_state["current_page"] = "main"

if "generate_new_dashboard" not in st.session_state:
    st.session_state["generate_new_dashboard"] = False

# Initialize session state for date selectors
if "date_preset" not in st.session_state:
    st.session_state["date_preset"] = None

# --------------------
# Backend and Static Data Setup
# --------------------
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.utils.db import save_uploaded_file, load_uploaded_file, load_faqs
links = pd.read_csv("backend/data/links.csv")
faqs_df = load_faqs()
faqs_context = ""
if faqs_df is not None and not faqs_df.empty:
    faqs_context = "\n".join(
        f"Q: {row['question']}\nA: {row['answer']}"
        for _, row in faqs_df.iterrows()
    )

# Load the dictionary corpus from Supabase
dictionary_corpus = load_dictionary_corpus()

# Apply styles
inject_styles()

# Render the authentication sidebar
with st.sidebar:
    auth_sidebar()
    
    # Only show navigation if authenticated
    if st.session_state.get("token") and st.session_state.get("user_id"):
        # Choose which sidebar to show based on the current page
        if st.session_state.get("current_page") == "chat":
            chat_sessions_sidebar()
        else:
            # Use the new structured sidebar
            full_sidebar()

# --------------------
# Main App Body
# --------------------
if st.session_state.get("token") and st.session_state.get("user_id"):
    user_id = st.session_state["user_id"]
    user_name = st.session_state.get("name", "User")
    user_email = st.session_state.get("email", "").lower()
    
    # Check current page and display appropriate content
    current_page = st.session_state.get("current_page", "main")
    
    if current_page == "dashboard":
        # Add back button
        col1, col2 = st.columns([1, 5])
        with col1:
            if st.button("< Back", use_container_width=True):
                st.session_state["current_page"] = "main"
                st.rerun()
        with col2:
            st.title("Preventive Maintenance Dashboard")
            
        # Display the dashboard page
        generate_new = st.session_state.get("generate_new_dashboard", False)
        display_dashboard_page(generate_new=generate_new)
        # Reset the flag after use
        st.session_state["generate_new_dashboard"] = False
        
    elif current_page == "chat":
        # Add back button
        col1, col2 = st.columns([1, 5])
        with col1:
            if st.button("< Back", use_container_width=True):
                st.session_state["current_page"] = "main"
                st.rerun()
        with col2:
            st.title("🤖 Preventive Maintenance Support Chatbot")
            
        st.markdown("Ask questions or explore preventive maintenance resources.")

        selected_session = st.session_state.get("selected_session")
        if selected_session is None:
            st.warning("Please create or select a chat session to start chatting.")
        else:
            df = None
            uploaded_file = st.file_uploader("📂 Upload a data file", type=["xlsx", "xls", "csv"])
            if uploaded_file is not None:
                try:
                    with st.spinner("Reading uploaded file..."):
                        bytes_data = uploaded_file.read()
                        save_uploaded_file(selected_session, uploaded_file.name, bytes_data, user_id=user_id)
                        if uploaded_file.name.endswith(".csv"):
                            df = pd.read_csv(BytesIO(bytes_data))
                        else:
                            df = pd.read_excel(BytesIO(bytes_data))
                        st.session_state.uploaded_df = df
                        st.success("✅ File uploaded and saved for this session.")
                        st.dataframe(df.head())
                except Exception as e:
                    st.error(f"❌ Error reading file: {e}")
            else:
                if "uploaded_df" not in st.session_state or st.session_state.uploaded_df is None:
                    with st.spinner("Loading previous session data..."):
                        df_from_db = load_uploaded_file(selected_session, user_id=user_id)
                        if df_from_db is not None:
                            st.session_state.uploaded_df = df_from_db
                            st.info("📁 Loaded previously uploaded file for this session.")
                            st.dataframe(df_from_db.head())
                        else:
                            st.session_state.uploaded_df = None
                            st.info("ℹ️ No uploaded file found. Please upload a file to start.")
            chat_interface(
                st.session_state.get("uploaded_df"),
                faqs_context=faqs_context,
                faqs_df=faqs_df,
                dictionary_corpus=dictionary_corpus
            )
            
    elif current_page == "faqs":
        # Add back button
        col1, col2 = st.columns([1, 5])
        with col1:
            if st.button("< Back", use_container_width=True):
                st.session_state["current_page"] = "main"
                st.rerun()
        with col2:
            st.title("Preventive Maintenance FAQs")
            
        show_faqs()
        
    elif current_page == "dictionary":
        # Add back button
        col1, col2 = st.columns([1, 5])
        with col1:
            if st.button("< Back", use_container_width=True):
                st.session_state["current_page"] = "main"
                st.rerun()
        with col2:
            st.title("PM Dictionary")
        
        show_dictionary_lookup()
            
    elif current_page == "forms":
        # Add back button
        col1, col2 = st.columns([1, 5])
        with col1:
            if st.button("< Back", use_container_width=True):
                st.session_state["current_page"] = "main"
                st.rerun()
        with col2:
            st.title("Forms & Documents")
            
        show_forms_and_docs(links)
        
    elif current_page == "manual_lookup":
        # Add back button
        col1, col2 = st.columns([1, 5])
        with col1:
            if st.button("< Back", use_container_width=True):
                st.session_state["current_page"] = "main"
                st.rerun()
        with col2:
            st.title("Manual Lookup")
            
        show_manual_lookup()
        
    elif current_page == "user_feedback":
        # Add back button
        col1, col2 = st.columns([1, 5])
        with col1:
            if st.button("< Back", use_container_width=True):
                st.session_state["current_page"] = "main"
                st.rerun()
        with col2:
            st.title("User Feedback")
            
        show_user_feedback()
        
    elif current_page == "analytics":
        # Add back button
        col1, col2 = st.columns([1, 5])
        with col1:
            if st.button("< Back", use_container_width=True):
                st.session_state["current_page"] = "main"
                st.rerun()
        with col2:
            st.title("Session Analytics")
            
        show_session_analytics()
        
    elif current_page == "dictionary_lookup":
        # Add back button
        col1, col2 = st.columns([1, 5])
        with col1:
            if st.button("< Back", use_container_width=True):
                st.session_state["current_page"] = "main"
                st.rerun()
        with col2:
            st.title("Dictionary Lookup")
            
        show_dictionary_lookup()
        
    elif current_page == "dictionary_upload":
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
                st.title("Upload Dictionary")
                
            show_admin_upload()
        
    # New pages for the sidebar structure
    elif current_page == "process_maps":
        # Add back button
        col1, col2 = st.columns([1, 5])
        with col1:
            if st.button("< Back", use_container_width=True):
                st.session_state["current_page"] = "main"
                st.rerun()
        with col2:
            st.title("PM Process Maps")
            
        st.info("Preventive maintenance process maps and workflows.")
        
        st.markdown("""
        ### Available Process Maps
        
        * Work Order Management Process
        * Preventative Maintenance Workflow
        * Emergency Response Procedure
        * Service Request Handling
        * Asset Inspection Checklist
        * Contractor Management Process
        """)
        
        st.warning("This section is under development. Process maps will be interactive in future updates.")
        
    elif current_page == "maintenance_records":
        # Add back button
        col1, col2 = st.columns([1, 5])
        with col1:
            if st.button("< Back", use_container_width=True):
                st.session_state["current_page"] = "main"
                st.rerun()
        with col2:
            st.title("Maintenance Records")

        st.info("Search and view maintenance record history.")

        # --- Functional search interface ---
        search_query = st.text_input("Search maintenance records:", placeholder="Enter building name, asset ID, or work order #")
        search_button = st.button("Search Records")

        # Import your backend function for retrieving maintenance records
        from backend.utils.pm_wo_retrieval import get_pm_data

        # Only search if user clicks button or enters a query
        records = []
        if search_button and search_query.strip():
            # Try to interpret the query as a work order number, asset ID, or building name
            # You can expand this logic as needed
            if search_query.strip().isdigit():
                # If it's all digits, treat as work order number
                records = get_pm_data(work_order=search_query.strip())
            else:
                # Otherwise, search by building name or asset/equipment
                records = get_pm_data(building=search_query.strip())
        else:
            # Show recent records by default (limit to 20)
            records = get_pm_data(limit=20)

        # Display results
        if isinstance(records, pd.DataFrame):
            if not records.empty:
                st.markdown("### Maintenance Records")
                st.dataframe(records)
            else:
                st.info("No maintenance records found for your search.")
        elif isinstance(records, list):
            if len(records) > 0:
                df_records = pd.DataFrame(records)
                st.markdown("### Maintenance Records")
                st.dataframe(df_records)
            else:
                st.info("No maintenance records found for your search.")
        else:
            st.info("No maintenance records found for your search.")
            
        st.markdown("### Recent Maintenance Records")
        st.write("This section will display recent maintenance records from the database.")
        
    elif current_page == "work_orders":
        # Add back button
        col1, col2 = st.columns([1, 5])
        with col1:
            if st.button("< Back", use_container_width=True):
                st.session_state["current_page"] = "main"
                st.rerun()
        with col2:
            st.title("Work Order Data")
            
        st.info("View and analyze work order information.")
        
        # Date range filter
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start Date:", datetime.now() - timedelta(days=30))
        with col2:
            end_date = st.date_input("End Date:", datetime.now())
            
        # Additional filters
        col1, col2, col3 = st.columns(3)
        with col1:
            status_filter = st.selectbox("Status:", ["All", "Open", "Closed", "In Progress"])
        with col2:
            priority_filter = st.selectbox("Priority:", ["All", "Critical", "High", "Medium", "Low"])
        with col3:
            building_filter = st.text_input("Building:", placeholder="Enter building name")
            
        if st.button("Apply Filters"):
            st.info("Filtering work orders...")
            st.warning("Work order filtering functionality is under development.")
            
        st.markdown("### Work Order Summary")
        st.write("This section will display filtered work orders from the database.")
    
    # Updated PM Data page with a more intuitive interface
    elif current_page == "pm_data":
        show_pm_data_page()

    # Updated PM Data Upload page
    elif current_page == "pm_data_upload":
        show_pm_data_upload()

    elif current_page == "equipment_data":
        # Add back button
        col1, col2 = st.columns([1, 5])
        with col1:
            if st.button("< Back", use_container_width=True):
                st.session_state["current_page"] = "main"
                st.rerun()
        with col2:
            st.title("Equipment Data")
            
        st.info("Access equipment inventory and specifications.")
        
        # Equipment search
        search_query = st.text_input("Search equipment:", placeholder="Enter equipment ID, name, or location")
        col1, col2 = st.columns(2)
        with col1:
            equipment_type = st.selectbox("Equipment Type:", ["All Types", "HVAC", "Plumbing", "Electrical", "Safety Systems", "Building Envelope"])
        with col2:
            location = st.text_input("Location:", placeholder="Building or zone")
            
        if st.button("Search Equipment"):
            st.info(f"Searching for equipment matching: '{search_query}'")
            st.warning("Equipment search functionality is under development.")
            
        st.markdown("### Equipment Inventory")
        st.write("This section will display equipment inventory from the database.")
        
    elif current_page == "regulations":
        # Add back button
        col1, col2 = st.columns([1, 5])
        with col1:
            if st.button("< Back", use_container_width=True):
                st.session_state["current_page"] = "main"
                st.rerun()
        with col2:
            st.title("Regulations & Governance")
            
        st.info("Access regulations and governance documents.")
        
        regulations = [
            "Preventive Maintenance Standard Operating Procedures",
            "City of Calgary Facilities Management Guidelines", 
            "Project Management Framework",
            "Asset Management Policies"
        ]
        
        selected_reg = st.selectbox("Select document to view:", regulations)
        
        st.markdown(f"## {selected_reg}")
        st.write("This section will display the selected regulation document.")
        st.warning("Document content functionality is under development.")
        
    elif current_page == "codes":
        # Add back button
        col1, col2 = st.columns([1, 5])
        with col1:
            if st.button("< Back", use_container_width=True):
                st.session_state["current_page"] = "main"
                st.rerun()
        with col2:
            st.title("Codes & Bylaws")
            
        st.info("Access building codes and bylaw information.")
        
        codes = [
            "Alberta Building Code",
            "City of Calgary Land Use Bylaw",
            "Fire Safety Codes",
            "Accessibility Standards",
            "Environmental Regulations"
        ]
        
        selected_code = st.selectbox("Select code/bylaw to view:", codes)
        
        st.markdown(f"## {selected_code}")
        st.write("This section will display the selected code or bylaw.")
        st.warning("Document content functionality is under development.")
        
    elif current_page == "best_practices":
        # Add back button
        col1, col2 = st.columns([1, 5])
        with col1:
            if st.button("< Back", use_container_width=True):
                st.session_state["current_page"] = "main"
                st.rerun()
        with col2:
            st.title("PM Best Practices")
            
        st.info("Access preventive maintenance best practice guides and standards.")
        
        practices = [
            "Preventative Maintenance Guidelines",
            "Emergency Response Procedures",
            "Energy Management Best Practices",
            "Sustainability Initiatives",
            "Vendor Management Procedures"
        ]
        
        selected_practice = st.selectbox("Select best practice to view:", practices)
        
        st.markdown(f"## {selected_practice}")
        st.write("This section will display the selected best practice guide.")
        st.warning("Document content functionality is under development.")
        
    elif current_page == "work_order_upload":
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
                st.title("Upload Work Orders")
                
            # Improved work order upload functionality
            st.info("Upload work order data in CSV or Excel format.")
            
            uploaded_file = st.file_uploader("Upload Work Order File", type=["xlsx", "xls", "csv"])
            if uploaded_file is not None:
                try:
                    with st.spinner("Reading file..."):
                        if uploaded_file.name.endswith(".csv"):
                            df = pd.read_csv(uploaded_file)
                        else:
                            df = pd.read_excel(uploaded_file)
                        
                        # Clean column names - convert to lowercase and replace spaces with underscores
                        df.columns = [col.lower().replace(' ', '_').replace('.', '').replace('__', '_') for col in df.columns]
                        
                        # Define expected columns based on the work_orders_history schema
                        expected_columns = [
                            'work_order', 'wo_type', 'status', 'equipment', 'building_name', 'building_id',
                            'description', 'assigned_to', 'trade', 'zone', 'organization', 'scheduled_start_date',
                            'date_completed', 'pm_code', 'last_updated_by', 'service_category', 'service_code',
                            'date_created', 'region', 'priority'
                        ]
                        
                        # Rename columns to match database schema exactly
                        column_mapping = {
                            'sched_start_date': 'scheduled_start_date',  # Fix sched_start_date to match schema
                            'start_date': 'scheduled_start_date',        # Also handle possible start_date variation
                            'completion_date': 'date_completed',         # Handle any possible date_completed variation  
                            'created_date': 'date_created',              # Handle any possible date_created variation
                            'complete_date': 'date_completed'            # Another possible variation
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
                        
                        # Handle the priority_icon to priority translation
                        if 'priority_icon' in df.columns:
                            if 'priority' in df.columns:
                                # If both exist, use priority and drop priority_icon
                                df = df.drop(columns=['priority_icon'])
                                st.info("Found both 'priority' and 'priority_icon' columns. Using 'priority' column.")
                            else:
                                # Rename priority_icon to priority
                                df = df.rename(columns={'priority_icon': 'priority'})
                                st.info("Renamed 'priority_icon' column to 'priority' for database compatibility.")
                        
                        # Check for duplicates in the work_order column
                        if 'work_order' in df.columns:
                            duplicate_mask = df.duplicated('work_order', keep=False)
                            duplicate_count = duplicate_mask.sum()
                            
                            if duplicate_count > 0:
                                st.warning(f"Found {duplicate_count} duplicate work order numbers in your upload file.")
                                duplicate_wo = df[duplicate_mask]['work_order'].unique()
                                
                                with st.expander(f"View {len(duplicate_wo)} duplicate work order numbers"):
                                    st.write(", ".join(str(wo) for wo in duplicate_wo[:20]))
                                    if len(duplicate_wo) > 20:
                                        st.write(f"... and {len(duplicate_wo) - 20} more")
                                
                                # Keep only the last instance of each duplicate work order
                                st.info("Removing duplicates by keeping the most recent entry for each work order...")
                                df = df.drop_duplicates('work_order', keep='last')
                                st.success(f"Removed {duplicate_count - len(duplicate_wo)} duplicate entries.")
                        
                        # Show preview
                        st.write("Data Preview:")
                        st.dataframe(df.head())
                        
                        # Calculate statistics
                        num_rows = len(df)
                        num_cols = len(df.columns)
                        
                        st.info(f"File contains {num_rows} rows and {num_cols} columns.")
                        
                        # Process button with actual database upload
                        if st.button("Process and Upload Data", use_container_width=True):
                            try:
                                with st.spinner("Processing data and uploading to database, this may take a moment..."):
                                    # Import the backend utility function to handle the upload
                                    from backend.utils.work_order_upload_supabase import upload_work_orders_to_supabase
                                    
                                    # Save the dataframe to a temporary Excel file
                                    temp_file = "temp_work_orders.xlsx"
                                    df.to_excel(temp_file, index=False)
                                    
                                    # Create a progress bar
                                    progress_bar = st.progress(0)
                                    
                                    # Define progress callback function to update Streamlit progress bar
                                    def update_progress(progress_value):
                                        progress_bar.progress(progress_value)
                                    
                                    try:
                                        # Call the backend function with progress callback
                                        summary = upload_work_orders_to_supabase(temp_file, update_progress)
                                        
                                        # Show success message using the summary returned by the function
                                        if summary["processed_records"] > 0:
                                            st.success(f"""✅ Work order processing complete! 
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
                                            - Target table: work_orders_history
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
                                
                                # More detailed error information for debugging
                                with st.expander("Technical Error Details"):
                                    st.code(str(e))
                                    import traceback
                                    st.code(traceback.format_exc())
                            
                except Exception as e:
                    st.error(f"❌ Error reading file: {str(e)}")
                    st.write("Please make sure the file is in the correct format.")
        
    else:
        # Default main page
        st.title("🤖 Preventive Maintenance Support System")
        st.markdown("Welcome to the Preventive Maintenance Support System. Use the sidebar navigation to access different features.")
        
        # Display quick access cards
        col1, col2 = st.columns(2)
        with col1:
            st.info("**Quick Links**")
            if st.button("💬 Start Chat", use_container_width=True):
                st.session_state["current_page"] = "chat"
                st.rerun()
                
            if st.button("📊 View Dashboard", use_container_width=True):
                st.session_state["current_page"] = "dashboard"
                st.rerun()
            
        with col2:
            st.info("**Resources**")
            if st.button("📚 Documentation", use_container_width=True):
                st.session_state["current_page"] = "faqs"
                st.rerun()
                
            if st.button("📝 Give Feedback", use_container_width=True):
                st.session_state["current_page"] = "user_feedback"
                st.rerun()
        
        # Show recent activity or announcements
        st.markdown("### Recent Activity")
        st.info("This section will display recent system activity and announcements.")
        
else:
    st.title("Welcome to Preventive Maintenance Support System")
    st.markdown("""
    ### Please log in to access the system
    
    This system provides:
    * AI-powered chat assistance for preventive maintenance queries
    * Work order and maintenance management
    * Documentation and reference materials
    * Data analysis and dashboards
    
    Use the login form in the sidebar to get started.
    """)
    
    # Add a simple image or logo
    st.image("https://via.placeholder.com/800x400?text=Preventive+Maintenance+Support+System", use_container_width=True)