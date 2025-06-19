import os
import argparse
import numpy as np
import matplotlib.pyplot as plt

# Edge is composed of two 4-byte VertexIDs
EDGE_SIZE = 8

def get_block_sizes(directory: str, p: int):
    """
    Scans a grid directory, collects the file size of all PxP blocks.
    Returns a sorted list of block sizes in bytes.
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
                block_sizes.append(size_in_bytes)
            else:
                block_sizes.append(0)
    
    block_sizes.sort()
    return block_sizes

def main():
    parser = argparse.ArgumentParser(
        description="Plot and compare the edge block size distribution of two GridGraph partitioning results."
    )
    parser.add_argument('--baseline_dir', type=str, required=True, help="Path to the baseline grid directory.")
    parser.add_argument('--p_baseline', type=int, required=True, help="P value used for the baseline grid.")
    parser.add_argument('--dv_dir', type=str, required=True, help="Path to the degree-based grid directory.")
    parser.add_argument('--p_dv', type=int, required=True, help="P value used for the degree-based grid.")
    parser.add_argument('--dataset_name', type=str, required=True, help="Name of the dataset for the plot title (e.g., LiveJournal, Twitter).")
    args = parser.parse_args()

    baseline_sizes = get_block_sizes(args.baseline_dir, args.p_baseline)
    dv_sizes = get_block_sizes(args.dv_dir, args.p_dv)

    if not baseline_sizes or not dv_sizes:
        print("Could not analyze one or both directories. Exiting.")
        return

    baseline_kb = np.array(baseline_sizes) / 1024
    dv_kb = np.array(dv_sizes) / 1024
    
    baseline_std = np.std(baseline_kb)
    dv_std = np.std(dv_kb)

    x_baseline = np.arange(1, len(baseline_kb) + 1)
    x_dv = np.arange(1, len(dv_kb) + 1)

    plt.style.use('seaborn-v0_8-whitegrid')
    fig, ax = plt.subplots(figsize=(12, 8))

    ax.scatter(x_baseline, baseline_kb, label=f'Baseline (P={args.p_baseline})', s=10, alpha=0.8)
    ax.scatter(x_dv, dv_kb, label=f'Degree-based (P={args.p_dv})', s=10, alpha=0.8)

    ax.set_xscale('log'); ax.set_yscale('log')
    ax.set_xlabel('Sorted Order (small -> large)', fontsize=14)
    ax.set_ylabel('Edge Block File Size (KB)', fontsize=14)
    ax.set_title(f'Edge Block Size Distribution on {args.dataset_name} Dataset', fontsize=16, fontweight='bold')
    ax.legend(fontsize=12, loc='upper left') 
    ax.tick_params(axis='both', which='major', labelsize=12)

    reduction = ((baseline_std - dv_std) / baseline_std) * 100 if baseline_std > 0 else 0
    
    stats_text = (f'Std. Deviation:\n'
                  f'  Baseline: {baseline_std:,.0f} KB\n'
                  f'  Degree-based: {dv_std:,.0f} KB\n\n'
                  f'Reduction: {reduction:.1f}%')

    props = dict(boxstyle='round,pad=0.5', facecolor='wheat', alpha=0.7)

    ax.text(0.95, 0.35, stats_text, transform=ax.transAxes, fontsize=12,
            verticalalignment='top', horizontalalignment='right', bbox=props)
    # ---------------------------------------------------
    
    output_filename = f'{args.dataset_name}_block_distribution_comparison.png'
    plt.savefig(output_filename, dpi=300, bbox_inches='tight')
    
    print(f"\n? Plot with statistics saved successfully as '{output_filename}'")

if __name__ == '__main__':
    main()