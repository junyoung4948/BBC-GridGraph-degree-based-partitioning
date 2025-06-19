import os
import struct
import argparse

# --- Configuration ---
# This part is still needed to read sample edges correctly.
VERTEX_ID_TYPE = 'I'
VERTEX_ID_SIZE = 4
EDGE_STRUCT_FORMAT = f'<{VERTEX_ID_TYPE}{VERTEX_ID_TYPE}' # Little-endian
EDGE_SIZE = VERTEX_ID_SIZE * 2
# --------------------

def analyze_block_edges(filepath: str, sample_count: int = 5):
    """
    Analyzes a block file to get the total number of edges and a few samples.
    This version does not calculate degree sums.
    """
    if not os.path.exists(filepath):
        return None, None

    try:
        # Get edge count directly from file size, which is very fast.
        file_size = os.path.getsize(filepath)
        num_edges = file_size // EDGE_SIZE
        
        sample_edges = []
        # It's still useful to see a few sample edges.
        with open(filepath, 'rb') as f:
            for _ in range(min(num_edges, sample_count)):
                edge_data = f.read(EDGE_SIZE)
                if not edge_data or len(edge_data) < EDGE_SIZE:
                    break
                edge = struct.unpack(EDGE_STRUCT_FORMAT, edge_data)
                sample_edges.append(edge)
                
        return num_edges, sample_edges
    except Exception as e:
        print(f"[Error] Failed to analyze file {filepath}: {e}")
        return 0, []

def print_analysis_results(title: str, filepath: str, num_edges: int, samples: list):
    """Prints the formatted analysis results for a block."""
    print(f"--- {title} ---")
    if num_edges is None:
        print(f"File not found: {filepath}")
        return

    print(f"File: {filepath}")
    print(f"Total Edges in Block: {num_edges:,}")
    print(f"Sample Edges: {samples}")

def main():
    parser = argparse.ArgumentParser(description="Compare the number of edges in GridGraph block partitions.")
    parser.add_argument('i', type=int, help="The row index (i) of the block.")
    parser.add_argument('j', type=int, help="The column index (j) of the block.")
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    default_base_dir = os.path.abspath(os.path.join(script_dir, '..', 'data', 'LiveJournal_Grid'))
    default_dv_dir = os.path.abspath(os.path.join(script_dir, '..', 'data', 'LiveJournal_Grid_dv'))

    parser.add_argument('--base_dir', type=str, default=default_base_dir)
    parser.add_argument('--dv_dir', type=str, default=default_dv_dir)
    args = parser.parse_args()

    print("=" * 50)
    print(f"Analyzing edge counts for block ({args.i}, {args.j})...")
    print("=" * 50)

    # --- Analyze each version ---
    base_block_path = os.path.join(args.base_dir, f'block-{args.i}-{args.j}')
    dv_block_path = os.path.join(args.dv_dir, f'block-{args.i}-{args.j}')

    base_num_edges, base_samples = analyze_block_edges(base_block_path)
    dv_num_edges, dv_samples = analyze_block_edges(dv_block_path)

    # --- Print Results ---
    print_analysis_results("Baseline Version", base_block_path, base_num_edges, base_samples)
    print("\n" + "-"*25 + "\n")
    print_analysis_results("Degree-Based Version", dv_block_path, dv_num_edges, dv_samples)
    print("\n" + "=" * 50)

    # --- Summary ---
    if base_num_edges is not None and dv_num_edges is not None:
        diff = dv_num_edges - base_num_edges
        percentage_change = (diff / base_num_edges * 100) if base_num_edges > 0 else float('inf')
        
        print("Summary:")
        if diff > 0:
            print(f"  The Degree-Based block is LARGER by {abs(diff):,} edges ({percentage_change:+.2f}%).")
        elif diff < 0:
            print(f"  The Degree-Based block is SMALLER by {abs(diff):,} edges ({percentage_change:+.2f}%).")
        else:
            print("  Both blocks have the same number of edges.")
    print("=" * 50)

if __name__ == '__main__':
    main()