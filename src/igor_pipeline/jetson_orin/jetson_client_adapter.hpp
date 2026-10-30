#ifndef JETSON_CLIENT_ADAPTER_HPP
#define JETSON_CLIENT_ADAPTER_HPP

#include <string>
#include <vector>
#include <cstdint>
#include <chrono>
#include <arpa/inet.h>
#include "../protocol/protocol_v2.h"

struct PipelineMetrics {
    uint32_t sent_frames;
    uint32_t received_frames;
    uint32_t dropped_frames;
    double last_rtt_us;
    double avg_rtt_us;
    double min_rtt_us;
    double max_rtt_us;
};

class JetsonClientAdapter {
public:
    JetsonClientAdapter(const std::string &target_ip = "127.0.0.1",
                        int port = UDP_PORT,
                        uint32_t timeout_ms = 30);
    ~JetsonClientAdapter();

    bool connect();
    void close();

    /**
     * Synchronously streams 74-D observation and waits for 3-D inference actions.
     */
    bool infer(const float obs[IGOR_OBS_DIM],
               const float nominal_twist[3],
               float actions_out[IGOR_ACTION_DIM],
               uint32_t *latency_us_out = nullptr);

    const PipelineMetrics& get_metrics() const { return metrics_; }

private:
    std::string target_ip_;
    int port_;
    uint32_t timeout_ms_;
    int sockfd_;
    sockaddr_in target_addr_;
    uint32_t frame_counter_;
    PipelineMetrics metrics_;

    uint64_t now_ns() const {
        return std::chrono::duration_cast<std::chrono::nanoseconds>(
            std::chrono::high_resolution_clock::now().time_since_epoch()).count();
    }
};

#endif // JETSON_CLIENT_ADAPTER_HPP
