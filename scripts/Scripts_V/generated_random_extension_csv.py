import polars as pl

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

# Write the data to CSV format, but use the .ABC extension
df_src.write_csv("source.ABC")
df_tgt.write_csv("target.ABC")

print("Test Case 1 (CSV as .ABC) successfully generated.")