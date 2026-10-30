"""Pin-only test of the fixed-model neural logic submission, at RTL and gate level."""
from pathlib import Path
import sys
import json
import cocotb
from cocotb.triggers import Timer
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'reference_model'))
from neural_reference import infer, read_mem

async def cycle(dut):
    dut.clk.value = 0
    await Timer(10, units='ns')
    dut.clk.value = 1
    await Timer(10, units='ns')

async def write(dut, address, value):
    dut.ui_in.value = (address << 1) | 1
    dut.uio_in.value = value & 255
    await cycle(dut)
    dut.ui_in.value = 0
    # The host command is latched on one edge and consumed on the next edge.
    await cycle(dut)

async def read(dut, select):
    dut.ui_in.value = select << 5
    await cycle(dut)
    return int(dut.uo_out.value)

async def reset(dut):
    dut.clk.value = 0
    dut.rst_n.value = 0
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0
    await cycle(dut)
    await cycle(dut)
    dut.rst_n.value = 1
    await cycle(dut)

@cocotb.test()
async def full_model_validation_readback_and_inference(dut):
    await reset(dut)
    assert await read(dut, 7) == 0xa6
    # An unloaded image must never start inference.
    await write(dut, 7, 0)
    assert (await read(dut, 0)) & 0x14 == 0x10
    await reset(dut)
    image = read_mem('bram_unified_weights.mem')
    assert len(image) == 6020
    await write(dut, 4, 1)
    for word in image:
        await write(dut, 2, word & 255)
        await write(dut, 3, (word & 65535) >> 8)
        await write(dut, 4, 2)
    assert (await read(dut, 5)) | ((await read(dut, 6)) << 8) == 6020
    for address, word in enumerate(image):
        await write(dut, 0, address & 255)
        await write(dut, 1, address >> 8)
        actual = (await read(dut, 1)) | ((await read(dut, 2)) << 8)
        assert actual == word & 65535, (address, actual, word)
    await write(dut, 4, 3)
    assert await read(dut, 0) & 0x32 == 2
    values = read_mem('test_inputs.mem')[:24]
    expected, fault = infer(values)
    assert not fault
    for index, value in enumerate(values):
        await write(dut, 5, index)
        await write(dut, 2, value & 255)
        await write(dut, 3, (value & 65535) >> 8)
        await write(dut, 6, 0)
    await write(dut, 7, 0)
    for _ in range(20000):
        status = await read(dut, 0)
        assert not status & 0x30, status
        if status & 8:
            break
    else:
        raise AssertionError('Neural inference timed out')
    actual = []
    for index in range(4):
        await write(dut, 8, index)
        value = (await read(dut, 3)) | ((await read(dut, 4)) << 8)
        actual.append(value - 65536 if value & 32768 else value)
    assert actual == expected, (actual, expected)
    cycles = 0
    for byte in range(4):
        await write(dut, 9, byte + 1)
        cycles |= (await read(dut, 7)) << (byte * 8)
    assert cycles == 3080, cycles
    assert int(dut.uio_oe.value) == 0 and int(dut.uio_out.value) == 0
    # COMMIT locks the immutable image. APPEND cannot alter it or expose a result.
    await write(dut, 4, 2)
    assert await read(dut, 0) & 0x10, 'APPEND after COMMIT must fault'
    assert await read(dut, 3) == 0 and await read(dut, 4) == 0
    await write(dut, 4, 1)
    assert await read(dut, 0) & 0x0a == 0, 'BEGIN must invalidate the previous result'
    await write(dut, 2, (image[0] ^ 1) & 255)
    await write(dut, 3, (image[0] & 65535) >> 8)
    await write(dut, 4, 2)
    assert await read(dut, 0) & 0x10, 'A different model must be rejected'
    assert await read(dut, 5) == 0 and await read(dut, 6) == 0
    Path('neural_logic_pin_results.json').write_text(json.dumps({
        'status':'PASS','readback_words':6020,'vectors':1,'outputs_checked':4,
        'latency_cycles':cycles,'interface':'Submission pins only, valid for RTL and GL'
    }, indent=2))


@cocotb.test()
async def host_faults_are_visible_and_reset_recovers(dut):
    """Check malformed host traffic strictly through submission pins."""
    await reset(dut)
    # Deselection prevents host commands from taking ownership of the model.
    dut.ena.value = 0
    await write(dut, 4, 1)
    assert await read(dut, 0) == 1
    dut.ena.value = 1

    cases = [
        ('unloaded_start', [(7, 0)]),
        ('early_commit', [(4, 1), (4, 3)]),
        ('missing_staged_byte', [(4, 1), (2, 0), (4, 2)]),
        ('out_of_order_address', [(4, 1), (0, 1), (2, 0), (3, 0), (4, 2)]),
        ('invalid_address_high_bits', [(1, 32)]),
        ('invalid_input_index', [(5, 24)]),
        ('invalid_output_index', [(8, 4)]),
        ('invalid_diagnostic_page', [(9, 5)]),
        ('undefined_register', [(15, 0)]),
    ]
    checked = []
    for name, commands in cases:
        await reset(dut)
        for address, value in commands:
            await write(dut, address, value)
        status = await read(dut, 0)
        assert status & 0x10, (name, status)
        assert not status & 0x06, (name, 'busy or ready despite fault', status)
        assert await read(dut, 3) == 0 and await read(dut, 4) == 0, name
        assert await read(dut, 5) == 0 and await read(dut, 6) == 0, name
        assert int(dut.uio_oe.value) == 0 and int(dut.uio_out.value) == 0, name
        await reset(dut)
        assert await read(dut, 0) == 1, (name, 'reset recovery')
        checked.append(name)
    Path('neural_logic_pin_guard_results.json').write_text(json.dumps({
        'status': 'PASS', 'fault_cases': checked,
        'ena_command_gating_checked': True, 'reset_recovery_checked': True,
        'all_fault_outputs_zero': True, 'interface': 'Submission pins only'
    }, indent=2) + '\n')
