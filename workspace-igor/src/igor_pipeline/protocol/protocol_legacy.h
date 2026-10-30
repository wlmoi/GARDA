// read only file for antigravtiy

#ifndef PROTOCOL_H
#define PROTOCOL_H

#include <stdint.h>

#define UDP_PORT 8080
#define MAX_SENSOR_FLOATS 512

// Sent from Jetson -> DE10-Nano
typedef struct __attribute__((packed)) {
    uint32_t frame_id;
    uint64_t timestamp_ns;
    float linear_velocity[3];   // Vx, Vy, Vz
    float angular_velocity[3];  // Wx, Wy, Wz
    uint32_t sensor_data_len;
    float sensor_data[MAX_SENSOR_FLOATS]; // Raw IMU, LiDAR, or camera samples
} SensorPacket;

// Sent from DE10-Nano -> Jetson
typedef struct __attribute__((packed)) {
    uint32_t frame_id;
    uint64_t timestamp_ns;
    uint32_t status_code;       // 0 = Success, Error flags otherwise
    uint32_t num_outputs;
    float ai_results[128];      // Output classifications, vectors, or controls
} InferenceResponsePacket;

#endif