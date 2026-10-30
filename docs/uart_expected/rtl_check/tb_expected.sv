`timescale 1ns/1ps
module tb_uart_board_stress;
  reg clk=0; always #10 clk=~clk;
  reg [1:0] key=2'b10;
  reg rx=1;
  wire tx; wire [7:0] led;
  igor_src_policy_de10_nano dut(clk,key,rx,tx,led);
  localparam real HOST_BIT_NS=1000000000.0/921600.0;
  real drive_bit_ns=HOST_BIT_NS;
  reg signed [15:0] obs[0:236*74-1], gold[0:236*3-1];
  reg [15:0] vectors[0:49];
  reg [7:0] received[0:1023], sample;
  integer count=0, monitor_bit, frame, i, j, base, limit;
  reg [7:0] check;
  reg [15:0] word_value;
  reg [7:0] request_crc;
  initial forever begin
    @(negedge tx);
    #(HOST_BIT_NS/2);
    if(tx!==0) $fatal(1,"TX start bit not stable");
    #(HOST_BIT_NS);
    for(monitor_bit=0;monitor_bit<8;monitor_bit=monitor_bit+1)begin
      sample[monitor_bit]=tx; #(HOST_BIT_NS);
    end
    if(tx!==1) $fatal(1,"TX invalid stop bit at byte %0d",count);
    if(count>=1024) $fatal(1,"TX flood");
    received[count]=sample; count=count+1;
  end
  always @(posedge clk) begin
    #1;
    if(!key[0] && tx!==1) $fatal(1,"TX not high during reset");
  end
  function [7:0] crc8;
    input [7:0] previous,value;
    reg [7:0] c; integer k;
    begin
      c=previous^value;
      for(k=0;k<8;k=k+1)c=c[0]?(c>>1)^8'h8c:c>>1;
      crc8=c;
    end
  endfunction
  task send_byte;
    input [7:0] value; integer k;
    begin
      rx=0; #(drive_bit_ns);
      for(k=0;k<8;k=k+1)begin rx=value[k];#(drive_bit_ns);end
      rx=1;#(drive_bit_ns);
    end
  endtask
  initial begin
    $readmemh("observations.hex",obs);
    $readmemh("expected.hex",gold);
    $readmemh("valid_vectors.hex",vectors);
    #100000;
    if(tx!==1 || count!=0)$fatal(1,"Reset produced bytes");
    key=2'b11;
    #1000000;
    if(tx!==1 || count!=0)$fatal(1,"Idle boot produced bytes");
    for(frame=0;frame<1;frame=frame+1)begin
      // Sweep asynchronous phase and host bit durations: nominal and +/-1%.
      case(frame%3)
        0: drive_bit_ns=HOST_BIT_NS;
        1: drive_bit_ns=HOST_BIT_NS*0.99;
        2: drive_bit_ns=HOST_BIT_NS*1.01;
      endcase
      #(3.7+frame%17);
      base=count;
      send_byte(8'h5a);send_byte(8'ha5);send_byte(1);send_byte(8'h94);
      request_crc=crc8(crc8(0,1),8'h94);
      for(i=0;i<74;i=i+1)begin
        word_value=obs[vectors[frame]*74+i];
        send_byte(word_value[7:0]);request_crc=crc8(request_crc,word_value[7:0]);
        send_byte(word_value[15:8]);request_crc=crc8(request_crc,word_value[15:8]);
      end
      send_byte(request_crc);
      limit=0;
      while(count<base+11 && limit<50000)begin @(posedge clk);limit=limit+1;end
      if(count!=base+11)$fatal(1,"Frame %0d response count %0d error %0d",frame,count-base,dut.error_code);
      if(received[base]!==8'h5a || received[base+1]!==8'ha5 || received[base+2]!==2 || received[base+3]!==6)
        $fatal(1,"Frame %0d header mismatch",frame);
      check=0;
      for(j=2;j<10;j=j+1)check=crc8(check,received[base+j]);
      if(received[base+10]!==check)$fatal(1,"Frame %0d CRC mismatch",frame);
      for(j=0;j<3;j=j+1)begin
        word_value={received[base+5+j*2],received[base+4+j*2]};
        if(word_value!==gold[vectors[frame]*3+j])$fatal(1,"Frame %0d action %0d numerical mismatch",frame,j);
      end
      #50000;
      if(count!=base+11 || tx!==1)$fatal(1,"Frame %0d extra bytes",frame);
    end
    #21000000;
    if(count!=11 || tx!==1 || dut.accepted!=1 || dut.rejected!=1 || dut.error_code!=11)
      $fatal(1,"Idle/stale state incorrect: bytes %0d accepted %0d rejected %0d error %0d",count,dut.accepted,dut.rejected,dut.error_code);
    for(j=0;j<11;j=j+1)$write("%02x ",received[j]);$write("\n");
    $display("PASS expected: 1 synthetic request, exact 11-byte CRC-valid response, 3 golden actions, quiet reset/boot/stale TX");
    $finish;
  end
  initial begin #150000000;$fatal(1,"Stress watchdog");end
endmodule
