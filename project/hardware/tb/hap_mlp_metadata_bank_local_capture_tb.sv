`timescale 1ns/1ps

// Integrated resident-bank + central-scheduler contract test for the V5
// bank-local response boundary.  Small memories preserve the production
// ready/valid, A/B-bank and depth-2 scheduler behavior.
module hap_mlp_metadata_bank_local_capture_tb;
    localparam integer G=16,D=8,GAW=4,DAW=3;
    reg clk=1'b0,rst_n=1'b0,clear=1'b0;
    always #5 clk=~clk;

    reg load_begin_valid=1'b0,load_begin_bank=1'b0;
    wire load_begin_ready;
    reg gate_wr_valid=1'b0,gate_wr_bank=1'b0;
    reg [GAW-1:0] gate_wr_addr=0;
    reg [223:0] gate_wr_meta=0;
    wire gate_wr_ready;
    reg down_wr_valid=1'b0,down_wr_bank=1'b0;
    reg [DAW-1:0] down_wr_addr=0;
    reg [223:0] down_wr_meta=0;
    wire down_wr_ready;
    reg commit_valid=1'b0,commit_bank=1'b0;
    reg [31:0] commit_generation=0;
    wire commit_ready,active_bank;
    wire [31:0] active_generation;
    wire [1:0] bank_valid,bank_loading;

    reg command_start=1'b0,command_done=1'b0;
    reg gate_enable=1'b0,down_enable=1'b0;
    wire gate_rd_valid,gate_rd_ready;
    wire [GAW-1:0] gate_rd_addr;
    wire gate_rsp_valid,gate_rsp_ready;
    wire [223:0] gate_rsp_meta;
    wire gate_meta_valid;
    reg gate_meta_ready=1'b0;
    wire [223:0] gate_meta;
    wire down_rd_valid,down_rd_ready;
    wire [DAW-1:0] down_rd_addr;
    wire down_rsp_valid,down_rsp_ready;
    wire [223:0] down_rsp_meta;
    wire down_meta_valid;
    reg down_meta_ready=1'b0;
    wire [223:0] down_meta;
    wire scheduler_active,scheduler_done,scheduler_error;
    wire [31:0] gate_issue_count,gate_delivery_count;
    wire [31:0] down_issue_count,down_delivery_count;
    wire [31:0] gw0,gw1,dw0,dw1,gr,dr;
    wire resident_error;

    integer cycles=0,checks=0,i;
    integer gate_expected=0,down_expected=0;
    integer last_gate_issue=-1,last_down_issue=-1;
    integer gate_ii_pairs=0,down_ii_pairs=0;
    reg check_gate_ii=1'b0,check_down_ii=1'b0;
    reg [223:0] expected_gate_base=0,expected_down_base=0;

    hap_mlp_metadata_scheduler #(
        .GATE_RECORDS(G),.DOWN_RECORDS(D),.GATE_ADDR_W(GAW),
        .DOWN_ADDR_W(DAW),.RESPONSE_FIFO_DEPTH(2),.PRODUCTION_SHAPE(0)
    ) u_sched (
        .clk(clk),.rst_n(rst_n),.clear(clear),
        .command_start(command_start),.command_done(command_done),
        .gate_enable(gate_enable),.down_enable(down_enable),
        .gate_rd_valid(gate_rd_valid),.gate_rd_ready(gate_rd_ready),
        .gate_rd_addr(gate_rd_addr),.gate_rsp_valid(gate_rsp_valid),
        .gate_rsp_ready(gate_rsp_ready),.gate_rsp_meta(gate_rsp_meta),
        .gate_meta_valid(gate_meta_valid),.gate_meta_ready(gate_meta_ready),
        .gate_meta(gate_meta),.down_rd_valid(down_rd_valid),
        .down_rd_ready(down_rd_ready),.down_rd_addr(down_rd_addr),
        .down_rsp_valid(down_rsp_valid),.down_rsp_ready(down_rsp_ready),
        .down_rsp_meta(down_rsp_meta),.down_meta_valid(down_meta_valid),
        .down_meta_ready(down_meta_ready),.down_meta(down_meta),
        .active(scheduler_active),.gate_issue_count(gate_issue_count),
        .gate_delivery_count(gate_delivery_count),
        .down_issue_count(down_issue_count),
        .down_delivery_count(down_delivery_count),
        .done(scheduler_done),.error(scheduler_error)
    );

    hap_mlp_weight_meta_resident_ab #(
        .GATE_DEPTH(G),.DOWN_DEPTH(D),.GATE_ADDR_W(GAW),
        .DOWN_ADDR_W(DAW),.PRODUCTION_SHAPE(0)
    ) u_resident (
        .clk(clk),.rst_n(rst_n),.clear(clear),
        .load_begin_valid(load_begin_valid),
        .load_begin_ready(load_begin_ready),.load_begin_bank(load_begin_bank),
        .gate_wr_valid(gate_wr_valid),.gate_wr_ready(gate_wr_ready),
        .gate_wr_bank(gate_wr_bank),.gate_wr_addr(gate_wr_addr),
        .gate_wr_meta_u224(gate_wr_meta),
        .down_wr_valid(down_wr_valid),.down_wr_ready(down_wr_ready),
        .down_wr_bank(down_wr_bank),.down_wr_addr(down_wr_addr),
        .down_wr_meta_u224(down_wr_meta),
        .commit_valid(commit_valid),.commit_ready(commit_ready),
        .commit_bank(commit_bank),.commit_generation(commit_generation),
        .consumer_quiescent(!scheduler_active),.active_bank(active_bank),
        .active_generation(active_generation),.bank_valid(bank_valid),
        .bank_loading(bank_loading),.gate_rd_valid(gate_rd_valid),
        .gate_rd_ready(gate_rd_ready),.gate_rd_addr(gate_rd_addr),
        .gate_rsp_valid(gate_rsp_valid),.gate_rsp_ready(gate_rsp_ready),
        .gate_rsp_meta_u224(gate_rsp_meta),
        .down_rd_valid(down_rd_valid),.down_rd_ready(down_rd_ready),
        .down_rd_addr(down_rd_addr),.down_rsp_valid(down_rsp_valid),
        .down_rsp_ready(down_rsp_ready),
        .down_rsp_meta_u224(down_rsp_meta),
        .gate_write_count_bank0(gw0),.gate_write_count_bank1(gw1),
        .down_write_count_bank0(dw0),.down_write_count_bank1(dw1),
        .gate_read_count(gr),.down_read_count(dr),.error(resident_error)
    );

    task tick; begin @(posedge clk); #1; end endtask
    task check;
        input condition; input [8*112-1:0] message;
        begin checks=checks+1; if (condition!==1'b1) begin
            $display("FAIL check=%0d cycle=%0d %0s",checks,cycles,message);
            $fatal(1);
        end end
    endtask
    task begin_load;
        input bank;
        begin load_begin_bank=bank;load_begin_valid=1'b1;#0.1;
            while(!load_begin_ready)tick();tick();load_begin_valid=1'b0;end
    endtask
    task write_gate;
        input bank;input[GAW-1:0]addr;input[223:0]value;
        begin gate_wr_bank=bank;gate_wr_addr=addr;gate_wr_meta=value;
            gate_wr_valid=1'b1;#0.1;while(!gate_wr_ready)tick();tick();
            gate_wr_valid=1'b0;end
    endtask
    task write_down;
        input bank;input[DAW-1:0]addr;input[223:0]value;
        begin down_wr_bank=bank;down_wr_addr=addr;down_wr_meta=value;
            down_wr_valid=1'b1;#0.1;while(!down_wr_ready)tick();tick();
            down_wr_valid=1'b0;end
    endtask
    task commit_image;
        input bank;input[31:0]generation;
        begin commit_bank=bank;commit_generation=generation;
            commit_valid=1'b1;#0.1;while(!commit_ready)tick();tick();
            commit_valid=1'b0;end
    endtask
    task load_image;
        input bank;input[223:0]gate_base;input[223:0]down_base;
        begin begin_load(bank);
            for(i=0;i<G;i=i+1)write_gate(bank,i,gate_base+i);
            for(i=0;i<D;i=i+1)write_down(bank,i,down_base+i);
        end
    endtask
    task start_run;
        input [223:0]gate_base;input[223:0]down_base;
        begin expected_gate_base=gate_base;expected_down_base=down_base;
            gate_expected=0;down_expected=0;
            command_start=1'b1;tick();command_start=1'b0;end
    endtask
    task finish_run;
        begin command_done=1'b1;tick();command_done=1'b0;
            check(scheduler_done&&!scheduler_error&&!scheduler_active,
                "scheduler did not finish exact clean command");end
    endtask

    always @(posedge clk) begin
        cycles <= cycles+1;
        if (cycles>5000) begin
            $display("FAIL timeout");$fatal(1);
        end
        if (rst_n&&!clear) begin
            if (gate_rd_valid&&gate_rd_ready) begin
                if (gate_rd_addr!==gate_issue_count[GAW-1:0]) begin
                    $display("FAIL gate issue address/order");$fatal(1);
                end
                if (check_gate_ii&&last_gate_issue>=0) begin
                    if (cycles-last_gate_issue!=1) begin
                        $display("FAIL gate unstalled II gap=%0d",
                            cycles-last_gate_issue);$fatal(1);
                    end
                    gate_ii_pairs <= gate_ii_pairs+1;
                end
                last_gate_issue <= cycles;
            end
            if (down_rd_valid&&down_rd_ready) begin
                if (down_rd_addr!==down_issue_count[DAW-1:0]) begin
                    $display("FAIL down issue address/order");$fatal(1);
                end
                if (check_down_ii&&last_down_issue>=0) begin
                    if (cycles-last_down_issue!=1) begin
                        $display("FAIL down unstalled II gap=%0d",
                            cycles-last_down_issue);$fatal(1);
                    end
                    down_ii_pairs <= down_ii_pairs+1;
                end
                last_down_issue <= cycles;
            end
            if (gate_meta_valid&&gate_meta_ready) begin
                if (gate_meta!==expected_gate_base+gate_expected) begin
                    $display("FAIL gate payload order expected=%h got=%h",
                        expected_gate_base+gate_expected,gate_meta);$fatal(1);
                end
                gate_expected <= gate_expected+1;
            end
            if (down_meta_valid&&down_meta_ready) begin
                if (down_meta!==expected_down_base+down_expected) begin
                    $display("FAIL down payload order expected=%h got=%h",
                        expected_down_base+down_expected,down_meta);$fatal(1);
                end
                down_expected <= down_expected+1;
            end
        end
    end

    integer frozen_issues;
    initial begin
        repeat(4)tick();rst_n=1'b1;tick();
        check(bank_valid==0&&!scheduler_active,"reset state invalid");

        // First run selects physical bank1 and holds the final consumer off
        // long enough to fill both central and bank-local response storage.
        load_image(1'b1,224'h1000,224'h2000);
        commit_image(1'b1,32'h11);
        check(active_bank&&active_generation==32'h11,
            "bank1 did not become active");
        gate_enable=1'b1;down_enable=1'b0;gate_meta_ready=1'b0;
        start_run(224'h1000,224'h2000);
        repeat(20)tick();
        check(gate_issue_count>=5&&gate_issue_count<G,
            "long backpressure did not fill distributed response credits");
        frozen_issues=gate_issue_count;repeat(8)tick();
        check(gate_issue_count==frozen_issues,
            "resident accepted read after all response credits filled");
        gate_meta_ready=1'b1;
        while(gate_delivery_count<G)tick();
        check(gate_expected==G,"bank1 gate response count/order mismatch");

        gate_enable=1'b0;down_enable=1'b1;down_meta_ready=1'b0;
        repeat(16)tick();
        check(down_issue_count>=5&&down_issue_count<D,
            "down long backpressure did not fill response credits");
        frozen_issues=down_issue_count;repeat(8)tick();
        check(down_issue_count==frozen_issues,
            "down read advanced while distributed response storage full");
        down_meta_ready=1'b1;
        while(down_delivery_count<D)tick();
        check(down_expected==D,"bank1 down response count/order mismatch");
        gate_enable=1'b0;down_enable=1'b0;finish_run();

        // Switch to physical bank0 and prove a fully unstalled command issues
        // each path on consecutive cycles (steady-state II=1).
        load_image(1'b0,224'h3000,224'h4000);
        commit_image(1'b0,32'h22);
        check(!active_bank&&active_generation==32'h22,
            "bank0 did not become active");
        gate_meta_ready=1'b1;down_meta_ready=1'b1;
        last_gate_issue=-1;last_down_issue=-1;
        gate_ii_pairs=0;down_ii_pairs=0;
        check_gate_ii=1'b1;check_down_ii=1'b0;
        gate_enable=1'b1;down_enable=1'b0;
        start_run(224'h3000,224'h4000);
        while(gate_delivery_count<G)tick();
        check_gate_ii=1'b0;
        check(gate_ii_pairs==G-1&&gate_expected==G,
            "bank0 gate did not maintain issue II=1 and exact order");
        gate_enable=1'b0;down_enable=1'b1;
        check_down_ii=1'b1;
        while(down_delivery_count<D)tick();
        check_down_ii=1'b0;
        check(down_ii_pairs==D-1&&down_expected==D,
            "bank0 down did not maintain issue II=1 and exact order");
        gate_enable=1'b0;down_enable=1'b0;finish_run();
        check(gr==2*G&&dr==2*D,"resident delivery counters mismatch");
        check(!resident_error,"unexpected resident sticky error");

        // Clear is applied only after the command is quiescent.  Payload bits
        // are resetless but every occupancy/valid control must be invalidated.
        clear=1'b1;tick();clear=1'b0;tick();
        check(bank_valid==0&&!gate_rsp_valid&&!down_rsp_valid,
            "quiescent clear did not invalidate resident response state");
        check(!scheduler_active&&!gate_meta_valid&&!down_meta_valid&&
            gate_issue_count==0&&down_issue_count==0,
            "quiescent clear did not invalidate scheduler state");
        $display("PASS hap_mlp_metadata_bank_local_capture checks=%0d gate_ii_pairs=%0d down_ii_pairs=%0d",
            checks,gate_ii_pairs,down_ii_pairs);
        $finish;
    end
endmodule

