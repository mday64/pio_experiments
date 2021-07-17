import time
import rp2
from rp2 import PIO
from machine import Pin

#
# An 8-bit parallel bus with clock.  The data is in the lower 8 bits of
# each FIFO word.
#
# There are 8 output pins (on consecutive GPIOs).  The least significant
# bit will be written to out_base, and the most significant will be
# written to out_base+7.
#
# There is one clock pin, sideset_base.  The clock will go high at the
# same time the data pins are updated.  The clock will be low while the
# state machine is waiting for data in its FIFO.
#
@rp2.asm_pio(out_init=(PIO.OUT_LOW,)*8, sideset_init=PIO.OUT_LOW,
             autopull=True, pull_thresh=8, out_shiftdir=PIO.SHIFT_RIGHT,
             fifo_join=PIO.JOIN_TX)
def parallel():
    # Set the clock pin low and wait for data in the FIFO.
    # This means the clock will be low while the state machine is
    # waiting for more data.
    pull(ifempty)    .side(0)

    # Output the data to the data pins and set the clock high
    out(pins, 8)     .side(1)

#
# An 8-bit parallel bus with clock.
#
# This is like parallel(), above, except that the data lines are updated
# before the clock goes high.  If you have trouble with the above routine
# because the data isn't stable as the clock is going high, then this
# would help.
#
# Note: the extra delay on the nop is there so that the clock will have
# a 50% duty cycle if the FIFO is supplied fast enough for the state
# machine to run at its maximum speed.  If the delay is removed, then
# the clock would have a 33.33% duty cycle (if the FIFO is supplied
# fast enough).
#
@rp2.asm_pio(out_init=(PIO.OUT_LOW,)*8, sideset_init=PIO.OUT_LOW,
             autopull=True, pull_thresh=8, out_shiftdir=PIO.SHIFT_RIGHT,
             fifo_join=PIO.JOIN_TX)
def parallel_delayed_clock():
    pull(ifempty)    .side(0)
    out(pins, 8)     .side(0)
    nop()            .side(1) [1]

#
# I connected 8 red LEDs to the data pins (GPIO 2 through 9) and a yellow LED to
# GPIO 1 for the clock.  All LEDs were connected to ground through current limiting
# resistors.
#
# The frequency is set to its minimum possible so that the clock will be (barely)
# visible as a brief flash.
#
writer = rp2.StateMachine(0, parallel, freq=2_000, out_base=Pin(2), sideset_base=Pin(1))
writer.active(1)

# Cycle through all 8-bit values, with a brief delay to make the values visible
for i in range(256):
    writer.put(int(i))
    time.sleep_ms(50)

# Pause for 1 second with all of the data LEDs on
time.sleep_ms(1000)

# Turn the data LEDs off, and turn off the state machine.  The sleep is to
# let the FIFO drain, which will cause the clock to go low (off).
writer.put(0)
time.sleep_ms(10)
writer.active(0)
