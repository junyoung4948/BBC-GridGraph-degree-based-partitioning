import os
import re
import argparse
import pandas as pd
import matplotlib.pyplot as plt
from collections import defaultdict

def parse_log_file(filepath):
    """Parses a single log file to extract all relevant timing data."""
    times = {}
    time_regex = re.compile(r'(\d+\.?\d*)\s+seconds')
    
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            match = time_regex.search(line)
            if not match: continue
            
            time_val = float(match.group(1))
            
            if "Phase 1 (Degree Calculation) took" in line: times['Pre_DegCalc'] = time_val
            elif "it takes" in line and "generate edge grid" in line: times['Pre_GridGen'] = time_val
            elif "degree calculation used" in line: times['PR_DegSetup'] = time_val
            elif "degree read used" in line: times['PR_DegSetup'] = time_val
            elif "iterations of pagerank took" in line: times['PR_Iter'] = time_val
    return times

def create_grouped_bar_chart(df, dataset_name):
    """Creates a grouped bar chart based on End-to-End time."""
    
    # Use 'Method' instead of 'Version'
    pivot_df = df.pivot(index='Memory(GB)', columns='Method', values='T_End_to_End(s)')
    
    # --- CHANGE: Rename columns for display ---
    display_names = {'dv': 'Degree-based', 'baseline': 'Baseline'}
    pivot_df.rename(columns=display_names, inplace=True)
    
    ax = pivot_df.plot(kind='bar', figsize=(12, 7), width=0.8, edgecolor='black')
    
    plt.title(f'End-to-End Time Comparison on {dataset_name.upper()} Dataset', fontsize=16)
    plt.xlabel('Memory(GB)', fontsize=12)
    plt.ylabel('End-to-End Time (seconds)', fontsize=12)
    plt.xticks(rotation=0)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    # Use 'Method' for the legend title
    plt.legend(title='Method')
    
    for container in ax.containers:
        ax.bar_label(container, fmt='%.2f', label_type='edge', padding=3)

    plt.tight_layout()
    filename = f"{dataset_name.lower()}_comparison.png"
    plt.savefig(filename)
    plt.close()
    print(f"[SUCCESS] Generated grouped bar chart: {filename}")

def create_end_to_end_stacked_chart(df):
    """Creates a stacked bar chart for the End-to-End time breakdown."""
    
    # Use 'Method' instead of 'Version'
    chart_data = df[(df['Dataset'] == 'twitter') & (df['Memory(GB)'] == 32)].set_index('Method')
    if chart_data.empty:
        print("[WARNING] Data for Twitter 32GB not found, skipping detailed stacked bar chart.")
        return

    # --- CHANGE: Create display labels for the x-axis ---
    display_names = {'dv': 'Degree-based', 'baseline': 'Baseline'}
    display_labels = chart_data.index.map(display_names)
    
    t_pre_degcalc = chart_data['T_Pre_DegCalc(s)']
    t_pre_gridgen = chart_data['T_Pre_GridGen(s)']
    t_pr_degsetup = chart_data['T_PR_DegSetup(s)']
    t_pr_iter = chart_data['T_PR_Iter(s)']

    fig, ax = plt.subplots(figsize=(10, 8))

    bottom1 = t_pre_degcalc
    bottom2 = bottom1 + t_pre_gridgen
    bottom3 = bottom2 + t_pr_degsetup

    # Use display_labels for the x-axis
    ax.bar(display_labels, t_pre_degcalc, label='T_Pre_DegCalc(s)', width=0.5)
    ax.bar(display_labels, t_pre_gridgen, bottom=bottom1, label='T_Pre_GridGen(s)', width=0.5)
    ax.bar(display_labels, t_pr_degsetup, bottom=bottom2, label='T_PR_DegSetup(s)', width=0.5)
    ax.bar(display_labels, t_pr_iter, bottom=bottom3, label='T_PR_Iter(s)', width=0.5)

    plt.title('End-to-End Time Breakdown (Twitter, 32GB)', fontsize=16)
    plt.xlabel('Method', fontsize=12) # Use 'Method' for the x-axis label
    plt.ylabel('Time (seconds)', fontsize=12)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.legend()
    
    offset = ax.get_ylim()[1] * 0.01 

    for i, method_name in enumerate(chart_data.index):
        total_time = chart_data.loc[method_name, 'T_End_to_End(s)']
        plt.text(i, total_time + offset, f'Total: {total_time:.2f}', ha='center', va='bottom')

    plt.tight_layout()
    filename = "twitter_32gb_end_to_end_detail.png"
    plt.savefig(filename)
    plt.close()
    print(f"[SUCCESS] Generated End-to-End stacked bar chart: {filename}")


def main():
    parser = argparse.ArgumentParser(description="Parse FINAL GridGraph experiment logs and generate a detailed report.")
    parser.add_argument('logs_directory', type=str, help="The directory containing final experiment log files.")
    parser.add_argument('-o', '--output', type=str, default='experiment_report.xlsx', help="Path to the output Excel file.")
    args = parser.parse_args()

    if not os.path.isdir(args.logs_directory):
        print(f"[ERROR] Directory not found -> {args.logs_directory}"); return

    all_runs = defaultdict(list)
    for filename in os.listdir(args.logs_directory):
        if not filename.endswith(".log"): continue
        parts = filename.replace(".log", "").split('_')
        try:
            run_type = parts[1]
            if run_type not in ["preprocess", "pagerank"]: continue
            dataset, version, p_val = parts[0], parts[2], int(parts[3][1:])
            m_val = int(parts[4][1:-2]) if run_type == "pagerank" else 0
            key = (dataset, version, p_val, m_val)
            all_runs[key].append(parse_log_file(os.path.join(args.logs_directory, filename)))
        except (IndexError, ValueError):
            print(f"[INFO] Could not parse filename: {filename}. Skipping.")
    
    if not all_runs: print("[ERROR] No log files found or parsed. Exiting."); return

    report_rows = []
    avg_preproc_times = {}
    for key, runs in all_runs.items():
        dataset, version, p_val, m_val = key
        if m_val == 0:
            avg_preproc_times[(dataset, version, p_val)] = pd.DataFrame(runs).mean().to_dict()

    for key, runs in all_runs.items():
        dataset, version, p_val, m_val = key
        if m_val == 0: continue
        pagerank_avg = pd.DataFrame(runs).mean().to_dict()
        preproc_avg = avg_preproc_times.get((dataset, version, p_val), {})
        
        T_Pre_DegCalc = preproc_avg.get('Pre_DegCalc', 0) if version == 'dv' else 0
        T_Pre_GridGen = preproc_avg.get('Pre_GridGen', 0)
        T_PR_DegSetup = pagerank_avg.get('PR_DegSetup', 0)
        T_PR_Iter = pagerank_avg.get('PR_Iter', 0)

        total_preproc = T_Pre_GridGen + T_Pre_DegCalc
        total_pagerank = T_PR_DegSetup + T_PR_Iter
        total_end_to_end = total_preproc + total_pagerank
        
        report_row = {
            'Dataset': dataset, 
            'Method': version, # Use 'Method' instead of 'Version'
            'P': p_val, 'Memory(GB)': m_val,
            'T_End_to_End(s)': total_end_to_end, 'T_Pre_Total(s)': total_preproc, 'T_PR_Total(s)': total_pagerank,
            'T_Pre_DegCalc(s)': T_Pre_DegCalc, 'T_Pre_GridGen(s)': T_Pre_GridGen,
            'T_PR_DegSetup(s)': T_PR_DegSetup, 'T_PR_Iter(s)': T_PR_Iter,
        }
        report_rows.append(report_row)
        
    # Use 'Method' for sorting
    report_df = pd.DataFrame(report_rows).sort_values(by=['Dataset', 'Method', 'P', 'Memory(GB)'])

    print("\n" + "="*30 + " Generating Visualizations " + "="*30)
    if not report_df.empty:
        for dataset in ['LiveJournal', 'twitter']:
            dataset_df = report_df[report_df['Dataset'] == dataset]
            if not dataset_df.empty:
                create_grouped_bar_chart(dataset_df, dataset)
            else:
                print(f"[WARNING] Data for '{dataset}' not found, skipping its grouped bar chart.")
                print(f"[INFO] Please check if '{dataset}_... .log' files exist in '{args.logs_directory}'.")

        create_end_to_end_stacked_chart(report_df)
    else:
        print("[WARNING] Report DataFrame is empty. Skipping visualization generation.")

    print("\n" + "="*30 + " Generating Reports " + "="*30)
    try:
        report_df.to_excel(args.output, index=False, sheet_name='Experiment_Report')
        print(f"[SUCCESS] Generated Excel report: {args.output}")
    except Exception as e:
        print(f"[ERROR] Could not write to Excel file: {e}")
    
    # --- For Console Display ---
    # Create a copy for display modifications
    display_df = report_df.copy()
    # Rename 'dv' to 'Degree-based' for the table as well
    display_df['Method'] = display_df['Method'].replace({'dv': 'Degree-based', 'baseline': 'Baseline'})
    
    pd.set_option('display.max_rows', 500); pd.set_option('display.width', 220)
    for col in display_df.columns:
        if '(s)' in col: display_df[col] = display_df[col].map('{:.2f}'.format)
            
    print("\n" + "="*30 + " Final Detailed Experiment Report " + "="*30)
    print(display_df.to_string(index=False))
    print("="*94)

if __name__ == '__main__':
    main()