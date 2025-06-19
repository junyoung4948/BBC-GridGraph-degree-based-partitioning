import os
import argparse
import numpy as np
import matplotlib.pyplot as plt

# Edge is composed of two 4-byte VertexIDs
EDGE_SIZE = 8

def get_block_sizes_kb(directory: str, p: int):
    """
    Scans a grid directory and returns a list of all block sizes in kilobytes.
    """
    if not os.path.isdir(directory):
        print(f"[Error] Directory not found: {directory}")
        return []

    block_sizes = []
    print(f"Analyzing directory: {directory}...")
    for i in range(p):
        for j in range(p):
            block_path = os.path.join(directory, f'block-{i}-{j}')
            
            if os.path.exists(block_path):
                size_in_bytes = os.path.getsize(block_path)
                # Convert bytes to KB for the analysis
                block_sizes.append(size_in_bytes / 1024.0)
            else:
                # Add 0 for non-existent (empty) blocks
                block_sizes.append(0)
    
    return block_sizes

def main():
    parser = argparse.ArgumentParser(
        description="Plot and compare the edge block size distribution of two GridGraph results using a histogram."
    )
    parser.add_argument('--baseline_dir', type=str, required=True, help="Path to the baseline grid directory.")
    parser.add_argument('--p_baseline', type=int, required=True, help="P value used for the baseline grid.")
    parser.add_argument('--dv_dir', type=str, required=True, help="Path to the degree-based grid directory.")
    parser.add_argument('--p_dv', type=int, required=True, help="P value used for the degree-based grid.")
    parser.add_argument('--dataset_name', type=str, required=True, help="Name of the dataset for the plot title (e.g., LiveJournal, Twitter).")
    args = parser.parse_args()

    # Get block sizes for both versions
    baseline_sizes_kb = get_block_sizes_kb(args.baseline_dir, args.p_baseline)
    dv_sizes_kb = get_block_sizes_kb(args.dv_dir, args.p_dv)

    if not baseline_sizes_kb or not dv_sizes_kb:
        print("Could not analyze one or both directories. Exiting.")
        return
        
    # For log scale, we should ignore zero-sized blocks as log(0) is undefined
    baseline_plot_data = [s for s in baseline_sizes_kb if s > 0]
    dv_plot_data = [s for s in dv_sizes_kb if s > 0]

    # --- Plotting the Histogram ---
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, ax = plt.subplots(figsize=(12, 8))

    # Create logarithmic bins that span the full range of the data
    min_val = min(min(baseline_plot_data), min(dv_plot_data))
    max_val = max(max(baseline_plot_data), max(dv_plot_data))
    log_bins = np.logspace(np.log10(min_val), np.log10(max_val), num=50)

    # Plot both histograms
    ax.hist(baseline_plot_data, bins=log_bins, alpha=0.7, label=f'Baseline (P={args.p_baseline})')
    ax.hist(dv_plot_data, bins=log_bins, alpha=0.7, label=f'Degree-based (P={args.p_dv})')

    # Set the x-axis to a log scale to handle the wide range of sizes
    ax.set_xscale('log')

    # Set labels and title
    ax.set_xlabel('Edge Block File Size (KB) [Log Scale]', fontsize=14)
    ax.set_ylabel('Number of Blocks (Count)', fontsize=14)
    ax.set_title(f'Histogram of Edge Block Sizes on {args.dataset_name} Dataset', fontsize=16, fontweight='bold')
    ax.legend(fontsize=12)
    ax.tick_params(axis='both', which='major', labelsize=12)
    
    # Save the figure
    output_filename = f'{args.dataset_name}_block_histogram.png'
    plt.savefig(output_filename, dpi=300, bbox_inches='tight')
    
    print(f"\n? Histogram plot saved successfully as '{output_filename}'")

if __name__ == '__main__':
    main()