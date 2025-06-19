/*
Copyright (c) 2014-2015 Xiaowei Zhu, Tsinghua University

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
*/

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <malloc.h>
#include <errno.h>
#include <assert.h>
#include <string.h>
#include <fstream>
#include <cassert>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>
#include <thread>
#include <atomic>
#include "core/constants.hpp"
#include "core/type.hpp"
#include "core/filesystem.hpp"
#include "core/queue.hpp"
#include "core/partition.hpp"
#include "core/time.hpp"
#include "core/atomic.hpp"

long PAGESIZE = 4096;

#include <numeric>

struct DegreeInfo {
    std::vector<uint32_t> out_degree;
    std::vector<uint32_t> in_degree;
    long long total_edges;
};

void calculate_and_save_degrees(std::string input, std::string output, VertexId vertices, int edge_type, DegreeInfo& out_info) {
	printf("Starting Phase 1: Calculating and saving degrees...\n");
	double function_start_time = get_time();
	int parallelism = std::thread::hardware_concurrency();
	int edge_unit;
	long long edges; // total_edges를 담을 변수
	switch (edge_type) {
		case 0:
			edge_unit = sizeof(VertexId) * 2;
			edges = file_size(input) / edge_unit;
			break;
		case 1:
			edge_unit = sizeof(VertexId) * 2 + sizeof(Weight);
			edges = file_size(input) / edge_unit;
			break;
		default:
			fprintf(stderr, "edge type (%d) is not supported.\n", edge_type);
			exit(-1);
	}

	std::vector<std::atomic<uint32_t>> out_degree(vertices);
    std::vector<std::atomic<uint32_t>> in_degree(vertices);

	// 멀티스레딩 설정 (기존 Pass 1과 동일)
	char ** buffers = new char * [parallelism*2];
	bool * occupied = new bool [parallelism*2];
	for (int i=0;i<parallelism*2;i++) {
		buffers[i] = (char *)memalign(PAGESIZE, IOSIZE);
		occupied[i] = false;
	}
	Queue<std::tuple<int, long> > tasks(parallelism);
	std::vector<std::thread> threads;
	for (int ti = 0; ti < parallelism; ti++) {
		threads.emplace_back([&]() {
			VertexId source, target;
			while (true) {
				auto task = tasks.pop();
				if (std::get<0>(task) == -1) break;
				char* buffer = buffers[std::get<0>(task)];
				for (long pos = 0; pos < std::get<1>(task); pos += edge_unit) {
					source = *(VertexId*)(buffer + pos);
					target = *(VertexId*)(buffer + pos + sizeof(VertexId));
					if (source < vertices && target < vertices) {
						out_degree[source]++;
						in_degree[target]++;
					}
				}
				occupied[std::get<0>(task)] = false;
			}
		});
	}

	int fin = open(input.c_str(), O_RDONLY);
    assert(fin != -1);
    long total_bytes = file_size(input);
    long read_bytes = 0;
    int cursor = 0;
    while (true) {
        long bytes = read(fin, buffers[cursor], IOSIZE);
        if (bytes <= 0) break; // 0 또는 에러(-1) 시 종료
        occupied[cursor] = true;
        tasks.push(std::make_tuple(cursor, bytes));
        read_bytes += bytes;
        // printf("progress: %.2f%%\r", 100. * read_bytes / total_bytes);
        // fflush(stdout);
        while (occupied[cursor]) {
            cursor = (cursor + 1) % (parallelism * 2);
        }
    }
    close(fin);

    // (2) 스레드 종료 신호 전송 및 join() 호출 루프 추가
    for (int ti=0; ti<parallelism; ti++) {
        tasks.push(std::make_tuple(-1, 0)); // 모든 스레드에 종료 신호
    }
    for (int ti=0; ti<parallelism; ti++) {
        threads[ti].join(); // 모든 스레드가 끝날 때까지 대기
    }
    

	// atomic 벡터에서 일반 벡터로 변환
    std::vector<uint32_t> final_out_degree(vertices);
    std::vector<uint32_t> final_in_degree(vertices);
    for(VertexId i = 0; i < vertices; ++i) {
        final_out_degree[i] = out_degree[i].load();
        final_in_degree[i] = in_degree[i].load();
    }
    
	// PageRank 등에서 사용하기 위해 파일로 저장
	std::ofstream out_degree_file(output + "/out_degree_preprocess.data", std::ios::binary);
	out_degree_file.write(reinterpret_cast<const char*>(final_out_degree.data()), vertices * sizeof(uint32_t));
    out_degree_file.close();

	std::ofstream in_degree_file(output + "/in_degree_preprocess.data", std::ios::binary);
	in_degree_file.write(reinterpret_cast<const char*>(final_in_degree.data()), vertices * sizeof(uint32_t));
	in_degree_file.close();

    out_info.out_degree = final_out_degree; // 변환된 일반 벡터
    out_info.in_degree = final_in_degree;
    out_info.total_edges = edges; // 계산된 총 엣지 수

    printf("Phase 1 (Degree Calculation) took: %.2f seconds.\n", get_time() - function_start_time);
    
    // 메모리 해제
    for (int i=0; i<parallelism*2; i++) {
        free(buffers[i]);
    }
    delete[] buffers;
    delete[] occupied;

	// 다음 단계에서 사용할 수 있도록 결과 반환
}

// degree 벡터를 기반으로 파티션 맵을 생성하는 함수
std::vector<int> create_degree_balanced_partition_map(
	const std::vector<uint32_t>& degrees,
	int partitions,
	VertexId vertices,
	long long total_degree
) {
    std::vector<int> partition_map(vertices);
    if (vertices == 0) return partition_map;
    
    long long target_degree_per_partition = total_degree / partitions;

    int current_partition_id = 0;
    long long current_partition_degree_sum = 0;

    for (VertexId v_id = 0; v_id < (VertexId)vertices; ++v_id) {
        if (current_partition_id < partitions - 1 &&
            current_partition_degree_sum + degrees[v_id] > target_degree_per_partition) {
            
            // [최적화된 비교] abs() 없이 항상 양수인 차이값을 계산하여 비교
            long long diff_after_add = (current_partition_degree_sum + degrees[v_id]) - target_degree_per_partition;
            long long diff_before_add = target_degree_per_partition - current_partition_degree_sum;

            if (diff_before_add <= diff_after_add) {
                current_partition_id++;
                current_partition_degree_sum = 0;
            }
        }

        partition_map[v_id] = current_partition_id;
        current_partition_degree_sum += degrees[v_id];
    }

    return partition_map;
}

void generate_edge_grid(std::string input, std::string output, VertexId vertices, int partitions, int edge_type,
	const std::vector<int>& source_partition_map,
	const std::vector<int>& target_partition_map) {
	int parallelism = std::thread::hardware_concurrency();
	int edge_unit;
	EdgeId edges;
	switch (edge_type) {
	case 0:
		edge_unit = sizeof(VertexId) * 2;
		edges = file_size(input) / edge_unit;
		break;
	case 1:
		edge_unit = sizeof(VertexId) * 2 + sizeof(Weight);
		edges = file_size(input) / edge_unit;
		break;
	default:
		fprintf(stderr, "edge type (%d) is not supported.\n", edge_type);
		exit(-1);
	}
	printf("vertices = %d, edges = %ld\n", vertices, edges);

	char ** buffers = new char * [parallelism*2];
	bool * occupied = new bool [parallelism*2];
	for (int i=0;i<parallelism*2;i++) {
		buffers[i] = (char *)memalign(PAGESIZE, IOSIZE);
		occupied[i] = false;
	}
	Queue<std::tuple<int, long> > tasks(parallelism);
	int ** fout;
	std::mutex ** mutexes;
	fout = new int * [partitions];
	mutexes = new std::mutex * [partitions];

	const int grid_buffer_size = 768; // 12 * 8 * 8
	char * global_grid_buffer = (char *) memalign(PAGESIZE, grid_buffer_size * partitions * partitions);
	char *** grid_buffer = new char ** [partitions];
	int ** grid_buffer_offset = new int * [partitions];
	for (int i=0;i<partitions;i++) {
		mutexes[i] = new std::mutex [partitions];
		fout[i] = new int [partitions];
		grid_buffer[i] = new char * [partitions];
		grid_buffer_offset[i] = new int [partitions];
		for (int j=0;j<partitions;j++) {
			char filename[4096];
			sprintf(filename, "%s/block-%d-%d", output.c_str(), i, j);
			fout[i][j] = open(filename, O_WRONLY|O_APPEND|O_CREAT, 0644);
			grid_buffer[i][j] = global_grid_buffer + (i * partitions + j) * grid_buffer_size;
			grid_buffer_offset[i][j] = 0;
		}
	}

	std::vector<std::thread> threads;
	for (int ti=0;ti<parallelism;ti++) {
		threads.emplace_back([&]() {
			char * local_buffer = (char *) memalign(PAGESIZE, IOSIZE);
			int * local_grid_offset = new int [partitions * partitions];
			int * local_grid_cursor = new int [partitions * partitions];
			VertexId source, target;
			Weight weight;
			while (true) {
				int cursor;
				long bytes;
				std::tie(cursor, bytes) = tasks.pop();
				if (cursor==-1) break;
				memset(local_grid_offset, 0, sizeof(int) * partitions * partitions);
				memset(local_grid_cursor, 0, sizeof(int) * partitions * partitions);
				char * buffer = buffers[cursor];
				for (long pos=0;pos<bytes;pos+=edge_unit) {
					source = *(VertexId*)(buffer+pos);
					target = *(VertexId*)(buffer+pos+sizeof(VertexId));
					int i = source_partition_map[source];
					int j = target_partition_map[target];
					local_grid_offset[i*partitions+j] += edge_unit;
				}
				local_grid_cursor[0] = 0;
				for (int ij=1;ij<partitions*partitions;ij++) {
					local_grid_cursor[ij] = local_grid_offset[ij - 1];
					local_grid_offset[ij] += local_grid_cursor[ij];
				}
				assert(local_grid_offset[partitions*partitions-1]==bytes);
				for (long pos=0;pos<bytes;pos+=edge_unit) {
					source = *(VertexId*)(buffer+pos);
					target = *(VertexId*)(buffer+pos+sizeof(VertexId));
					int i = source_partition_map[source];
					int j = target_partition_map[target];
					*(VertexId*)(local_buffer+local_grid_cursor[i*partitions+j]) = source;
					*(VertexId*)(local_buffer+local_grid_cursor[i*partitions+j]+sizeof(VertexId)) = target;
					if (edge_type==1) {
						weight = *(Weight*)(buffer+pos+sizeof(VertexId)*2);
						*(Weight*)(local_buffer+local_grid_cursor[i*partitions+j]+sizeof(VertexId)*2) = weight;
					}
					local_grid_cursor[i*partitions+j] += edge_unit;
				}
				int start = 0;
				for (int ij=0;ij<partitions*partitions;ij++) {
					assert(local_grid_cursor[ij]==local_grid_offset[ij]);
					int i = ij / partitions;
					int j = ij % partitions;
					std::unique_lock<std::mutex> lock(mutexes[i][j]);
					if (local_grid_offset[ij] - start > edge_unit) {
						write(fout[i][j], local_buffer+start, local_grid_offset[ij]-start);
					} else if (local_grid_offset[ij] - start == edge_unit) {
						memcpy(grid_buffer[i][j]+grid_buffer_offset[i][j], local_buffer+start, edge_unit);
						grid_buffer_offset[i][j] += edge_unit;
						if (grid_buffer_offset[i][j]==grid_buffer_size) {
							write(fout[i][j], grid_buffer[i][j], grid_buffer_size);
							grid_buffer_offset[i][j] = 0;
						}
					}
					start = local_grid_offset[ij];
				}
				occupied[cursor] = false;
			}
		});
	}

	int fin = open(input.c_str(), O_RDONLY);
	if (fin==-1) printf("%s\n", strerror(errno));
	assert(fin!=-1);
	int cursor = 0;
	long total_bytes = file_size(input);
	long read_bytes = 0;
	double start_time = get_time();
	while (true) {
		long bytes = read(fin, buffers[cursor], IOSIZE);
		assert(bytes!=-1);
		if (bytes==0) break;
		occupied[cursor] = true;
		tasks.push(std::make_tuple(cursor, bytes));
		read_bytes += bytes;
		// printf("progress: %.2f%%\r", 100. * read_bytes / total_bytes);
		// fflush(stdout);
		while (occupied[cursor]) {
			cursor = (cursor + 1) % (parallelism * 2);
		}
	}
	close(fin);
	assert(read_bytes==edges*edge_unit);

	for (int ti=0;ti<parallelism;ti++) {
		tasks.push(std::make_tuple(-1, 0));
	}

	for (int ti=0;ti<parallelism;ti++) {
		threads[ti].join();
	}

	printf("%lf -> ", get_time() - start_time);
	long ts = 0;
	for (int i=0;i<partitions;i++) {
		for (int j=0;j<partitions;j++) {
			if (grid_buffer_offset[i][j]>0) {
				ts += grid_buffer_offset[i][j];
				write(fout[i][j], grid_buffer[i][j], grid_buffer_offset[i][j]);
			}
		}
	}
	printf("%lf (%ld)\n", get_time() - start_time, ts);

	for (int i=0;i<partitions;i++) {
		for (int j=0;j<partitions;j++) {
			close(fout[i][j]);
		}
	}

	printf("it takes %.2f seconds to generate edge blocks\n", get_time() - start_time);

	

	long offset;
	int fout_column = open((output+"/column").c_str(), O_WRONLY|O_APPEND|O_CREAT, 0644);
	int fout_column_offset = open((output+"/column_offset").c_str(), O_WRONLY|O_APPEND|O_CREAT, 0644);
	offset = 0;
	for (int j=0;j<partitions;j++) {
		for (int i=0;i<partitions;i++) {
			// printf("progress: %.2f%%\r", 100. * offset / total_bytes);
			// fflush(stdout);
			write(fout_column_offset, &offset, sizeof(offset));
			char filename[4096];
			sprintf(filename, "%s/block-%d-%d", output.c_str(), i, j);
			offset += file_size(filename);
			fin = open(filename, O_RDONLY);
			while (true) {
				long bytes = read(fin, buffers[0], IOSIZE);
				assert(bytes!=-1);
				if (bytes==0) break;
				write(fout_column, buffers[0], bytes);
			}
			close(fin);
		}
	}
	write(fout_column_offset, &offset, sizeof(offset));
	close(fout_column_offset);
	close(fout_column);
	printf("column oriented grid generated\n");
	int fout_row = open((output+"/row").c_str(), O_WRONLY|O_APPEND|O_CREAT, 0644);
	int fout_row_offset = open((output+"/row_offset").c_str(), O_WRONLY|O_APPEND|O_CREAT, 0644);
	offset = 0;
	for (int i=0;i<partitions;i++) {
		for (int j=0;j<partitions;j++) {
			// printf("progress: %.2f%%\r", 100. * offset / total_bytes);
			// fflush(stdout);
			write(fout_row_offset, &offset, sizeof(offset));
			char filename[4096];
			sprintf(filename, "%s/block-%d-%d", output.c_str(), i, j);
			offset += file_size(filename);
			fin = open(filename, O_RDONLY);
			while (true) {
				long bytes = read(fin, buffers[0], IOSIZE);
				assert(bytes!=-1);
				if (bytes==0) break;
				write(fout_row, buffers[0], bytes);
			}
			close(fin);
		}
	}
	write(fout_row_offset, &offset, sizeof(offset));
	close(fout_row_offset);
	close(fout_row);
	printf("row oriented grid generated\n");

	printf("it takes %.2f seconds to generate edge grid\n", get_time() - start_time);

	FILE * fmeta = fopen((output+"/meta").c_str(), "w");
	fprintf(fmeta, "%d %d %ld %d", edge_type, vertices, edges, partitions);
	fclose(fmeta);
}

int main(int argc, char ** argv) {
	int opt;
	std::string input = "";
	std::string output = "";
	VertexId vertices = -1;
	int partitions = -1;
	int edge_type = 0;
	while ((opt = getopt(argc, argv, "i:o:v:p:t:")) != -1) {
		switch (opt) {
		case 'i':
			input = optarg;
			break;
		case 'o':
			output = optarg;
			break;
		case 'v':
			vertices = atoi(optarg);
			break;
		case 'p':
			partitions = atoi(optarg);
			break;
		case 't':
			edge_type = atoi(optarg);
			break;
		}
	}
	if (input=="" || output=="" || vertices==-1) {
		fprintf(stderr, "usage: %s -i [input path] -o [output path] -v [vertices] -p [partitions] -t [edge type: 0=unweighted, 1=weighted]\n", argv[0]);
		exit(-1);
	}
	if (partitions==-1) {
		partitions = vertices / CHUNKSIZE;
	}

	if (file_exists(output)) {
		remove_directory(output);
	}
	create_directory(output);

	DegreeInfo degree_info;
	calculate_and_save_degrees(input, output, vertices, edge_type, degree_info);
	std::vector<uint32_t> out_degree = degree_info.out_degree;
	std::vector<uint32_t> in_degree = degree_info.in_degree;
	auto total_edges = degree_info.total_edges;
	printf("Creating degree-balanced partition maps...\n");
	double map_creation_start_time = get_time();
	auto source_partition_map = create_degree_balanced_partition_map(out_degree, partitions, vertices, total_edges);
	auto target_partition_map = create_degree_balanced_partition_map(in_degree, partitions, vertices, total_edges);
	printf("Partition Map Creation took: %.2f seconds.\n", get_time() - map_creation_start_time);
	generate_edge_grid(input, output, vertices, partitions, edge_type, source_partition_map, target_partition_map);
	return 0;
}
