import argparse

from amaranth import *
from amaranth.build import *
from ulx4m import *

from vga2dvid import VGA2DVID
from vga import VGA
from vga_timings import *
from ecp5pll import ECP5PLL
from debouncer import Debouncer
from spi_ram_btn import SpiRamBtn
from spi_osd import SpiOsd
from rle import rle

# Spi pins from ESP32 re-use two of the sd card pins
esp32_spi = [
    Resource("esp32_spi", 0,
        Subsignal("irq", Pins("L2", dir="o")),
        Subsignal("csn", Pins("N4", dir="i")),
        Subsignal("copi", Pins("H1", dir="i")),
        Subsignal("cipo", Pins("K1", dir="o")),
        Subsignal("sclk", Pins("L1", dir="i")),
        Attrs(PULLMODE="NONE", DRIVE="4", IO_TYPE="LVCMOS33"))
]

class Life(Elaboratable):
    """ John Conway's Game of Life """
    def __init__(self,
                 timing: VGATiming, # VGATiming class
                 fore_color = C(0xffff00, 24),
                 back_color = C(0x0f0f0f, 24),
                 frames_per_gen = 5,
                 xadjustf=0, # adjust -3..3 if no picture
                 yadjustf=0, # or to fine-tune f
                 ddr=True): # False: SDR, True: DDR
        # Pins
        self.o_led = Signal(4)
        self.o_gpdi_dp = Signal(4)
        # Configuration
        self.width = timing.x
        self.height = timing.y
        self.fore_color = fore_color
        self.back_color= back_color
        self.frames_per_gen = frames_per_gen
        self.timing = timing
        self.x = timing.x
        self.y = timing.y
        self.f = timing.pixel_freq
        self.xadjustf = xadjustf
        self.yadjustf = yadjustf
        self.ddr = ddr

    def elaborate(self, platform: Platform) -> Module:
        m = Module()
        print("width:", self.width, "height:", self.height)

        if platform:
            # Pins
            clk_in = platform.request(platform.default_clk, dir='-')[0]

            led   = [platform.request("led", i) for i in range(4)]
            m.d.comb += Cat([i.o for i in led]).eq(self.o_led)

            btn = Cat([platform.request("button", i) for i in range(6)])

            esp32 = platform.request("esp32_spi")
            csn = esp32.csn
            sclk = esp32.sclk
            copi = esp32.copi
            cipo = esp32.cipo
            irq  = esp32.irq

            # Constants
            pixel_f           = self.timing.pixel_freq
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

            # Cells set-up
            def to_bytes(l):
                bl = []
                b = 0
                i = 0

                for e in l:
                    b = (e << (7 - i)) + b
                    if i == 7:
                        bl.append(b)
                        i = 0
                        b = 0
                    else:
                        i += 1

                return bl

            def glider(y,x):
                cells[y][x] = 1
                cells[y+1][x+1] = 1
                cells[y+1][x+2] = 1
                cells[y+2][x] = 1
                cells[y+2][x+1] = 1

            # Note that this starts at x=1, y=1
            def gun(y,x):
                cells[y+5][x+1] = cells[y+5][x+2] = 1
                cells[y+6][x+1] = cells[y+6][x+2] = 1

                cells[y+3][x+13] = cells[y+3][x+14] = 1
                cells[y+4][x+12] = cells[y+4][x+16] = 1
                cells[y+5][x+11] = cells[y+5][x+17] = 1
                cells[y+6][x+11] = cells[y+6][x+15] = cells[y+6][x+17] = cells[y+6][x+18] = 1
                cells[y+7][x+11] = cells[y+7][x+17] = 1
                cells[y+8][x+12] = cells[y+8][x+16] = 1
                cells[y+9][x+13] = cells[y+9][x+14] = 1

                cells[y+1][x+25] = 1
                cells[y+2][x+23] = cells[y+2][x+25] = 1
                cells[y+3][x+21] = cells[y+3][x+22] = 1
                cells[y+4][x+21] = cells[y+4][x+22] = 1
                cells[y+5][x+21] = cells[y+5][x+22] = 1
                cells[y+6][x+23] = cells[y+6][x+25] = 1
                cells[y+7][x+25] = 1

                cells[y+3][x+35] = cells[y+3][x+36] = 1
                cells[y+4][x+35] = cells[y+4][x+36] = 1

            def pulsar(y,x):
                cells[y+0][x+2] = cells[y+0][x+3] = cells[y+0][x+4] = cells[y+0][x+8] = cells[y+0][x+9] = cells[y+0][x+10] = 1
                cells[y+2][x+0] = cells[y+2][x+5] = cells[y+2][x+7] = cells[y+2][x+12] = 1
                cells[y+3][x+0] = cells[y+3][x+5] = cells[y+3][x+7] = cells[y+3][x+12] = 1
                cells[y+4][x+0] = cells[y+4][x+5] = cells[y+4][x+7] = cells[y+4][x+12] = 1
                cells[y+5][x+2] = cells[y+5][x+3] = cells[y+5][x+4] = cells[y+5][x+8] = cells[y+5][x+9] = cells[y+5][x+10] = 1
                cells[y+7][x+2] = cells[y+7][x+3] = cells[y+7][x+4] = cells[y+7][x+8] = cells[y+7][x+9] = cells[y+7][x+10] = 1
                cells[y+8][x+0] = cells[y+8][x+5] = cells[y+8][x+7] = cells[y+8][x+12] = 1
                cells[y+9][x+0] = cells[y+9][x+5] = cells[y+9][x+7] = cells[y+9][x+12] = 1
                cells[y+10][x+0] = cells[y+10][x+5] = cells[y+10][x+7] = cells[y+10][x+12] = 1
                cells[y+12][x+2] = cells[y+12][x+3] = cells[y+12][x+4] = cells[y+12][x+8] = cells[y+12][x+9] = cells[y+12][x+10] = 1

            def penta_dec(y,x):
                cells[y+0][x+1] = cells[y+0][x+2] = cells[y+0][x+3] = 1
                cells[y+1][x+0] = cells[y+1][x+4] = 1
                cells[y+2][x+0] = cells[y+2][x+4] = 1
                cells[y+3][x+1] = cells[y+3][x+2] = cells[y+3][x+3] = 1
                cells[y+8][x+1] = cells[y+8][x+2] = cells[y+8][x+3] = 1
                cells[y+9][x+0] = cells[y+9][x+4] = 1
                cells[y+10][x+0] = cells[y+10][x+4] = 1
                cells[y+11][x+1] = cells[y+11][x+2] = cells[y+11][x+3] = 1

            def acorn(y,x):
                cells[y+0][x+1] = 1
                cells[y+1][x+3] = 1
                cells[y+2][x+0] = cells[y+2][x+1] = cells[y+2][x+4] = cells[y+2][x+5] = cells[y+2][x+6] = 1

            def r_pent(y,x):
                cells[y+0][x+1] = cells[y+0][x+2] = 1
                cells[y+1][x+0] = cells[y+1][x+1] = 1
                cells[y+2][x+1] = 1

            def die_hard(y,x):
                cells[y+0][x+6] = 1
                cells[y+1][x+0] = cells[y+1][x+1] = 1
                cells[y+2][x+1] = cells[y+2][x+5] = cells[y+2][x+6] = cells[y+2][x+7] = 1

            def lwss_l(y,x):
                cells[y+0][x+1] = cells[y+0][x+4] = 1
                cells[y+1][x+0] = 1
                cells[y+2][x+0] = cells[y+2][x+4] = 1
                cells[y+3][x+0] = cells[y+3][x+1] = cells[y+3][x+2] = cells[y+3][x+3] = 1

            def lwss_r(y,x):
                cells[y+0][x+1] = cells[y+0][x+2] = cells[y+0][x+3] = cells[y+0][x+4] = 1
                cells[y+1][x+0] = cells[y+1][x+4] = 1
                cells[y+2][x+4] = 1
                cells[y+3][x+0] = cells[y+3][x+3] = 1

            def block(y,x):
                cells[y+0][x+0] = cells[y+0][x+1] = 1
                cells[y+1][x+0] = cells[y+1][x+1] = 1

            def eater(y,x):
                cells[y+0][x+0] = cells[y+0][x+1] = 1
                cells[y+1][x+0] = cells[y+1][x+2] = 1
                cells[y+2][x+2] = 1
                cells[y+3][x+2] = cells[y+3][x+3] = 1

            def read_plain(y,x,fn):
                f = open(fn, 'r')
                lines = f.readlines()
 
                for line in lines:
                    if line[0] == "!":
                        continue
                    i = 0
                    for c in line.strip():
                        if c == 'O':
                            cells[y][x+i] = 1
                        i += 1
                    y += 1
        
                f.close()

            cells = [ [0] * self.width for _ in range(self.height)]

            # Guns at top and left of screen
            for i in range(10):
                rle(51,51 + i*50, "gopher.rle",cells)
            
            for i in range(7):
                gun(50 + i*50, 50)

            for i in range(11):
                eater(754, 468 + i*50)

            #for i in range(10):
            #    pulsar(100, 50 + 50*i)

            #for i in range(10):
            #    penta_dec(200,50 + 50*i)

            #acorn(240, 320)
            #for i in range(47):
            #    lwss_r(10 + i*10, 10)

            #r_pent(240, 320)

            #die_hard(240, 320)

            #for i in range(5):
            #    read_plain(40 + 100*i, 550,"tagalong.txt")

            #glider(4,4)

            #read_plain(400,10,"breeder1.txt")
            #block(2, 4)

            # Flatten cells
            fcells = [x for l in cells for x in to_bytes(l)]

            # Write to binary file
            f = open("cells.bin","wb")
            f.write(bytearray(fcells))
            f.close()

            # Spi Ram
            rd   = Signal()    # Set when read requested
            wr   = Signal()    # Set when write requested
            addr = Signal(32)  # The requested address
            din  = Signal(8)   # The data to be sent back
            dout = Signal(8)   # The data to be written

            cpu_control = Signal(8)
            spi_load    = Signal()

            m.submodules.spimem = spimem = SpiRamBtn(addr_bits=32)

            m.d.comb += [
                # Connect spimem
                spimem.csn.eq(~csn),
                spimem.sclk.eq(sclk),
                spimem.copi.eq(copi),
                spimem.din.eq(din),
                spimem.btn.eq(Cat(0b0, btn)),
                cipo.eq(spimem.cipo),
                addr.eq(spimem.addr),
                dout.eq(spimem.dout),
                rd.eq(spimem.rd),
                wr.eq(spimem.wr),
                irq.eq(~spimem.irq),
                spi_load.eq(cpu_control[1])
            ]

            # CPU control from ESP32
            with m.If(wr & (addr[24:] == 0xFF)):
                m.d.pixel += cpu_control.eq(dout)

            # Cell memory
            mem = Memory(width = 8, depth = (self.width * self.height) // 8, init = fcells)
            m.submodules.r = r = mem.read_port(domain="pixel")
            m.submodules.w = w = mem.write_port(domain="pixel")

            m.d.comb += din.eq(r.data)

            # Previous line memory
            pmem = Memory(width = 8, depth = self.width // 8)
            m.submodules.pr = pr = pmem.read_port(domain="pixel")
            m.submodules.pw = pw = pmem.write_port(domain="pixel")

            # Pixel shift registers
            s0 = Signal(17)
            s1 = Signal(17)
            s2 = Signal(17)

            # Current pixel (cell) and neighbours
            p00 = s0[16]
            p01 = s0[15]
            p02 = s0[14]
            p10 = s1[16]
            p11 = s1[15]
            p12 = s1[14]
            p20 = s2[16]
            p21 = s2[15]
            p22 = s2[14]

            # Neighbour count
            nc = Signal(4)
            m.d.comb += nc.eq(p00 + p01 + p02 + p10 + p12 + p20 + p21 + p22)

            # Byte containing current pixel for writing out
            cb = Signal(8)

            # Next generation
            live = Signal()
            m.d.comb += live.eq((nc | p11) == 3)

            # VGA signal generator.
            vga_r = Signal(8)
            vga_g = Signal(8)
            vga_b = Signal(8)
            vga_hsync = Signal()
            vga_vsync = Signal()
            vga_blank = Signal()

            # Count frames and generations
            fc = Signal(6)
            gen = Signal(16)
            frames_per_gen = Signal(6, reset=self.frames_per_gen)
            new_frames_per_gen = Signal(6, reset=self.frames_per_gen)
            old_vsync = Signal()
            m.d.pixel += old_vsync.eq(vga_vsync)

            with m.If(vga_vsync & ~old_vsync):
                m.d.pixel += fc.eq(fc+1)

                with m.If(fc == frames_per_gen - 1):
                    m.d.pixel += [
                        fc.eq(0),
                        gen.eq(gen+1),
                        frames_per_gen.eq(new_frames_per_gen)
                    ]
        
            m.submodules.deb1 = deb1 = Debouncer()
            m.submodules.deb2 = deb2 = Debouncer()

            m.d.comb += [
                deb1.btn.eq(btn[0]),
                deb2.btn.eq(btn[1])
            ]

            with m.If(deb1.btn_up & (frames_per_gen < 60)):
                m.d.pixel += new_frames_per_gen.eq(frames_per_gen + 1)

            with m.If(deb2.btn_up & (frames_per_gen > 1)):
                m.d.pixel += new_frames_per_gen.eq(frames_per_gen - 1)

            # VGA module
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

            # Connect previous line memory, so it is written when current line is read
            m.d.comb += [
                pr.addr.eq(Mux(vga.o_beam_x >= self.width, 0, (vga.o_beam_x >> 3) + 1)),
                pw.addr.eq(pr.addr),
                pw.data.eq(r.data),
                pw.en.eq((vga.o_beam_x == self.width + 2) | 
                         ((vga.o_beam_x[:3] == 2) & (vga.o_beam_x < self.width) & (vga.o_beam_y < self.height)))
            ]

            # Read and write VRAM
            with m.If(~spi_load & (vga.o_beam_x < self.width) & (vga.o_beam_y < self.height)):
                # Move to next pixel
                m.d.pixel += [
                    s0.eq(Cat(C(0,1), s0[:16])),
                    s1.eq(Cat(C(0,1), s1[:16])),
                    s2.eq(Cat(C(0,1), s2[:16]))
                ]

                # Get next byte for each row
                with m.If(vga.o_beam_x[:3] == 1):
                    m.d.comb += r.addr.eq(((((vga.o_beam_y    ) * self.width) + vga.o_beam_x) >> 3) + 1)
                    m.d.pixel += s0[2:10].eq(pr.data)
                with m.Elif(vga.o_beam_x[:3] == 2):
                    m.d.comb += r.addr.eq(((((vga.o_beam_y + 1) * self.width) + vga.o_beam_x) >> 3) + 1)
                    m.d.pixel += s1[3:11].eq(r.data)
                with m.Elif(vga.o_beam_x[:3] == 3):
                    m.d.pixel += s2[4:12].eq(r.data)

                # Write when byte is complete
                with m.If(vga.o_beam_x[:3] == 7):
                    m.d.comb += w.addr.eq(((vga.o_beam_y * self.width) + vga.o_beam_x) >> 3)
                    m.d.comb += w.data.eq(Cat(live, cb[1:]))

                    # Write updated byte
                    with m.If(fc == frames_per_gen - 1):
                        m.d.comb += w.en.eq(1)

                # New generation every second
                with m.If((fc == frames_per_gen - 1)):
                    m.d.pixel += cb.bit_select(~vga.o_beam_x[:3],1).eq(live)

            # Show speed on leds
            m.d.pixel += self.o_led.eq(frames_per_gen)

            # Reset shift registers at end of line
            with m.If(~spi_load):
                with m.If(vga.o_beam_x == self.width + 1):
                    m.d.comb += r.addr.eq(((vga.o_beam_y + 1) * self.width) >> 3)
                    m.d.pixel += s0[8:].eq(pr.data)
                with m.Elif(vga.o_beam_x == self.width + 2):
                    m.d.comb += r.addr.eq(((vga.o_beam_y + 2) * self.width) >> 3)
                    m.d.pixel += s1[8:].eq(r.data)
                with m.Elif(vga.o_beam_x == self.width + 3):
                    m.d.pixel += s2[8:].eq(r.data)

            # Override r.addr and w.addr if loading from ESP32
            with m.If(spi_load & rd & (addr[24:] == 0)):
                m.d.comb += r.addr.eq(addr)

            with m.If(spi_load & wr & (addr[24:] == 0)):
                m.d.comb += [
                    w.addr.eq(addr),
                    w.data.eq(dout),
                    w.en.eq(1)
                ]

            # Display current pixel
            with m.If(p11):
                m.d.comb += [
                    vga.i_r.eq(self.fore_color[16:]),
                    vga.i_g.eq(self.fore_color[8:16]),
                    vga.i_b.eq(self.fore_color[:8])
                ]
            with m.Else():
                m.d.comb += [
                    vga.i_r.eq(self.back_color[16:]),
                    vga.i_g.eq(self.back_color[8:16]),
                    vga.i_b.eq(self.back_color[:8])
                ]

            m.submodules.osd = osd = SpiOsd(start_x=220, start_y=60, chars_x=64, chars_y=20)

            m.d.comb += [
                # Connect osd
                osd.i_csn.eq(~csn),
                osd.i_sclk.eq(sclk),
                osd.i_copi.eq(copi),
                osd.clk_ena.eq(1),
                osd.i_hsync.eq(vga.o_vga_hsync),
                osd.i_vsync.eq(vga.o_vga_vsync),
                osd.i_blank.eq(vga.o_vga_blank),
                osd.i_r.eq(vga_r),
                osd.i_g.eq(vga_g),
                osd.i_b.eq(vga_b),
            ]

            # VGA to digital video converter.
            tmds = [Signal(2) for i in range(4)]
            m.submodules.vga2dvid = vga2dvid = VGA2DVID(ddr=self.ddr, shift_clock_synchronizer=False)
            m.d.comb += [
                #vga2dvid.i_red.eq(vga_r),
                #vga2dvid.i_green.eq(vga_g),
                #vga2dvid.i_blue.eq(vga_b),
                #vga2dvid.i_hsync.eq(vga.o_vga_hsync),
                #vga2dvid.i_vsync.eq(vga.o_vga_vsync),
                #vga2dvid.i_blank.eq(vga.o_vga_blank),
                vga2dvid.i_red.eq(osd.o_r),
                vga2dvid.i_green.eq(osd.o_g),
                vga2dvid.i_blue.eq(osd.o_b),
                vga2dvid.i_hsync.eq(osd.o_hsync),
                vga2dvid.i_vsync.eq(osd.o_vsync),
                vga2dvid.i_blank.eq(osd.o_blank),
                tmds[3].eq(vga2dvid.o_clk),
                tmds[2].eq(vga2dvid.o_red),
                tmds[1].eq(vga2dvid.o_green),
                tmds[0].eq(vga2dvid.o_blue)
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
        '12F': ULX4M_12F_Platform,
        '45F': ULX4M_45F_Platform,
        '85F': ULX4M_85F_Platform
    }

    # Figure out which FPGA variant we want to target...
    parser = argparse.ArgumentParser()
    parser.add_argument('variant', choices=variants.keys())
    parser.add_argument("--tool", default="fujprog")
    args = parser.parse_args()

    platform = variants[args.variant]()

    # Add the GPDI resource defined above to the platform so we
    # can reference it below.
    platform.add_resources(esp32_spi)

    m = Module()
    m.submodules.top = top = Life(timing=vga_timings['1024x768@60Hz'])

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

    platform.build(m, do_program=True, nextpnr_opts="--timing-allow-fail", program_opts={"tool":args.tool})
