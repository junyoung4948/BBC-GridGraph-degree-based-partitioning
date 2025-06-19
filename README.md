# GridGraph
A large scale graph processing framework on a single machine.

## Compilation
Compilers supporting basic C++11 features (lambdas, threads, etc.) and OpenMP are required.

To compile:
```
make
```

## Preprocessing
Before running applications on a graph, GridGraph needs to partition the original edge list into the grid format.

Two types of edge list files are supported:
- Unweighted. Edges are tuples of <4 byte source, 4 byte destination>.
- Weighted. Edges are tuples of <4 byte source, 4 byte destination, 4 byte float typed weight>.

To partition the edge list:
```
./bin/preprocess -i [input path] -o [output path] -v [vertices] -p [partitions] -t [edge type: 0=unweighted, 1=weighted]
```
For example, we want to partition the unweighted [LiveJournal](http://snap.stanford.edu/data/soc-LiveJournal1.html) graph into a 4x4 grid:
```
./bin/preprocess -i /data/LiveJournal -o /data/LiveJournal_Grid -v 4847571 -p 4 -t 0
```

> You may need to raise the limit of maximum open file descriptors (./tools/raise\_ulimit\_n.sh).

## Running Applications
To run the applications, just give the path of the grid format and the memory budge (unit in GB), as well as other necessary program parameters (e.g. the starting vertex of BFS, the number of iterations of PageRank, etc.):

### BFS
```
./bin/bfs [path] [start vertex id] [memory budget]
```

### WCC
```
./bin/wcc [path] [memory budget]
```

### SpMV
```
./bin/spmv [path] [memory budget]
```

### PageRank
```
./bin/pagerank [path] [number of iterations] [memory budget]
```

For example, to run 20 iterations of PageRank on the (grid partitioned) [LiveJournal](http://snap.stanford.edu/data/soc-LiveJournal1.html) graph using a machine with 8 GB RAM:
```
./bin/pagerank /data/LiveJournal_Grid 20 8
```

## Resources
Xiaowei Zhu, Wentao Han and Wenguang Chen. [GridGraph: Large-Scale Graph Processing on a Single Machine Using 2-Level Hierarchical Partitioning](https://www.usenix.org/system/files/conference/atc15/atc15-paper-zhu.pdf). Proceedings of the 2015 USENIX Annual Technical Conference, pages 375-386.

To cite GridGraph, you can use the following BibTeX entry:
```
@inproceedings {zhu2015gridgraph,
author = {Xiaowei Zhu and Wentao Han and Wenguang Chen},
title = {GridGraph: Large-Scale Graph Processing on a Single Machine Using 2-Level Hierarchical Partitioning},
booktitle = {2015 USENIX Annual Technical Conference (USENIX ATC 15)},
year = {2015},
month = Jul,
isbn = {978-1-931971-225},
address = {Santa Clara, CA},
pages = {375--386},
url = {https://www.usenix.org/conference/atc15/technical-session/presentation/zhu},
publisher = {USENIX Association},
}
```

# Evaluating Degree-Based Partitioning in GridGraph

This repository contains a modified version of GridGraph that implements a novel degree-based partitioning method. The goal is to improve the load balancing and overall performance of large-scale graph processing on a single machine.

This document provides a step-by-step guide to reproduce the performance evaluation experiments that compare the proposed **Degree-Based (DV)** partitioning against the original **Baseline** (ID-based) method using the PageRank algorithm.

## Table of Contents
1. [Prerequisites](#1-prerequisites)
2. [Step 1: Setup and Compilation](#step-1-setup-and-compilation)
3. [Step 2: Dataset Preparation](#step-2-dataset-preparation)
4. [Step 3: Running the Experiments](#step-3-running-the-experiments)
    - [Phase 1: Finding Optimal P](#phase-1-finding-optimal-p)
    - [Phase 2: Final Performance Measurement](#phase-2-final-performance-measurement)
5. [Step 4: Analyzing Results](#step-4-analyzing-results)
6. [Appendix: Sudo Configuration for Automation](#appendix-sudo-configuration-for-automation)

---

## 1. Prerequisites

To reproduce these experiments, the following environment is required:

* A Linux-based OS (e.g., Ubuntu 16.04 or newer)
* `g++` compiler (e.g., v5.4.0 or newer) and `make`
* Standard command-line tools: `wget`, `gunzip`
* `python3` and `pip`
* Required Python libraries: `pandas`, `openpyxl`
    ```bash
    pip install pandas openpyxl
    ```
* `sudo` privileges are necessary to clear the file system cache for accurate measurements.

## Step 1: Setup and Compilation

1.  **Clone this Repository**:
    ```bash
    git clone <URL_of_your_GitHub_repository>
    cd <repository_name>/
    ```

2.  **Verify Source Files**:
    This repository should contain all the modified source code and scripts needed for the experiments, including:
    * `tools/preprocess.cpp` (Baseline)
    * `tools/preprocess_dv.cpp` (Degree-based)
    * `apps/pagerank.cpp` (Baseline)
    * `apps/pagerank_dv.cpp` (Degree-based)
    * `tools/txt2bin_fast.cpp`
    * `find_optimal_p_hybrid.sh`
    * `run_memory_scaling_tests.sh`
    * `parse_results.py`

3.  **Compile the Source Code**:
    The provided `Makefile` should be configured to build all necessary executables. Run `make` to compile them.
    ```bash
    make
    ```
    After compilation, the following binaries should be present in the `bin/` directory.

## Step 2: Dataset Preparation

The large dataset files are not included in this repository. You must download and convert them manually.

1.  **Create Data Directory**:
    ```bash
    mkdir -p data
    cd data/
    ```

2.  **Download and Decompress Datasets**:
    ```bash
    # LiveJournal Dataset (~105MB compressed)
    wget [https://snap.stanford.edu/data/soc-LiveJournal1.txt.gz](https://snap.stanford.edu/data/soc-LiveJournal1.txt.gz)
    gunzip soc-LiveJournal1.txt.gz

    # Twitter Dataset (~1.4GB compressed)
    wget [https://snap.stanford.edu/data/twitter-2010.txt.gz](https://snap.stanford.edu/data/twitter-2010.txt.gz)
    gunzip twitter-2010.txt.gz
    ```

3.  **Convert Text Files to Binary Format**:
    Use the compiled `txt2bin_fast` tool. Note the `|V|=...` output for each dataset, as you will need these vertex counts for the experiment scripts.
    ```bash
    # Move back to the project root directory
    cd ../
    
    # Convert LiveJournal
    ./bin/txt2bin_fast ./data/soc-LiveJournal1.txt ./data/soc-LiveJournal1.bin
    # Expected output contains: |V|=4847571

    # Convert Twitter
    ./bin/txt2bin_fast ./data/twitter-2010.txt ./data/twitter-2010.bin
    # Expected output contains: Official node count from documentation = 41,652,230
    ```

## Step 3: Running the Experiments

The experiment is conducted in two phases.

**IMPORTANT**: Before starting, you must complete the one-time setup described in the **[Appendix: Sudo Configuration for Automation](#appendix-sudo-configuration-for-automation)** section. This is required for the scripts to run automatically without password prompts.

### Phase 1: Finding Optimal P

This phase finds the optimal partition value `P` for each of the 4 configurations.

1.  **Grant Execute Permission**:
    ```bash
    chmod +x find_optimal_p_hybrid.sh
    ```
2.  **Run**: This script may take a very long time. 
    ```bash
    nohup ./find_optimal_p_hybrid.sh > p_test_summary.log 2>&1 &
    ```
3.  **Get Results**: Once the script is complete, you can find the determined optimal `P` value for each of the 4 configurations in _final_optimal_p_summary.txt. 

### Phase 2: Final Performance Measurement

1.  **Configure Optimal P values**: Open the `run_memory_scaling_tests.sh` script in an editor. In the section marked `USER ACTION REQUIRED`, replace the placeholder values with the optimal `P` values you found in Phase 1.

2.  **Grant Execute Permission**:
    ```bash
    chmod +x run_memory_scaling_tests.sh
    ```
3.  **Run**: This script runs the final tests across different memory sizes (8, 32, 128GB).
    ```bash
    nohup ./run_memory_scaling_tests.sh > final_experiments.log 2>&1 &
    ```
    This will generate detailed logs for each experimental run in the `final_results/` directory.

## Step 4: Analyzing Results

After all experiments in Phase 2 are complete, the `final_results/` directory will contain all the necessary log files. This section describes how to use the provided Python scripts to generate the final tables and figures for the paper.

### 4.1. Generating the Performance Report Table

This step creates a comprehensive Excel spreadsheet summarizing all performance metrics.

1.  **Run the Parsing Script**:
    Execute the `parse_results.py` script, pointing it to the directory containing the final logs.

    ```bash
    python parse_results.py final_results/
    ```

2.  **Get the Final Report**:
    The script will analyze all logs, calculate the average times and ratios according to the defined methodology, and print a summary to the console. More importantly, it will create a file named **`final_experiment_report.xlsx`** in your project's root directory. This Excel file contains the complete, detailed breakdown of all experiment results, ready for creating the final tables for your paper.

### 4.2. Generating the Block Distribution Plot

This step creates the log-log plot to visually compare the uniformity of block sizes between the two partitioning methods, similar to Figure 2 in the original GridGraph paper.

1.  **Run the Plotting Script**:
    Execute the `plot_block_distribution.py` or `plot_block_histogram.py` script. You must provide the paths to the two grid directories you want to compare, along with their corresponding P values.

    **Example for the Twitter dataset (using its P = 32):**
    ```bash
    python plot_block_distribution.py --baseline_dir ./data/twitter_grid --p_baseline 32 --dv_dir ./data/twitter_grid_dv/ --p_dv 32 --dataset_name "Twitter"
    ```

2.  **Get the Final Plot**:
    The script will generate a `.png` image file (e.g., `Twitter_block_distribution_comparison.png`, `Twitter_block_histogram.png`) in your project's root directory. It will also print a quantitative analysis of the block size uniformity to the console, including the standard deviation for each method and the percentage improvement. This plot and the accompanying statistical analysis provide strong evidence for the effectiveness of the degree-based balancing approach.

---

## Appendix: Sudo Configuration for Automation

Since it is important to clear the cache every iteration of experiment, I've created a wrapper script for cache clearing to run sudo non-interatively. Please modify the code line in the sh files with other code for clearing caches.
```bash
sudo /usr/local/bin/clear_caches.sh
```


1.  **Create a Wrapper Script for Cache Clearing**:
    ```bash
    sudo nano /usr/local/bin/clear_caches.sh
    ```
    Paste the following into the editor and save:
    ```bash
    #!/bin/bash
    sync
    echo 3 > /proc/sys/vm/drop_caches
    ```

2.  **Set Secure Permissions**:
    ```bash
    sudo chown root:root /usr/local/bin/clear_caches.sh
    sudo chmod 755 /usr/local/bin/clear_caches.sh
    ```

3.  **Edit `sudoers` File**: Run `sudo visudo`. At the end of the file, add the following lines, replacing `user` with your username and verifying the full paths to your binaries.
    ```
    # Allow user to run experiment commands without a password
    user ALL=(ALL) NOPASSWD: GridGraph/bin/pagerank
    user ALL=(ALL) NOPASSWD: GridGraph/bin/pagerank_dv
    user ALL=(ALL) NOPASSWD: /usr/local/bin/clear_caches.sh
    ```