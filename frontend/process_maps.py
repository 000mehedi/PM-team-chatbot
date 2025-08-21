import streamlit as st
from backend.utils.supabase_client import supabase
import pandas as pd
import base64
import io
import uuid

def process_maps_page():
    """Display process maps organized in dropdown categories with PDF viewers"""
    
    # Ensure table exists with correct columns
    create_or_update_table()
    
    # Page header
    col1, col2 = st.columns([1, 10])
    with col1:
        if st.button("←", help="Back to Dashboard", use_container_width=True):
            st.session_state["current_page"] = "main"
            st.rerun()
    with col2:
        st.title("Process Maps")
        
    st.info("Browse preventive maintenance process maps organized by category. Click any document to view or download.")

    # Add search bar at the top
    search_query = st.text_input("🔍 Search process maps", 
                                help="Search by title, category, or description")
    
    # Check if we need to show the admin upload interface
    user_email = st.session_state.get("email", "").lower()
    is_admin = (user_email == "admin@calgary.ca")
    
    # Add upload option for admins
    if is_admin:
        with st.expander("🔧 Admin: Upload Process Map", expanded=False):
            upload_process_map()
    
    # Fetch process maps from database
    maps_data = fetch_process_maps()
    
    if not maps_data:
        st.warning("No process maps available. Please check back later or contact your administrator.")
        return
    
    # Convert to DataFrame for easier filtering
    df = pd.DataFrame(maps_data)
    if 'category' not in df.columns:
        st.error("Process maps data is missing the 'category' field.")
        return
    
    # Filter based on search query if provided
    if search_query:
        # Convert everything to lowercase for case-insensitive search
        search_lower = search_query.lower()
        
        # Search in title, category, and description
        mask = df['title'].str.lower().str.contains(search_lower, na=False)
        mask |= df['category'].str.lower().str.contains(search_lower, na=False)
        
        # Only search description if it exists
        if 'description' in df.columns:
            # Handle None values with fillna
            mask |= df['description'].fillna('').str.lower().str.contains(search_lower, na=False)
        
        filtered_df = df[mask]
        
        # Show search results count
        if len(filtered_df) == 0:
            st.warning(f"No process maps found matching '{search_query}'")
            return
        else:
            st.success(f"Found {len(filtered_df)} process maps matching '{search_query}'")
            
        # Get categories from filtered results
        categories = sorted(filtered_df['category'].unique())
    else:
        # No search, use all data
        filtered_df = df
        categories = sorted(df['category'].unique())
    
    if len(categories) == 0:
        st.warning("No categories found in the process maps data.")
        return
    
    # Create a tab for each category
    tabs = st.tabs(categories)
    
    for i, category in enumerate(categories):
        with tabs[i]:
            category_maps = filtered_df[filtered_df['category'] == category]
            
            # Display process maps for this category
            for _, map_item in category_maps.iterrows():
                with st.expander(map_item['title'], expanded=False):
                    if map_item.get('description'):
                        st.write(map_item.get('description'))
                    
                    # Display PDF viewer
                    if 'pdf_data' in map_item and map_item['pdf_data']:
                        display_pdf_from_data(map_item['pdf_data'], map_item['title'])
                    elif 'file_url' in map_item and map_item['file_url']:
                        display_pdf_from_url(map_item['file_url'], map_item['title'])
                    else:
                        st.warning("No PDF file available for this document.")
def fetch_process_maps():
    """Fetch process maps from Supabase database"""
    try:
        response = supabase.table("process_maps").select("*").order('category').execute()
        return response.data
    except Exception as e:
        st.error(f"Error fetching process maps: {str(e)}")
        return []

def display_pdf_from_url(file_url, title):
    """Display a PDF file from URL - automatically shown when dropdown is opened"""
    
    # Display PDF immediately using an iframe
    pdf_display = f"""
    <iframe src="{file_url}" width="100%" height="600" type="application/pdf"></iframe>
    """
    st.markdown(pdf_display, unsafe_allow_html=True)
    
    # Download option below the PDF
    st.markdown(f"[📥 Download PDF]({file_url})", unsafe_allow_html=True)

def display_pdf_from_data(pdf_data, title):
    """Display a PDF file from base64 data - automatically shown when dropdown is opened"""
    
    # Display PDF immediately using an iframe
    pdf_display = f"""
    <iframe src="data:application/pdf;base64,{pdf_data}" width="100%" height="600" type="application/pdf"></iframe>
    """
    st.markdown(pdf_display, unsafe_allow_html=True)
    
    # Download link below the PDF
    href = f'<a href="data:application/pdf;base64,{pdf_data}" download="{title}.pdf">📥 Download PDF</a>'
    st.markdown(href, unsafe_allow_html=True)

def create_bucket_if_not_exists(bucket_name="pm_files"):
    """Create storage bucket if it doesn't exist"""
    try:
        # List available buckets
        buckets = supabase.storage.list_buckets()
        
        # Check if bucket exists
        if not any(b["name"] == bucket_name for b in buckets):
            # Create the bucket
            supabase.storage.create_bucket(bucket_name)
            return True
        return True
    except Exception as e:
        st.error(f"Error with storage bucket: {str(e)}")
        return False

def create_or_update_table():
    """Create or update the process_maps table with all required columns"""
    try:
        # First, check if the table exists by attempting a select
        try:
            supabase.table("process_maps").select("id").limit(1).execute()
        except Exception as e:
            if "relation \"process_maps\" does not exist" in str(e):
                # Table doesn't exist, create it via SQL
                sql = """
                CREATE TABLE IF NOT EXISTS public.process_maps (
                    id UUID PRIMARY KEY,
                    title TEXT NOT NULL,
                    category TEXT NOT NULL,
                    description TEXT,
                    file_url TEXT,
                    pdf_data TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
                """
                # Direct SQL execution via Supabase REST API
                # Using table().select() to force execution
                supabase.table("_dummy").select("*").execute()
                
                # Let the user know they need to create the table manually
                st.warning(
                    "The process_maps table doesn't exist. Please run this SQL in the Supabase SQL Editor: "
                    "```sql\nCREATE TABLE IF NOT EXISTS public.process_maps (\n"
                    "    id UUID PRIMARY KEY,\n"
                    "    title TEXT NOT NULL,\n"
                    "    category TEXT NOT NULL,\n"
                    "    description TEXT,\n"
                    "    file_url TEXT,\n"
                    "    pdf_data TEXT,\n"
                    "    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()\n"
                    ");\n```"
                )
    except Exception as e:
        st.error(f"Error checking/creating process_maps table: {str(e)}")

def upload_process_map():
    """Admin interface to upload new process maps"""
    
    # Form for uploading
    with st.form("upload_process_map_form"):
        title = st.text_input("Document Title")
        
        # Using text_input instead of selectbox for category
        category = st.text_input("Category", 
                               help="Enter a category like 'Work Order Management', 'Preventive Maintenance', etc.")
        
        description = st.text_area("Description", help="Optional: Add a description for this document")
        
        # Try to list storage buckets
        bucket_name = None
        try:
            buckets = supabase.storage.list_buckets()
            if buckets:
                bucket_names = [b["name"] for b in buckets]
                st.info(f"Available storage buckets: {', '.join(bucket_names)}")
                bucket_name = st.selectbox("Select storage bucket", bucket_names)
            else:
                st.warning("No storage buckets available. Will store file data directly in database.")
        except Exception as e:
            st.warning("Could not list storage buckets. Will store file data directly in database.")
        
        # File uploader that accepts PDFs
        uploaded_file = st.file_uploader("Upload PDF", type="pdf")
        
        submit_button = st.form_submit_button("Upload Process Map")
        
        if submit_button:
            if not title:
                st.error("Please enter a document title.")
                return
                
            if not category:
                st.error("Please enter a category.")
                return
                
            if not uploaded_file:
                st.error("Please upload a PDF file.")
                return
            
            try:
                with st.spinner("Uploading file..."):
                    # Create a unique ID for this document
                    doc_id = str(uuid.uuid4())
                    
                    file_url = None
                    pdf_data = None
                    
                    # Try to upload to storage if bucket is available
                    if bucket_name:
                        try:
                            file_path = f"process_maps/{category}/{uploaded_file.name}"
                            
                            # Upload to storage
                            result = supabase.storage.from_(bucket_name).upload(
                                file_path,
                                uploaded_file.getvalue()
                            )
                            
                            # Get public URL
                            file_url = supabase.storage.from_(bucket_name).get_public_url(file_path)
                            
                            st.success(f"File uploaded to storage bucket: {bucket_name}")
                        except Exception as storage_error:
                            st.warning(f"Storage upload failed: {str(storage_error)}. Storing file data in database instead.")
                            file_url = None
                    
                    # If storage upload failed or no bucket was selected, store the file data in the database
                    if not file_url:
                        pdf_bytes = uploaded_file.getvalue()
                        pdf_data = base64.b64encode(pdf_bytes).decode()
                        st.info("PDF data encoded and will be stored in database.")
                    
                    # Save metadata to database
                    insert_data = {
                        "id": doc_id,
                        "title": title,
                        "category": category,
                    }
                    
                    if description:
                        insert_data["description"] = description
                        
                    if file_url:
                        insert_data["file_url"] = file_url
                    
                    if pdf_data:
                        # Check if pdf_data column exists
                        try:
                            insert_data["pdf_data"] = pdf_data
                            result = supabase.table("process_maps").insert(insert_data).execute()
                            st.success(f"Process map '{title}' uploaded successfully!")
                            st.rerun()
                        except Exception as column_error:
                            if "column \"pdf_data\" of relation \"process_maps\" does not exist" in str(column_error):
                                st.error("The pdf_data column is missing from your table. Please run this SQL in the Supabase SQL Editor: ALTER TABLE process_maps ADD COLUMN pdf_data TEXT;")
                            else:
                                raise column_error
                    else:
                        # Just insert the record with the file URL
                        result = supabase.table("process_maps").insert(insert_data).execute()
                        st.success(f"Process map '{title}' uploaded successfully!")
                        st.rerun()
                
            except Exception as e:
                st.error(f"Error uploading file: {str(e)}")
                st.info("If you're seeing an error about missing columns, please run this SQL in your Supabase SQL Editor: ALTER TABLE process_maps ADD COLUMN IF NOT EXISTS pdf_data TEXT;")