# `i2c`
A library for using the I2C protocol with the [Spade hardware description language](https://spade-lang.org/).

## Implemented Features
- [x] Controller Mode
- [x] Repeated Start
- [x] 10-bit addresses
- [ ] Share I2C Bus with other controllers
- [ ] Fast-mode Plus

## Usage
Import the following:
```
use i2c::{i2c_controller, Config, Req, Output, Status, AddrRw, Addr, Rw};
```
In your top module, you will need to use `inout<bool>` for the SCL and SDA pins. Like this:
```
#[no_mangle(all)]
entity top(
    // 27 MHz
    clk: clock,
    rst: bool,
    scl: inout<bool>,
    sda: inout<bool>,
)
```
And then convert them into a `(Option<bool>, inv Option<bool>)`:
```
let (scl, scl_inv) = scl.read_write();
let (sda, sda_inv) = sda.read_write();
```
Then define a `Config`. See the docs for `Config` for the requirements for `N`.

The entity takes `bool` for `sda` and `scl`, but the inputs we got from `read_write` are `Option<bool>`. The entity doesn't care about the values when it is pulling them low, so just do
```
let sda = sda == Some(true);
let scl = scl == Some(true);
```
The entity uses `ready_valid` for what command it should do, so create a port for the ready variable:
```
let (ready, ready_inv) = port();
```
Then, based on your application, define a `req: Option<Req>` variable, which will probably be derived from state that comes from `reg(clk)`.

Then, create the entity:
```
let output = inst i2c_controller(
    clk,
    rst,
    sda,
    scl,
    Rv(req, ready_inv),
    config,
);
```
Set the SDA and SCL pins according to the output:
```
set scl_inv = if output.scl { None } else { Some(false) };
set sda_inv = if output.sda { None } else { Some(false) };
```
Use `output.status` and `ready` to advance your state as commands complete. You always have to start with the `Start` command, then `ReadByte` or `WriteByte`. Then you can `Restart` or `Stop`. Note that `output.status` indicates if the command was successful or not. `Start`, `WriteByte`, and `Restart` are successful if the status is `Status::Ack` and unsuccessful if the status is `Status::Nack`. `ReadByte` outputs the byte as `Status::ReadByte`. `Stop` doesn't output anything. 

## Examples
- TODO

## I2C protocol
This is from the perspective of the controller

Starting a read or write
```
SDA    : - -- --- --- --- --- --- --- --- --- AA --- --- --- --- --- --- --- --- AA
SDA inv: H LL 666 555 444 333 222 111 000 RRR -- 000 111 222 333 444 555 666 777 -- LLH H
SCL inv: H HL LHL LHL LHL LHL LHL LHL LHL LHL LH LHL LHL LHL LHL LHL LHL LHL LHL LH LHH H
         ^ ^^ ^^^ ^                         ^ ^^                                    ^^^ ^
         a bc def g                         h ij                                    klm n
```
H - high
L - low
0 - data bit 0 (low if 1, high if 0)
R - read/write bit (low if write, high if read)
- - don't pull low
A - low to signal ACK. If this is high, that means that there was an error due to a lack of acknowledgement.

`a`: idle

`b`: START
Time between `a` and `b` can be unlimited.

Time between `b` and `c` is the start condition hold time. Our default assumption can be 1/2 of a clock cycle time. In the SSD1309 driver, it's called "T HSTART", and is specified to be at least 0.6 us. For this default the default assumption will also work, which is a sign that our default assumption is valid. 

`d`: data write
Once we pull SDA low, we pull SCL low, and we start to send clocks. The controller is not allowed to switch SDA at the same time it pulls SCL low. It has to wait a specified amount of time. This is the amount of time between `c` and `d`, and is known as the data hold time. Technically at this point, we aren't holding data. We are just holding SDA low, which is signaling the start condition. The SSD1309 specification doesn't explicitly say that the data hold time applies to the start condition, but it is safe to assume it does. For generic i2c, we can assume that the data hold time is (exactly) 1/4 of a clock cycle. SSD1309 specifies at least 0.3 us, which is <1/4 of a clock cycle, so it will work if we follow our generic timings. 

Time between `d` and `e` needs to follow 2 constraints. One is the data setup time. This is the amount of time between setting SDA to its new value and setting SCL high. For generic I2C we can assume this is exaclty 1/4 of a clock cycle. We can simply change it from its old value to the new value exactly in the middle of SCL being low. SSD1309 specifies the data setup time to be at least 0.1 us, being compatible with our generic timing. The other constraint is the clock cycle time. We should be holding SCL low for at least 1/2 of a clock cycle. We can make the clock slower than the target's fastest speed, but not faster. Practically, our time between `c` and `e` should be exactly 1/2 of a clock cycle.

`e`: data is stable for the target to read
Time beween `e` and `f` is constrained by the clock cycle. It must be at least 1/2 of a clock cycle. Practically, we will make it exactly 1/2 of a clock cycle (rounding up). 

`g`: data write
Similar to `d`. The time between `f` and `g` has the same requirement as the time between `c` and `d`, which is the data hold time.

`i`: The min time between `h` and `i` is the data hold time. Some time while the controller holds SCL low, the target will pull SDA low. It's ok if both the controller and the target pull SDA low in this time. It won't cause any data issues because no one reads during this time.It won't have any electrical problems because the lines are open drain, so it's safe for multiple devices to pull it low simultaneously.

`j`: The controller sets SCL high and reads SDA. It should be low to indicate an ACK. Based on the SSD1309 specifications, the controller should be good to read SDA at the same time as setting SCL high, because SDA should already be set by the target at the time. However, it's safest to read SDA in the middle of SCL being high. 

`k`: The controller signals the stop condition. 

`m`: The controller swiches SDA from low to high while SCL stays high. The time between  `l` and `m` is the stop condition setup time. For generic I2C it's safe to use 1/2 of a clock duration. The SSD1309 specifies at least 0.6 us, which is compatible with our generic assumption.

`n`: The controller is available to start a new transaction. The time between `m` and `n` must be at least the "idle time". For the SSD1309, that's 1.3 us. 

The most important timing is the clock cycle time. The SSD1309 specifies this to be at least 2.5us. This corresponds to a clock speed of exactly 400 kHz.

Repeated start
```
SDA    : --- AA ---  ---
SDA inv: 777 -- HHLL 000
SCL inv: LHL LH LHHL LHL
                ^^^  ^
                abc  d
```
`a`: set SDA to high before setting SCL high. The time between `a` and `b` must be at least "data setup time". . Again, a good generic I2C duration for this is 1/2 of a clock duration.

`c`: the controller changes SDA from high to low while SCL is high, indicating a repeated start condition. The time between `b` and `c` must be at least the "start condition setup time", which for the SSD1309 is 0.6 us. For a generic value, we can use 1/2 of a clock duration.
