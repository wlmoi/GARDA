"""Clocked host protocol for the neural SRAM register top.

Provide write_register(index, byte) and read_byte(selector) callbacks from
your board transport. Both must wait through the next rising SRAM edge after the register command.
This interface is separate from the existing FPGA UART opcodes.
"""
from pathlib import Path

WORDS = 6020


def read_image(path):
    words = [int(token, 16) for line in Path(path).read_text().splitlines()
             for token in line.split('//')[0].split()]
    if len(words) != WORDS or any(not 0 <= w <= 65535 for w in words):
        raise ValueError('Expected exactly 6020 unsigned 16-bit words')
    return words


class NeuralSRAM:
    def __init__(self, write_register, read_byte):
        self.write, self.read = write_register, read_byte

    def check(self):
        value = self.read(0)
        if value & 0x30:
            raise RuntimeError(f'Host/neural fault: 0x{value:02x}; reset before retry')
        return value

    def upload(self, words):
        # Validate before touching any hardware.
        if len(words) != WORDS or any(not 0 <= w <= 65535 for w in words):
            raise ValueError('Expected exactly 6020 unsigned 16-bit words')
        self.write(9, 0)
        if self.read(7) != 0xa6:
            raise RuntimeError('Wrong neural SRAM register interface')
        self.write(4, 1)  # BEGIN clears validity and sequential upload count.
        self.check()
        for word in words:
            self.write(2, word & 255)
            self.write(3, word >> 8)
            self.write(4, 2)  # WRITE consumes both staged bytes, increments address.
            self.check()
        if self.read(5) | (self.read(6) << 8) != WORDS:
            raise RuntimeError('Incomplete SRAM upload')
        # Read every weight and bias back before permitting inference.
        for address, expected in enumerate(words):
            self.write(0, address & 255)
            self.write(1, address >> 8)
            actual = self.read(1) | (self.read(2) << 8)
            if actual != expected:
                raise RuntimeError(f'SRAM mismatch at {address}: {actual:04x} != {expected:04x}')
        self.write(4, 3)  # COMMIT only after all data has been verified by host.
        if not self.check() & 2:
            raise RuntimeError('SRAM did not become ready')

    def load_inputs(self, values):
        if len(values) != 24 or any(not -32768 <= v <= 32767 for v in values):
            raise ValueError('Expected 24 signed Q8.8 inputs')
        for index, value in enumerate(values):
            self.write(5, index)
            self.write(2, value & 255)
            self.write(3, (value & 65535) >> 8)
            self.write(6, 0)
            self.check()  # Allow the datapath to consume the input pulse.

    def start(self):
        self.write(7, 0)
        self.check()

    def outputs(self):
        if not self.check() & 8:
            raise RuntimeError('Inference has not finished')
        result = []
        for index in range(4):
            self.write(8, index)
            value = self.read(3) | (self.read(4) << 8)
            result.append(value - 65536 if value & 32768 else value)
        return result

    def latency_cycles(self):
        value = 0
        for byte in range(4):
            self.write(9, byte + 1)
            value |= self.read(7) << (byte * 8)
        self.write(9, 0)
        return value
