`timescale 1ns/1ps
module m7_qk_tm_tb;
    parameter CASE_ID=1;
    parameter DATA_DIR="data";
    localparam R=8,K=128;
    reg clk=0,rst_n=0,clear=0,qlv=0,iv=0,ordy=0,ilast=0,imask=0;
    wire qlr,ir,ov,om,olast,err;
    wire signed [19:0] os;
    wire [6:0] oi;
    wire [31:0] ic,oc,cc;
    reg [4095:0] q32[0:R-1],k32[0:R*K-1];
    reg [2047:0] q16[0:R-1],k16[0:R*K-1];
    reg [19:0] e16[0:R*K-1],e32[0:R*K-1];
    reg mask[0:R*K-1];
    integer cy=0,qsend=0,send=0,recv=0,mis=0,start=-1;
    integer maxlat=0,maxinterval=0,lastdone=-1,c;
    integer qstart[0:R-1];

    generate
        if(CASE_ID==1) m7_fp16_qk_row_tm d(
          .clk(clk),.rst_n(rst_n),.clear(clear),.query_load_valid(qlv),
          .query_load_ready(qlr),.query_fp16(q16[(qsend<R)?qsend:R-1]),
          .in_valid(iv),.in_ready(ir),.in_last_key(ilast),.in_mask(imask),
          .key_fp16(k16[(send<R*K)?send:R*K-1]),.out_valid(ov),
          .out_ready(ordy),.out_score_q14_s20(os),.out_mask(om),
          .out_key_index(oi),.out_last_key(olast),.input_key_count(ic),
          .output_score_count(oc),.clip_count(cc),.error(err));
        else m7_fp32_qk_row_tm d(
          .clk(clk),.rst_n(rst_n),.clear(clear),.query_load_valid(qlv),
          .query_load_ready(qlr),.query_fp32(q32[(qsend<R)?qsend:R-1]),
          .in_valid(iv),.in_ready(ir),.in_last_key(ilast),.in_mask(imask),
          .key_fp32(k32[(send<R*K)?send:R*K-1]),.out_valid(ov),
          .out_ready(ordy),.out_score_q14_s20(os),.out_mask(om),
          .out_key_index(oi),.out_last_key(olast),.input_key_count(ic),
          .output_score_count(oc),.clip_count(cc),.error(err));
    endgenerate

    always #3.3335 clk=~clk;
    initial begin
        $readmemh({DATA_DIR,"/query_fp16.mem"},q16);
        $readmemh({DATA_DIR,"/query_fp32.mem"},q32);
        $readmemh({DATA_DIR,"/key_fp16.mem"},k16);
        $readmemh({DATA_DIR,"/key_fp32.mem"},k32);
        $readmemh({DATA_DIR,"/expected_fp16.mem"},e16);
        $readmemh({DATA_DIR,"/expected_fp32.mem"},e32);
        $readmemh({DATA_DIR,"/mask.mem"},mask);
        repeat(8)@(posedge clk);rst_n<=1;
    end
    always@(negedge clk) if(rst_n) begin
        ordy<=!((cy%43)>=31&&(cy%43)<=36);
        qlv<=qsend<R;
        if(send<R*K)begin
            iv<=1;ilast<=(send%K)==K-1;imask<=mask[send];
        end else begin
            iv<=0;ilast<=0;imask<=0;
        end
    end
    always@(posedge clk) if(rst_n) begin
        cy<=cy+1;
        if(qlv&&qlr)begin
            if(start<0)start=cy;
            qstart[qsend]=cy;
            qsend<=qsend+1;
        end
        if(iv&&ir)send<=send+1;
        if(err)begin
            $display("FAIL: M7 TM error qsend=%0d send=%0d recv=%0d",qsend,send,recv);
            $finish;
        end
        if(ov&&ordy)begin
            if(os!==(CASE_ID==1?e16[recv]:e32[recv])||om!==mask[recv]||
              oi!=(recv%K)||olast!==((recv%K)==K-1))begin
                if(mis<8)$display("MISMATCH recv=%0d expected=%h got=%h mask=%0d/%0d idx=%0d last=%0d",recv,CASE_ID==1?e16[recv]:e32[recv],os,mask[recv],om,oi,olast);
                mis<=mis+1;
            end
            recv<=recv+1;
            if(olast)begin
                c=cy-qstart[recv/K];
                if(c>maxlat)maxlat=c;
                if(lastdone>=0&&cy-lastdone>maxinterval)maxinterval=cy-lastdone;
                lastdone=cy;
            end
            if(recv==R*K-1)begin
                if(mis==0&&ic==R*K&&oc==R*K-1)begin
                    $display("M7_QK_TM_METRIC_JSON: {\"case\":\"%s\",\"rows\":8,\"keys\":1024,\"mismatches\":0,\"max_row_latency_cycles\":%0d,\"max_completion_interval_cycles\":%0d,\"clip_count\":%0d,\"cycles\":%0d}",CASE_ID==1?"fp16_tm":"fp32_tm",c>maxlat?c:maxlat,maxinterval,cc,cy);
                    $display("PASS: M7 throughput-matched QK");
                end else $display("FAIL: M7 TM final mis=%0d ic=%0d oc=%0d",mis,ic,oc);
                $finish;
            end
        end
        if(cy>12000)begin
            $display("FAIL: M7 TM timeout qsend=%0d send=%0d recv=%0d ic=%0d oc=%0d cc=%0d qlv/r=%0d/%0d iv/r=%0d/%0d ov/r=%0d/%0d",qsend,send,recv,ic,oc,cc,qlv,qlr,iv,ir,ov,ordy);
            $finish;
        end
    end
endmodule
