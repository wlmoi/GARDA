#include <iostream>
#include <cstring>
#include <arpa/inet.h>
#include <unistd.h>
#include <chrono>
#include "../protocol/protocol_legacy.h"

#define DE10_IP "192.168.1.50"

uint64_t get_time_ns() {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::high_resolution_clock::now().time_since_epoch()).count();
}

int main() {
    int sockfd = socket(AF_INET, SOCK_DGRAM, 0);
    struct sockaddr_in de10_addr;
    memset(&de10_addr, 0, sizeof(de10_addr));
    de10_addr.sin_family = AF_INET;
    de10_addr.sin_port = htons(UDP_PORT);
    inet_pton(AF_INET, DE10_IP, &de10_addr.sin_addr);

    // Set socket timeout (e.g., 50ms)
    struct timeval tv = {0, 50000};
    setsockopt(sockfd, SOL_SOCKET, SO_RCVTIMEO, (const char*)&tv, sizeof(tv));

    uint32_t frame_counter = 0;

    while (true) {
        SensorPacket packet;
        packet.frame_id = frame_counter++;
        packet.timestamp_ns = get_time_ns();

        // Populate velocities (from ROS topic or onboard sensors)
        packet.linear_velocity[0] = 1.2f; // Vx
        packet.linear_velocity[1] = 0.0f; // Vy
        packet.linear_velocity[2] = 0.1f; // Vz
        packet.angular_velocity[0] = 0.0f;
        packet.angular_velocity[1] = 0.0f;
        packet.angular_velocity[2] = 0.05f;

        // Dummy raw sensor fill (e.g. LiDAR or IMU array)
        packet.sensor_data_len = 256;
        for (int i = 0; i < 256; ++i) {
            packet.sensor_data[i] = static_cast<float>(i) * 0.01f;
        }

        // Send to DE10-Nano FPGA Accelerator
        sendto(sockfd, &packet, sizeof(SensorPacket), 0, (struct sockaddr *)&de10_addr, sizeof(de10_addr));

        // Receive Accelerated Inference Results
        InferenceResponsePacket response;
        socklen_t addr_len = sizeof(de10_addr);
        ssize_t recvd = recvfrom(sockfd, &response, sizeof(InferenceResponsePacket), 0, (struct sockaddr *)&de10_addr, &addr_len);

        if (recvd > 0) {
            uint64_t roundtrip_latency_us = (get_time_ns() - response.timestamp_ns) / 1000;
            std::cout << "[Frame " << response.frame_id << "] AI Accelerated Output[0]: " 
                      << response.ai_results[0] << " | RTT Latency: " << roundtrip_latency_us << " us" << std::endl;
        } else {
            std::cerr << "Timeout or dropped frame waiting for DE10-Nano hardware reply." << std::endl;
        }

        usleep(10000); // Stream loop delay (~100 Hz)
    }

    close(sockfd);
    return 0;
}