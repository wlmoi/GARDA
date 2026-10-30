# GARDA board self-test: actual RV32IC instructions and PicoRV32 IRQ extension.
# x8=HWPE, x9=fixture pointer, x18=result RAM, x20=IRQ serviced, x23=frames.
    jal x0, reset                        # 0x0000: 1000006f
.org 0x10
    jal x0, handler                      # 0x0010: 2f00006f
.org 0x100
reset:
    .hword 0x0001 # 0x0100: 0001
    lui x8, 0x10000                      # 0x0102: 10000437
    lui x9, 0x1                          # 0x0106: 000014b7
    lui x18, 0x20000                     # 0x010a: 20000937
    addi x20, x0, 0                      # 0x010e: 00000a13
    addi x23, x0, 3                      # 0x0112: 00300b93
    addi x5, x0, -17                     # 0x0116: fef00293
    maskirq x0, x5 # 0x011a: 0602800b
frame:
    addi x5, x0, 4                       # 0x011e: 00400293
    sw x5, 0(x8)                         # 0x0122: 00542023
    addi x7, x0, 74                      # 0x0126: 04a00393
load:
    lw x6, 0(x9)                         # 0x012a: 0004a303
    sw x6, 12(x8)                        # 0x012e: 00642623
    addi x9, x9, 4                       # 0x0132: 00448493
    addi x7, x7, -1                      # 0x0136: fff38393
    bne x7, x0, load                     # 0x013a: fe0398e3
    addi x5, x0, 1                       # 0x013e: 00100293
    sw x5, 0(x8)                         # 0x0142: 00542023
wait_for_accelerator:
    waitirq x31 # 0x0146: 08000f8b
    beq x20, x0, wait_for_accelerator    # 0x014a: fe0a0ee3
    addi x20, x0, 0                      # 0x014e: 00000a13
    addi x23, x23, -1                    # 0x0152: fffb8b93
    bne x23, x0, frame                   # 0x0156: fc0b94e3
    lui x5, 0x600d6                      # 0x015a: 600d62b7
    addi x5, x5, 13                      # 0x015e: 00d28293
    lui x6, 0x30000                      # 0x0162: 30000337
    sw x5, 0(x6)                         # 0x0166: 00532023
finished:
    waitirq x31                          # 0x016a: 08000f8b
    jal x0, finished                     # 0x016e: ffdff06f
.org 0x300
handler:
    lw x24, 4(x8)                        # 0x0300: 00442c03
    andi x24, x24, 7                     # 0x0304: 007c7c13
    addi x25, x0, 2                      # 0x0308: 00200c93
    bne x24, x25, fail                   # 0x030c: 099c1263
    lw x24, 28(x8)                       # 0x0310: 01c42c03
    lui x25, 0x1                         # 0x0314: 00001cb7
    addi x25, x25, -540                  # 0x0318: de4c8c93
    bne x24, x25, fail                   # 0x031c: 079c1a63
    lw x24, 16(x8)                       # 0x0320: 01042c03
    lw x25, 0(x9)                        # 0x0324: 0004ac83
    bne x24, x25, fail                   # 0x0328: 079c1463
    sw x24, 0(x18)                       # 0x032c: 01892023
    lw x26, 0(x18)                       # 0x0330: 00092d03
    bne x24, x26, fail                   # 0x0334: 05ac1e63
    addi x18, x18, 4                     # 0x0338: 00490913
    addi x9, x9, 4                       # 0x033c: 00448493
    lw x24, 20(x8)                       # 0x0340: 01442c03
    lw x25, 0(x9)                        # 0x0344: 0004ac83
    bne x24, x25, fail                   # 0x0348: 059c1463
    sw x24, 0(x18)                       # 0x034c: 01892023
    lw x26, 0(x18)                       # 0x0350: 00092d03
    bne x24, x26, fail                   # 0x0354: 03ac1e63
    addi x18, x18, 4                     # 0x0358: 00490913
    addi x9, x9, 4                       # 0x035c: 00448493
    lw x24, 24(x8)                       # 0x0360: 01842c03
    lw x25, 0(x9)                        # 0x0364: 0004ac83
    bne x24, x25, fail                   # 0x0368: 039c1463
    sw x24, 0(x18)                       # 0x036c: 01892023
    lw x26, 0(x18)                       # 0x0370: 00092d03
    bne x24, x26, fail                   # 0x0374: 01ac1e63
    addi x18, x18, 4                     # 0x0378: 00490913
    addi x9, x9, 4                       # 0x037c: 00448493
    addi x24, x0, 4                      # 0x0380: 00400c13
    sw x24, 0(x8)                        # 0x0384: 01842023
    addi x20, x0, 1                      # 0x0388: 00100a13
    retirq                               # 0x038c: 0400000b
fail:
    lui x24, 0xbad00                     # 0x0390: bad00c37
    addi x24, x24, 1                     # 0x0394: 001c0c13
    lui x25, 0x30000                     # 0x0398: 30000cb7
    sw x24, 0(x25)                       # 0x039c: 018ca023
failed_forever:
    jal x0, failed_forever               # 0x03a0: 0000006f
