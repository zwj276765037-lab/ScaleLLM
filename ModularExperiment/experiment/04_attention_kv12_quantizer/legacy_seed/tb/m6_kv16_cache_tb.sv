`timescale 1ns/1ps
module m6_kv16_cache_tb;
`ifdef CASE_FP32
    localparam integer MW=32;
`else
    localparam integer MW=16;
`endif
    localparam integer DEPTH=4096;
    reg clk=0,rst_n=0,clear=0,wr_valid=0,wr_is_v=0;
    reg [11:0] wr_addr=0; reg [511:0] wr_s16=0; reg [MW-1:0] wr_scale=0;
    wire wr_ready;
    reg k_rd_valid=0,v_rd_valid=0,k_rsp_ready=0,v_rsp_ready=0;
    reg [11:0] k_rd_addr=0,v_rd_addr=0;
    wire k_rd_ready,v_rd_ready,k_rsp_valid,v_rsp_valid;
    wire [511:0] k_rsp_s16,v_rsp_s16;
    wire [MW-1:0] k_rsp_scale,v_rsp_scale;
    wire [31:0] kw,vw,kr,vr,fe; wire error;
    integer cycle=0,wi=0,kqi=0,vqi=0,krc=0,vrc=0,mis=0;
    reg [11:0] kexp=0,vexp=0; reg [511+MW:0] khold=0,vhold=0;
    reg kwas=0,vwas=0;

    function automatic [511:0] value_pattern;
        input [11:0] addr; input is_v; integer lane; reg signed [15:0] val;
        begin
            value_pattern=0;
            for(lane=0;lane<32;lane=lane+1) begin
                val=$signed({1'b0,addr})*7 + lane*13 + (is_v?101:17);
                if ((lane+addr[3:0])&1) val=-val;
                value_pattern[lane*16+:16]=val;
            end
        end
    endfunction
    function automatic [MW-1:0] scale_pattern;
        input [11:0] addr; input is_v;
        begin
            if (MW==16) scale_pattern=16'h2400 | {8'd0,addr[5:0]} | is_v;
            else scale_pattern=32'h38800000 | {19'd0,addr[11:0]} | is_v;
        end
    endfunction
    function automatic [11:0] order_pattern;
        input integer idx; begin order_pattern=(idx*4051+37)&4095; end
    endfunction

`ifdef CASE_FP32
    m6_kv16_fp32_cache dut(.*,.k_write_count(kw),.v_write_count(vw),
      .k_read_count(kr),.v_read_count(vr),.format_error_count(fe));
`else
    m6_kv16_fp16_cache dut(.*,.k_write_count(kw),.v_write_count(vw),
      .k_read_count(kr),.v_read_count(vr),.format_error_count(fe));
`endif
    always #3.3335 clk=~clk;
    initial begin repeat(8)@(posedge clk);rst_n<=1;end
    always @(negedge clk) begin
        if(!rst_n) begin wr_valid<=0;k_rd_valid<=0;v_rd_valid<=0;
          k_rsp_ready<=0;v_rsp_ready<=0;end
        else if(wi<2*DEPTH) begin
            wr_valid<=1;wr_is_v<=wi[0];wr_addr<=wi>>1;
            wr_s16<=value_pattern(wi>>1,wi[0]);
            wr_scale<=scale_pattern(wi>>1,wi[0]);
            k_rd_valid<=0;v_rd_valid<=0;k_rsp_ready<=0;v_rsp_ready<=0;
        end else begin
            wr_valid<=0;
            k_rsp_ready<=!(((cycle%31)>=21)&&((cycle%31)<=25));
            v_rsp_ready<=!(((cycle%43)>=29)&&((cycle%43)<=36));
            if(kqi<DEPTH)begin k_rd_addr<=order_pattern(kqi);k_rd_valid<=1;end
            else k_rd_valid<=0;
            if(vqi<DEPTH)begin v_rd_addr<=order_pattern(vqi);v_rd_valid<=1;end
            else v_rd_valid<=0;
        end
    end
    always @(posedge clk) if(rst_n) begin
        cycle<=cycle+1;
        if(wr_valid&&wr_ready)wi<=wi+1;
        if(kwas&&(!k_rsp_valid||{k_rsp_scale,k_rsp_s16}!==khold))begin
          $display("FAIL: K changed under stall");$finish;end
        if(vwas&&(!v_rsp_valid||{v_rsp_scale,v_rsp_s16}!==vhold))begin
          $display("FAIL: V changed under stall");$finish;end
        kwas<=k_rsp_valid&&!k_rsp_ready;vwas<=v_rsp_valid&&!v_rsp_ready;
        if(k_rsp_valid&&!k_rsp_ready)khold<={k_rsp_scale,k_rsp_s16};
        if(v_rsp_valid&&!v_rsp_ready)vhold<={v_rsp_scale,v_rsp_s16};
        if(k_rd_valid&&k_rd_ready)begin kexp<=k_rd_addr;kqi<=kqi+1;end
        if(v_rd_valid&&v_rd_ready)begin vexp<=v_rd_addr;vqi<=vqi+1;end
        if(k_rsp_valid&&k_rsp_ready)begin
          if({k_rsp_scale,k_rsp_s16}!=={scale_pattern(kexp,0),value_pattern(kexp,0)})mis<=mis+1;
          krc<=krc+1;end
        if(v_rsp_valid&&v_rsp_ready)begin
          if({v_rsp_scale,v_rsp_s16}!=={scale_pattern(vexp,1),value_pattern(vexp,1)})mis<=mis+1;
          vrc<=vrc+1;end
        if(error)begin $display("FAIL: format error %0d",fe);$finish;end
        if(cycle>50000)begin $display("FAIL: timeout");$finish;end
        if(krc==DEPTH&&vrc==DEPTH)begin
          if(mis==0&&kw==DEPTH&&vw==DEPTH&&kr==DEPTH&&vr==DEPTH)begin
`ifdef CASE_FP32
            $display("M6_KV16_CACHE_METRIC_JSON: {\"case\":\"fp32\",\"record_bits\":544,\"depth\":4096,\"k_writes\":4096,\"v_writes\":4096,\"k_reads\":4096,\"v_reads\":4096,\"read_latency\":1,\"read_ii\":1,\"mismatches\":0,\"cycles\":%0d}",cycle);
`else
            $display("M6_KV16_CACHE_METRIC_JSON: {\"case\":\"fp16\",\"record_bits\":528,\"depth\":4096,\"k_writes\":4096,\"v_writes\":4096,\"k_reads\":4096,\"v_reads\":4096,\"read_latency\":1,\"read_ii\":1,\"mismatches\":0,\"cycles\":%0d}",cycle);
`endif
            $display("PASS: M6 matched KV16 cache");
          end else $display("FAIL: final mis=%0d kw=%0d vw=%0d kr=%0d vr=%0d",mis,kw,vw,kr,vr);
          $finish;
        end
    end
endmodule
