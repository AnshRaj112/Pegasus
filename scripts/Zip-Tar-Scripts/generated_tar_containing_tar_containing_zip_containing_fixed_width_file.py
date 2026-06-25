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

# Case 13
write_fwf(df_src, "src.txt")
write_fwf(df_tgt, "tgt.txt")

for prefix in ["src", "tgt"]:
    with zipfile.ZipFile(f"inner_{prefix}.zip", "w") as z:
        z.write(f"{prefix}.txt")
    with tarfile.open(f"inner_{prefix}.tar", "w") as tar:
        tar.add(f"inner_{prefix}.zip")
    with tarfile.open(f"case13_{prefix}.tar", "w") as tar:
        tar.add(f"inner_{prefix}.tar")

cleanup_temps(["src.txt", "tgt.txt", "inner_src.zip", "inner_tgt.zip", "inner_src.tar", "inner_tgt.tar"])
print("Case 13 generated.")