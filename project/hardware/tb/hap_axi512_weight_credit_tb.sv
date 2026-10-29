`timescale 1ns/1ps
module hap_axi512_weight_credit_case #(parameter integer DEPTH=128)(output reg finished=0);
    reg clk=0,rst_n=0,clear=0,cmd_valid=0,consume=0,inject=0,ar_hold_test=0;
    always #2.5 clk=~clk;
    reg [31:0] base=32'h11800000;
    reg [16:0] group_count=0;
    wire cmd_ready,valid,ready_last,arvalid,arready,rvalid,rready,rlast,busy,done,error;
    wire [511:0] data,rdata;
    wire [31:0] araddr,issued,received,received_beats,emitted_groups,protocol_errors,max_outstanding;
    wire [7:0] arlen;wire [2:0] arsize;wire [1:0] arburst;
    integer accepted_words=0,returned=0,outputs=0,command_cycles=0,hold_cycles=0;
    integer triple=0,held_offer_with_error=0,wraps=0,checks=0;
    wire ar_fire=arvalid&&arready,r_fire=rvalid&&rready,out_fire=valid&&consume;
    wire hold_ar=ar_hold_test&&accepted_words>=32&&hold_cycles<64;
    assign arready=rst_n&&!clear&&!hold_ar;
    assign rvalid=rst_n&&!clear&&command_cycles>=32&&returned<accepted_words;
    assign rdata=payload(base+returned*64);
    assign rlast=(returned%16==15)||(inject&&returned==4);

    function automatic [511:0] payload(input [31:0] address);
        integer k;
        begin
            for(k=0;k<16;k=k+1)payload[k*32+:32]=(address+k*4)^32'h72c13b59;
        end
    endfunction
    hap_axi512_weight_reader #(.RESPONSE_FIFO_DEPTH(DEPTH)) dut(
        .clk(clk),.rst_n(rst_n),.clear(clear),.cmd_valid(cmd_valid),.cmd_ready(cmd_ready),
        .cmd_base_addr(base),.cmd_group_count(group_count),
        .beat_valid(valid),.beat_ready(consume),.beat_data(data),.beat_group_last(ready_last),
        .m_axi_arvalid(arvalid),.m_axi_arready(arready),.m_axi_araddr(araddr),
        .m_axi_arlen(arlen),.m_axi_arsize(arsize),.m_axi_arburst(arburst),
        .m_axi_rvalid(rvalid),.m_axi_rready(rready),.m_axi_rdata(rdata),
        .m_axi_rresp(inject&&returned==3?2'b10:2'b00),.m_axi_rlast(rlast),
        .busy(busy),.done(done),.error(error),.command_count(),
        .issued_burst_count(issued),.received_burst_count(received),.received_beat_count(received_beats),
        .emitted_group_count(emitted_groups),.protocol_error_count(protocol_errors),
        .max_outstanding_count(max_outstanding));
    reg stalled_ar=0,stalled_output=0;reg [44:0] held_ar;reg [512:0] held_output;
    always @(posedge clk)begin
        if(!rst_n||clear)begin
            accepted_words<=0;returned<=0;outputs<=0;command_cycles<=0;hold_cycles<=0;
            stalled_ar<=0;stalled_output<=0;
        end else begin
            command_cycles<=command_cycles+1;
            if(hold_ar)hold_cycles<=hold_cycles+1;
            if(stalled_ar&&(!arvalid||{araddr,arlen,arsize,arburst}!==held_ar))
                $fatal(1,"D%0d AR offer changed under stall",DEPTH);
            if(stalled_output&&(!valid||{data,ready_last}!==held_output))
                $fatal(1,"D%0d buffered output changed under stall",DEPTH);
            stalled_ar<=arvalid&&!arready;held_ar<={araddr,arlen,arsize,arburst};
            stalled_output<=valid&&!consume;held_output<={data,ready_last};
            if(dut.received_queued>dut.reserved_r||dut.reserved_r>DEPTH||
               dut.received_queued!==returned-outputs||dut.reserved_r!==accepted_words-outputs||
               dut.unreturned!==accepted_words-returned)
                $fatal(1,"D%0d independent reservation/Q/U invariant Q=%0d reserve=%0d U=%0d accepted=%0d received=%0d out=%0d",DEPTH,dut.received_queued,dut.reserved_r,dut.unreturned,accepted_words,returned,outputs);
            if(accepted_words>returned&&!rready)$fatal(1,"D%0d committed R was backpressured",DEPTH);
            if(ar_fire)begin
                if(araddr!==base+accepted_words*64||arlen!==15||arsize!==6||arburst!==1)
                    $fatal(1,"D%0d independent AR shape/address mismatch",DEPTH);
                accepted_words<=accepted_words+16;
            end
            if(r_fire)returned<=returned+1;
            if(out_fire)begin
                if(data!==payload(base+outputs*64)||ready_last!==(outputs%4==3))
                    $fatal(1,"D%0d output payload/group-last mismatch beat%0d",DEPTH,outputs);
                outputs<=outputs+1;
            end
            if(ar_fire&&r_fire&&out_fire)triple<=triple+1;
            if(arvalid&&!arready&&error)held_offer_with_error<=held_offer_with_error+1;
            if(r_fire&&dut.ram_wr_r==DEPTH-1)wraps<=wraps+1;
            if(done&&group_count!=0&&outputs!=group_count*4)$fatal(1,"D%0d premature done",DEPTH);
        end
    end
    task automatic clean(input [31:0] address);
    begin
        wait(!busy);@(negedge clk);clear=1;consume=0;inject=0;ar_hold_test=0;base=address;
        @(negedge clk);clear=0;
        if(valid||dut.reserved_r!=0||dut.ram_count_r!=0)$fatal(1,"clear leaked old payload validity");
    end
    endtask
    task automatic start(input integer n);
    begin
        @(negedge clk);group_count=n;cmd_valid=1;
        @(posedge clk);if(!cmd_ready)$fatal(1,"command not ready");
        @(negedge clk);cmd_valid=0;
    end
    endtask
    task automatic drain(input integer expected_beats,input integer expected_errors);
        integer n;
    begin
        consume=1;n=0;
        while(!done&&n<4000)begin @(negedge clk);n=n+1;end
        if(!done||busy||!cmd_ready||outputs!=expected_beats||returned!=expected_beats||
           received!=expected_beats/16||emitted_groups!=expected_beats/4||
           protocol_errors!=expected_errors||error!==(expected_errors!=0))
            $fatal(1,"D%0d final drain/count mismatch out=%0d received=%0d groups=%0d protocol=%0d",DEPTH,outputs,returned,emitted_groups,protocol_errors);
        checks=checks+1;
    end
    endtask
    initial begin
        repeat(6)@(negedge clk);rst_n=1;
        clean(32'h11800000);start(DEPTH/4);
        wait(returned==DEPTH);repeat(16)@(negedge clk);
        if(outputs!=0||issued!=DEPTH/16||max_outstanding!=DEPTH/16||
           !busy||cmd_ready||done||dut.reserved_r!=DEPTH||dut.unreturned!=0)
            $fatal(1,"D%0d complete reservation/late-output boundary",DEPTH);
        checks=checks+1;drain(DEPTH,0);

        clean(32'h12000000);start(128);
        wait(returned==DEPTH);repeat(8)@(negedge clk);
        if(accepted_words!=DEPTH||outputs!=0)$fatal(1,"AR exceeded exhausted credit");
        checks=checks+1;drain(512,0);
        if(triple==0||wraps<4)$fatal(1,"D%0d missing triple-handshake/wrap coverage",DEPTH);

        clean(32'h13000000);inject=1;ar_hold_test=1;consume=1;start(32);
        drain(128,2);
        if(held_offer_with_error==0)$fatal(1,"D%0d AR-stall with sticky protocol status not covered",DEPTH);
        clean(32'h14000000);start(0);
        if(!done||!error||busy||issued!=0)$fatal(1,"invalid-command contract changed");
        checks=checks+1;
        $display("CREDIT_COVERAGE depth=%0d max_window=%0d checks=%0d triple=%0d wraps=%0d AR_stall_with_sticky_status=%0d",DEPTH,DEPTH/16,checks,triple,wraps,held_offer_with_error);
        finished=1;
    end
    initial begin #100000;$fatal(1,"credit regression cycle ceiling D%0d",DEPTH);end
endmodule

module hap_axi512_weight_credit_tb;
    wire finished128,finished32;
    hap_axi512_weight_credit_case #(.DEPTH(128)) c128(finished128);
    hap_axi512_weight_credit_case #(.DEPTH(32)) c32(finished32);
    initial begin
        wait(finished128&&finished32);
        $display("HARDWARE_AGENT_SIM_PASS");$finish;
    end
endmodule
