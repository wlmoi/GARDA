#!/usr/bin/env python3
"""Generate rtl/de10_lite/garda_vga_status.v: the live VGA status screen (v2 layout).

640x480 @ 60 Hz (DE10-Lite manual tables 3-9/3-10: H 96/48/640/16, V 2/33/480/10),
25 MHz pixel rate = 50 MHz / 2. Text boxes use a 5x7 font in 8x8 cells at 2x or 4x.
Three pipeline stages: (1) box hit tests + background, (2) character/glyph select,
(3) font lookup. The screen only READS GARDA status signals.
"""
import re
from pathlib import Path

FONT = {
 '0':[" ### ","#   #","#  ##","# # #","##  #","#   #"," ### "],
 '1':["  #  "," ##  ","  #  ","  #  ","  #  ","  #  "," ### "],
 '2':[" ### ","#   #","    #","   # ","  #  "," #   ","#####"],
 '3':["#####","   # ","  #  ","   # ","    #","#   #"," ### "],
 '4':["   # ","  ## "," # # ","#  # ","#####","   # ","   # "],
 '5':["#####","#    ","#### ","    #","    #","#   #"," ### "],
 '6':["  ## "," #   ","#    ","#### ","#   #","#   #"," ### "],
 '7':["#####","    #","   # ","  #  "," #   "," #   "," #   "],
 '8':[" ### ","#   #","#   #"," ### ","#   #","#   #"," ### "],
 '9':[" ### ","#   #","#   #"," ####","    #","   # "," ##  "],
 'A':[" ### ","#   #","#   #","#####","#   #","#   #","#   #"],
 'B':["#### ","#   #","#   #","#### ","#   #","#   #","#### "],
 'C':[" ### ","#   #","#    ","#    ","#    ","#   #"," ### "],
 'D':["#### ","#   #","#   #","#   #","#   #","#   #","#### "],
 'E':["#####","#    ","#    ","#### ","#    ","#    ","#####"],
 'F':["#####","#    ","#    ","#### ","#    ","#    ","#    "],
 'G':[" ### ","#   #","#    ","# ###","#   #","#   #"," ####"],
 'H':["#   #","#   #","#   #","#####","#   #","#   #","#   #"],
 'I':[" ### ","  #  ","  #  ","  #  ","  #  ","  #  "," ### "],
 'J':["  ###","   # ","   # ","   # ","   # ","#  # "," ##  "],
 'K':["#   #","#  # ","# #  ","##   ","# #  ","#  # ","#   #"],
 'L':["#    ","#    ","#    ","#    ","#    ","#    ","#####"],
 'M':["#   #","## ##","# # #","# # #","#   #","#   #","#   #"],
 'N':["#   #","#   #","##  #","# # #","#  ##","#   #","#   #"],
 'O':[" ### ","#   #","#   #","#   #","#   #","#   #"," ### "],
 'P':["#### ","#   #","#   #","#### ","#    ","#    ","#    "],
 'Q':[" ### ","#   #","#   #","#   #","# # #","#  # "," ## #"],
 'R':["#### ","#   #","#   #","#### ","# #  ","#  # ","#   #"],
 'S':[" ####","#    ","#    "," ### ","    #","    #","#### "],
 'T':["#####","  #  ","  #  ","  #  ","  #  ","  #  ","  #  "],
 'U':["#   #","#   #","#   #","#   #","#   #","#   #"," ### "],
 'V':["#   #","#   #","#   #","#   #","#   #"," # # ","  #  "],
 'W':["#   #","#   #","#   #","# # #","# # #","# # #"," # # "],
 'X':["#   #","#   #"," # # ","  #  "," # # ","#   #","#   #"],
 'Y':["#   #","#   #"," # # ","  #  ","  #  ","  #  ","  #  "],
 'Z':["#####","    #","   # ","  #  "," #   ","#    ","#####"],
 '-':["     ","     ","     ","#####","     ","     ","     "],
 '+':["     ","  #  ","  #  ","#####","  #  ","  #  ","     "],
 ':':["     "," ##  "," ##  ","     "," ##  "," ##  ","     "],
 '.':["     ","     ","     ","     ","     "," ##  "," ##  "],
 '/':["     ","    #","   # ","  #  "," #   ","#    ","     "],
 '=':["     ","     ","#####","     ","#####","     ","     "],
}
for k, v in FONT.items():
    assert len(v) == 7 and all(len(r) == 5 for r in v), k

# Colours, 4 bits per channel {R,G,B}
COL = dict(NAVY="12'h013", SURFACE="12'h124", CARD="12'h135", EDGE="12'h358", BLUE="12'h35f", DEEP="12'h24c",
           LIME="12'hbf3", WHITE="12'hfff", RED="12'hf56", GREY="12'h9ab", DIM="12'h68a", AMBER="12'hfb5",
           PALE="12'hcdf", DARKRED="12'h912")

# Cards: 3 x 2 grid
CARD_X = [16, 224, 432]
CARD_Y = [232, 320]
CARD_W, CARD_H = 192, 80

# Text boxes: (name, x, y, scale, chars, source, colour expression)
#   source = "static text" or ("wire", n)
BOXES = [
 ("title",   24, 16, 4, 5,  "GARDA", "LIME"),
 ("sub1",   208, 16, 2, 20, "HARDWARE SAFETY GATE", "WHITE"),
 ("sub2",   208, 38, 2, 17, "TERASIC DE10-LITE", "PALE"),
 ("live",   568, 38, 2, 4,  "LIVE", "beat[24] ? LIME : DIM"),
 ("head",   112, 100, 4, 16, ("head_word", 16), "panel_fg"),
 ("reason", 112, 148, 2, 30, ("reason_word", 30), "panel_fg"),
 ("detail", 112, 172, 2, 30, ("detail_word", 30), "panel_sub"),
]
labels = ["FAULT CODE", "VELOCITY V", "OMEGA W", "PLANNER", "NEURAL", "LATCHES"]
values = [(("fault_hex", 2), "fault_col"), (("v_dec", 3), "WHITE"), (("w_dec", 3), "WHITE"),
          (("planner_word", 5), "planner_col"), (("neural_word", 5), "neural_col")]
for i, lab in enumerate(labels):
    x, y = CARD_X[i % 3] + 12, CARD_Y[i // 3] + 10
    BOXES.append((f"lab{i}", x, y, 2, len(lab), lab, "GREY"))
    if i < 5:
        BOXES.append((f"val{i}", x, y + 26, 4, values[i][0][1], values[i][0], values[i][1]))
BOXES += [
 ("l_es",  CARD_X[2] + 12, CARD_Y[1] + 34, 2, 6, "E-STOP", "GREY"),
 ("v_es",  CARD_X[2] + 124, CARD_Y[1] + 34, 2, 3, ("hestop_word", 3), "estop_col"),
 ("l_wd",  CARD_X[2] + 12, CARD_Y[1] + 54, 2, 4, "WDOG", "GREY"),
 ("v_wd",  CARD_X[2] + 92, CARD_Y[1] + 54, 2, 5, ("wd_word", 5), "wd_col"),
 ("pa_l",  40, 412, 2, 9, "PORT A PC", "PALE"),
 ("pa_v", 200, 412, 2, 4, ("pa_hex", 4), "WHITE"),
 ("pb_l", 332, 412, 2, 13, "PORT B JETSON", "PALE"),
 ("pb_v", 572, 412, 2, 4, ("pb_hex", 4), "WHITE"),
 ("sw_l",  16, 444, 2, 6, "SW9..0", "GREY"),
 ("sw_v", 120, 444, 2, 10, ("sw_word", 10), "WHITE"),
 ("uart", 316, 444, 2, 19, "UART 115200 8N1 A+B", "GREY"),
]
SCALE_SHIFT = {2: 1, 4: 2}


def check_layout():
    for n, x, y, s, c, src, _ in BOXES:
        assert x + c * 8 * s <= 640 and y + 8 * s <= 480, f"box {n} off screen"
        if isinstance(src, str):
            assert len(src) == c, n


def lsb_first_const(text: str) -> str:
    return "{" + ",".join(f"8'h{ord(ch):02x}" for ch in reversed(text)) + "}"


def gen() -> str:
    check_layout()
    nb = len(BOXES)
    o = ["// GENERATED by scripts/gen_vga_screen.py - do not edit by hand.",
         "// Live VGA status screen for GARDA DE10-Lite (640x480@60, 25 MHz pixel rate = 50 MHz / 2).",
         "// Observation only: no signal from this module reaches the GARDA core.",
         "`timescale 1ns/1ps\n`default_nettype none",
         """module garda_vga_status(input wire clk,rst_n,
 input wire motor_enable,busy,done,protocol_fault,invalid_command,
 input wire host_estop,key_estop,watchdog_armed,watchdog_trip,nn_busy,nn_done,nn_fault,uart_activity,
 input wire [7:0] fault,last_fault,last_op,input wire [4:0] v_cmd,input wire signed [6:0] w_cmd,
 input wire [15:0] frames,port_a,port_b,input wire [9:0] sw,
 output reg [3:0] vga_r,vga_g,vga_b,output reg vga_hs,vga_vs);
""" + "\n".join(f"localparam [11:0] {k}={v};" for k, v in COL.items()) + """
// ---------------- timing ----------------
reg pe;reg [9:0] hc,vc;
always @(posedge clk or negedge rst_n)begin
 if(!rst_n)begin pe<=0;hc<=0;vc<=0;end
 else begin pe<=~pe;
  if(pe)begin if(hc==10'd799)begin hc<=0;vc<=(vc==10'd524) ? 10'd0 : vc+1'b1;end else hc<=hc+1'b1;end
 end
end
wire active=hc<10'd640 && vc<10'd480;
wire hs=!(hc>=10'd656 && hc<10'd752), vs=!(vc>=10'd490 && vc<10'd492);
reg [25:0] beat;always @(posedge clk or negedge rst_n)if(!rst_n)beat<=0;else beat<=beat+1'b1;
// ---------------- formatted values (registered once) ----------------
function [7:0] hexc;input [3:0] n;hexc=n<10 ? 8'h30+n : 8'h37+n;endfunction
function [15:0] dec2;input [6:0] n;reg [7:0] t,u;begin t=8'h30+n/7'd10;u=8'h30+n%7'd10;dec2={t,u};end endfunction
wire [6:0] w_abs=w_cmd[6] ? -w_cmd : w_cmd;
reg [8*2-1:0] fault_hex;reg [8*3-1:0] v_dec,w_dec;reg [8*4-1:0] pa_hex,pb_hex;
always @(posedge clk)begin
 fault_hex<={hexc(fault[7:4]),hexc(fault[3:0])};
 v_dec<={" ",dec2({2'b0,v_cmd})};
 w_dec<={w_cmd[6] ? "-" : "+",dec2(w_abs)};
 pa_hex<={hexc(port_a[15:12]),hexc(port_a[11:8]),hexc(port_a[7:4]),hexc(port_a[3:0])};
 pb_hex<={hexc(port_b[15:12]),hexc(port_b[11:8]),hexc(port_b[7:4]),hexc(port_b[3:0])};
end
wire [8*5-1:0] planner_word=busy ? "BUSY " : done ? "DONE " : "IDLE ";
wire [8*5-1:0] neural_word=nn_fault ? "FAULT" : nn_busy ? "BUSY " : nn_done ? "DONE " : "IDLE ";
wire [8*3-1:0] hestop_word=host_estop ? "ON " : "OFF";
wire [8*5-1:0] wd_word=watchdog_trip ? "TRIP " : watchdog_armed ? "ARMED" : "OFF  ";
wire [8*10-1:0] sw_word;genvar si;
generate for(si=0;si<10;si=si+1)begin:swc assign sw_word[si*8 +: 8]=sw[si] ? "1" : "0";end endgenerate
wire [11:0] fault_col=fault==8'd0 ? LIME : RED;
wire [11:0] planner_col=busy ? AMBER : done ? LIME : GREY;
wire [11:0] neural_col=nn_fault ? RED : nn_busy ? AMBER : nn_done ? LIME : GREY;
wire [11:0] estop_col=host_estop ? RED : GREY;
wire [11:0] wd_col=watchdog_trip ? RED : watchdog_armed ? AMBER : GREY;
// activity lamps for the two UART ports (stretched ~40 ms in the 50 MHz domain)
reg [15:0] pa_q,pb_q;reg [20:0] act_a,act_b;
always @(posedge clk or negedge rst_n)begin
 if(!rst_n)begin pa_q<=0;pb_q<=0;act_a<=0;act_b<=0;end
 else begin pa_q<=port_a;pb_q<=port_b;
  act_a<=pa_q!=port_a ? 21'h1fffff : (act_a!=0 ? act_a-1'b1 : 21'd0);
  act_b<=pb_q!=port_b ? 21'h1fffff : (act_b!=0 ? act_b-1'b1 : 21'd0);
 end
end
// ---------------- state, headline, reason ----------------
wire estop=host_estop || key_estop;
wire [1:0] state=motor_enable ? 2'd0 : (estop || fault==8'd2) ? 2'd1 : (fault==8'd3) ? 2'd2 : 2'd3;
reg [8*16-1:0] head_word;reg [8*30-1:0] reason_word,detail_word;reg [11:0] panel_bg,panel_fg,panel_sub,panel_edge;
always @(*)begin
 case(state)
  2'd0:begin head_word="MOTION PERMITTED";panel_bg=LIME;panel_fg=NAVY;panel_sub=DEEP;panel_edge=WHITE;end
  2'd1:begin head_word="  E-STOP ACTIVE ";panel_bg=RED;panel_fg=WHITE;panel_sub=PALE;panel_edge=DARKRED;end
  2'd2:begin head_word="PROTECTIVE  STOP";panel_bg=AMBER;panel_fg=NAVY;panel_sub=DEEP;panel_edge=WHITE;end
  default:begin head_word=" MOTOR  STOPPED ";panel_bg=SURFACE;panel_fg=WHITE;panel_sub=GREY;panel_edge=EDGE;end
 endcase
 case(fault)
  8'd0:reason_word="ALL SAFETY CHECKS PASSED";
  8'd1:reason_word="RESET ACTIVE";
  8'd2:reason_word="EMERGENCY STOP";
  8'd3:reason_word="PROTECTIVE STOP";
  8'd4:reason_word="NOT READY OR BAD COMMAND";
  8'd5:reason_word="NO VALID FRESH MAP";
  8'd6:reason_word="CONFIGURATION NOT LOCKED";
  8'd7:reason_word="ROLLOUT ARITHMETIC FAULT";
  8'd8:reason_word="DEADLINE OR LEASE EXPIRED";
  8'd9:reason_word="PLANNER RESULT NOT READY";
  8'd10:reason_word="SPEED LIMIT EXCEEDED";
  8'd11:reason_word="ACCELERATION LIMIT EXCEEDED";
  default:reason_word="UNKNOWN FAULT";
 endcase
 if(motor_enable)detail_word="COMMAND PASSED TO MOTORS";
 else if(key_estop)detail_word="SOURCE: KEY1 BUTTON";
 else if(host_estop)detail_word="SOURCE: HOST E-STOP COMMAND";
 else if(watchdog_trip)detail_word="SOURCE: HOST LINK WATCHDOG";
 else if(fault==8'd3 && sw[3])detail_word="SOURCE: SWITCH SW3";
 else if(fault==8'd4 && sw[2])detail_word="SOURCE: SWITCH SW2";
 else if(protocol_fault)detail_word="UART FRAME ERROR - PRESS KEY0";
 else if(invalid_command)detail_word="INVALID COMMAND REJECTED";
 else detail_word="MOTOR OUTPUT HELD AT ZERO";
end
"""]
    # LSB-first text for every box
    for i, (n, x, y, s, c, src, colx) in enumerate(BOXES):
        if isinstance(src, str):
            o.append(f"wire [{8*c-1}:0] t_{n}={lsb_first_const(src)};")
        else:
            w, wn = src
            parts = ",".join(f"{w}[{8*k+7}:{8*k}]" for k in range(wn))   # last char first -> char0 at LSB
            o.append(f"wire [{8*c-1}:0] t_{n}={{{parts}}};")
    # stage 1: hit tests + background
    o.append(f"// ---------------- stage 1: box hits and background ----------------\nreg [{nb-1}:0] hit1;reg [9:0] hc1,vc1;reg s1_active,s1_hs,s1_vs;reg [11:0] bg1;")
    o.append("wire signed [10:0] ldx=$signed({1'b0,hc})-11'sd64,ldy=$signed({1'b0,vc})-11'sd148;\nwire [21:0] ld2=ldx*ldx+ldy*ldy;")
    o.append("wire [9:0] scan_x={beat[23:15],1'b0};")
    hits = []
    for i, (n, x, y, s, c, src, colx) in enumerate(BOXES):
        hits.append(f"(hc>=10'd{x} && hc<10'd{x + c*8*s} && vc>=10'd{y} && vc<10'd{y + 8*s})")
    o.append("reg [11:0] bg;\nalways @(*)begin")
    o.append(" bg=NAVY;")
    o.append(" if(vc<10'd64)bg=(vc[5:4]==2'd0) ? BLUE : (vc[5:4]==2'd1 ? 12'h34e : (vc[5:4]==2'd2 ? 12'h33d : 12'h33c));")
    o.append(" else if(vc<10'd67)bg=LIME;")
    o.append(" if(hc>=10'd560 && hc<10'd566 && vc>=10'd42 && vc<10'd48)bg=beat[24] ? LIME : DIM;   // live dot")
    o.append(" if(vc>=10'd80 && vc<10'd216 && hc>=10'd8 && hc<10'd632)begin")
    o.append("  bg=(vc<10'd82 || vc>=10'd214 || hc<10'd10 || hc>=10'd630) ? panel_edge : panel_bg;")
    o.append("  if(ld2<22'd1296)bg=panel_fg;                                     // lamp ring r=36")
    o.append("  if(ld2<22'd900)bg=panel_bg;")
    o.append("  if(ld2<22'd484 && !(state==2'd1 && beat[23]))bg=panel_fg;      // lamp core r=22, blinks on E-stop")
    o.append(" end")
    for cx in CARD_X:
        for cy in CARD_Y:
            o.append(f" if(hc>=10'd{cx} && hc<10'd{cx+CARD_W} && vc>=10'd{cy} && vc<10'd{cy+CARD_H})"
                     f"bg=(hc==10'd{cx} || hc==10'd{cx+CARD_W-1} || vc==10'd{cy} || vc==10'd{cy+CARD_H-1}) ? EDGE : CARD;")
    o.append(" if(vc>=10'd404 && vc<10'd405)bg=EDGE;")
    o.append(" if(hc>=10'd16 && hc<10'd30 && vc>=10'd413 && vc<10'd427)bg=act_a!=0 ? LIME : EDGE;   // port A lamp")
    o.append(" if(hc>=10'd310 && hc<10'd324 && vc>=10'd413 && vc<10'd427)bg=act_b!=0 ? LIME : EDGE; // port B lamp")
    o.append(" if(vc>=10'd470 && vc<10'd474)bg=(hc>=scan_x && hc<scan_x+10'd96) ? LIME : SURFACE;   // scan bar")
    o.append("end")
    o.append("always @(posedge clk or negedge rst_n)begin\n if(!rst_n)begin hit1<=0;hc1<=0;vc1<=0;s1_active<=0;s1_hs<=1;s1_vs<=1;bg1<=0;end\n else if(pe)begin")
    o.append("  hc1<=hc;vc1<=vc;s1_active<=active;s1_hs<=hs;s1_vs<=vs;bg1<=bg;")
    o.append("  hit1<={" + ",".join(reversed(hits)) + "};")
    o.append(" end\nend")
    # stage 2: choose box, glyph coordinates, character, colour
    o.append("// ---------------- stage 2: character and colour ----------------\nreg [7:0] ch2;reg [2:0] gx2,gy2;reg [11:0] fg2,bg2;reg on2,s2_active,s2_hs,s2_vs;")
    o.append("always @(posedge clk or negedge rst_n)begin\n if(!rst_n)begin ch2<=0;gx2<=0;gy2<=0;fg2<=0;bg2<=0;on2<=0;s2_active<=0;s2_hs<=1;s2_vs<=1;end\n else if(pe)begin")
    o.append("  s2_active<=s1_active;s2_hs<=s1_hs;s2_vs<=s1_vs;bg2<=bg1;on2<=|hit1;ch2<=8'h20;gx2<=0;gy2<=0;fg2<=WHITE;")
    o.append("  casez(hit1)")
    for i, (n, x, y, s, c, src, colx) in enumerate(BOXES):
        pat = "".join("1" if j == i else ("0" if j < i else "?") for j in range(nb))[::-1]   # lowest index wins
        sh = SCALE_SHIFT[s]
        o.append(f"   {nb}'b{pat}:begin ch2<=t_{n}[((hc1-10'd{x})>>{3+sh})*8 +: 8];gx2<=(hc1-10'd{x})>>{sh};gy2<=(vc1-10'd{y})>>{sh};fg2<={colx};end")
    o.append("   default:;\n  endcase\n end\nend")
    # font + output
    o.append("// ---------------- stage 3: font lookup and output ----------------\nfunction [4:0] font;input [7:0] c;input [2:0] r;begin\n font=5'b00000;\n case({c,r})")
    for chr_, rows in FONT.items():
        for r, bits in enumerate(rows):
            val = int(bits.replace('#', '1').replace(' ', '0'), 2)
            if val:
                o.append(f"  {{8'h{ord(chr_):02x},3'd{r}}}:font=5'b{val:05b};")
    o.append(""" default:;
 endcase
end endfunction
wire [4:0] glyph=font(ch2,gy2);
wire pix=on2 && gx2>=3'd1 && gx2<=3'd5 && gy2<=3'd6 && glyph[3'd5-gx2];
always @(posedge clk or negedge rst_n)begin
 if(!rst_n)begin vga_r<=0;vga_g<=0;vga_b<=0;vga_hs<=1;vga_vs<=1;end
 else if(pe)begin
  vga_hs<=s2_hs;vga_vs<=s2_vs;
  if(!s2_active)begin vga_r<=0;vga_g<=0;vga_b<=0;end
  else {vga_r,vga_g,vga_b}<=pix ? fg2 : bg2;
 end
end
endmodule
`default_nettype wire""")
    text = "\n".join(o) + "\n"
    # Pad reason/detail/head literals to their exact widths (Verilog drops leading chars of over-long
    # literals and left-pads short ones with NUL, which would shift the text).
    text = re.sub(r'(reason_word|detail_word)="([^"]*)"', lambda m: f'{m.group(1)}="{m.group(2)[:30].ljust(30)}"', text)
    text = re.sub(r'head_word="([^"]*)"', lambda m: f'head_word="{m.group(1)[:16].ljust(16)}"', text)
    return text


if __name__ == "__main__":
    out = Path(__file__).resolve().parents[1] / "rtl/de10_lite/garda_vga_status.v"
    out.write_text(gen(), encoding="ascii")
    print(f"wrote {out} ({len(BOXES)} text boxes)")
