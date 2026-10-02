`timescale 1ns/1ps
module m7_qk_tb;
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
    integer cy=0,row=0,send=0,recv=0,mis=0,start=-1,rowstart=-1,maxrow=0,c,qdelay=0;reg qloaded=0;

    generate
        if(CASE_ID==1) m7_fp16_qk_row d(
          .clk(clk),.rst_n(rst_n),.clear(clear),.query_load_valid(qlv),
          .query_load_ready(qlr),.query_fp16(q16[row]),.in_valid(iv),
          .in_ready(ir),.in_last_key(ilast),.in_mask(imask),.key_fp16(k16[send]),
          .out_valid(ov),.out_ready(ordy),.out_score_q14_s20(os),.out_mask(om),
          .out_key_index(oi),.out_last_key(olast),.input_key_count(ic),
          .output_score_count(oc),.clip_count(cc),.error(err));
        else m7_fp32_qk_row d(
          .clk(clk),.rst_n(rst_n),.clear(clear),.query_load_valid(qlv),
          .query_load_ready(qlr),.query_fp32(q32[row]),.in_valid(iv),
          .in_ready(ir),.in_last_key(ilast),.in_mask(imask),.key_fp32(k32[send]),
          .out_valid(ov),.out_ready(ordy),.out_score_q14_s20(os),.out_mask(om),
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
        qlv<=row<R&&send==row*K&&!qloaded;
        if(send<R*K&&send>=row*K&&send<(row+1)*K&&
          ((CASE_ID==1&&qdelay>=8)||(CASE_ID==2&&qdelay>=1)))begin
            iv<=1;ilast<=(send%K)==K-1;imask<=mask[send];
        end else iv<=0;
    end
    always@(posedge clk) if(rst_n) begin
        cy<=cy+1;
        if(qlv&&qlr)begin if(start<0)start=cy;rowstart=cy;qdelay<=1;qloaded<=1;end
        else if(qdelay>0&&qdelay<8)qdelay<=qdelay+1;
        if(iv&&ir)send<=send+1;
        if(err)begin
            $display("FAIL: M7 error row=%0d send=%0d recv=%0d",row,send,recv);
            $finish;
        end
        if(ov&&ordy)begin
            if(os!==(CASE_ID==1?e16[recv]:e32[recv])||om!==mask[recv]||
              oi!=(recv%K)||olast!==((recv%K)==K-1))begin
                if(mis<8)$display("MISMATCH recv=%0d expected=%h got=%h mask=%0d/%0d idx=%0d last=%0d",recv,CASE_ID==1?e16[recv]:e32[recv],os,mask[recv],om,oi,olast);
                mis<=mis+1;
            end
            recv<=recv+1;
            if(olast)begin c=cy-rowstart;if(c>maxrow)maxrow=c;row<=row+1;qdelay<=0;qloaded<=0;end
            if(recv==R*K-1)begin
                if(mis==0&&ic==R*K&&oc==R*K-1)begin
                    $display("M7_QK_METRIC_JSON: {\"case\":\"%s\",\"rows\":8,\"keys\":1024,\"mismatches\":0,\"max_row_cycles\":%0d,\"clip_count\":%0d,\"cycles\":%0d}",CASE_ID==1?"fp16":"fp32",c>maxrow?c:maxrow,cc,cy);
                    $display("PASS: M7 matched QK");
                end else $display("FAIL: M7 final mis=%0d ic=%0d oc=%0d",mis,ic,oc);
                $finish;
            end
        end
        if(cy>3000)begin
            $display("FAIL: M7 timeout row=%0d send=%0d recv=%0d ic=%0d oc=%0d cc=%0d qlv/r=%0d/%0d iv/r=%0d/%0d ov/r=%0d/%0d qdelay=%0d qloaded=%0d",row,send,recv,ic,oc,cc,qlv,qlr,iv,ir,ov,ordy,qdelay,qloaded);
            $finish;
        end
    end
endmodule
