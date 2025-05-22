import streamlit as st
import pandas as pd
from backend.utils.manual_fetcher import add_manual_links_to_df

def show_manual_lookup():
    st.subheader("🔍 Manual Lookup by Manufacturer & Model")

    uploaded_file = st.file_uploader("Upload Excel File (with Manufacturer, Model, Serial Number)", type=["xlsx", "csv"])

    if uploaded_file:
        try:
            if uploaded_file.name.endswith(".csv"):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)

            st.write("### Preview of Uploaded Data")
            st.dataframe(df.head())

            if st.button("🔎 Fetch Manuals"):
                with st.spinner("Looking up manuals..."):
                    result_df = add_manual_links_to_df(df)
                    st.success("Manual links added!")

                st.write("### Results with Manual Links")
                if "manual_link" in result_df.columns:
                    st.dataframe(result_df[["manufacturer", "model_number", "serial_number", "manual_link"]])
                else:
                    st.dataframe(result_df)

                # Download button
                csv = result_df.to_csv(index=False).encode("utf-8")
                st.download_button("📥 Download Result as CSV", data=csv, file_name="manuals_result.csv", mime="text/csv")

        except Exception as e:
            st.error(f"Error processing file: {e}")
