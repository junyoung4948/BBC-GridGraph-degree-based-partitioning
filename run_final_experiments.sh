#!/bin/bash

# ==============================================================================
# GridGraph Final Experiment Automation Script (v2 - Using Internal Timers)
# ==============================================================================

## --- Configuration (Please verify these paths) --- ##

# GridGraph project root directory
PROJECT_ROOT="/data/kjuny000/BBC/GridGraph"

# Directory containing original .bin datasets
DATA_DIR="${PROJECT_ROOT}/data"

# Paths to the executables
PREPROCESS_BASE_BIN="${PROJECT_ROOT}/bin/preprocess"
PREPROCESS_DV_BIN="${PROJECT_ROOT}/bin/preprocess_dv"
PAGERANK_BASE_BIN="${PROJECT_ROOT}/bin/pagerank"
PAGERANK_DV_BIN="${PROJECT_ROOT}/bin/pagerank_dv"

# Directory to save log files and generated grid data
OUTPUT_ROOT_DIR="${PROJECT_ROOT}/experiment_outputs"

# PageRank iterations
ITERATIONS=20

## --- Experiment Variables --- ##

DATASETS=("LiveJournal" "twitter")
VERSIONS=("baseline" "dv")
P_VALUES=(4 8 16 32 64 128)
MEM_SIZES=(8 32 128)

# Create base output directory
mkdir -p "$OUTPUT_ROOT_DIR"

# ======================== Start Experiments ========================

echo "===== Starting GridGraph Final Experiments (using internal timers) =====" >&2
echo "Start Time: $(date)" >&2
echo "==================================================================" >&2

# Loop over Datasets
for DATASET in "${DATASETS[@]}"; do
    # Set dataset-specific parameters
    if [ "$DATASET" == "LiveJournal" ]; then
        V=4847571
        INPUT_BIN="${DATA_DIR}/soc-LiveJournal1.bin"
    elif [ "$DATASET" == "twitter" ]; then
        V=41652230
        INPUT_BIN="${DATA_DIR}/twitter-2010.bin"
    else
        echo "[Warning] Unknown dataset: $DATASET. Skipping." >&2
        continue
    fi

    # Loop over Versions (baseline vs. dv)
    for VERSION in "${VERSIONS[@]}"; do
        # Select the correct executables for the version
        if [ "$VERSION" == "baseline" ]; then
            PREPROCESS_BIN=$PREPROCESS_BASE_BIN
            PAGERANK_BIN=$PAGERANK_BASE_BIN
        else # dv
            PREPROCESS_BIN=$PREPROCESS_DV_BIN
            PAGERANK_BIN=$PAGERANK_DV_BIN
        fi

        # Loop over P values
        for P in "${P_VALUES[@]}"; do
            
            # --- 1. Preprocessing Step ---
            GRID_OUTPUT_DIR="${OUTPUT_ROOT_DIR}/${DATASET}_grid_${VERSION}_p${P}"
            PREPROCESS_LOG="${OUTPUT_ROOT_DIR}/${DATASET}_preprocess_${VERSION}_p${P}.log"
            
            echo -e "\n--- [Preprocessing] $DATASET | $VERSION | P=$P ---" >&2
            echo "Log file: $PREPROCESS_LOG" >&2

            $PREPROCESS_BIN -i "$INPUT_BIN" -o "$GRID_OUTPUT_DIR" -v $V -p $P -t 0 > "$PREPROCESS_LOG" 2>&1
            echo "Preprocessing finished." >&2

            # Loop over Memory sizes
            for MEM in "${MEM_SIZES[@]}"; do
                
                # --- 2. Pagerank Step ---
                PAGERANK_LOG="${OUTPUT_ROOT_DIR}/${DATASET}_pagerank_${VERSION}_p${P}_m${MEM}GB.log"

                echo -e "\n--- [Pagerank] $DATASET | $VERSION | P=$P | Mem=${MEM}GB ---" >&2
                echo "Log file: $PAGERANK_LOG" >&2

                echo "Clearing file system cache..." >&2
                sync
                echo 3 | sudo tee /proc/sys/vm/drop_caches > /dev/null
                echo "Cache cleared." >&2

                # [수정] 외부 time 유틸리티 제거
                sudo $PAGERANK_BIN "$GRID_OUTPUT_DIR" $ITERATIONS $MEM > "$PAGERANK_LOG" 2>&1
                
                echo "Pagerank run finished." >&2

            done # End Memory loop
        done # End P value loop
    done # End Version loop
done # End Dataset loop

echo -e "\n==================================================================" >&2
echo "All experiments finished." >&2
echo "End Time: $(date)" >&2
echo "==================================================================" >&2