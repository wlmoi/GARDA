"""Pin-only tests for the one-SRAM parameter example, also used on its netlist."""
from pathlib import Path
import sys
import cocotb
from cocotb.triggers import Timer

async def cycle(dut):
    dut.clk.value=0
    await Timer(10,units='ns')
    dut.clk.value=1
    await Timer(10,units='ns')

async def command(dut,control,data=0):
    dut.ui_in.value=control
    dut.uio_in.value=data
    await cycle(dut)
    dut.ui_in.value=0

async def reset(dut):
    dut.clk.value=0;dut.ena.value=1;dut.rst_n.value=0
    dut.ui_in.value=0;dut.uio_in.value=0
    await cycle(dut);await cycle(dut)
    dut.rst_n.value=1
    await cycle(dut)

async def read(dut,address):
    await command(dut,1,address)
    await cycle(dut)
    low=int(dut.uo_out.value)
    dut.ui_in.value=16
    await cycle(dut)
    return low|(int(dut.uo_out.value)<<8)

async def store(dut,address,value):
    await command(dut,1,address)
    await command(dut,2,value&255)
    await command(dut,4,value>>8)
    await command(dut,8)

@cocotb.test()
async def parameter_image_and_memory_controls(dut):
    await reset(dut)
    dut.ui_in.value=32
    await cycle(dut)
    assert int(dut.uo_out.value)==0xA7
    root=Path(__file__).resolve().parents[2]
    sys.path.insert(0,str(root/'reference_model'))
    from neural_reference import read_mem
    words=read_mem('bram_unified_weights.mem')
    words=[word&65535 for word in words]
    image=words[5760:6016]
    assert len(image)==256
    for address,value in enumerate(image):
        await store(dut,address,value)
    for address,value in enumerate(image):
        assert await read(dut,address)==value,(address,value)
    # Exercise every data bit and both endpoints, independently of W3 contents.
    for address in range(256):
        await store(dut,address,((address*257)^0xA55A)&65535)
    for address in range(256):
        expected=((address*257)^0xA55A)&65535
        assert await read(dut,address)==expected,(address,expected)
    # Writes retain the read output. Disabling the macro retains it as well.
    before=await read(dut,19)
    await store(dut,19,0x1234)
    dut.ui_in.value=0
    await Timer(1,units='ns')
    assert int(dut.uo_out.value)==before&255
    dut.ena.value=0
    await command(dut,1,20)
    await command(dut,2,0xFF);await command(dut,4,0xFF);await command(dut,8)
    assert int(dut.uo_out.value)==before&255
    dut.ena.value=1
    assert await read(dut,19)==0x1234
    assert await read(dut,20)==((20*257)^0xA55A)&65535
    await reset(dut)
    assert await read(dut,19)==0x1234
    assert await read(dut,255)==((255*257)^0xA55A)&65535
    assert int(dut.uio_oe.value)==0
    assert int(dut.uio_out.value)==0
