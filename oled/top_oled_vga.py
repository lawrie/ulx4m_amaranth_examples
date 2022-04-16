import argparse

from amaranth import *
from amaranth.build import *
from ulx4m import *

from vga import VGA
from oled_vga import *

oled_resource = [
    Resource("oled", 0,
        Subsignal("oled_clk",  Pins("17", dir="o", conn=("gpio",0))),
        Subsignal("oled_mosi", Pins("15", dir="o", conn=("gpio",0))),
        Subsignal("oled_dc",   Pins("13", dir="o", conn=("gpio",0))),
        Subsignal("oled_resn", Pins("14", dir="o", conn=("gpio",0))),
        Subsignal("oled_csn",  Pins("12", dir="o", conn=("gpio",0))),
        Attrs(IO_TYPE="LVCMOS33", DRIVE="4", PULLMODE="UP"))
]

class Top_OLED_VGA(Elaboratable):
    def __init__(self):
        # On board blinky
        self.o_led = Signal(4)

        # OLED
        self.o_oled_csn  = Signal()
        self.o_oled_clk  = Signal()
        self.o_oled_mosi = Signal()
        self.o_oled_dc   = Signal()
        self.o_oled_resn = Signal()

    def ports(self) -> []:
        return [
            self.o_oled_clk,
            self.o_oled_csn,
            self.o_oled_dc,
            self.o_oled_mosi,
            self.o_oled_resn
        ]

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        R_counter = Signal(64)
        m.d.sync += R_counter.eq(R_counter + 1)

        # VGA signal generator
        vga_hsync_test = Signal()
        vga_vsync_test = Signal()
        vga_blank_test = Signal()
        vga_rgb_test   = Signal(8)

        m.submodules.vga = vga = DomainRenamer({"pixel":"sync"})(VGA(
            resolution_x      = 96,
            hsync_front_porch = 1800,
            hsync_pulse       = 1,
            hsync_back_porch  = 1800,
            resolution_y      = 64,
            vsync_front_porch = 1,
            vsync_pulse       = 1,
            vsync_back_porch  = 1,
            bits_x            = 12,
            bits_y            = 8
        ))
        m.d.comb += [
            vga.i_clk_en.eq(1),
            vga.i_test_picture.eq(1),
            vga.i_r.eq(0),
            vga.i_g.eq(0),
            vga.i_b.eq(0),
            vga_rgb_test[5:8].eq(vga.o_vga_r[5:8]),
            vga_rgb_test[2:5].eq(vga.o_vga_g[5:8]),
            vga_rgb_test[0:2].eq(vga.o_vga_b[5:8]),
            vga_hsync_test.eq(vga.o_vga_hsync),
            vga_vsync_test.eq(vga.o_vga_vsync),
            vga_blank_test.eq(vga.o_vga_blank),
        ]

        m.submodules.oled = oled = OLED_VGA(color_bits=len(vga_rgb_test))
        m.d.comb += [
            oled.i_clk_en.eq(R_counter[0]),
            oled.i_clk_pixel_ena.eq(1),
            oled.i_blank.eq(vga_blank_test),
            oled.i_hsync.eq(vga_hsync_test),
            oled.i_vsync.eq(vga_vsync_test),
            oled.i_pixel.eq(vga_rgb_test),
            self.o_oled_resn.eq(oled.o_spi_resn),
            self.o_oled_clk .eq(oled.o_spi_clk),
            self.o_oled_csn .eq(oled.o_spi_csn),
            self.o_oled_dc  .eq(oled.o_spi_dc),
            self.o_oled_mosi.eq(oled.o_spi_mosi),
        ]

        m.d.comb += [
            self.o_led[0].eq(self.o_oled_resn),
            self.o_led[1].eq(self.o_oled_csn),
            self.o_led[2].eq(self.o_oled_dc),
            self.o_led[3].eq(self.o_oled_clk),
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
    parser.add_argument("--tool", default="dfu")
    args = parser.parse_args()

    m = Module()
    m.submodules.top = top = Top_OLED_VGA()

    platform = variants[args.variant]()

    # Add the OLED resource defined above to the platform so we
    # can reference it below.
    platform.add_resources(oled_resource)

    # LEDs
    leds = [platform.request("led", 0),
            platform.request("led", 1),
            platform.request("led", 2),
            platform.request("led", 3)]

    for i in range(len(leds)):
        m.d.comb += leds[i].eq(top.o_led[i])

    # OLED
    oled      = platform.request("oled")

    m.d.comb += [
        oled.oled_clk .eq(top.o_oled_clk),
        oled.oled_mosi.eq(top.o_oled_mosi),
        oled.oled_dc  .eq(top.o_oled_dc),
        oled.oled_resn.eq(top.o_oled_resn),
        oled.oled_csn .eq(top.o_oled_csn)
    ]

    platform.build(m, do_program=True, nextpnr_opts="--timing-allow-fail", program_opts={"tool":args.tool})
