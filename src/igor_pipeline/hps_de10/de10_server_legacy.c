#include <stdio.h>
#include <string.h>
#include <arpa/inet.h>
#include "protocol.h"
#include "de10_driver.h"

int main() {
    SoC_FPGA_Context soc;
    if (init_soc(&soc) != 0) {
        perror("Failed to map FPGA bridges");
        return -1;
    }

    int sockfd = socket(AF_INET, SOCK_DGRAM, 0);
    struct sockaddr_in server_addr, client_addr;
    socklen_t addr_len = sizeof(client_addr);

    memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(UDP_PORT);
    server_addr.sin_addr.s_addr = INADDR_ANY;

    bind(sockfd, (struct sockaddr *)&server_addr, sizeof(server_addr));
    printf("DE10-Nano HPS UDP AI Accelerator Node Running...\n");

    // Assign DDR offsets for inputs and outputs
    float *in_ddr_virt  = (float *)soc.shared_ram_virt;
    float *out_ddr_virt = (float *)((uint8_t *)soc.shared_ram_virt + 0x800000); // 8MB offset

    uint32_t in_ddr_phys  = soc.shared_ram_phys;
    uint32_t out_ddr_phys = soc.shared_ram_phys + 0x800000;

    SensorPacket rx_packet;
    InferenceResponsePacket tx_packet;

    while (1) {
        // 1. Receive Ethernet Packet from Jetson
        ssize_t bytes_recvd = recvfrom(sockfd, &rx_packet, sizeof(SensorPacket), 0,
                                       (struct sockaddr *)&client_addr, &addr_len);
        if (bytes_recvd <= 0) continue;

        // 2. Load payload directly into Shared DDR Memory
        // Copy velocity components first, then raw sensor data array
        in_ddr_virt[0] = rx_packet.linear_velocity[0];
        in_ddr_virt[1] = rx_packet.linear_velocity[1];
        in_ddr_virt[2] = rx_packet.linear_velocity[2];
        in_ddr_virt[3] = rx_packet.angular_velocity[0];
        in_ddr_virt[4] = rx_packet.angular_velocity[1];
        in_ddr_virt[5] = rx_packet.angular_velocity[2];

        memcpy(&in_ddr_virt[6], rx_packet.sensor_data, rx_packet.sensor_data_len * sizeof(float));

        // 3. Configure and Trigger FPGA Accelerator Logic via Bridge
        *soc.accel_in_ptr  = in_ddr_phys;
        *soc.accel_out_ptr = out_ddr_phys;
        *soc.accel_len     = rx_packet.sensor_data_len + 6;
        *soc.accel_ctrl    = 0x01; // Start pulse

        // 4. Poll Status Register for Done Flag (or use HW Interrupt)
        while ((*soc.accel_status & 0x01) == 0) {
            // Busy wait loop / usleep(10) depending on target accelerator latency
        }

        // Reset control signal
        *soc.accel_ctrl = 0x00;

        // 5. Build Response Packet from PL DDR Output Buffer
        tx_packet.frame_id = rx_packet.frame_id;
        tx_packet.timestamp_ns = rx_packet.timestamp_ns;
        tx_packet.status_code = 0;
        tx_packet.num_outputs = 128; // Configured output shape
        memcpy(tx_packet.ai_results, out_ddr_virt, 128 * sizeof(float));

        // 6. Return Processed Payload to Jetson
        sendto(sockfd, &tx_packet, sizeof(InferenceResponsePacket), 0,
               (struct sockaddr *)&client_addr, addr_len);
    }

    return 0;
}