"""Assemble the visible RV32IC + PicoRV32 IRQ self-test without a cross SDK.

This small encoder emits real CPU instructions. It does not execute/emulate them.
The independent fixture oracle supplies only neural inputs and expected results.
"""
from pathlib import Path
import argparse
import json
import struct

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FIXTURES = ROOT / 'fpga/verification/src_policy/artifacts'


class Assembler:
    def __init__(self):
        self.image = bytearray(8192)
        self.pc = 0
        self.labels = {}
        self.fixups = []
        self.source = ['# GARDA board self-test: actual RV32IC instructions and PicoRV32 IRQ extension.',
                       '# x8=HWPE, x9=fixture pointer, x18=result RAM, x20=IRQ serviced, x23=frames.']

    def org(self, address):
        self.pc = address
        self.source.append(f'.org 0x{address:x}')

    def label(self, name):
        self.labels[name] = self.pc
        self.source.append(name + ':')

    def emit(self, value, source, size=4):
        self.image[self.pc:self.pc + size] = value.to_bytes(size, 'little')
        self.source.append(f'    {source:<36} # 0x{self.pc:04x}: {value:0{size*2}x}')
        self.pc += size

    def addi(self, rd, rs, value):
        assert -2048 <= value < 2048
        self.emit((value & 4095) << 20 | rs << 15 | rd << 7 | 0x13, f'addi x{rd}, x{rs}, {value}')

    def andi(self, rd, rs, value):
        self.emit((value & 4095) << 20 | rs << 15 | 7 << 12 | rd << 7 | 0x13, f'andi x{rd}, x{rs}, {value}')

    def lui(self, rd, upper):
        self.emit(upper << 12 | rd << 7 | 0x37, f'lui x{rd}, 0x{upper:x}')

    def li(self, rd, value):
        value &= 0xffffffff
        low = (value & 4095) - (4096 if value & 2048 else 0)
        self.lui(rd, ((value - low) >> 12) & 0xfffff)
        self.addi(rd, rd, low)

    def lw(self, rd, rs, offset=0):
        self.emit((offset & 4095) << 20 | rs << 15 | 2 << 12 | rd << 7 | 3, f'lw x{rd}, {offset}(x{rs})')

    def sw(self, rs2, rs1, offset=0):
        value = offset & 4095
        self.emit((value >> 5) << 25 | rs2 << 20 | rs1 << 15 | 2 << 12 | (value & 31) << 7 | 0x23,
                  f'sw x{rs2}, {offset}(x{rs1})')

    def branch(self, op, rs1, rs2, label):
        self.fixups.append((self.pc, op, rs1, rs2, label))
        self.emit(0, f'{op} x{rs1}, x{rs2}, {label}')

    def jump(self, label):
        self.fixups.append((self.pc, 'jal', 0, 0, label))
        self.emit(0, f'jal x0, {label}')

    def finish(self):
        for pc, op, rs1, rs2, target in self.fixups:
            displacement = self.labels[target] - pc
            if op == 'jal':
                assert -(1 << 20) <= displacement < (1 << 20) and displacement % 2 == 0
                v = displacement & 0x1fffff
                encoded = (v >> 20) << 31 | ((v >> 1) & 1023) << 21 | ((v >> 11) & 1) << 20 | ((v >> 12) & 255) << 12 | 0x6f
            else:
                assert -4096 <= displacement < 4096 and displacement % 2 == 0
                v = displacement & 8191
                encoded = (v >> 12) << 31 | ((v >> 5) & 63) << 25 | rs2 << 20 | rs1 << 15
                encoded |= (1 if op == 'bne' else 0) << 12 | ((v >> 1) & 15) << 8 | ((v >> 11) & 1) << 7 | 0x63
            self.image[pc:pc + 4] = encoded.to_bytes(4, 'little')
        # Update the annotated assembly listing with resolved branch encodings.
        for index, line in enumerate(self.source):
            if '# 0x' in line:
                address = int(line.split('# 0x')[1].split(':')[0], 16)
                size = 2 if '.hword' in line else 4
                value = int.from_bytes(self.image[address:address + size], 'little')
                self.source[index] = line.split('#')[0] + f'# 0x{address:04x}: {value:0{size*2}x}'


def build():
    a = Assembler()
    a.jump('reset')
    a.org(0x10)
    a.jump('handler')
    a.org(0x100)
    a.label('reset')
    # Exercise the actual compressed decoder; multiplication belongs to HWPE.
    a.emit(0x0001, '.hword 0x0001 # c.nop', size=2)
    a.lui(8, 0x10000)
    a.lui(9, 1)
    a.lui(18, 0x20000)
    a.addi(20, 0, 0)
    a.addi(23, 0, 3)
    a.addi(5, 0, -17)
    a.emit(3 << 25 | 5 << 15 | 0x0b, 'maskirq x0, x5 # enable external IRQ 4')
    a.label('frame')
    a.addi(5, 0, 4)
    a.sw(5, 8)
    a.addi(7, 0, 74)
    a.label('load')
    a.lw(6, 9)
    a.sw(6, 8, 12)
    a.addi(9, 9, 4)
    a.addi(7, 7, -1)
    a.branch('bne', 7, 0, 'load')
    a.addi(5, 0, 1)
    a.sw(5, 8)
    a.label('wait_for_accelerator')
    a.emit(4 << 25 | 31 << 7 | 0x0b, 'waitirq x31 # fetch stops while waiting')
    a.branch('beq', 20, 0, 'wait_for_accelerator')
    a.addi(20, 0, 0)
    a.addi(23, 23, -1)
    a.branch('bne', 23, 0, 'frame')
    a.li(5, 0x600d600d)
    a.lui(6, 0x30000)
    a.sw(5, 6)
    a.label('finished')
    a.emit(4 << 25 | 31 << 7 | 0x0b, 'waitirq x31')
    a.jump('finished')
    a.org(0x300)
    a.label('handler')
    # Reserved x24..x30 are handler temporaries; no main state is clobbered.
    a.lw(24, 8, 4)
    a.andi(24, 24, 7)
    a.addi(25, 0, 2)
    a.branch('bne', 24, 25, 'fail')
    a.lw(24, 8, 28)
    a.li(25, 3556)
    a.branch('bne', 24, 25, 'fail')
    for index in range(3):
        a.lw(24, 8, 16 + 4*index)
        a.lw(25, 9)
        a.branch('bne', 24, 25, 'fail')
        a.sw(24, 18)
        a.lw(26, 18)
        a.branch('bne', 24, 26, 'fail')
        a.addi(18, 18, 4)
        a.addi(9, 9, 4)
    a.addi(24, 0, 4)
    a.sw(24, 8)
    a.addi(20, 0, 1)
    a.emit(2 << 25 | 0x0b, 'retirq')
    a.label('fail')
    a.li(24, 0xbad00001)
    a.lui(25, 0x30000)
    a.sw(24, 25)
    a.label('failed_forever')
    a.jump('failed_forever')
    a.finish()
    # First vector includes zeros; additional fixtures vary signed inputs.
    observations = [int(word, 16) for word in (FIXTURES / 'observations.hex').read_text().split()]
    expected = [int(word, 16) for word in (FIXTURES / 'expected.hex').read_text().split()]
    selected = [0, 1, 17]
    offset = 0x1000
    for vector in selected:
        for word in observations[vector*74:(vector+1)*74] + expected[vector*3:(vector+1)*3]:
            signed = word - 65536 if word & 32768 else word
            a.image[offset:offset+4] = struct.pack('<I', signed & 0xffffffff)
            offset += 4
    hex_text = ''.join(f'{word:08x}\n' for word in struct.unpack('<2048I', a.image))
    return hex_text, '\n'.join(a.source) + '\n', {'vectors': selected, 'input_words_per_vector':74,
          'output_words_per_vector':3, 'inference_cycles':3556, 'labels':a.labels,
          'isa_used':'RV32I, C.NOP, PicoRV32 maskirq/waitirq/retirq'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    hex_text, assembly, metadata = build()
    for name, text in [('boot.hex',hex_text),('boot.S',assembly),('layout.json',json.dumps(metadata,indent=2)+'\n')]:
        path = HERE / name
        if args.check:
            if not path.is_file() or path.read_text() != text:
                raise SystemExit(f'Stale firmware: {path}')
        else:
            path.write_text(text,encoding='ascii',newline='\n')
    print('PASS: deterministic real RV32IC firmware image, 3 independent fixture frames')
