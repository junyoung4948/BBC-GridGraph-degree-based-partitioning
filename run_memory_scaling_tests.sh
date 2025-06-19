#!/bin/bash

# ========================================================================================
# PHASE 2 (Corrected): Run final tests with repetitions for accuracy
# ========================================================================================

declare -A OPTIMAL_P
OPTIMAL_P["LiveJournal,baseline"]=64 
OPTIMAL_P["LiveJournal,dv"]=64        
OPTIMAL_P["twitter,baseline"]=128     
OPTIMAL_P["twitter,dv"]=16       
# ----------------------------------------- ##

## --- Configuration --- ##
PROJECT_ROOT="/data/kjuny000/BBC/GridGraph"
DATA_DIR="${PROJECT_ROOT}/data"
PREPROCESS_BASE_BIN="${PROJECT_ROOT}/bin/preprocess"
PREPROCESS_DV_BIN="${PROJECT_ROOT}/bin/preprocess_dv"
PAGERANK_BASE_BIN="${PROJECT_ROOT}/bin/pagerank"
PAGERANK_DV_BIN="${PROJECT_ROOT}/bin/pagerank_dv"
FINAL_RESULTS_DIR="${PROJECT_ROOT}/final_results"
ITERATIONS=20
REPETITIONS=3 # 최종 실험 반복 횟수

## --- Experiment Variables --- ##
DATASETS=("LiveJournal" "twitter")
VERSIONS=("baseline" "dv")
MEM_SIZES=(8 32 128)

mkdir -p "$FINAL_RESULTS_DIR"

# ======================== Start Final Tests ========================
echo "===== Starting Phase 2: Memory Scaling Tests (Repetitions: $REPETITIONS) =====" >&2

for DATASET in "${DATASETS[@]}"; do
    if [ "$DATASET" == "LiveJournal" ]; then V=4847571; INPUT_BIN="${DATA_DIR}/soc-LiveJournal1.bin"; fi
    if [ "$DATASET" == "twitter" ]; then V=41652230; INPUT_BIN="${DATA_DIR}/twitter-2010.bin"; fi

    for VERSION in "${VERSIONS[@]}"; do
        P=${OPTIMAL_P["$DATASET,$VERSION"]}
        
        if [ -z "$P" ]; then
            echo "[Error] Optimal P for $DATASET, $VERSION is not set. Skipping." >&2
            continue
        fi

        GRID_OUTPUT_DIR="${FINAL_RESULTS_DIR}/${DATASET}_grid_${VERSION}_p${P}_optimal"
        PREPROCESS_LOG="${FINAL_RESULTS_DIR}/${DATASET}_preprocess_${VERSION}_p${P}.log"
        
        echo -e "\n--- [Preprocessing] $DATASET | $VERSION | Optimal P=$P ---" >&2
        
        if [ "$VERSION" == "baseline" ]; then PREPROCESS_BIN=$PREPROCESS_BASE_BIN; PAGERANK_BIN=$PAGERANK_BASE_BIN; else PREPROCESS_BIN=$PREPROCESS_DV_BIN; PAGERANK_BIN=$PAGERANK_DV_BIN; fi
        
        if [ ! -d "$GRID_OUTPUT_DIR" ]; then
            echo "Grid data not found. Running preprocessing..." >&2
            $PREPROCESS_BIN -i "$INPUT_BIN" -o "$GRID_OUTPUT_DIR" -v $V -p $P -t 0 > "$PREPROCESS_LOG" 2>&1
            echo "Preprocessing finished." >&2
        else
            echo "Grid data already exists. Skipping preprocessing." >&2
        fi

        for MEM in "${MEM_SIZES[@]}"; do
            # [수정] 반복 실행을 위한 루프 추가
            for i in $(seq 1 $REPETITIONS); do
                # [수정] 각 실행마다 고유한 로그 파일 이름 생성
                PAGERANK_LOG="${FINAL_RESULTS_DIR}/${DATASET}_pagerank_${VERSION}_p${P}_m${MEM}GB_run${i}.log"

                echo -e "\n--- [Pagerank Repetition $i/$REPETITIONS] $DATASET | $VERSION | P=$P | Mem=${MEM}GB ---" >&2
                echo "Log file: $PAGERANK_LOG" >&2

                echo "Clearing file system cache..." >&2
                sudo /usr/local/bin/clear_caches.sh
                echo "Cache cleared. Running Pagerank..." >&2

                sudo $PAGERANK_BIN "$GRID_OUTPUT_DIR" $ITERATIONS $MEM > "$PAGERANK_LOG" 2>&1
                
                echo "Run $i finished." >&2
            done # End Repetition loop
        done # End Memory loop
    done # End Version loop
done # End Dataset loop

echo -e "\n===== All final experiments finished. Please analyze logs in '$FINAL_RESULTS_DIR'. =====" >&2