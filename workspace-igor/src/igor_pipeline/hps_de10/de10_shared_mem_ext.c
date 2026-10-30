/* Retained for legacy mock-only tools. Current hardware has no DDR/MMIO ABI. */
#include "de10_shared_mem_ext.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int hal_init(SoC_HAL_Context *ctx, int is_mock) {
    if(!ctx)return -1;
    memset(ctx,0,sizeof(*ctx));ctx->mem_fd=-1;
    if(!is_mock){
        fprintf(stderr,"[HAL] No Parallel8 DDR/MMIO backend. Use de10_udp_gateway.py --backend uart.\n");
        return -10;
    }
    ctx->is_mock=1;
    ctx->lw_base_virt=calloc(1,0x1000);
    ctx->shared_ram_virt=calloc(1,SHARED_RAM_SPAN);
    if(!ctx->lw_base_virt || !ctx->shared_ram_virt){hal_cleanup(ctx);return -2;}
    volatile uint32_t *r=ctx->lw_base_virt;
    ctx->accel_ctrl=&r[REG_CONTROL];ctx->accel_in_ptr=&r[REG_IN_PTR];
    ctx->accel_out_ptr=&r[REG_OUT_PTR];ctx->accel_len=&r[REG_LENGTH];
    ctx->accel_status=&r[REG_STATUS];ctx->accel_cycles=&r[REG_CYCLES];
    unsigned char *ram=ctx->shared_ram_virt;
    ctx->in_buf_ping=(int16_t *)ram;ctx->out_buf_ping=(int16_t *)(ram+0x400000);
    ctx->in_buf_pong=(int16_t *)(ram+0x800000);ctx->out_buf_pong=(int16_t *)(ram+0xc00000);
    return 0;
}
void hal_write_reg(SoC_HAL_Context *ctx,uint32_t idx,uint32_t value){
    if(ctx && ctx->is_mock && ctx->lw_base_virt && idx<=REG_CYCLES)
        ((uint32_t *)ctx->lw_base_virt)[idx]=value;
}
uint32_t hal_read_reg(SoC_HAL_Context *ctx,uint32_t idx){
    if(ctx && ctx->is_mock && ctx->lw_base_virt && idx<=REG_CYCLES)
        return ((uint32_t *)ctx->lw_base_virt)[idx];
    return 0;
}
int hal_trigger_inference(SoC_HAL_Context *ctx,int bank,uint32_t count,uint32_t timeout){
    (void)timeout;
    if(!ctx || !ctx->is_mock || !ctx->lw_base_virt || (bank!=0 && bank!=1) || count!=74)return -1;
    hal_write_reg(ctx,REG_LENGTH,count);hal_write_reg(ctx,REG_STATUS,1);
    return 0;
}
void hal_cleanup(SoC_HAL_Context *ctx){
    if(!ctx)return;
    if(ctx->is_mock){free(ctx->lw_base_virt);free(ctx->shared_ram_virt);}
    memset(ctx,0,sizeof(*ctx));ctx->mem_fd=-1;
}
