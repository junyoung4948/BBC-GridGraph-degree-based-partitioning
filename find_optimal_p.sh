#!/bin/bash

# ====================================================================================
# PHASE 1 (Clean Version): Find Optimal P with dataset-specific methodologies
# ====================================================================================

## --- Configuration --- ##
PROJECT_ROOT="/data/kjuny000/BBC/GridGraph"
DATA_DIR="${PROJECT_ROOT}/data"
PREPROCESS_BASE_BIN="${PROJECT_ROOT}/bin/preprocess"
PREPROCESS_DV_BIN="${PROJECT_ROOT}/bin/preprocess_dv"
PAGERANK_BASE_BIN="${PROJECT_ROOT}/bin/pagerank"
PAGERANK_DV_BIN="${PROJECT_ROOT}/bin/pagerank_dv"
TMP_RESULTS_DIR="${PROJECT_ROOT}/p_test_hybrid_results"
ITERATIONS=20
FIXED_MEM_FOR_P_TEST=128
REPETITIONS_LJ=5
REPETITIONS_TW=3

## --- Experiment Variables --- ##
DATASETS=("LiveJournal" "twitter")
VERSIONS=("baseline" "dv")
P_VALUES=(4 8 16 32 64 128)

mkdir -p "$TMP_RESULTS_DIR"

# ======================== Start Hybrid P-value Tests ========================
echo "===== Starting Hybrid P-value Test (Cleaned-up Version) =====" >&2

FINAL_SUMMARY_FILE="${TMP_RESULTS_DIR}/_final_optimal_p_summary.txt"
echo "Optimal P Final Summary (Hybrid Methodology)" > "$FINAL_SUMMARY_FILE"
echo "==========================================" >> "$FINAL_SUMMARY_FILE"

for DATASET in "${DATASETS[@]}"; do
    # Set dataset-specific parameters
    if [ "$DATASET" == "LiveJournal" ]; then V=4847571; INPUT_BIN="${DATA_DIR}/soc-LiveJournal1.bin"; REPETITIONS=$REPETITIONS_LJ; fi
    if [ "$DATASET" == "twitter" ]; then V=41652230; INPUT_BIN="${DATA_DIR}/twitter-2010.bin"; REPETITIONS=$REPETITIONS_TW; fi

    for VERSION in "${VERSIONS[@]}"; do
        BEST_P_FOR_CONFIG=0
        MIN_AVG_TIME="999999.0"

        echo -e "\n\n### Analyzing Configuration: $DATASET / $VERSION ###" >&2
        
        # Select executables based on version
        if [ "$VERSION" == "baseline" ]; then PREPROCESS_BIN=$PREPROCESS_BASE_BIN; PAGERANK_BIN=$PAGERANK_BASE_BIN; else PREPROCESS_BIN=$PREPROCESS_DV_BIN; PAGERANK_BIN=$PAGERANK_DV_BIN; fi

        # Announce methodology
        if [ "$DATASET" == "LiveJournal" ]; then
            echo "--- Applying End-to-End Time Methodology (Repetitions: $REPETITIONS) ---" >&2
        else # twitter
            echo "--- Applying Pagerank-Only Time Methodology (Repetitions: $REPETITIONS) ---" >&2
        fi

        for P in "${P_VALUES[@]}"; do
            GRID_OUTPUT_DIR="${TMP_RESULTS_DIR}/${DATASET}_grid_${VERSION}_p${P}"
            echo -e "\n--- Testing P=$P ---" >&2
            
            # For Twitter, preprocess once outside the repetition loop
            if [ "$DATASET" == "twitter" ]; then
                echo "  Preprocessing once for P=$P..." >&2
                $PREPROCESS_BIN -i "$INPUT_BIN" -o "$GRID_OUTPUT_DIR" -v $V -p $P -t 0 > /dev/null 2>&1
            fi
            
            total_time_for_avg=0.0
            run_details=""

            for i in $(seq 1 $REPETITIONS); do
                echo -n "    Run $i/$REPETITIONS: " >&2
                
                current_run_metric_time=0
                
                # LiveJournal: Measure End-to-End Time (Preproc + Pagerank)
                if [ "$DATASET" == "LiveJournal" ]; then
                    PREPROC_LOG_FILE=$(mktemp)
                    PAGERANK_LOG_FILE=$(mktemp)

                    $PREPROCESS_BIN -i "$INPUT_BIN" -o "$GRID_OUTPUT_DIR" -v $V -p $P -t 0 > "$PREPROC_LOG_FILE" 2>&1
                    sudo /usr/local/bin/clear_caches.sh
                    sudo $PAGERANK_BIN "$GRID_OUTPUT_DIR" $ITERATIONS $FIXED_MEM_FOR_P_TEST > "$PAGERANK_LOG_FILE" 2>&1
                    
                    preproc_grid_gen_time=$(grep "generate edge grid" "$PREPROC_LOG_FILE" | awk '{print $3}')
                    total_preproc_time=${preproc_grid_gen_time:-0}
                    if [ "$VERSION" == "dv" ]; then
                        preproc_degree_time=$(grep "Degree Calculation) took" "$PREPROC_LOG_FILE" | awk '{print $6}')
                        total_preproc_time=$(echo "$preproc_grid_gen_time + ${preproc_degree_time:-0}" | bc)
                    fi
                    
                    iter_time=$(grep "iterations of pagerank took" "$PAGERANK_LOG_FILE" | awk '{print $6}')
                    setup_time=0
                    if [ "$VERSION" == "baseline" ]; then setup_time=$(grep "degree calculation used" "$PAGERANK_LOG_FILE" | awk '{print $4}'); else setup_time=$(grep "degree read used" "$PAGERANK_LOG_FILE" | awk '{print $4}'); fi
                    total_pagerank_time=$(echo "${iter_time:-0} + ${setup_time:-0}" | bc)

                    current_run_metric_time=$(echo "$total_preproc_time + $total_pagerank_time" | bc)
                    echo "Preproc(${total_preproc_time}s) + Pagerank(${total_pagerank_time}s) = ${current_run_metric_time}s" >&2

                    rm "$PREPROC_LOG_FILE" "$PAGERANK_LOG_FILE"
                
                # Twitter: Measure Pagerank Time Only
                else 
                    PAGERANK_LOG_FILE=$(mktemp)
                    sudo /usr/local/bin/clear_caches.sh
                    sudo $PAGERANK_BIN "$GRID_OUTPUT_DIR" $ITERATIONS $FIXED_MEM_FOR_P_TEST > "$PAGERANK_LOG_FILE" 2>&1

                    iter_time=$(grep "iterations of pagerank took" "$PAGERANK_LOG_FILE" | awk '{print $6}')
                    setup_time=0
                    if [ "$VERSION" == "baseline" ]; then setup_time=$(grep "degree calculation used" "$PAGERANK_LOG_FILE" | awk '{print $4}'); else setup_time=$(grep "degree read used" "$PAGERANK_LOG_FILE" | awk '{print $4}'); fi
                    
                    current_run_metric_time=$(echo "${iter_time:-0} + ${setup_time:-0}" | bc)
                    echo "Pagerank Total Time: ${current_run_metric_time}s" >&2
                    
                    rm "$PAGERANK_LOG_FILE"
                fi
                
                run_details+="${current_run_metric_time}s "
                total_time_for_avg=$(echo "$total_time_for_avg + $current_run_metric_time" | bc)
            done
            
            avg_time=$(echo "scale=4; $total_time_for_avg / $REPETITIONS" | bc)
            
            printf "  -> Average Time for P=%-3d: %.4f s  (Runs: %s)\n" "$P" "$avg_time" "$run_details" >&2

            is_better=$(echo "$avg_time < $MIN_AVG_TIME" | bc -l)
            if [ "$is_better" -eq 1 ]; then
                MIN_AVG_TIME=$avg_time
                BEST_P_FOR_CONFIG=$P
            fi

        done # P loop

        printf "\n  >>> Optimal P for [%s, %s] is %d with average time %.4f s <<<\n" "$DATASET" "$VERSION" "$BEST_P_FOR_CONFIG" "$MIN_AVG_TIME" >&2
        echo "$DATASET,${VERSION},${BEST_P_FOR_CONFIG}" >> "$FINAL_SUMMARY_FILE"

    done # Version loop
done # Dataset loop

echo -e "\n==================================================================" >&2
echo "Hybrid P-value test finished. Summary saved to '$FINAL_SUMMARY_FILE'." >&2
cat "$FINAL_SUMMARY_FILE" >&2
echo "==================================================================" >&2