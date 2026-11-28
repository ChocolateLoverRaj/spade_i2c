from enum import Enum
from typing import TypedDict

from cocotb.triggers import ReadOnly, RisingEdge
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
    "restart_setup_cycles": 6,
    "data_valid_ack_time": 9,
}
async def reset(dut):
    s = SpadeExt(dut)
    s.i.rst = True
    await step(dut)
    s.i.rst = False

class Rw(Enum):
    READ = 1
    WRITE = 0

    def spade_enum(self):
        match self:
            case Rw.READ:
                return "Rw::Read"
            case Rw.WRITE:
                return "Rw::Write"

def get_7_bit_addr_byte(addr: int, rw: Rw):
    rw_bit = rw.value
    return rw_bit | addr << 1
