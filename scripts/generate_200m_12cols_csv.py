import pandas as pd
import numpy as np
import time
import os

def create_massive_csvs():
    total_rows = 200_000_000
    chunk_size = 500_000
    total_chunks = total_rows // chunk_size
    
    # --- NEW: Path and Filename Configuration ---
    output_dir = '../test-data'
    
    # Create the folder if it doesn't already exist so the script doesn't crash
    os.makedirs(output_dir, exist_ok=True) 
    
    source_file = os.path.join(output_dir, 'generated-200m-12col-source.csv')
    target_file = os.path.join(output_dir, 'generated-200m-12col-target.csv')
    # --------------------------------------------
    
    # 1 ID column + 11 data columns = 12 columns total
    col_names = ['id'] + [f'col_{i}' for i in range(1, 12)]
    
    print(f"Starting generation of {total_rows:,} rows in {total_chunks} chunks...")
    print(f"Saving files to: {os.path.abspath(output_dir)}")
    start_time = time.time()

    for chunk_idx in range(total_chunks):
        # 1. Generate primary key (ID) for the current chunk
        start_id = chunk_idx * chunk_size + 1
        end_id = start_id + chunk_size
        
        # Using int32 to save memory (supports up to ~2.1 billion)
        ids = np.arange(start_id, end_id, dtype=np.int32)
        
        # 2. Generate random float data for the 11 columns
        # Using float32 to keep the memory footprint very light
        data = np.random.rand(chunk_size, 11).astype(np.float32)
        
        # Create the base DataFrame for the source
        source_df = pd.DataFrame(data, columns=col_names[1:])
        source_df.insert(0, 'id', ids)
        
        # Create target DataFrame as an exact copy initially
        target_df = source_df.copy()
        
        # 3. Inject at least 20 mismatches per column in the Target CSV
        if chunk_idx == 0:
            for col in col_names[1:]:
                # Pick 25 random row indices to alter
                mismatch_indices = np.random.choice(chunk_size, 25, replace=False)
                target_df.loc[mismatch_indices, col] += 9999.0
                
        # 4. Write to CSV using the new dynamic paths
        write_mode = 'w' if chunk_idx == 0 else 'a'
        write_header = True if chunk_idx == 0 else False
        
        source_df.to_csv(source_file, mode=write_mode, header=write_header, index=False)
        target_df.to_csv(target_file, mode=write_mode, header=write_header, index=False)
        
        # Print progress
        if (chunk_idx + 1) % 10 == 0 or chunk_idx == 0:
            elapsed = time.time() - start_time
            print(f"Processed chunk {chunk_idx + 1}/{total_chunks} | Elapsed time: {elapsed:.2f}s")

    print(f"Finished! Total time: {(time.time() - start_time) / 60:.2f} minutes.")

if __name__ == "__main__":
    create_massive_csvs()