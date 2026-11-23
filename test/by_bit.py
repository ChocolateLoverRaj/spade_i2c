# top = i2c_controller_by_bit_th

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge, ReadOnly, Timer
from spade import SpadeExt

async def setup(dut):
    s = SpadeExt(dut)
    clk = dut.clk

    # 1. Start 10 MHz clock (100 ns period)
    cocotb.start_soon(Clock(clk, 100, unit="ns").start())

    s.i.rst = False
    s.i.sda = True
    s.i.scl = True
    s.i.req._data = "None"
    s.i.config.start_hold_cycles = 6;
    s.i.config.data_hold_cycles = 3;
    s.i.config.data_setup_cycles = 1;
    s.i.config.scl_low_cycles = 13;
    s.i.config.scl_high_cycles = 6;
    s.i.config.scl_cycles = 25;
    s.i.config.stop_setup_cycles = 6;
    s.i.config.after_stop_cycles = 13;
    s.i.config.restart_setup_cycles = 6;

    return (s, clk)

async def reset(dut):
    s = SpadeExt(dut)
    clk = dut.clk
    s.i.rst = True
    await FallingEdge(clk)
    s.i.rst = False
    await FallingEdge(clk)


@cocotb.test()
async def idle(dut):
    (s, _clk) = await setup(dut)
    await reset(dut)

    s.o.sda.assert_eq(True)
    s.o.scl.assert_eq(True)
    s.o.read_bit.assert_eq("None")
    s.i.req.ready.assert_eq(False)

@cocotb.test()
async def _start(dut):
    (s, clk) = await setup(dut)

    s.i.req._data = "Some(ReqByBit::Start)"

    await reset(dut)

    # Next 6 clocks should be...
    for _ in range(6):
        s.o.sda.assert_eq(False)
        s.o.scl.assert_eq(True)
        s.o.read_bit.assert_eq("None")
        s.i.req.ready.assert_eq(False)

        await FallingEdge(clk)

    # Next 3 clocks should be...
    for i in range(3):
        s.o.sda.assert_eq(False)
        s.o.scl.assert_eq(False)
        s.o.read_bit.assert_eq("None")
        s.i.req.ready.assert_eq(i == 2)

        await FallingEdge(clk)

async def next_cycle_after_rising(clk):
    await RisingEdge(clk)
    await Timer(1, unit="ns")

@cocotb.test()
async def start(dut):
    (s, clk) = await setup(dut)
    s.i.req._data = "Some(ReqByBit::Start)"

    # await reset(dut)
    s.i.rst = True
    await FallingEdge(clk)
    s.i.rst = False

    # Next 6 clocks should be...
    for _ in range(6):
        await next_cycle_after_rising(clk)
        s.o.sda.assert_eq(False)
        s.o.scl.assert_eq(True)
        s.o.read_bit.assert_eq("None")
        s.i.req.ready.assert_eq(False)
        # await FallingEdge(clk)

    # Next 3 clocks should be...
    for i in range(3):
        await next_cycle_after_rising(clk)
        s.o.sda.assert_eq(False)
        s.o.scl.assert_eq(False)
        s.o.read_bit.assert_eq("None")
        s.i.req.ready.assert_eq(i == 2)
        # await FallingEdge(clk)

    # Now pretend we're sending an addr
    addr = 0x3C
    read_write_bit = 0
    byte = read_write_bit | addr << 1

    for i in range(8):
        await FallingEdge(clk)
        bit = (byte >> (7-i)) & 1 != 0
        bit = "true" if bit else "false"
        s.i.req._data = f"Some(ReqByBit::WriteBit{{bit:{bit}}})"

        # Next 16 cycles should be...
        for i in range(16):
            await next_cycle_after_rising(clk)
            s.o.sda.assert_eq(bit)
            s.o.scl.assert_eq(False)
            s.o.read_bit.assert_eq("None")
            s.i.req.ready.assert_eq(False)
            # await FallingEdge(clk)


        # Next 6 cycles
        for i in range(6):
            await next_cycle_after_rising(clk)
            s.o.sda.assert_eq(bit)
            s.o.scl.assert_eq(True)
            s.o.read_bit.assert_eq("None")
            s.i.req.ready.assert_eq(False)
            # await FallingEdge(clk)


        # Next 3 cycles
        for i in range(3):
            await next_cycle_after_rising(clk)
            s.o.sda.assert_eq(bit)
            s.o.scl.assert_eq(False)
            s.o.read_bit.assert_eq("None")
            s.i.req.ready.assert_eq(i == 2)
            # await FallingEdge(clk)
