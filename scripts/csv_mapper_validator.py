import os
import pandas as pd


def generate_sample_files(num_rows):
    """Generates source and target CSV files with a user-defined row count."""

    # Base pool of diverse test names to handle various edge cases
    base_names = [
        ("John Smith", "John", "Smith"),
        ("Alice Marie Johnson", "Alice", "Marie Johnson"),
        ("Bob", "Bob", ""),
        ("Jane Doe", "Jane", "Doe"),
        ("Dr. Eleanor Vance", "Dr. Eleanor", "Vance"),
        ("Li Wang", "Li", "Wang"),
    ]

    source_rows = []
    target_rows = []

    # Loop to dynamically generate the requested number of rows
    for i in range(num_rows):
        user_id = 1000 + i

        # Rotate through the base test cases repeatedly to fill rows
        base_name, expected_first, expected_last = base_names[i % len(base_names)]

        # Append unique ID markers to make data realistic if row count is high
        suffix = f"_{i}" if i >= len(base_names) else ""
        full_name = f"{base_name}{suffix}"
        first_name = f"{expected_first}{suffix}"
        last_name = expected_last  # Keep last name clean

        status = "Active" if i % 2 == 0 else "Inactive"

        # Append to source structure
        source_rows.append(
            {"User_ID": user_id, "Full_Name": full_name, "Status": status}
        )

        # Append to target structure
        target_rows.append(
            {
                "ID": user_id,
                "First_Name": first_name,
                "Last_Name": last_name,
                "Account_Status": status,
            }
        )

    # Convert lists to Pandas DataFrames and save to CSV
    df_source = pd.DataFrame(source_rows)
    df_target = pd.DataFrame(target_rows)

    df_source.to_csv("source.csv", index=False)
    df_target.to_csv("target.csv", index=False)

    print(f"\n✅ Successfully created 'source.csv' with {len(df_source)} rows.")
    print(f"✅ Successfully created 'target.csv' with {len(df_target)} rows.\n")


def validate_mapping():
    """Loads files and validates 1-to-Many column mapping line by line."""
    print("🔄 Starting Validation Mapping...")

    src = pd.read_csv("source.csv")
    tgt = pd.read_csv("target.csv")

    validation_passed = True

    if len(src) != len(tgt):
        print(
            f"❌ Row count mismatch! Source: {len(src)} rows, Target: {len(tgt)} rows"
        )
        return False

    # Limit console output if file contains too many rows
    max_print_rows = min(len(src), 10)

    for index in range(len(src)):
        src_row = src.iloc[index]
        tgt_row = tgt.iloc[index]

        source_name = str(src_row["Full_Name"]).strip()
        target_first = str(tgt_row["First_Name"]).strip()
        target_last = (
            str(tgt_row["Last_Name"]).strip()
            if pd.notna(tgt_row["Last_Name"])
            else ""
        )

        # Reconstruct the name for comparison
        reconstructed = (
            f"{target_first} {target_last}".strip() if target_last else target_first
        )

        if source_name != reconstructed:
            print(f"❌ Mapping Failure at Row index {index}:")
            print(f"   Source: '{source_name}' | Target Reconstructed: '{reconstructed}'")
            validation_passed = False
        else:
            # Print success logs only for the first few items to prevent terminal spam
            if index < max_print_rows:
                print(f"--- Row {index} Passed ({source_name} -> {target_first} + {target_last}) ---")

    if len(src) > max_print_rows:
        print(f"... [{len(src) - max_print_rows} more rows validated successfully] ...")

    if validation_passed:
        print("\n🎉 SUCCESS: All column mappings are 100% valid!")
    else:
        print("\n🚨 FAILURE: Data discrepancies found during mapping validation.")


if __name__ == "__main__":
    # Clean up old files if they exist
    for f in ["source.csv", "target.csv"]:
        if os.path.exists(f):
            os.remove(f)

    # Dynamic CLI User input choice
    try:
        requested_rows = int(input("How many rows do you want to keep/generate? "))
        if requested_rows <= 0:
            print("Please enter a number greater than 0. Defaulting to 5 rows.")
            requested_rows = 5
    except ValueError:
        print("Invalid input. Defaulting to 5 rows.")
        requested_rows = 5

    # Run execution pipeline
    generate_sample_files(requested_rows)
    validate_mapping()
