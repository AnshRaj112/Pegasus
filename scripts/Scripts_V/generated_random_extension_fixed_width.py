import polars as pl

# Helper function to write Fixed Width Files (FWF)
# Allocates 5 characters for 'id' and 5 characters for 'value'
def write_fwf(df, filepath):
    with open(filepath, 'w') as f:
        for row in df.iter_rows():
            f.write(f"{str(row[0]):<5}{str(row[1]):<5}\n")

# Define Source Data (9 rows)
df_src = pl.DataFrame({
    "id": [1, 2, 3, 4, 5, 7, 8, 9, 10],
    "value": ["A", "B", "C", "D", "E", "G", "H", "I", "J"]
})

# Define Target Data (9 rows)
# Includes: Mismatch (id 2), Missing (id 4), Extra (id 6)
df_tgt = pl.DataFrame({
    "id": [1, 2, 3, 5, 6, 7, 8, 9, 10],
    "value": ["A", "X", "C", "E", "F", "G", "H", "I", "J"]
})

# Write the data to Fixed Width format, but use the .QWE extension
write_fwf(df_src, "source.QWE")
write_fwf(df_tgt, "target.QWE")

print("Test Case 2 (Fixed Width as .QWE) successfully generated.")