import os
import csv
import pdal
import numpy as np
import argparse
import zipfile
from datetime import datetime

def main():

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Check that for each impulsion (unique gps_time) in a COPC.laz file, the number of points matches NumberOfReturns.")
    parser.add_argument("input_file", help="Path to the COPC.laz file")
    args = parser.parse_args()
    file_path = args.input_file
    base = os.path.basename(file_path)
    if base.endswith('.copc.laz'):
        base = base[:-9]
    else:
        base = os.path.splitext(base)[0]
    inconsistent_csv = f"inconsistent_NumberOfReturns_{base}.csv"
    count_mismatch_csv = f"count_mismatch_{base}.csv"

    # Build and execute a PDAL pipeline to read the COPC.laz file
    pipeline_json = f"""
    [
        "{file_path}"
    ]
    """
    pipeline = pdal.Pipeline(pipeline_json)
    pipeline.execute()
    arr = pipeline.arrays[0]  # Get the point data as a NumPy structured array

    # Extract gps_time and NumberOfReturns fields as NumPy arrays
    gps_times = arr['GpsTime']
    num_returns = arr['NumberOfReturns']

    # Sort by gps_time for efficient grouping (all points with the same gps_time will be consecutive)
    sort_idx = np.argsort(gps_times)
    gps_times_sorted = gps_times[sort_idx]
    num_returns_sorted = num_returns[sort_idx]

    # Find the boundaries where gps_time changes (i.e., new impulsion starts)
    boundaries = np.flatnonzero(np.diff(gps_times_sorted)) + 1
    # Start and end indices for each group of points with the same gps_time
    group_starts = np.concatenate(([0], boundaries))
    group_ends = np.concatenate((boundaries, [len(gps_times_sorted)]))

    # Lists to store error details
    inconsistent_details = []
    count_mismatch_details = []
    inconsistent_returns = 0  # len(unique_returns) != 1
    count_mismatch = 0        # n_points != unique_returns[0]
    total = len(group_starts)  # Total number of impulsions

    # Iterate over each impulsion (unique gps_time group)
    for start, end in zip(group_starts, group_ends):
        n_points = end - start  # Number of points in this impulsion
        returns = num_returns_sorted[start:end]  # NumberOfReturns values for this impulsion
        unique_returns = np.unique(returns)  # Unique NumberOfReturns values in this group
        gps_time_val = gps_times_sorted[start]
        if len(unique_returns) != 1:
            inconsistent_returns += 1
            inconsistent_details.append({
                'gps_time': gps_time_val,
                'n_points': n_points,
                'unique_NumberOfReturns': unique_returns.tolist()
            })
        elif n_points != unique_returns[0]:
            count_mismatch += 1
            count_mismatch_details.append({
                'gps_time': gps_time_val,
                'n_points': n_points,
                'NumberOfReturns': int(unique_returns[0])
            })

    def write_csv(filename, fieldnames, rows):
        if rows:
            with open(filename, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for row in rows:
                    writer.writerow(row)

    write_csv(inconsistent_csv, ['gps_time', 'n_points', 'unique_NumberOfReturns'], inconsistent_details)
    write_csv(count_mismatch_csv, ['gps_time', 'n_points', 'NumberOfReturns'], count_mismatch_details)

    # Prepare report content and filename
    report_lines = []
    report_base = base
    report_filename = f"report_{report_base}.txt"

    # Output the result: percentage of impulsions for each error type
    if inconsistent_returns == 0 and count_mismatch == 0:
        msg = "All impulsions have correct number of points and consistent NumberOfReturns."
        print(msg)
        report_lines.append(msg)
    else:
        percent_inconsistent = 100.0 * inconsistent_returns / total if total > 0 else 0.0
        percent_count_mismatch = 100.0 * count_mismatch / total if total > 0 else 0.0
        msg1 = f"{percent_inconsistent:.2f}% of impulsions have inconsistent NumberOfReturns (see '{inconsistent_csv}')."
        msg2 = f"{percent_count_mismatch:.2f}% of impulsions have a count mismatch compared to NumberOfReturns (see '{count_mismatch_csv}')."
        print(msg1)
        print(msg2)
        report_lines.append(msg1)
        report_lines.append(msg2)

    # Write the report file
    with open(report_filename, 'w') as f:
        for line in report_lines:
            f.write(line + '\n')

    # Create a zip archive containing the CSVs and the report, with filename and datetime in the archive name
    now_str = datetime.now().strftime('%Y%m%d_%H%M%S')
    archive_name = f"{base}_{now_str}_results.zip"
    with zipfile.ZipFile(archive_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        if inconsistent_details:
            zipf.write(inconsistent_csv)
        if count_mismatch_details:
            zipf.write(count_mismatch_csv)
        zipf.write(report_filename)
    print(f"Created archive: {archive_name}")

    # Clean up CSV and TXT files after archiving
    for f in [inconsistent_csv, count_mismatch_csv, report_filename]:
        if os.path.exists(f):
            os.remove(f)

if __name__ == "__main__":
    main()
