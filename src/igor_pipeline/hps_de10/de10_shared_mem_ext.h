#ifndef DE10_SHARED_MEM_EXT_H
#define DE10_SHARED_MEM_EXT_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#define LWHPS2FPGA_BASE  0xFF200000
#define LWHPS2FPGA_SPAN  0x00200000
#define AI_ACCEL_OFFSET  0x00000000

#define SHARED_RAM_BASE  0x20000000 // Upper 512MB region
#define SHARED_RAM_SPAN  0x01000000 // 16MB buffer space

// Historical mock ABI only. No matching register slave exists in Parallel8.
// Production gateway uses local UART; hal_init(..., 0) refuses hardware access.
#define REG_CONTROL      0
#define REG_IN_PTR       1
#define REG_OUT_PTR      2
#define REG_LENGTH       3
#define REG_STATUS       4
#define REG_CYCLES       5

typedef struct {
    int is_mock;
    int mem_fd;
    void *lw_base_virt;
    volatile uint32_t *accel_ctrl;
    volatile uint32_t *accel_in_ptr;
    volatile uint32_t *accel_out_ptr;
    volatile uint32_t *accel_len;
    volatile uint32_t *accel_status;
    volatile uint32_t *accel_cycles;

    void *shared_ram_virt;
    uint32_t shared_ram_phys;

    // Double buffering pointers
    int16_t *in_buf_ping;
    int16_t *in_buf_pong;
    int16_t *out_buf_ping;
    int16_t *out_buf_pong;

    uint32_t in_phys_ping;
    uint32_t in_phys_pong;
    uint32_t out_phys_ping;
    uint32_t out_phys_pong;
} SoC_HAL_Context;

/**
 * Initialize legacy heap-only test buffers. Not a physical DDR/MMIO backend.
 * @param ctx Pointer to SoC_HAL_Context
 * @param is_mock Must be 1. Zero returns -10 without touching /dev/mem.
 * @return 0 on success, negative error code on failure
 */
int hal_init(SoC_HAL_Context *ctx, int is_mock);

/**
 * Write a 32-bit value to an accelerator control register.
 */
void hal_write_reg(SoC_HAL_Context *ctx, uint32_t reg_idx, uint32_t val);

/**
 * Read a 32-bit value from an accelerator control register.
 */
uint32_t hal_read_reg(SoC_HAL_Context *ctx, uint32_t reg_idx);

/**
 * Trigger PL execution and wait for completion with a timeout.
 * @param timeout_us Timeout in microseconds
 * @return 0 on success (done asserted), -1 on timeout
 */
int hal_trigger_inference(SoC_HAL_Context *ctx, int bank, uint32_t num_inputs, uint32_t timeout_us);

/**
 * Cleanly unmap and close FPGA bridge resources.
 */
void hal_cleanup(SoC_HAL_Context *ctx);

#ifdef __cplusplus
}
#endif

#endif // DE10_SHARED_MEM_EXT_H
