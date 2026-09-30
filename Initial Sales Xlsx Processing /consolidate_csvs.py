import pandas as pd
from pathlib import Path

input_dir = Path("eabl parsed csv")
print(input_dir)
output_path = input_dir / "eabl_sales_consolidated.csv"
print(output_path)


csv_files = sorted(input_dir.glob("*_parsed.csv"))
print(f"Found {len(csv_files)} files")


reference_columns = None
for f in csv_files:
    cols = pd.read_csv(f, nrows=0).columns.tolist()
    if reference_columns is None:
        reference_columns = cols
    elif cols != reference_columns:
        raise ValueError(f"{f.name} has different columns: {cols}")
    
    
dataframes = [pd.read_csv(f) for f in csv_files]
print(dataframes)
consolidated = pd.concat(dataframes, ignore_index=True)

expected_total = sum(len(df) for df in dataframes)
assert len(consolidated) == expected_total, "Row count mismatch!"
print(f"Consolidated table has {len(consolidated)} rows (expected {expected_total})")


consolidated.to_csv(output_path, index=False)
print(f"Saved to {output_path}")
