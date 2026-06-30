import polars as pl
import zipfile
import tarfile
import os
import io

# Source Data (5 rows)
df_src = pl.DataFrame({
    "id": [1, 2, 3, 4, 5],
    "value": ["A", "B", "C", "D", "E"]
})

# Target Data:
# - id 2 has a mismatch ('X' instead of 'B')
# - id 4 is missing
# - id 6 is an extra row
df_tgt = pl.DataFrame({
    "id": [1, 2, 3, 5, 6],
    "value": ["A", "X", "C", "E", "F"]
})

# Helper function to write Fixed Width Files (FWF)
# id: 5 characters, value: 5 characters
def write_fwf(df, filepath):
    with open(filepath, 'w') as f:
        for row in df.iter_rows():
            f.write(f"{str(row[0]):<5}{str(row[1]):<5}\n")

# Helper function to cleanup temporary files
def cleanup_temps(files):
    for f in files:
        if os.path.exists(f):
            os.remove(f)
            
# Case 4
write_fwf(df_src, "src.txt")
write_fwf(df_tgt, "tgt.txt")

with zipfile.ZipFile("case4_src.zip", "w") as z:
    z.write("src.txt")
with zipfile.ZipFile("case4_tgt.zip", "w") as z:
    z.write("tgt.txt")

cleanup_temps(["src.txt", "tgt.txt"])
print("Case 4 generated.")