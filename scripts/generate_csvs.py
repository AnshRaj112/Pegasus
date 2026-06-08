import os
import random
import string

def generate_random_string(length=8):
    """Generates a random string of fixed length."""
    letters = string.ascii_letters
    return ''.join(random.choice(letters) for _ in range(length))

def write_custom_csv(filepath, headers, data, delimiter):
    """Writes to a CSV manually to support multi-character delimiters."""
    with open(filepath, mode='w', encoding='utf-8') as f:
        # Write headers
        f.write(delimiter.join(map(str, headers)) + '\n')
        # Write data rows
        for row in data:
            f.write(delimiter.join(map(str, row)) + '\n')

def create_csv_files():
    print("=== CSV Test Data Generator ===")
    
    # 1. Get Folder Location and Name
    base_path = input("Enter the directory path where you want the folder (use '.' for current directory): ").strip()
    folder_name = input("Enter the name of the new folder: ").strip()
    
    # 2. Get Data Requirements
    try:
        total_source = int(input("Enter the TOTAL number of rows in the SOURCE file: "))
        total_target = int(input("Enter the TOTAL number of rows in the TARGET file: "))
        num_cols = int(input("Enter the number of data columns (excluding the ID column): "))
        num_mismatches = int(input("Enter the number of MISMATCHED rows: "))
        num_missing = int(input("Enter the number of MISSING rows (in source, but not target): "))
        num_extras = int(input("Enter the number of EXTRA rows (in target, but not source): "))
    except ValueError:
        print("\nError: Please enter valid integers for rows and columns.")
        return

    # 3. Calculate Exact Matches and Validate Math
    matches_from_source = total_source - num_mismatches - num_missing
    matches_from_target = total_target - num_mismatches - num_extras

    if matches_from_source != matches_from_target:
        print("\nError: Your numbers don't balance out mathematically!")
        print(f"Source implies {matches_from_source} exact matches.")
        print(f"Target implies {matches_from_target} exact matches.")
        print("Please check your totals, missing, and extra rows.")
        return
    
    if matches_from_source < 0:
        print("\nError: The number of mismatches and missing rows exceeds the total source rows!")
        return

    num_matches = matches_from_source
    print(f"\n[Calculated] Generating {num_matches} EXACT MATCH rows based on your inputs...")

    # 4. Get Delimiter
    delimiter = input("Enter the delimiter (e.g., ',' or '||' or ';'): ")
    if not delimiter:
        delimiter = ',' # Default to comma

    # Create the directory
    full_path = os.path.join(base_path, folder_name)
    try:
        os.makedirs(full_path, exist_ok=True)
        print(f"Created/Verified directory: {full_path}")
    except Exception as e:
        print(f"Error creating directory: {e}")
        return

    # Define headers
    headers = ['ID'] + [f'Column_{i}' for i in range(1, num_cols + 1)]

    source_data = []
    target_data = []
    current_id = 1

    # --- Generate EXACT MATCHES ---
    for _ in range(num_matches):
        row = [current_id] + [generate_random_string() for _ in range(num_cols)]
        source_data.append(row)
        target_data.append(row)
        current_id += 1

    # --- Generate MISMATCHES ---
    for _ in range(num_mismatches):
        source_row = [current_id] + [generate_random_string() for _ in range(num_cols)]
        target_row = source_row.copy()
        if num_cols > 0:
            target_row[1] = target_row[1] + "_MODIFIED"
            
        source_data.append(source_row)
        target_data.append(target_row)
        current_id += 1

    # --- Generate MISSING ROWS (Only in Source) ---
    for _ in range(num_missing):
        row = [current_id] + [generate_random_string() for _ in range(num_cols)]
        source_data.append(row)
        current_id += 1

    # --- Generate EXTRA ROWS (Only in Target) ---
    for _ in range(num_extras):
        row = [current_id] + [generate_random_string() for _ in range(num_cols)]
        target_data.append(row)
        current_id += 1

    # File paths
    source_file = os.path.join(full_path, 'source.csv')
    target_file = os.path.join(full_path, 'target.csv')

    # Write Files using our custom function to support multi-character delimiters
    write_custom_csv(source_file, headers, source_data, delimiter)
    write_custom_csv(target_file, headers, target_data, delimiter)

    print("\n=== Generation Complete ===")
    print(f"Source file saved to: {source_file} ({len(source_data)} rows)")
    print(f"Target file saved to: {target_file} ({len(target_data)} rows)")

if __name__ == "__main__":
    create_csv_files()