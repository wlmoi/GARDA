#include "jetson_client_adapter.hpp"
#include <iostream>
#include <cstring>
#include <unistd.h>
#include <cmath>
#include <algorithm>

JetsonClientAdapter::JetsonClientAdapter(const std::string &target_ip, int port, uint32_t timeout_ms)
    : target_ip_(target_ip), port_(port), timeout_ms_(timeout_ms), sockfd_(-1), frame_counter_(0) {
    memset(&metrics_, 0, sizeof(metrics_));
    metrics_.min_rtt_us = 1e9;
}

JetsonClientAdapter::~JetsonClientAdapter() {
    close();
}

bool JetsonClientAdapter::connect() {
    close();
    sockfd_ = socket(AF_INET, SOCK_DGRAM, 0);
    if (sockfd_ < 0) {
        perror("[JetsonClient] Failed to create UDP socket");
        return false;
    }

    struct timeval tv;
    tv.tv_sec = timeout_ms_ / 1000;
    tv.tv_usec = (timeout_ms_ % 1000) * 1000;
    setsockopt(sockfd_, SOL_SOCKET, SO_RCVTIMEO, (const char*)&tv, sizeof(tv));

    memset(&target_addr_, 0, sizeof(target_addr_));
    target_addr_.sin_family = AF_INET;
    target_addr_.sin_port = htons(port_);
    if (inet_pton(AF_INET, target_ip_.c_str(), &target_addr_.sin_addr) <= 0) {
        std::cerr << "[JetsonClient] Invalid target IP address: " << target_ip_ << std::endl;
        close();
        return false;
    }

    return true;
}

void JetsonClientAdapter::close() {
    if (sockfd_ >= 0) {
        ::close(sockfd_);
        sockfd_ = -1;
    }
}

bool JetsonClientAdapter::infer(const float obs[IGOR_OBS_DIM],
                                const float nominal_twist[3],
                                float actions_out[IGOR_ACTION_DIM],
                                uint32_t *latency_us_out) {
    if (sockfd_ < 0) {
        if (!connect()) return false;
    }

    SensorPacketV2 pkt;
    pkt.magic = PROTOCOL_MAGIC;
    pkt.frame_id = frame_counter_++;
    pkt.timestamp_ns = now_ns();

    if (nominal_twist) {
        pkt.linear_velocity[0] = nominal_twist[0];
        pkt.linear_velocity[1] = nominal_twist[1];
        pkt.linear_velocity[2] = 0.0f;
        pkt.angular_velocity[0] = 0.0f;
        pkt.angular_velocity[1] = 0.0f;
        pkt.angular_velocity[2] = nominal_twist[2];
    } else {
        memset(pkt.linear_velocity, 0, sizeof(pkt.linear_velocity));
        memset(pkt.angular_velocity, 0, sizeof(pkt.angular_velocity));
    }

    pkt.sensor_data_len = IGOR_OBS_DIM;
    for (int i = 0; i < IGOR_OBS_DIM; ++i) {
        pkt.sensor_data[i] = obs[i];
        // Quantize to Q8.8
        pkt.q8_8_data[i] = static_cast<int16_t>(std::clamp(std::round(obs[i] * 256.0f), -32768.0f, 32767.0f));
    }

    serialize_sensor_packet(&pkt);

    ssize_t sent = sendto(sockfd_, &pkt, sizeof(SensorPacketV2), 0,
                          (struct sockaddr *)&target_addr_, sizeof(target_addr_));
    if (sent != sizeof(SensorPacketV2)) {
        metrics_.dropped_frames++;
        return false;
    }
    metrics_.sent_frames++;

    InferenceResponsePacketV2 resp;
    socklen_t addr_len = sizeof(target_addr_);
    ssize_t recvd = recvfrom(sockfd_, &resp, sizeof(InferenceResponsePacketV2), 0,
                             (struct sockaddr *)&target_addr_, &addr_len);

    uint64_t t_now = now_ns();
    if (recvd <= 0) {
        metrics_.dropped_frames++;
        return false;
    }

    if (validate_response_packet(&resp) != 0) {
        metrics_.dropped_frames++;
        return false;
    }

    double rtt_us = static_cast<double>(t_now - resp.timestamp_ns) / 1000.0;
    metrics_.last_rtt_us = rtt_us;
    metrics_.min_rtt_us = std::min(metrics_.min_rtt_us, rtt_us);
    metrics_.max_rtt_us = std::max(metrics_.max_rtt_us, rtt_us);
    metrics_.received_frames++;
    metrics_.avg_rtt_us += (rtt_us - metrics_.avg_rtt_us) / metrics_.received_frames;

    if (latency_us_out) {
        *latency_us_out = static_cast<uint32_t>(rtt_us);
    }

    for (int i = 0; i < IGOR_ACTION_DIM; ++i) {
        actions_out[i] = resp.ai_results[i];
    }

    return true;
}
