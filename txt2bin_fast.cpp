#include <iostream>
#include <fstream>
#include <cstdint>
#include <algorithm>
#include <string>

int main(int argc, char ** argv) {
    if (argc != 3) {
        fprintf(stderr, "Usage: %s <input_text_file> <output_binary_file>\n", argv[0]);
        return 1;
    }

    std::ios_base::sync_with_stdio(false);
    std::cin.tie(NULL);

    std::ifstream fin(argv[1]);
    std::ofstream fout(argv[2], std::ios::binary);

    if (!fin.is_open() || !fout.is_open()) {
        fprintf(stderr, "Error opening files.\n");
        return 1;
    }

    // --- Progress Indicator: 1. Get total file size ---
    fin.seekg(0, std::ios::end);
    long long total_size_bytes = fin.tellg();
    fin.seekg(0, std::ios::beg);
    // --------------------------------------------------

    uint32_t src, dst;
    uint32_t max_vid = 0;
    std::string line;
    long long edge_count = 0;
    const int UPDATE_INTERVAL = 1000000; // Update progress every 1 million edges

    // Skip header comment lines
    while (fin.peek() == '#') {
        std::getline(fin, line);
    }

    // Main processing loop
    while (fin >> src >> dst) {
        fout.write(reinterpret_cast<const char*>(&src), sizeof(uint32_t));
        fout.write(reinterpret_cast<const char*>(&dst), sizeof(uint32_t));
        
        if (src > max_vid) max_vid = src;
        if (dst > max_vid) max_vid = dst;
        
        edge_count++;

        // --- Progress Indicator: 2. Print status periodically ---
        if (edge_count % UPDATE_INTERVAL == 0) {
            long long current_pos_bytes = fin.tellg();
            if (current_pos_bytes != -1) {
                double percentage = static_cast<double>(current_pos_bytes) / total_size_bytes * 100.0;
                // Use \r to overwrite the same line in the terminal
                printf("Progress: %.2f%% (%lld edges processed)\r", percentage, edge_count);
                fflush(stdout); // Ensure the output is displayed immediately
            }
        }
        // -------------------------------------------------------
    }
    
    // --- Progress Indicator: 3. Print final 100% ---
    // Ensure the line is cleared and shows 100% at the end.
    printf("Progress: 100.00%% (%lld edges processed)\n", edge_count);
    // -------------------------------------------------
    
    fin.close();
    fout.close();

    printf("|V| based on max_vid = %u\n", max_vid + 1);
    printf("Official node count from documentation = 41,652,230\n");

    return 0;
}