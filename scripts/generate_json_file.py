import os
import json
import argparse
import copy
from pathlib import Path

def create_json_files(folder_name, num_mismatches, record_count):
    # 1. Setup the directory paths
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    target_dir = project_root / 'test-data' / folder_name
    
    target_dir.mkdir(parents=True, exist_ok=True)
    
    source_file = target_dir / 'source.json'
    target_file = target_dir / 'target.json'

    # 2. Generate the Dynamic Source Data (Document A)
    errors_list = []
    for i in range(record_count):
        # Alternate the error type for some variety
        error_type = "invalid" if i % 2 == 0 else "required"
        # Generate unique field names
        field_name = "email" if i == 0 else ("name" if i == 1 else f"field_{i}")
        
        errors_list.append({"error": error_type, "field": field_name})

    source_data = {
        "errors": errors_list,
        "success": False
    }

    # 3. Create the Target Data (Document B)
    target_data = copy.deepcopy(source_data)
    target_data["errors"].reverse()

    # 4. Inject explicit Mismatches
    mismatches_applied = 0
    
    # Mismatch 1: Flip the success boolean
    if mismatches_applied < num_mismatches:
        target_data["success"] = not target_data["success"]
        mismatches_applied += 1

    # Mismatch 2+: Mutate the fields inside the dynamically generated array
    for i in range(len(target_data["errors"])):
        if mismatches_applied < num_mismatches:
            target_data["errors"][i]["error"] += "_mismatch"
            mismatches_applied += 1
        if mismatches_applied < num_mismatches:
            target_data["errors"][i]["field"] += "_mismatch"
            mismatches_applied += 1

    # Mismatch Catch-all: If you ask for more mismatches than there is data to mutate, inject new keys
    while mismatches_applied < num_mismatches:
        target_data[f"injected_mismatch_{mismatches_applied}"] = "unexpected_data"
        mismatches_applied += 1

    # 5. Write the files
    with open(source_file, 'w') as f:
        json.dump(source_data, f, indent=4)

    with open(target_file, 'w') as f:
        # Reorder to put "success" first to match your Document B structure
        ordered_target = {"success": target_data["success"]}
        for key, val in target_data.items():
            if key != "success":
                ordered_target[key] = val
        
        json.dump(ordered_target, f, indent=4)

    print(f"✅ Success! Files created in: {target_dir}")
    print(f"📦 Total records in array: {record_count}")
    print(f"🔧 Total explicit mismatches injected: {num_mismatches}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Generate scalable source and target JSON files.")
    parser.add_argument('--folder', type=str, required=True, help="Folder to create under 'test-data/'")
    parser.add_argument('--count', type=int, default=2, help="Amount of data records in the JSON array (default: 2)")
    parser.add_argument('--mismatches', type=int, default=0, help="Number of data mismatches to introduce (default: 0)")
    
    args = parser.parse_args()
    
    create_json_files(args.folder, args.mismatches, args.count)