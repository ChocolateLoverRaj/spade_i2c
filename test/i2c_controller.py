# top = i2c_controller_th

import sys
from os import environ
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from spade import SpadeExt

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(f"{environ['SWIM_ROOT']}")
from util import Config, Rw, config_400_khz, get_7_bit_addr_byte, reset, step


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


async def idle(dut):
    s = SpadeExt(dut)
    s.i.req._data = "None"

    await step(dut)
    s.o.sda.assert_eq(True)
    s.o.scl.assert_eq(True)
    s.o.status.assert_eq("None")
    s.i.req.ready.assert_eq(False)

async def start(dut, config: Config):
    s = SpadeExt(dut)
    for _ in range(config["start_hold_cycles"]):
        await step(dut)
        s.o.sda.assert_eq(False)
        s.o.scl.assert_eq(True)
        s.o.status.assert_eq("None")
        s.i.req.ready.assert_eq(False)
    for i in range(config["data_hold_cycles"]):
        await step(dut)
        s.o.sda.assert_eq(False)
        s.o.scl.assert_eq(False)
        s.o.status.assert_eq("None")
        s.i.req.ready.assert_eq(False)

async def restart(dut, config: Config, cycles_low: int):
    s = SpadeExt(dut)
    for i in range(config["scl_low_cycles"] - cycles_low):
        await step(dut)
        s.o.sda.assert_eq(True)
        s.o.scl.assert_eq(False)
        s.o.status.assert_eq("None")
        s.i.req.ready.assert_eq(False)

    for i in range(config["restart_setup_cycles"]):
        await step(dut)
        s.o.sda.assert_eq(True)
        s.o.scl.assert_eq(True)
        s.o.status.assert_eq("None")
        s.i.req.ready.assert_eq(False)

    for i in range(config["start_hold_cycles"]):
        await step(dut)
        s.o.sda.assert_eq(False)
        s.o.scl.assert_eq(True)
        s.o.status.assert_eq("None")
        s.i.req.ready.assert_eq(False)

    count = config["data_hold_cycles"]
    for i in range(count):
        await step(dut)
        s.o.sda.assert_eq(False)
        s.o.scl.assert_eq(False)
        s.o.status.assert_eq("None")
        s.i.req.ready.assert_eq(False)

async def write_bit(dut, config: Config, cycles_low: int, bit: bool, expect_ready: bool):
    s = SpadeExt(dut)
    for i in range(config["scl_cycles"] - config["scl_high_cycles"] - cycles_low):
        await step(dut)
        s.o.sda.assert_eq(bit)
        s.o.scl.assert_eq(False)
        s.o.status.assert_eq("None")
        s.i.req.ready.assert_eq(False)

    for i in range(config["scl_high_cycles"]):
        await step(dut)
        s.o.sda.assert_eq(bit)
        s.o.scl.assert_eq(True)
        s.o.status.assert_eq("None")
        s.i.req.ready.assert_eq(False)

    count = config["data_hold_cycles"]
    for i in range(count):
        await step(dut)
        s.o.sda.assert_eq(bit)
        s.o.scl.assert_eq(False)
        s.o.status.assert_eq("None")
        s.i.req.ready.assert_eq(i == count - 1 and expect_ready)

async def read_bit(dut, config: Config, cycles_low: int, bit: bool, expected_status: str|None, expect_ready: bool):
    s = SpadeExt(dut)
    # Simulate the target instantly ACKing
    s.i.sda = bit

    for i in range(config["scl_cycles"] - config["scl_high_cycles"] - cycles_low):

        await step(dut)
        s.o.sda.assert_eq(True)
        s.o.scl.assert_eq(False)
        s.o.status.assert_eq("None")
        s.i.req.ready.assert_eq(False)

    count = config["scl_high_cycles"]
    for i in range(count):
        await step(dut)
        s.o.sda.assert_eq(True)
        s.o.scl.assert_eq(True)
        s.o.status.assert_eq(f"Some({expected_status})" if i == count // 2 - 1 and (expected_status is not None) else "None")
        s.i.req.ready.assert_eq(i == count - 1 and expect_ready)

    s.i.sda = True

async def write_byte(dut, config: Config, cycles_low: int, byte: int, ack: bool, expected_status: str|None, expect_ready: bool):
    for i in range(8):
        bit = (byte >> (7 - i)) & 1 != 0
        current_cycles_low = cycles_low if i == 0 else config["data_hold_cycles"]
        await write_bit(dut, config, current_cycles_low, bit, False)
    # Read ACK
    await read_bit(dut, config, config["data_hold_cycles"], not ack, expected_status, expect_ready)

async def write_byte_req(dut, config: Config, cycles_low: int, byte: int, ack: bool, expected_status: str|None, expect_ready: bool):
    s = SpadeExt(dut)
    s.i.req._data = f"Some(Req::WriteByte({byte}))"
    await write_byte(dut, config, cycles_low, byte, ack, expected_status, expect_ready)

async def read_byte_req(dut, config: Config, cycles_low: int, byte: int, is_last: bool):
    s = SpadeExt(dut)
    is_last_str = "true" if is_last else "false"
    s.i.req._data = f"Some(Req::ReadByte({is_last_str}))"
    for i in range(8):
        bit = (byte >> (7 - i)) & 1 != 0
        current_cycles_low = cycles_low if i == 0 else 0
        await read_bit(dut, config, current_cycles_low, bit, f"Status::ReadByte({byte})" if i == 7 else None, False)
    # ACK
    await write_bit(dut, config, 0, is_last, True)

async def send_10_bit_addr(dut, config: Config, addr: int, rw: Rw, acks: int):
    s = SpadeExt(dut)
    s.i.req._data = f"Some(Req::Start(AddrRw(Addr::_10Bit({addr}), {rw.spade_enum()})))"
    byte_0 = rw.value | (((addr >> 8) & 1) << 1) | (((addr >> 9) & 1) << 2) | 0b11110 << 3
    byte_1 = addr & 0xFF
    await start(dut, config)

    if acks == 0:
        await write_byte(dut, config, config["data_hold_cycles"], byte_0, False, "Status::Nack", True)
        return

    await write_byte(dut, config, config["data_hold_cycles"], byte_0, True, None, False)

    if acks == 1:
        await write_byte(dut, config, 0, byte_1, False, "Status::Nack", True)
        return

    await write_byte(dut, config, 0, byte_1, True, "Status::Ack", True)

async def send_7_bit_addr(dut, config: Config, addr: int, rw: Rw, ack: bool, repeated: bool, cycles_low: int):
    s = SpadeExt(dut)
    variant = "Restart" if repeated else "Start"
    s.i.req._data = f"Some(Req::{variant}(AddrRw(Addr::_7Bit({addr}), {rw.spade_enum()})))"
    if repeated:
        await restart(dut, config, cycles_low)
    else:
        await start(dut, config)

    if not ack:
        await write_byte(dut, config, config["data_hold_cycles"], get_7_bit_addr_byte(addr, rw), False, "Status::Nack", True)
        return

    await write_byte(dut, config, config["data_hold_cycles"], get_7_bit_addr_byte(addr, rw), True, "Status::Ack", True)

async def stop(dut, config: Config, cycles_low: int):
    s = SpadeExt(dut)
    s.i.req._data = "Some(Req::Stop)"

    for i in range(config["scl_low_cycles"] - cycles_low):
        await step(dut)
        s.o.sda.assert_eq(False)
        s.o.scl.assert_eq(False)
        s.o.status.assert_eq("None")
        s.i.req.ready.assert_eq(False)

    for i in range(config["stop_setup_cycles"]):
        await step(dut)
        s.o.sda.assert_eq(False)
        s.o.scl.assert_eq(True)
        s.o.status.assert_eq("None")
        s.i.req.ready.assert_eq(False)

    count = config["after_stop_cycles"]
    for i in range(count):
        await step(dut)
        s.o.sda.assert_eq(True)
        s.o.scl.assert_eq(True)
        s.o.status.assert_eq("None")
        s.i.req.ready.assert_eq(i == count - 1)

@cocotb.test()
async def test_idle(dut):
    await setup(config_400_khz, dut)
    await idle(dut)

@cocotb.test()
async def test_7_bit_addr_nack(dut):
    "Simulates a scenario where the target is not present"
    await setup(config_400_khz, dut)
    await send_7_bit_addr(dut, config_400_khz, 0x3C, Rw.WRITE, False, False, 0)

@cocotb.test()
async def test_7_bit_addr(dut):
    await setup(config_400_khz, dut)
    await send_7_bit_addr(dut, config_400_khz, 0x3C, Rw.WRITE, True, False, 0)

@cocotb.test()
async def test_10_bit_addr_immediate_nack(dut):
    "Simulates a scenario where there are no 10-bit targets on the bus"
    await setup(config_400_khz, dut)
    await send_10_bit_addr(dut, config_400_khz, 0x2A5, Rw.WRITE, 0)

@cocotb.test()
async def test_10_bit_addr_late_nack(dut):
    "Simulates a scenario where there is at least 1 other 10-bit target with the same bits 8..=9 on the bus but the wanted target is not present"
    await setup(config_400_khz, dut)
    await send_10_bit_addr(dut, config_400_khz, 0x2A5, Rw.WRITE, 1)

@cocotb.test()
async def test_10_bit_addr(dut):
    await setup(config_400_khz, dut)
    await send_10_bit_addr(dut, config_400_khz, 0x2A5, Rw.WRITE, 2)

@cocotb.test()
async def test_7_bit_write_2_stop(dut):
    await setup(config_400_khz, dut)
    await send_7_bit_addr(dut, config_400_khz, 0x3C, Rw.WRITE, True, False, 0)
    for i in range(2):
        value = 15 + i
        await write_byte_req(dut, config_400_khz, 0, value, True, "Status::Ack", True)
    await stop(dut, config_400_khz, 0)

@cocotb.test()
async def test_7_bit_write_2_restart_read_2_stop(dut):
    await setup(config_400_khz, dut)
    await send_7_bit_addr(dut, config_400_khz, 0x3C, Rw.WRITE, True, False, 0)
    for i in range(2):
        value = 15 + i
        await write_byte_req(dut, config_400_khz, 0, value, True, "Status::Ack", True)
    await send_7_bit_addr(dut, config_400_khz, 0x3C, Rw.READ, True, True, 0)
    bytes_to_read = 2
    for i in range(bytes_to_read):
        value = i
        await read_byte_req(dut, config_400_khz, 0 if i == 0 else config_400_khz["data_hold_cycles"], value, i == bytes_to_read - 1)
    await stop(dut, config_400_khz, config_400_khz["data_hold_cycles"])
