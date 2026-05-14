import polars as pl
import os
import time
import numpy as np

def create_mock_wide_data(filename="wide_data.parquet", rows=10000, cols=1000):
    print(f"Generating mock data: {rows} rows x {cols} columns...")
    # Create a Primary Key column
    data = {"row_id": np.arange(rows)}
    
    # Add 1000 columns with random data to simulate a very wide dataset
    for i in range(1, cols + 1):
        data[f"col_{i}"] = np.random.randint(0, 100, size=rows)
        
    df = pl.DataFrame(data)
    
    # Saving as Parquet is CRUCIAL. If this was CSV, vertical slicing would be incredibly slow.
    df.write_parquet(filename)
    print(f"Saved to {filename} ({os.path.getsize(filename) / 1024 / 1024:.2f} MB)")
    return filename

def validate_by_column_chunks(filename, pk_col="row_id", chunk_size=100):
    print(f"\nStarting Vertical Validation (Batch size: {chunk_size} columns)...")
    start_time = time.time()
    
    # 1. Read JUST the schema to get column names without loading any actual data into RAM
    schema = pl.read_parquet_schema(filename)
    all_columns = list(schema.keys())
    
    # Remove the primary key from the list of columns to be chunked
    if pk_col in all_columns:
        all_columns.remove(pk_col)
    
    # 2. Split the 1000 columns into chunks (e.g., 10 chunks of 100)
    column_chunks = [
        all_columns[i:i + chunk_size] 
        for i in range(0, len(all_columns), chunk_size)
    ]
    
    print(f"Total columns to validate: {len(all_columns)}")
    print(f"Split into {len(column_chunks)} batches.\n")
    
    # 3. Process each vertical chunk one by one
    for idx, chunk in enumerate(column_chunks):
        batch_start_time = time.time()
        
        # We MUST include the primary key in every chunk so we know WHICH row failed
        columns_to_read = [pk_col] + chunk
        
        # Load ONLY this vertical slice into RAM
        df_chunk = pl.read_parquet(filename, columns=columns_to_read)
        
        # --- MOCK VALIDATION LOGIC ---
        # Example: Let's pretend any value > 95 is a "validation error"
        # We find errors and tie them back to the row_id
        
        errors_found = 0
        for col in chunk:
            # Filter rows where validation fails for this specific column
            failed_rows = df_chunk.filter(pl.col(col) > 95).select(pk_col)
            errors_found += len(failed_rows)
            
        batch_time = time.time() - batch_start_time
        print(f"Processed Batch {idx + 1:02d}/{len(column_chunks)} ({len(chunk):3d} cols) | "
              f"RAM used: Minimal | Errors found: {errors_found:5d} | Time: {batch_time:.3f}s")

    total_time = time.time() - start_time
    print(f"\n✅ Total Vertical Validation completed in {total_time:.2f} seconds!")

if __name__ == "__main__":
    file_path = "wide_data_1000_cols.parquet"
    
    # 1. Generate the test data if it doesn't exist
    if not os.path.exists(file_path):
        create_mock_wide_data(file_path)
    else:
        print(f"Using existing data file: {file_path}")
        
    # 2. Run the vertical validation
    # We will process 200 columns at a time out of the 1000
    validate_by_column_chunks(file_path, chunk_size=200)
