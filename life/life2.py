import argparse

from amaranth import *
from amaranth.build import *
from amaranth_boards.ulx3s import *

from vga2dvid import VGA2DVID
from vga import VGA
from vga_timings import *
from ecp5pll import ECP5PLL

# The GPDI pins are not defined in the ULX3S platform in nmigen_boards. I've created a
# pull request, so until it is accepted and merged, we can define it here and add to
# the platform ourselves.
gpdi_resource = [
    # GPDI
    Resource("gpdi",     0, DiffPairs("A16", "B16"), Attrs(IO_TYPE="LVCMOS33D", DRIVE="4")),
    Resource("gpdi",     1, DiffPairs("A14", "C14"), Attrs(IO_TYPE="LVCMOS33D", DRIVE="4")),
    Resource("gpdi",     2, DiffPairs("A12", "A13"), Attrs(IO_TYPE="LVCMOS33D", DRIVE="4")),
    Resource("gpdi",     3, DiffPairs("A17", "B18"), Attrs(IO_TYPE="LVCMOS33D", DRIVE="4")),
    Resource("gpdi_eth", 0, DiffPairs("A19", "B20"), Attrs(IO_TYPE="LVCMOS33D", DRIVE="4")),
    Resource("gpdi_cec", 0, Pins("A18"),             Attrs(IO_TYPE="LVCMOS33",  DRIVE="4", PULLMODE="UP")),
    Resource("gpdi_sda", 0, Pins("B19"),             Attrs(IO_TYPE="LVCMOS33",  DRIVE="4", PULLMODE="UP")),
    Resource("gpdi_scl", 0, Pins("E12"),             Attrs(IO_TYPE="LVCMOS33",  DRIVE="4", PULLMODE="UP")),
]

class Life(Elaboratable):
    def __init__(self,
                 timing: VGATiming, # VGATiming class
                 xadjustf=0, # adjust -3..3 if no picture
                 yadjustf=0, # or to fine-tune f
                 ddr=True): # False: SDR, True: DDR
        self.i_btn = Signal(7)
        self.o_led = Signal(8)
        self.o_gpdi_dp = Signal(4)
        self.o_user_programn = Signal()
        self.o_wifi_gpio0 = Signal()
        # Configuration
        self.timing = timing
        self.x = timing.x
        self.y = timing.y
        self.f = timing.pixel_freq
        self.xadjustf = xadjustf
        self.yadjustf = yadjustf
        self.ddr = ddr

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        if platform:
            clk_in = platform.request(platform.default_clk, dir='-')[0]

            # Constants
            pixel_f     = self.timing.pixel_freq
            hsync_front_porch = self.timing.h_front_porch
            hsync_pulse_width = self.timing.h_sync_pulse
            hsync_back_porch  = self.timing.h_back_porch
            vsync_front_porch = self.timing.v_front_porch
            vsync_pulse_width = self.timing.v_sync_pulse
            vsync_back_porch  = self.timing.v_back_porch

            # Clock generator.
            m.domains.sync  = cd_sync  = ClockDomain("sync")
            m.domains.pixel = cd_pixel = ClockDomain("pixel")
            m.domains.shift = cd_shift = ClockDomain("shift")

            m.submodules.ecp5pll = pll = ECP5PLL()
            pll.register_clkin(clk_in,  platform.default_clk_frequency)
            pll.create_clkout(cd_sync,  platform.default_clk_frequency)
            pll.create_clkout(cd_pixel, pixel_f)
            pll.create_clkout(cd_shift, pixel_f * 5.0 * (1.0 if self.ddr else 2.0))

            platform.add_clock_constraint(cd_sync.clk,  platform.default_clk_frequency)
            platform.add_clock_constraint(cd_pixel.clk, pixel_f)
            platform.add_clock_constraint(cd_shift.clk, pixel_f * 5.0 * (1.0 if self.ddr else 2.0))

            # Array of cells

            w = 80
            h = 30

            cells = Array([Array([Signal() for _ in range(h)]) for _ in range(w)])
            nc = Signal(4)
            init = Signal(reset=1)
            div = Signal(26)

            m.d.sync += div.eq(div+1)

            for x in range(1,w-1):
                for y in range(1,h-1):
                    with m.If(init):
                        m.d.sync += init.eq(0)
                        m.d.sync += [
                            cells[1][1].eq(1),
                            cells[1][3].eq(1),
                            cells[2][2].eq(1),
                            cells[2][3].eq(1),
                            cells[3][2].eq(1)
                        ]
                    with m.Elif(div.all()):
                        nc = cells[x-1][y-1] + cells[x-1][y] + cells[x-1][y+1] + cells[x][y-1] + cells[x][y+1] + cells[x+1][y-1] + cells[x+1][y] + cells[x+1][y+1]
                        with m.If(cells[x][y] & (nc != 2) & (nc != 3)):
                            m.d.sync += cells[x][y].eq(0)
                        with m.Elif(~cells[x][y] & (nc == 3)):
                            m.d.sync += cells[x][y].eq(1)
            # VGA signal generator.
            vga_r = Signal(8)
            vga_g = Signal(8)
            vga_b = Signal(8)
            vga_hsync = Signal()
            vga_vsync = Signal()
            vga_blank = Signal()

            m.submodules.vga = vga = VGA(
                resolution_x      = self.timing.x,
                hsync_front_porch = hsync_front_porch,
                hsync_pulse       = hsync_pulse_width,
                hsync_back_porch  = hsync_back_porch,
                resolution_y      = self.timing.y,
                vsync_front_porch = vsync_front_porch,
                vsync_pulse       = vsync_pulse_width,
                vsync_back_porch  = vsync_back_porch,
                bits_x            = 16, # Play around with the sizes because sometimes
                bits_y            = 16  # a smaller/larger value will make it pass timing.
            )
            with m.If(cells[vga.o_beam_x[3:]][vga.o_beam_y[4:]]):
                m.d.comb += [
                    vga.i_r.eq(0xff),
                    vga.i_g.eq(0),
                    vga.i_b.eq(0)
                ]
            with m.Else():
                m.d.comb += [
                    vga.i_r.eq(0),
                    vga.i_g.eq(0xff),
                    vga.i_b.eq(0)
                ]
            m.d.comb += [
                vga.i_clk_en.eq(1),
                vga.i_test_picture.eq(0),
                vga_r.eq(vga.o_vga_r),
                vga_g.eq(vga.o_vga_g),
                vga_b.eq(vga.o_vga_b),
                vga_hsync.eq(vga.o_vga_hsync),
                vga_vsync.eq(vga.o_vga_vsync),
                vga_blank.eq(vga.o_vga_blank),
            ]

            # VGA to digital video converter.
            tmds = [Signal(2) for i in range(4)]
            m.submodules.vga2dvid = vga2dvid = VGA2DVID(ddr=self.ddr, shift_clock_synchronizer=False)
            m.d.comb += [
                vga2dvid.i_red.eq(vga_r),
                vga2dvid.i_green.eq(vga_g),
                vga2dvid.i_blue.eq(vga_b),
                vga2dvid.i_hsync.eq(vga_hsync),
                vga2dvid.i_vsync.eq(vga_vsync),
                vga2dvid.i_blank.eq(vga_blank),
                tmds[3].eq(vga2dvid.o_clk),
                tmds[2].eq(vga2dvid.o_red),
                tmds[1].eq(vga2dvid.o_green),
                tmds[0].eq(vga2dvid.o_blue),
            ]

            if (self.ddr):
                # Vendor specific DDR modules.
                # Convert SDR 2-bit input to DDR clocked 1-bit output (single-ended)
                # onboard GPDI.
                m.submodules.ddr0_clock = Instance("ODDRX1F",
                    i_SCLK = ClockSignal("shift"),
                    i_RST  = 0b0,
                    i_D0   = tmds[3][0],
                    i_D1   = tmds[3][1],
                    o_Q    = self.o_gpdi_dp[3])
                m.submodules.ddr0_red   = Instance("ODDRX1F",
                    i_SCLK = ClockSignal("shift"),
                    i_RST  = 0b0,
                    i_D0   = tmds[2][0],
                    i_D1   = tmds[2][1],
                    o_Q    = self.o_gpdi_dp[2])
                m.submodules.ddr0_green = Instance("ODDRX1F",
                    i_SCLK = ClockSignal("shift"),
                    i_RST  = 0b0,
                    i_D0   = tmds[1][0],
                    i_D1   = tmds[1][1],
                    o_Q    = self.o_gpdi_dp[1])
                m.submodules.ddr0_blue  = Instance("ODDRX1F",
                    i_SCLK = ClockSignal("shift"),
                    i_RST  = 0b0,
                    i_D0   = tmds[0][0],
                    i_D1   = tmds[0][1],
                    o_Q    = self.o_gpdi_dp[0])
            else:
                m.d.comb += [
                    self.o_gpdi_dp[3].eq(tmds[3][0]),
                    self.o_gpdi_dp[2].eq(tmds[2][0]),
                    self.o_gpdi_dp[1].eq(tmds[1][0]),
                    self.o_gpdi_dp[0].eq(tmds[0][0]),
                ]

        return m


if __name__ == "__main__":
    variants = {
        '12F': ULX3S_12F_Platform,
        '25F': ULX3S_25F_Platform,
        '45F': ULX3S_45F_Platform,
        '85F': ULX3S_85F_Platform
    }

    # Figure out which FPGA variant we want to target...
    parser = argparse.ArgumentParser()
    parser.add_argument('variant', choices=variants.keys())
    args = parser.parse_args()

    platform = variants[args.variant]()

    # Add the GPDI resource defined above to the platform so we
    # can reference it below.
    platform.add_resources(gpdi_resource)

    m = Module()
    m.submodules.top = top = Life(timing=vga_timings['640x480@60Hz'])

    # The dir='-' is required because else nmigen will instantiate
    # differential pair buffers for us. Since we instantiate ODDRX1F
    # by hand, we do not want this, and dir='-' gives us access to the
    # _p signal.
    gpdi = [platform.request("gpdi", 0, dir='-'),    
            platform.request("gpdi", 1, dir='-'),
            platform.request("gpdi", 2, dir='-'),
            platform.request("gpdi", 3, dir='-')]

    for i in range(len(gpdi)):
        m.d.comb += gpdi[i].p.eq(top.o_gpdi_dp[i])

    platform.build(m, do_program=True, nextpnr_opts="--timing-allow-fail")
