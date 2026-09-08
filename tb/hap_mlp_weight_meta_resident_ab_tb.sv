`timescale 1ns / 1ps

module hap_mlp_weight_meta_resident_ab_tb;
    localparam integer GD=16,DD=8,GAW=4,DAW=3;
    reg clk=1'b0,rst_n=1'b0,clear=1'b0;
    reg load_begin_valid=1'b0,load_begin_bank=1'b0;
    wire load_begin_ready;
    reg gate_wr_valid=1'b0,gate_wr_bank=1'b0;
    reg [GAW-1:0] gate_wr_addr=0;
    reg [223:0] gate_wr_meta_u224=0;
    wire gate_wr_ready;
    reg down_wr_valid=1'b0,down_wr_bank=1'b0;
    reg [DAW-1:0] down_wr_addr=0;
    reg [223:0] down_wr_meta_u224=0;
    wire down_wr_ready;
    reg commit_valid=1'b0,commit_bank=1'b0;
    reg [31:0] commit_generation=0;
    reg consumer_quiescent=1'b1;
    wire commit_ready,active_bank;
    wire [31:0] active_generation;
    wire [1:0] bank_valid,bank_loading;
    reg gate_rd_valid=1'b0,gate_rsp_ready=1'b0;
    reg [GAW-1:0] gate_rd_addr=0;
    wire gate_rd_ready,gate_rsp_valid;
    wire [223:0] gate_rsp_meta_u224;
    reg down_rd_valid=1'b0,down_rsp_ready=1'b0;
    reg [DAW-1:0] down_rd_addr=0;
    wire down_rd_ready,down_rsp_valid;
    wire [223:0] down_rsp_meta_u224;
    wire [31:0] gw0,gw1,dw0,dw1,gr,dr;
    wire error;
    integer i,checks=0;
    integer cycles=0;

    always #3.333 clk=~clk;
    always @(posedge clk) begin
        cycles <= cycles+1;
        if (cycles==2001) begin
            $display("FAIL timeout active=%0d valid=%b loading=%b gw=%0d/%0d dw=%0d/%0d commit_ready=%0d gate_rsp=%0d down_rsp=%0d error=%0d",
                active_bank,bank_valid,bank_loading,gw0,gw1,dw0,dw1,
                commit_ready,gate_rsp_valid,down_rsp_valid,error);
            $fatal(1);
        end
    end

    hap_mlp_weight_meta_resident_ab #(
        .GATE_DEPTH(GD),.DOWN_DEPTH(DD),.GATE_ADDR_W(GAW),
        .DOWN_ADDR_W(DAW),.PRODUCTION_SHAPE(0)
    ) dut (
        .clk(clk),.rst_n(rst_n),.clear(clear),
        .load_begin_valid(load_begin_valid),
        .load_begin_ready(load_begin_ready),.load_begin_bank(load_begin_bank),
        .gate_wr_valid(gate_wr_valid),.gate_wr_ready(gate_wr_ready),
        .gate_wr_bank(gate_wr_bank),.gate_wr_addr(gate_wr_addr),
        .gate_wr_meta_u224(gate_wr_meta_u224),
        .down_wr_valid(down_wr_valid),.down_wr_ready(down_wr_ready),
        .down_wr_bank(down_wr_bank),.down_wr_addr(down_wr_addr),
        .down_wr_meta_u224(down_wr_meta_u224),
        .commit_valid(commit_valid),.commit_ready(commit_ready),
        .commit_bank(commit_bank),.commit_generation(commit_generation),
        .consumer_quiescent(consumer_quiescent),.active_bank(active_bank),
        .active_generation(active_generation),.bank_valid(bank_valid),
        .bank_loading(bank_loading),.gate_rd_valid(gate_rd_valid),
        .gate_rd_ready(gate_rd_ready),.gate_rd_addr(gate_rd_addr),
        .gate_rsp_valid(gate_rsp_valid),.gate_rsp_ready(gate_rsp_ready),
        .gate_rsp_meta_u224(gate_rsp_meta_u224),
        .down_rd_valid(down_rd_valid),.down_rd_ready(down_rd_ready),
        .down_rd_addr(down_rd_addr),.down_rsp_valid(down_rsp_valid),
        .down_rsp_ready(down_rsp_ready),
        .down_rsp_meta_u224(down_rsp_meta_u224),
        .gate_write_count_bank0(gw0),.gate_write_count_bank1(gw1),
        .down_write_count_bank0(dw0),.down_write_count_bank1(dw1),
        .gate_read_count(gr),.down_read_count(dr),.error(error)
    );

    task tick; begin @(posedge clk); #1; end endtask
    task check;
        input condition; input [8*96-1:0] message;
        begin checks=checks+1; if (!condition) begin
            $display("FAIL check=%0d %0s",checks,message); $fatal(1);
        end end
    endtask
    task begin_load;
        input bank;
        begin load_begin_bank=bank;load_begin_valid=1'b1;#0.1;
            while(!load_begin_ready) tick();tick();
            load_begin_valid=1'b0; end
    endtask
    task write_gate;
        input bank; input [GAW-1:0] addr; input [223:0] value;
        begin gate_wr_bank=bank;gate_wr_addr=addr;gate_wr_meta_u224=value;
            gate_wr_valid=1'b1;#0.1;
            while (!gate_wr_ready) tick(); tick();
            gate_wr_valid=1'b0; end
    endtask
    task write_down;
        input bank; input [DAW-1:0] addr; input [223:0] value;
        begin down_wr_bank=bank;down_wr_addr=addr;down_wr_meta_u224=value;
            down_wr_valid=1'b1;#0.1;
            while (!down_wr_ready) tick(); tick();
            down_wr_valid=1'b0; end
    endtask
    task commit;
        input bank; input [31:0] generation;
        begin commit_bank=bank;commit_generation=generation;
            commit_valid=1'b1;#0.1;
            while (!commit_ready) tick();tick();
            commit_valid=1'b0; end
    endtask
    task read_gate;
        input [GAW-1:0] addr; input [223:0] expected;
        begin gate_rd_addr=addr;gate_rd_valid=1'b1;
            #0.1;
            while (!gate_rd_ready) tick();tick();gate_rd_valid=1'b0;
            while (!gate_rsp_valid) tick();
            check(gate_rsp_meta_u224===expected,"gate metadata mismatch");
            gate_rsp_ready=1'b1;tick();gate_rsp_ready=1'b0; end
    endtask
    task read_down;
        input [DAW-1:0] addr; input [223:0] expected;
        begin down_rd_addr=addr;down_rd_valid=1'b1;
            #0.1;
            while (!down_rd_ready) tick();tick();down_rd_valid=1'b0;
            while (!down_rsp_valid) tick();
            check(down_rsp_meta_u224===expected,"down metadata mismatch");
            down_rsp_ready=1'b1;tick();down_rsp_ready=1'b0; end
    endtask

    initial begin
        repeat(4) tick();rst_n=1'b1;tick();
        check(!bank_valid[0]&&!bank_valid[1],"reset bank validity");
        check(!gate_rd_ready&&!down_rd_ready,"read accepted without valid bank");

        begin_load(1'b1);
        $display("STAGE load bank1 cycle=%0d",cycles);
        check(bank_loading==2'b10,"bank1 load did not begin");
        for(i=0;i<GD;i=i+1) write_gate(1'b1,i,224'h1000+i);
        for(i=0;i<DD;i=i+1) write_down(1'b1,i,224'h2000+i);
        check(gw1==GD&&dw1==DD,"exact bank1 counts not reached");
        commit_bank=1'b1;consumer_quiescent=1'b0;#1;
        check(!commit_ready,"commit allowed while consumer active");
        consumer_quiescent=1'b1;commit(1'b1,32'h11);
        $display("STAGE commit bank1 cycle=%0d",cycles);
        check(active_bank&&active_generation==32'h11&&bank_valid[1],
            "bank1 commit failed");
        read_gate(4'd5,224'h1005);read_down(3'd6,224'h2006);

        begin_load(1'b0);
        $display("STAGE load bank0 cycle=%0d",cycles);
        for(i=0;i<GD;i=i+1) write_gate(1'b0,i,224'h3000+i);
        for(i=0;i<DD;i=i+1) write_down(1'b0,i,224'h4000+i);
        commit(1'b0,32'h22);
        $display("STAGE commit bank0 cycle=%0d",cycles);
        check(!active_bank&&active_generation==32'h22&&bank_valid[0],
            "bank0 atomic commit failed");
        read_gate(4'd15,224'h300f);read_down(3'd0,224'h4000);
        check(gr==2&&dr==2,"read counters mismatch");
        check(!error,"unexpected sticky metadata error");
        $display("PASS hap_mlp_weight_meta_resident_ab checks=%0d",checks);
        $finish;
    end
endmodule
