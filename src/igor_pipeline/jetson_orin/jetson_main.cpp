#include "jetson_client_adapter.hpp"
#include <iostream>
#include <thread>
#include <chrono>

int main(int argc, char **argv) {
    std::string target_ip = "127.0.0.1";
    int port = UDP_PORT;
    int test_iterations = 200;

    for (int i = 1; i < argc; ++i) {
        if (std::string(argv[i]) == "--target" && i + 1 < argc) {
            target_ip = argv[++i];
        } else if (std::string(argv[i]) == "--port" && i + 1 < argc) {
            port = std::stoi(argv[++i]);
        } else if (std::string(argv[i]) == "--iter" && i + 1 < argc) {
            test_iterations = std::stoi(argv[++i]);
        }
    }

    std::cout << "==================================================================" << std::endl;
    std::cout << "  Project IGOR - Jetson Orin Nano AI Streamer Client" << std::endl;
    std::cout << "  Target: " << target_ip << ":" << port << " | Iterations: " << test_iterations << std::endl;
    std::cout << "==================================================================" << std::endl;

    JetsonClientAdapter client(target_ip, port, 30);
    if (!client.connect()) {
        std::cerr << "Could not connect to target!" << std::endl;
        return 1;
    }

    float obs[IGOR_OBS_DIM];
    float nominal_twist[3] = {0.4f, 0.0f, 0.1f};
    float actions[IGOR_ACTION_DIM];

    // Populate synthetic test observation
    for (int i = 0; i < IGOR_OBS_DIM; ++i) {
        obs[i] = (i < 64) ? 0.8f : 0.0f; // LiDAR rays clear
    }

    for (int iter = 0; iter < test_iterations; ++iter) {
        uint32_t latency_us = 0;
        bool ok = client.infer(obs, nominal_twist, actions, &latency_us);

        if (ok) {
            if (iter % 20 == 0 || iter == test_iterations - 1) {
                std::cout << "[Frame " << iter << "] Actions: ["
                          << actions[0] << ", " << actions[1] << ", " << actions[2]
                          << "] | RTT: " << latency_us << " us" << std::endl;
            }
        } else {
            std::cerr << "[Frame " << iter << "] Timeout / Packet dropped" << std::endl;
        }

        std::this_thread::sleep_for(std::chrono::milliseconds(5)); // ~200 Hz
    }

    const auto &m = client.get_metrics();
    std::cout << "\n--- Streaming Benchmark Results ---" << std::endl;
    std::cout << "Frames Sent:     " << m.sent_frames << std::endl;
    std::cout << "Frames Received: " << m.received_frames << std::endl;
    std::cout << "Frames Dropped:  " << m.dropped_frames << std::endl;
    std::cout << "Average RTT:     " << m.avg_rtt_us << " us" << std::endl;
    std::cout << "Min RTT:         " << m.min_rtt_us << " us" << std::endl;
    std::cout << "Max RTT:         " << m.max_rtt_us << " us" << std::endl;

    return (m.dropped_frames == 0) ? 0 : 1;
}
