# top = i2c_controller_by_bit_th

from enum import Enum
from typing import TypedDict

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ReadOnly, RisingEdge, Timer
from spade import SpadeExt


async def settle():
    """
    Wait for the current cycle to propagate, can sample outputs after this
    """

    await ReadOnly()


async def advance(dut):
    """
    Cross the clock edge. Drive DUT inputs after this returns.
    """

    await RisingEdge(dut.clk)


async def step(dut):
    """
    Settle then advance, without sampling in between.
    """

    await settle()
    await advance(dut)


class Config(TypedDict):
    start_hold_cycles: int
    data_hold_cycles: int
    data_setup_cycles: int
    scl_low_cycles: int
    scl_high_cycles: int
    scl_cycles: int
    stop_setup_cycles: int
    after_stop_cycles: int
    restart_setup_cycles: int

    data_valid_ack_time: int


async def reset(dut):
    s = SpadeExt(dut)
    s.i.rst = True
    await step(dut)
    s.i.rst = False


async def setup(config: Config, dut):
    s = SpadeExt(dut)
    clk = dut.clk

    # 1. Start 10 MHz clock (100 ns period)
    cocotb.start_soon(Clock(clk, 100, unit="ns").start())

    s.i.rst = False
    s.i.sda = True
    s.i.scl = True
    s.i.req._data = "None"
    s.i.config.start_hold_cycles = config["start_hold_cycles"]
    s.i.config.data_hold_cycles = config["data_hold_cycles"]
    s.i.config.data_setup_cycles = config["data_setup_cycles"]
    s.i.config.scl_low_cycles = config["scl_low_cycles"]
    s.i.config.scl_high_cycles = config["scl_high_cycles"]
    s.i.config.scl_cycles = config["scl_cycles"]
    s.i.config.stop_setup_cycles = config["stop_setup_cycles"]
    s.i.config.after_stop_cycles = config["after_stop_cycles"]
    s.i.config.restart_setup_cycles = config["restart_setup_cycles"]

    await reset(dut)


# Based on the I2C specification and SSD1306 specification
config_400_khz: Config = {
    "start_hold_cycles": 6,
    "data_hold_cycles": 3,
    "data_setup_cycles": 1,
    "scl_low_cycles": 13,
    "scl_high_cycles": 6,
    "scl_cycles": 25,
    "stop_setup_cycles": 6,
    "after_stop_cycles": 13,
    "restart_setup_cycles": 13,
    "data_valid_ack_time": 9,
}


async def next_cycle_after_rising(clk):
    await RisingEdge(clk)
    await Timer(1, unit="ns")


async def start(dut, config: Config):
    s = SpadeExt(dut)
    s.i.req._data = "Some(ReqByBit::Start)"

    for _ in range(config["start_hold_cycles"]):
        await step(dut)
        s.o.sda.assert_eq(False)
        s.o.scl.assert_eq(True)
        s.o.read_bit.assert_eq("None")
        s.i.req.ready.assert_eq(False)

    count = config["data_hold_cycles"]
    for i in range(count):
        await step(dut)
        s.o.sda.assert_eq(False)
        s.o.scl.assert_eq(False)
        s.o.read_bit.assert_eq("None")
        s.i.req.ready.assert_eq(i == count - 1)


async def write_bit(dut, config: Config, cycles_low: int, bit: bool):
    s = SpadeExt(dut)
    bit_str = "true" if bit else "false"
    s.i.req._data = f"Some(ReqByBit::WriteBit{{bit:{bit_str}}})"

    for i in range(config["scl_cycles"] - config["scl_high_cycles"] - cycles_low):
        await step(dut)
        s.o.sda.assert_eq(bit)
        s.o.scl.assert_eq(False)
        s.o.read_bit.assert_eq("None")
        s.i.req.ready.assert_eq(False)

    for i in range(config["scl_high_cycles"]):
        await step(dut)
        s.o.sda.assert_eq(bit)
        s.o.scl.assert_eq(True)
        s.o.read_bit.assert_eq("None")
        s.i.req.ready.assert_eq(False)

    count = config["data_hold_cycles"]
    for i in range(count):
        await step(dut)
        s.o.sda.assert_eq(bit)
        s.o.scl.assert_eq(False)
        s.o.read_bit.assert_eq("None")
        s.i.req.ready.assert_eq(i == count - 1)


async def write_byte(dut, config: Config, cycles_low: int, byte: int, ack = True):
    for i in range(8):
        bit = (byte >> (7 - i)) & 1 != 0
        current_cycles_low = cycles_low if i == 0 else config["data_hold_cycles"]
        await write_bit(dut, config, current_cycles_low, bit)
    # Read ACK
    await read_bit(dut, config, config["data_hold_cycles"], not ack)


async def read_bit(dut, config: Config, cycles_low: int, bit: bool):
    s = SpadeExt(dut)
    s.i.req._data = "Some(ReqByBit::ReadBit)"
    # Simulate the target instantly ACKing
    s.i.sda = bit

    for i in range(config["scl_cycles"] - config["scl_high_cycles"] - cycles_low):
        await step(dut)
        s.o.sda.assert_eq(True)
        s.o.scl.assert_eq(False)
        s.o.read_bit.assert_eq("None")
        s.i.req.ready.assert_eq(False)

    count = config["scl_high_cycles"]
    for i in range(count):
        await step(dut)
        s.o.sda.assert_eq(True)
        s.o.scl.assert_eq(True)
        bit_str = "true" if bit else "false"
        s.o.read_bit.assert_eq(f"Some({bit_str})" if i == 2 else "None")
        s.i.req.ready.assert_eq(i == count - 1)


async def stop(dut, config: Config, cycles_low: int):
    s = SpadeExt(dut)
    s.i.req._data = "Some(ReqByBit::Stop)"

    for i in range(config["scl_low_cycles"] - cycles_low):
        await step(dut)
        s.o.sda.assert_eq(False)
        s.o.scl.assert_eq(False)
        s.o.read_bit.assert_eq("None")
        s.i.req.ready.assert_eq(False)

    for i in range(config["stop_setup_cycles"]):
        await step(dut)
        s.o.sda.assert_eq(False)
        s.o.scl.assert_eq(True)
        s.o.read_bit.assert_eq("None")
        s.i.req.ready.assert_eq(False)

    count = config["after_stop_cycles"]
    for i in range(count):
        await step(dut)
        s.o.sda.assert_eq(True)
        s.o.scl.assert_eq(True)
        s.o.read_bit.assert_eq("None")
        s.i.req.ready.assert_eq(i == count - 1)


async def restart(dut, config: Config, cycles_low: int):
    s = SpadeExt(dut)
    s.i.req._data = "Some(ReqByBit::Restart)"

    for i in range(config["scl_low_cycles"] - cycles_low):
        await step(dut)
        s.o.sda.assert_eq(True)
        s.o.scl.assert_eq(False)
        s.o.read_bit.assert_eq("None")
        s.i.req.ready.assert_eq(False)

    for i in range(config["restart_setup_cycles"]):
        await step(dut)
        s.o.sda.assert_eq(True)
        s.o.scl.assert_eq(True)
        s.o.read_bit.assert_eq("None")
        s.i.req.ready.assert_eq(False)

    for i in range(config["start_hold_cycles"]):
        await step(dut)
        s.o.sda.assert_eq(False)
        s.o.scl.assert_eq(True)
        s.o.read_bit.assert_eq("None")
        s.i.req.ready.assert_eq(False)

    count = config["data_hold_cycles"]
    for i in range(count):
        await step(dut)
        s.o.sda.assert_eq(False)
        s.o.scl.assert_eq(False)
        s.o.read_bit.assert_eq("None")
        s.i.req.ready.assert_eq(i == count - 1)


async def read_byte(dut, config: Config, cycles_low: int, byte: int):
    for i in range(8):
        bit = (byte >> (7 - i)) & 1 != 0
        current_cycles_low = cycles_low if i == 0 else 0
        await read_bit(dut, config, current_cycles_low, bit)
    # ACK
    await write_bit(dut, config, 0, False)


async def idle(dut):
    s = SpadeExt(dut)
    s.i.req._data = "None"

    await step(dut)
    s.o.sda.assert_eq(True)
    s.o.scl.assert_eq(True)
    s.o.read_bit.assert_eq("None")
    s.i.req.ready.assert_eq(False)


class Rw(Enum):
    READ = 1
    WRITE = 0


def get_addr_byte(addr: int, rw: Rw):
    rw_bit = rw.value
    return rw_bit | addr << 1


@cocotb.test()
async def test_idle(dut):
    await setup(config_400_khz, dut)
    await idle(dut)


@cocotb.test()
async def test_start_addr_write_0_stop(dut):
    "0-byte writes are used to check the presence of a device"
    await setup(config_400_khz, dut)
    await start(dut, config_400_khz)
    await write_byte(
        dut,
        config_400_khz,
        config_400_khz["data_hold_cycles"],
        get_addr_byte(0x3C, Rw.WRITE),
    )
    await stop(dut, config_400_khz, 0)
    await idle(dut)

@cocotb.test()
async def test_no_target(dut):
    "A write was attempted but the target didn't respond"
    await setup(config_400_khz, dut)
    await start(dut, config_400_khz)
    await write_byte(
        dut,
        config_400_khz,
        config_400_khz["data_hold_cycles"],
        get_addr_byte(0x3C, Rw.WRITE),
        ack=False
    )
    await stop(dut, config_400_khz, 0)
    await idle(dut)

@cocotb.test()
async def test_start_addr_write_2_stop(dut):
    "Tests writing 2 bytes to a device"
    await setup(config_400_khz, dut)
    await start(dut, config_400_khz)
    await write_byte(
        dut,
        config_400_khz,
        config_400_khz["data_hold_cycles"],
        get_addr_byte(0x3C, Rw.WRITE),
    )
    for i in range(2):
        await write_byte(dut, config_400_khz, 0, i)
    await stop(dut, config_400_khz, 0)
    await idle(dut)


@cocotb.test()
async def test_start_addr_write_2_restart_addr_read_2_stop(dut):
    "Many devices use write, restart, read|write. The first write is the register address."
    await setup(config_400_khz, dut)

    await start(dut, config_400_khz)
    await write_byte(
        dut,
        config_400_khz,
        config_400_khz["data_hold_cycles"],
        get_addr_byte(0x3C, Rw.WRITE),
    )
    for i in range(1):
        await write_byte(dut, config_400_khz, 0, i)

    await restart(dut, config_400_khz, 0)
    await write_byte(
        dut,
        config_400_khz,
        config_400_khz["data_hold_cycles"],
        get_addr_byte(0x3C, Rw.READ),
    )
    for i in range(1):
        await read_byte(dut, config_400_khz, 0 if i == 0 else config_400_khz["data_hold_cycles"], 0x03)

    await stop(dut, config_400_khz, config_400_khz["data_hold_cycles"])
    await idle(dut)
