import time
import rp2
from rp2 import asm_pio, PIO, StateMachine
from machine import Pin

#
# Output NeoPixel data via an out() pin.  Assumes that the data is in the upper 24 bits
# of each word.
# 
# There is one output pin and one set pin, both the same pin number.  That allows the
# code to use set() to output a constant value, and out() to output a variable value,
# all on the same physical pin.
#
# Ideally, we would drive this with DMA, including the mandatory delay at the end
# of data transmission.  As it is, the caller needs to send data to the FIFO fast
# enough to keep up with the data transfer, and do a delay between updates of the
# strip.
#
# Assumes that the state machine is run at 4.8 MHz.  The loop is 6 cycles, which
# means the entire loop executes at a rate of 800 kHz (4.8 MhZ / 6).
#
# The NeoPixel protocol is a simple one wire serial protocol.  It is a series of
# pulses with a frequency of 800 kHz.  Each bit is encoded as a single pulse.
# The width of the pulse determines whether the value is a 1 or 0.  (As far as I
# can tell, it samples the data line near the middle of the period.)  After all
# pixel data is transmitted, the output must remain low (50us seems to work) so
# that the pixels can update, and know that the next data is for the first pixel.
# 
# The idea is to break each period into thirds.  During the first third, the output
# is high (the start of the pulse).  During the middle third, the output is equal
# to the data bit we are transmitting.  During the last third, the output is low
# (end of the pulse).  This results in a 1 bit having a 2/3 duty cycle, and a 0
# bit having a 1/3 duty cycle.
#
@asm_pio(out_init=PIO.OUT_LOW, autopull=True, pull_thresh=24, out_shiftdir=PIO.SHIFT_LEFT,
         set_init=PIO.OUT_LOW, fifo_join=PIO.JOIN_TX)
def neopixel_write():
    # Wait for more data, while the output is low
    pull(ifempty)

    # Start the pulse by setting the output pin high.
    # Delay 1/3 of the period.
    set(pins, 1)[1]

    # Output the data bit.  In the case of a 1 bit, this will continue
    # the pulse.  In the case of a 0 bit, it will end the pulse.
    out(pins, 1)[1]

    # Set the output low.  If the data bit was 1, this ends the pulse.
    # If the data bit was 0, this just keeps the output low.
    set(pins, 0)

#
# NOTE: The NeoPixel data pin is attached to the Pico's pin 12.
#
writer = StateMachine(0, neopixel_write, freq=4_800_000, out_base=Pin(12), set_base=Pin(12))
writer.active(1)

NUM_LEDS=90

def color_wheel(offset, brightness=255):
    "Convert an offset (0-44, inclusive) to a GRBx 32-bit color"
    green = 0
    red = 0
    blue = 0
    
    # 0-14 is green-red
    if offset < 15:
        red = offset * brightness // 14
        green = brightness - red
    # 15-29 is red-blue
    elif offset < 30:
        blue = (offset - 15) * brightness // 14
        red = brightness -blue
    # 30-44 is blue-green
    else:
        green = (offset - 30) * brightness // 14
        blue = brightness - green
    
    # print("offset: {0}, red: {1}, green: {2}, blue: {3}".format(offset, red, green, blue))
    return green << 24 | red << 16 | blue << 8

colors = [color_wheel(i, 63) for i in range(45)]    # A rainbow: one of each color
colors = colors + colors    # Repeat the rainbow twice for the whole strip

def single_chase(color, reverse=False):
    """
    Light up one LED at a time, using the given color.  All other LEDs
    will be off.  By default, it goes from offset 0 to NUM_LEDS-1.
    If the `reverse` argument is true, it will go in the opposite direction.
    """
    # The order that the LEDs will light
    on_offsets = range(NUM_LEDS)
    if reverse:
        on_offsets = reversed(on_offsets)
    
    for offset in on_offsets:
        # Set LED #offset to the given color, and all others off.
        for i in range(NUM_LEDS):
            if i == offset:
                writer.put(color)
            else:
                writer.put(0)
        
        # Wait for the PIO state machine to consume all of the data we've
        # given it, then delay 50us so the NeoPixels know we are done.
        while writer.tx_fifo() > 0:
            pass
        time.sleep_us(50)

def back_and_forth_chasers():
    for color in [0x003f0000, 0x3f3f0000, 0x3f000000, 0x3f003f00, 0x00003f00, 0x003f3f00, 0x3f3f3f00]:
        single_chase(color)
        single_chase(color, reverse=True)

def sliding_rainbow(colors, times=5):
    for n in range(NUM_LEDS * times):
        for color in colors:
            writer.put(color)
        colors = colors[1:] + colors[0:1]   # Rotate the colors one spot to the left
        time.sleep_ms(100)  # Delay between updates, and slow the animation

def rainbow_chaser(colors, times=10):
    """
    Light up one LED at a time, from start to end, then back to the start,
    like back_and_forth_chasers, except that the color depends on the position
    in the strip.
    """
    for n in range(times):
        for i in range(NUM_LEDS):
            # i is the index of the LED that will be lit during this iteration

            # Update all of the LEDs in the strip.
            for j in range(NUM_LEDS):
                if i == j:
                    writer.put(colors[j])
                else:
                    writer.put(0)
            time.sleep_us(500)  # Delay between updates, and slow the animation
        
        # Do the same thing, backwards
        for i in reversed(range(NUM_LEDS)):
            for j in range(NUM_LEDS):
                if i == j:
                    writer.put(colors[j])
                else:
                    writer.put(0)
            time.sleep_us(500)

def rainbow_wave(colors, times=10):
    """
    Similar to rainbow_chaser(), except that all LEDs are on (in a rainbow),
    and one will be brighter.  The brighter one moves back and forth.
    """
    dim_colors = colors[:]
    bright_colors = [color << 2 | 0x33333300 for color in colors]

    for n in range(times):
        for i in range(NUM_LEDS):
            for j in range(NUM_LEDS):
                if i == j:
                    writer.put(bright_colors[j])
                else:
                    writer.put(dim_colors[j])
            time.sleep_us(500)
        for i in reversed(range(NUM_LEDS)):
            for j in range(NUM_LEDS):
                if i == j:
                    writer.put(bright_colors[j])
                else:
                    writer.put(dim_colors[j])
            time.sleep_us(500)

# Do the rainbow chaser the default number of times
rainbow_chaser(colors)

# Turn off all the LEDs
for i in range(NUM_LEDS):
    writer.put(0)
