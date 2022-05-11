import argparse

from amaranth import *
from amaranth.build import *
from ulx4m import *

from  st7789 import *

# The OLED pins are not defined in the ULX3S platform in nmigen_boards.
oled_resource = [
    Resource("st7789", 0,
        Subsignal("oled_clk",  Pins("11", dir="o", conn=("gpio",0))),
        Subsignal("oled_mosi", Pins("10", dir="o", conn=("gpio",0))),
        Subsignal("oled_dc",   Pins("25", dir="o", conn=("gpio",0))),
        Subsignal("oled_resn", Pins("27", dir="o", conn=("gpio",0))),
        Subsignal("oled_blk",  Pins("24", dir="o", conn=("gpio",0))),
        Subsignal("oled_csn",  Pins("8", dir="o", conn=("gpio",0))),
        Attrs(IO_TYPE="LVCMOS33", DRIVE="4", PULLMODE="UP"))
]

class ST7789Test(Elaboratable):
    def elaborate(self, platform):
        led = [platform.request("led", i) for i in range(4)]

        # OLED
        oled      = platform.request("st7789")
        oled_clk  = oled.oled_clk
        oled_mosi = oled.oled_mosi
        oled_dc   = oled.oled_dc
        oled_resn = oled.oled_resn
        oled_csn  = oled.oled_csn
        oled_blk  = oled.oled_blk

        st7789 = ST7789(150000)
        m = Module()
        m.submodules.st7789 = st7789
       
        x = Signal(8)
        y = Signal(8)
        next_pixel = Signal()
 
        m.d.comb += [
            oled_clk .eq(st7789.spi_clk),
            oled_mosi.eq(st7789.spi_mosi),
            oled_dc  .eq(st7789.spi_dc),
            oled_resn.eq(st7789.spi_resn),
            oled_csn .eq(st7789.spi_csn),
            oled_blk .eq(1),
            next_pixel.eq(st7789.next_pixel),
            x.eq(st7789.x),
            y.eq(st7789.y),
        ]

        with m.If(x[4] ^ y[4]):
            m.d.comb += st7789.color.eq(x[3:8] << 6)
        with m.Else():
            m.d.comb += st7789.color.eq(y[3:8] << 11)


        m.d.comb += [
            Cat([i.o for i in led]).eq(st7789.x)
        ]

        return m

if __name__ == "__main__":
    variants = {
        '12F': ULX4M_12F_Platform,
        '45F': ULX4M_45F_Platform,
        '85F': ULX4M_85F_Platform
    }

    # Figure out which FPGA variant we want to target...
    parser = argparse.ArgumentParser()
    parser.add_argument('variant', choices=variants.keys())
    args = parser.parse_args()

    platform = variants[args.variant]()
    
    # Add the OLED resource defined above to the platform so we
    # can reference it below.
    platform.add_resources(oled_resource)

    platform.build(ST7789Test(), do_program=True)
