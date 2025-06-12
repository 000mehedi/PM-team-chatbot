import pandas as pd
from supabase_client import supabase
import numpy as np

excel_file = "Dictionary Format 2024_Jun 20.xlsx"

# First, read the complete sheets without a header to extract PM header info (A1 and B1)
all_sheets = pd.read_excel(excel_file, sheet_name=None, header=None)
pm_names = {}
for sheet_name, df in all_sheets.items():
    if df.shape[0] >= 1 and df.shape[1] >= 2:
        # Extract PM name from cell B1 (first row, second column)
        pm_names[sheet_name] = df.iloc[0, 1]
    else:
        pm_names[sheet_name] = None

# Now, read the sheets with header=2 for the tabular data (starting from row 3)
sheets_dict = pd.read_excel(excel_file, sheet_name=None, header=2)

def normalize_columns(columns):
    # Normalize: trim, lowercase, replace spaces with underscores, remove parentheses
    return [str(col).strip().lower().replace(" ", "_").replace("(", "").replace(")", "") for col in columns]

# Adjust allowed_columns: "pm_code" (from sheet), "sequence", "description", "pm_name"
allowed_columns = {"pm_code", "sequence", "description", "pm_name"}
rows = []
for sheet_name, df in sheets_dict.items():
    # Add sheet name as the "pm_code" column
    df["pm_code"] = sheet_name
    # Add PM name extracted earlier as a new column "pm_name"
    df["pm_name"] = pm_names.get(sheet_name)
    df = df.replace({np.nan: None, np.inf: None, -np.inf: None})
    df.columns = normalize_columns(df.columns)
    print(f"Sheet: {sheet_name} normalized columns: {df.columns.tolist()}")
    # Filter out columns not in allowed_columns
    filtered_cols = [col for col in df.columns if col in allowed_columns]
    print(f"Sheet: {sheet_name} filtered columns: {filtered_cols}")
    df = df[filtered_cols]
    
    # Convert sequence column to numeric
    if "sequence" in df.columns:
        df["sequence"] = pd.to_numeric(df["sequence"], errors="coerce")
        # Drop rows where conversion fails and cast valid numbers to integer
        df = df.dropna(subset=["sequence"])
        df["sequence"] = df["sequence"].apply(lambda x: int(x))
    
    rows.extend(df.to_dict(orient="records"))

print("Rows to insert:", rows)

try:
    response = supabase.table("dictionary").insert(rows).execute()
    print("Insert response:", response)
except Exception as e:
    print("Insert error:", e)