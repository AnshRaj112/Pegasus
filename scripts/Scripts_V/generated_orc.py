import polars as pl
import pyarrow.orc as orc

# Helper function to write ORC files (bypassing the Polars limitation)
def write_orc_file(df, filepath):
    table = df.to_arrow()
    orc.write_table(table, filepath)

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

# Write the data to ORC format using the helper function
write_orc_file(df_src, "case1_src.orc")
write_orc_file(df_tgt, "case1_tgt.orc")

print("Single ORC Test Case successfully generated.")