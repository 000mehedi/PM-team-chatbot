import streamlit as st
import pandas as pd
from backend.utils.supabase_client import supabase
import numpy as np

def show_admin_upload():
    st.title("📤 Admin: Upload/Update Dictionary")

    uploaded_file = st.file_uploader("Upload the updated dictionary Excel file (.xlsx)", type=["xlsx"])

    if uploaded_file is not None:
        # Step 1: Read all sheets to extract PM names from B1 and scan for "Existing task in EAM" markers
        all_sheets = pd.read_excel(uploaded_file, sheet_name=None, header=None)
        pm_names = {}
        existing_task_markers = {}  # {sheet_name: [(row_index, eam_pm_name)]}
        
        for sheet_name, sheet_data in all_sheets.items():
            # Get PM name from B1
            if sheet_data.shape[0] >= 1 and sheet_data.shape[1] >= 2:
                pm_names[sheet_name] = sheet_data.iloc[0, 1]
            else:
                pm_names[sheet_name] = None
            
            # Scan for "Existing task in EAM" markers
            markers = []
            for i, row in sheet_data.iterrows():
                if pd.notnull(row.iloc[0]) and isinstance(row.iloc[0], str):
                    if "existing task in eam" in row.iloc[0].lower():
                        # Check if there's a PM name in the cell to the right
                        eam_pm_name = None
                        if sheet_data.shape[1] > 1 and pd.notnull(row.iloc[1]):
                            eam_pm_name = str(row.iloc[1])
                        markers.append((i, eam_pm_name))
            
            if markers:
                existing_task_markers[sheet_name] = markers
        
        # Process each sheet based on whether it has markers
        all_rows = []
        
        for sheet_name in all_sheets.keys():
            if sheet_name in existing_task_markers and existing_task_markers[sheet_name]:
                # Sheet has "Existing task in EAM" markers
                markers = existing_task_markers[sheet_name]
                
                # Process main section (before first marker)
                if markers[0][0] > 3:  # At least header + one row
                    main_df = pd.read_excel(uploaded_file, sheet_name=sheet_name, 
                                          header=2, nrows=markers[0][0]-3)
                    main_df["pm_code"] = sheet_name
                    main_df["pm_name"] = pm_names.get(sheet_name)
                    # Add blank eam_pm_name for current tasks
                    main_df["eam_pm_name"] = None
                    
                    # Process dataframe
                    main_df = process_dataframe(main_df)
                    if not main_df.empty:
                        all_rows.extend(main_df.to_dict(orient="records"))
                
                # Process each existing task section
                for i, marker_info in enumerate(markers):
                    marker_row, eam_pm_name = marker_info
                    
                    # Determine where this section ends
                    next_section = markers[i+1][0] if i < len(markers)-1 else None
                    
                    # Read this section's data - but inspect it first to check column structure
                    try:
                        # First, try to examine what's in the section without assuming structure
                        if next_section:
                            raw_data = pd.read_excel(uploaded_file, sheet_name=sheet_name, 
                                                  header=None, skiprows=marker_row+1, 
                                                  nrows=next_section-marker_row-1)
                        else:
                            raw_data = pd.read_excel(uploaded_file, sheet_name=sheet_name, 
                                                  header=None, skiprows=marker_row+1)
                        
                        # If empty, skip
                        if raw_data.empty:
                            continue
                        
                        # Look at first row to see if it contains column names
                        has_header = False
                        for col in raw_data.iloc[0]:
                            if pd.notnull(col) and isinstance(col, str) and ("sequence" in col.lower() or "seqience" in col.lower() or "desc" in col.lower()):
                                has_header = True
                                break
                        
                        # If it seems to have a header, read with that as header
                        if has_header:
                            if next_section:
                                eam_df = pd.read_excel(uploaded_file, sheet_name=sheet_name,
                                                    header=marker_row+1, nrows=next_section-marker_row-2)
                            else:
                                eam_df = pd.read_excel(uploaded_file, sheet_name=sheet_name,
                                                    header=marker_row+1)
                        else:
                            # Create our own column names
                            eam_df = raw_data.copy()
                            if eam_df.shape[1] >= 2:
                                eam_df.columns = ["sequence", "description"] + [f"col{i+3}" for i in range(eam_df.shape[1]-2)]
                            else:
                                # Not enough columns - skip this section
                                st.warning(f"Skipping section in {sheet_name}: insufficient columns")
                                continue
                        
                        # Add metadata
                        eam_df["pm_code"] = sheet_name
                        eam_df["pm_name"] = pm_names.get(sheet_name)
                        # Store the EAM-specific PM name if available
                        eam_df["eam_pm_name"] = eam_pm_name
                        
                        # If we don't have eam_pm_name column, add it to description
                        if eam_pm_name and "description" in eam_df.columns:
                            eam_df["description"] = eam_df["description"].apply(
                                lambda x: f"[EAM: {eam_pm_name}] {x}" if pd.notnull(x) else f"[EAM: {eam_pm_name}]"
                            )
                        
                        # Process dataframe
                        eam_df = process_dataframe(eam_df)
                        if not eam_df.empty:
                            all_rows.extend(eam_df.to_dict(orient="records"))
                    except Exception as e:
                        st.warning(f"Couldn't process section in {sheet_name}: {str(e)}")
                        # For debugging
                        import traceback
                        st.text(traceback.format_exc())
            else:
                # Normal sheet processing - no "Existing task" markers
                try:
                    df = pd.read_excel(uploaded_file, sheet_name=sheet_name, header=2)
                    df["pm_code"] = sheet_name
                    df["pm_name"] = pm_names.get(sheet_name)
                    # Add blank eam_pm_name for regular tasks
                    df["eam_pm_name"] = None
                    
                    # Process dataframe
                    df = process_dataframe(df)
                    if not df.empty:
                        all_rows.extend(df.to_dict(orient="records"))
                except Exception as e:
                    st.warning(f"Couldn't process sheet {sheet_name}: {str(e)}")

        if not all_rows:
            st.error("No valid data found in the uploaded file. Check that your Excel has the right structure.")
            return

        preview_df = pd.DataFrame(all_rows).head(10)
        st.write(f"Preview of extracted data ({len(all_rows)} total rows):")
        st.dataframe(preview_df)
        
        # Show some statistics about the data
        counts_df = pd.DataFrame(all_rows)
        st.write(f"Total PM codes: {counts_df['pm_code'].nunique()}")
        st.write(f"Total tasks: {len(counts_df)}")
        
        # Show counts of EAM tasks with previous PM names
        eam_with_names = counts_df[pd.notnull(counts_df['eam_pm_name'])]
        if not eam_with_names.empty:
            st.write(f"EAM tasks with previous PM names: {len(eam_with_names)}")

        if st.button("Upload to Supabase (replace all)"):
            try:
                # First, check if eam_pm_name column exists in the table
                try:
                    # Try a small query to see if the column exists
                    test_query = supabase.table("dictionary").select("eam_pm_name").limit(1).execute()
                except Exception as e:
                    if "eam_pm_name" in str(e):
                        # Column doesn't exist, so remove it from our data
                        st.warning("The 'eam_pm_name' column doesn't exist in the database. EAM PM names will be added to task descriptions only.")
                        for row in all_rows:
                            if "eam_pm_name" in row:
                                del row["eam_pm_name"]
                
                # Delete all existing data
                supabase.table("dictionary").delete().neq("pm_code", "").execute()
                
                # Insert in batches of 100
                batch_size = 100
                success_count = 0
                
                for i in range(0, len(all_rows), batch_size):
                    batch = all_rows[i:i+batch_size]
                    res = supabase.table("dictionary").insert(batch).execute()
                    if res.data:
                        success_count += len(res.data)
                
                st.success(f"Successfully uploaded {success_count} rows to Supabase! Old data replaced.")
            except Exception as e:
                st.error(f"Error uploading to Supabase: {e}")
                st.info(f"Error details: {str(e)}")

def process_dataframe(df):
    """Process a dataframe to clean columns and handle data types."""
    # Handle NaN values
    df = df.replace({np.nan: None, np.inf: None, -np.inf: None})
    
    # Clean column names and fix typos
    fixed_columns = []
    for col in df.columns:
        col_name = str(col).strip().lower().replace(" ", "_")
        # Fix common typos
        if col_name in ["seqience", "sequance", "sequnce", "sequece", "seqnce", "seq", "seqeunce"]:
            col_name = "sequence"
        elif col_name in ["desc", "desciption", "discription", "descripton"]:
            col_name = "description"
        fixed_columns.append(col_name)
    df.columns = fixed_columns
    
    # Only keep essential columns and skip header rows that might have been ingested
    if "sequence" in df.columns and "description" in df.columns:
        # Convert sequence to numeric, coerce errors to NaN
        df["sequence"] = pd.to_numeric(df["sequence"], errors="coerce")
        # Drop rows where sequence is not a number
        df = df.dropna(subset=["sequence"])
        # Convert sequence to integer
        df["sequence"] = df["sequence"].astype(int)
        # Only keep necessary columns
        keep_cols = ["pm_code", "pm_name", "eam_pm_name", "sequence", "description"]
        df = df[[col for col in keep_cols if col in df.columns]]
        return df
    return pd.DataFrame()  # Return empty dataframe if missing essential columns