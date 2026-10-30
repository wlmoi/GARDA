#include <stdio.h>
#include <stdlib.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <unistd.h>
#include <stdint.h>

#define LWHPS2FPGA_BASE  0xFF200000
#define LWHPS2FPGA_SPAN  0x00200000
#define AI_ACCEL_OFFSET  0x00000000

#define SHARED_RAM_BASE  0x20000000 // Upper 512MB region
#define SHARED_RAM_SPAN  0x01000000 // 16MB buffer space

typedef struct {
    volatile uint32_t *accel_ctrl;
    volatile uint32_t *accel_in_ptr;
    volatile uint32_t *accel_out_ptr;
    volatile uint32_t *accel_len;
    volatile uint32_t *accel_status;
    void *shared_ram_virt;
    uint32_t shared_ram_phys;
} SoC_FPGA_Context;

int init_soc(SoC_FPGA_Context *ctx) {
    int fd = open("/dev/mem", O_RDWR | O_SYNC);
    if (fd < 0) return -1;

    // Map Lightweight Bridge for Control Registers
    void *lw_base = mmap(NULL, LWHPS2FPGA_SPAN, PROT_READ | PROT_WRITE, MAP_SHARED, fd, LWHPS2FPGA_BASE);
    volatile uint32_t *accel = (uint32_t *)((uint8_t *)lw_base + AI_ACCEL_OFFSET);

    ctx->accel_ctrl    = &accel[0];
    ctx->accel_in_ptr  = &accel[1];
    ctx->accel_out_ptr = &accel[2];
    ctx->accel_len     = &accel[3];
    ctx->accel_status  = &accel[4];

    // Map Shared SDRAM for DMA transfers
    ctx->shared_ram_phys = SHARED_RAM_BASE;
    ctx->shared_ram_virt = mmap(NULL, SHARED_RAM_SPAN, PROT_READ | PROT_WRITE, MAP_SHARED, fd, SHARED_RAM_BASE);

    close(fd);
    return 0;
}