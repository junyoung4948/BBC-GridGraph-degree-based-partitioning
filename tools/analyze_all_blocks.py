import os
import argparse
import numpy as np # Used for pretty printing numbers

# --- Configuration ---
EDGE_SIZE = 8 # Assuming VertexId is 4 bytes, so an edge is 8 bytes.
# --------------------

def calculate_partition_stats(directory: str, p: int, total_edges: int):
    """
    Analyzes all blocks in a directory to calculate partitioning quality metrics.
    Returns a dictionary containing the calculated statistics.
    """
    if not os.path.isdir(directory):
        print(f"[Error] Directory not found: {directory}")
        return None

    num_total_blocks = p * p
    if num_total_blocks == 0:
        return None
    
    ideal_edges_per_block = total_edges / num_total_blocks
    
    total_absolute_deviation = 0.0
    sum_of_block_edges = 0
    non_empty_blocks = 0

    print(f"Analyzing directory: {directory}...")
    
    # Loop through all possible blocks from (0,0) to (p-1, p-1)
    for i in range(p):
        # A simple progress indicator for large 'p'
        print(f"  Processing partition row {i+1}/{p}...", end='\r')
        for j in range(p):
            block_path = os.path.join(directory, f'block-{i}-{j}')
            
            actual_edges = 0
            if os.path.exists(block_path):
                file_size = os.path.getsize(block_path)
                actual_edges = file_size // EDGE_SIZE
            
            if actual_edges > 0:
                non_empty_blocks += 1

            total_absolute_deviation += abs(actual_edges - ideal_edges_per_block)
            sum_of_block_edges += actual_edges
    
    # Clear the progress indicator line
    print("\nAnalysis complete.")

    return {
        "ideal_edges": ideal_edges_per_block,
        "total_deviation": total_absolute_deviation,
        "verified_edges": sum_of_block_edges,
        "non_empty_blocks": non_empty_blocks,
        "total_blocks": num_total_blocks
    }

def main():
    parser = argparse.ArgumentParser(
        description="Holistically analyze and compare GridGraph partitioning quality."
    )
    parser.add_argument('-p', type=int, required=True, help="Number of partitions per dimension (p).")
    parser.add_argument('--edges', type=int, required=True, help="Total number of edges in the graph.")
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_base_dir = os.path.abspath(os.path.join(script_dir, '..', 'data', 'LiveJournal_Grid'))
    default_dv_dir = os.path.abspath(os.path.join(script_dir, '..', 'data', 'LiveJournal_Grid_dv'))

    parser.add_argument('--base_dir', type=str, default=default_base_dir)
    parser.add_argument('--dv_dir', type=str, default=default_dv_dir)
    
    args = parser.parse_args()

    print("=" * 60)
    print("Starting Partitioning Quality Analysis")
    print(f"Total Edges: {args.edges:,}, Partitions: {args.p}x{args.p} = {args.p*args.p:,}")
    print("=" * 60)

    # --- Analyze each version ---
    baseline_stats = calculate_partition_stats(args.base_dir, args.p, args.edges)
    print("-" * 60)
    dv_stats = calculate_partition_stats(args.dv_dir, args.p, args.edges)

    # --- Print Comparative Results ---
    print("\n" + "=" * 60)
    print("Comparative Analysis Results")
    print("=" * 60)

    if baseline_stats:
        print("\n--- Baseline Version ---")
        print(f"  Ideal Edges per Block: {baseline_stats['ideal_edges']:,.2f}")
        print(f"  Total Absolute Deviation: {baseline_stats['total_deviation']:,.0f}")
        print(f"  Verified Total Edges: {baseline_stats['verified_edges']:,}")
        print(f"  Non-Empty Blocks: {baseline_stats['non_empty_blocks']:,} / {baseline_stats['total_blocks']:,}")

    if dv_stats:
        print("\n--- Degree-Based Version ---")
        print(f"  Ideal Edges per Block: {dv_stats['ideal_edges']:,.2f}")
        print(f"  Total Absolute Deviation: {dv_stats['total_deviation']:,.0f}")
        print(f"  Verified Total Edges: {dv_stats['verified_edges']:,}")
        print(f"  Non-Empty Blocks: {dv_stats['non_empty_blocks']:,} / {dv_stats['total_blocks']:,}")

    # --- Final Conclusion ---
    print("\n" + "=" * 60)
    print("Conclusion")
    print("-" * 60)
    if baseline_stats and dv_stats:
        # Verification check
        if dv_stats['verified_edges'] != args.edges or baseline_stats['verified_edges'] != args.edges:
            print("! Verification Warning: Sum of edges in blocks does not match the provided total edges.")
        
        # Comparison
        if dv_stats['total_deviation'] < baseline_stats['total_deviation']:
            reduction = (baseline_stats['total_deviation'] - dv_stats['total_deviation']) / baseline_stats['total_deviation'] * 100
            print("? The Degree-Based partitioning is MORE BALANCED.")
            print(f"   It reduced the total deviation from the ideal by {reduction:.2f}%.")
        elif dv_stats['total_deviation'] > baseline_stats['total_deviation']:
             print("? The Degree-Based partitioning is LESS BALANCED.")
        else:
            print("?? Both partitioning methods have the same level of balance.")
    print("=" * 60)

if __name__ == '__main__':
    main()