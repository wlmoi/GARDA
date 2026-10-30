#include <iostream>
#include <vector>
#include <cstring>
#include <chrono>
#include <thread>
#include <arpa/inet.h>
#include <unistd.h>
#include <signal.h>
#include "../protocol/protocol_v2.h"

static volatile bool g_running = true;

void handle_signal(int) {
    g_running = false;
}

int main(int argc, char **argv) {
    int port = UDP_PORT;
    int latency_us = 500; // Simulated latency

    for (int i = 1; i < argc; ++i) {
        if (std::string(argv[i]) == "--port" && i + 1 < argc) {
            port = std::stoi(argv[++i]);
        } else if (std::string(argv[i]) == "--delay" && i + 1 < argc) {
            latency_us = std::stoi(argv[++i]);
        }
    }

    signal(SIGINT, handle_signal);
    signal(SIGTERM, handle_signal);

    std::cout << "==================================================================" << std::endl;
    std::cout << "  Project IGOR - Offline Mock DE10 Host Server Simulator" << std::endl;
    std::cout << "  Port: " << port << " | Sim Latency: " << latency_us << " us" << std::endl;
    std::cout << "==================================================================" << std::endl;

    int sockfd = socket(AF_INET, SOCK_DGRAM, 0);
    if (sockfd < 0) {
        std::cerr << "Failed to open socket" << std::endl;
        return 1;
    }

    int opt = 1;
    setsockopt(sockfd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    sockaddr_in server_addr{}, client_addr{};
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(port);
    server_addr.sin_addr.s_addr = INADDR_ANY;

    if (bind(sockfd, (struct sockaddr *)&server_addr, sizeof(server_addr)) < 0) {
        std::cerr << "Failed to bind to port " << port << std::endl;
        close(sockfd);
        return 1;
    }

    std::cout << "[Simulator] Listening for SensorPacketV2 frames..." << std::endl;

    SensorPacketV2 rx;
    InferenceResponsePacketV2 tx;
    socklen_t client_len = sizeof(client_addr);
    uint32_t count = 0;

    while (g_running) {
        ssize_t n = recvfrom(sockfd, &rx, sizeof(SensorPacketV2), 0, (struct sockaddr *)&client_addr, &client_len);
        if (n <= 0) continue;

        if (validate_sensor_packet(&rx) != 0) {
            std::cerr << "[Simulator] Corrupted SensorPacketV2 rejected (CRC/Magic mismatch)" << std::endl;
            continue;
        }

        if (latency_us > 0) {
            std::this_thread::sleep_for(std::chrono::microseconds(latency_us));
        }

        tx.magic = PROTOCOL_MAGIC;
        tx.frame_id = rx.frame_id;
        tx.timestamp_ns = rx.timestamp_ns;
        tx.status_code = STATUS_OK;
        tx.num_outputs = IGOR_ACTION_DIM;

        // Neural policy simulation:
        // Examine frontal LiDAR beams (rays 0..63)
        float min_lidar = 1.0f;
        for (int i = 0; i < 64; ++i) {
            if (rx.sensor_data[i] < min_lidar) min_lidar = rx.sensor_data[i];
        }

        if (min_lidar < 0.35f) {
            tx.ai_results[0] = -0.90f; // Strong reverse delta
            tx.ai_results[1] = 0.0f;
            tx.ai_results[2] = 0.0f;
        } else if (min_lidar < 0.60f) {
            tx.ai_results[0] = -0.40f; // Mild brake
            tx.ai_results[1] = 0.0f;
            tx.ai_results[2] = 0.0f;
        } else {
            tx.ai_results[0] = 0.0f;
            tx.ai_results[1] = 0.0f;
            tx.ai_results[2] = 0.0f;
        }

        for (int i = 0; i < IGOR_ACTION_DIM; ++i) {
            tx.q8_8_results[i] = static_cast<int16_t>(tx.ai_results[i] * 256.0f);
        }
        tx.execution_cycles = 1200;

        serialize_response_packet(&tx);
        sendto(sockfd, &tx, sizeof(InferenceResponsePacketV2), 0, (struct sockaddr *)&client_addr, client_len);
        count++;
    }

    std::cout << "[Simulator] Shutting down. Served " << count << " packets." << std::endl;
    close(sockfd);
    return 0;
}
