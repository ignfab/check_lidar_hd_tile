import pdal
import numpy as np
import argparse

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Check that for each impulsion (unique gps_time) in a COPC.laz file, the number of points matches NumberOfReturns.")
    parser.add_argument("input_file", help="Path to the COPC.laz file")
    args = parser.parse_args()
    file_path = args.input_file

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

    import csv
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

    # Write CSV files for each error case
    if inconsistent_details:
        with open('impulsions_inconsistent_NumberOfReturns.csv', 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['gps_time', 'n_points', 'unique_NumberOfReturns'])
            writer.writeheader()
            for row in inconsistent_details:
                writer.writerow(row)
    if count_mismatch_details:
        with open('impulsions_count_mismatch.csv', 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['gps_time', 'n_points', 'NumberOfReturns'])
            writer.writeheader()
            for row in count_mismatch_details:
                writer.writerow(row)

    # Output the result: percentage of impulsions for each error type
    if inconsistent_returns == 0 and count_mismatch == 0:
        print("All impulsions have correct number of points and consistent NumberOfReturns.")
    else:
        percent_inconsistent = 100.0 * inconsistent_returns / total if total > 0 else 0.0
        percent_count_mismatch = 100.0 * count_mismatch / total if total > 0 else 0.0
        print(f"{percent_inconsistent:.2f}% of impulsions have inconsistent NumberOfReturns (see 'impulsions_inconsistent_NumberOfReturns.csv').")
        print(f"{percent_count_mismatch:.2f}% of impulsions have a count mismatch compared to NumberOfReturns (see 'impulsions_count_mismatch.csv').")

if __name__ == "__main__":
    main()
