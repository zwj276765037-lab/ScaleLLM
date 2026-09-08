`timescale 1ns / 1ps

module hap_ddr_read_owner_guard_tb;
    localparam [1:0] OWNER_IDLE=2'd0, OWNER_ATTN=2'd1, OWNER_MLP=2'd2;
    reg core_clk=1'b0,ddr0_clk=1'b0,ddr1_clk=1'b0;
    reg core_rst_n=1'b0,ddr0_rst_n=1'b0,ddr1_rst_n=1'b0;
    reg core_clear=1'b0,ddr0_clear=1'b0,ddr1_clear=1'b0;
    reg request_valid=1'b0;
    wire request_ready;
    reg [1:0] request_owner=OWNER_IDLE;
    wire request_done;
    reg attention_quiescent=1'b1,mlp_quiescent=1'b1;
    reg ddr0_ar_fire=1'b0,ddr0_rlast_fire=1'b0;
    reg ddr1_ar_fire=1'b0,ddr1_rlast_fire=1'b0;
    wire [1:0] active_owner,ddr0_active_owner,ddr1_active_owner;
    wire attention_launch_enable,mlp_launch_enable,switch_pending;
    wire [3:0] ddr0_outstanding,ddr1_outstanding;
    wire protocol_error;
    integer checks=0;

    always #3.333 core_clk=~core_clk;
    always #1.667 ddr0_clk=~ddr0_clk;
    always #1.543 ddr1_clk=~ddr1_clk;

    hap_ddr_read_owner_guard #(.OUTSTANDING_W(4)) dut (
        .core_clk(core_clk),.core_rst_n(core_rst_n),.core_clear(core_clear),
        .request_valid(request_valid),.request_ready(request_ready),
        .request_owner(request_owner),.request_done(request_done),
        .attention_quiescent(attention_quiescent),
        .mlp_quiescent(mlp_quiescent),
        .ddr0_clk(ddr0_clk),.ddr0_rst_n(ddr0_rst_n),.ddr0_clear(ddr0_clear),
        .ddr0_ar_fire(ddr0_ar_fire),.ddr0_rlast_fire(ddr0_rlast_fire),
        .ddr0_active_owner(ddr0_active_owner),
        .ddr0_outstanding(ddr0_outstanding),
        .ddr1_clk(ddr1_clk),.ddr1_rst_n(ddr1_rst_n),.ddr1_clear(ddr1_clear),
        .ddr1_ar_fire(ddr1_ar_fire),.ddr1_rlast_fire(ddr1_rlast_fire),
        .ddr1_active_owner(ddr1_active_owner),
        .ddr1_outstanding(ddr1_outstanding),
        .active_owner(active_owner),
        .attention_launch_enable(attention_launch_enable),
        .mlp_launch_enable(mlp_launch_enable),
        .switch_pending(switch_pending),.protocol_error(protocol_error)
    );

    task automatic core_tick; begin @(posedge core_clk); #1; end endtask
    task automatic ddr0_tick; begin @(posedge ddr0_clk); #0.2; end endtask
    task automatic ddr1_tick; begin @(posedge ddr1_clk); #0.2; end endtask

    task automatic check;
        input condition;
        input [8*96-1:0] message;
        begin
            checks=checks+1;
            if (!condition) begin
                $display("FAIL check=%0d %0s",checks,message);
                $fatal(1);
            end
        end
    endtask

    task automatic request;
        input [1:0] owner;
        begin
            while (!request_ready) core_tick();
            request_owner=owner;
            request_valid=1'b1;
            core_tick();
            request_valid=1'b0;
        end
    endtask

    task automatic wait_done;
        integer timeout;
        begin
            timeout=0;
            while (!request_done && timeout<100) begin
                core_tick();
                timeout=timeout+1;
            end
            check(request_done,"owner request timed out");
        end
    endtask

    task automatic ddr0_ar; begin
        @(negedge ddr0_clk); ddr0_ar_fire=1'b1;
        ddr0_tick();
        @(negedge ddr0_clk); ddr0_ar_fire=1'b0;
    end endtask
    task automatic ddr1_ar; begin
        @(negedge ddr1_clk); ddr1_ar_fire=1'b1;
        ddr1_tick();
        @(negedge ddr1_clk); ddr1_ar_fire=1'b0;
    end endtask
    task automatic ddr0_rlast; begin
        @(negedge ddr0_clk); ddr0_rlast_fire=1'b1;
        ddr0_tick();
        @(negedge ddr0_clk); ddr0_rlast_fire=1'b0;
    end endtask
    task automatic ddr1_rlast; begin
        @(negedge ddr1_clk); ddr1_rlast_fire=1'b1;
        ddr1_tick();
        @(negedge ddr1_clk); ddr1_rlast_fire=1'b0;
    end endtask

    initial begin
        repeat (5) core_tick();
        core_rst_n=1'b1; ddr0_rst_n=1'b1; ddr1_rst_n=1'b1;
        repeat (3) core_tick();
        check(active_owner==OWNER_IDLE && ddr0_active_owner==OWNER_IDLE &&
            ddr1_active_owner==OWNER_IDLE,"reset owners must be IDLE");

        request(OWNER_ATTN);
        check(switch_pending && !attention_launch_enable,
            "target launch was enabled before both DDR acknowledgements");
        wait_done();
        check(active_owner==OWNER_ATTN && ddr0_active_owner==OWNER_ATTN &&
            ddr1_active_owner==OWNER_ATTN,"IDLE-to-ATTN did not update all domains");
        core_tick();
        check(attention_launch_enable,"ATTN launch not enabled after dual ack");

        attention_quiescent=1'b0;
        fork ddr0_ar(); ddr1_ar(); join
        fork ddr0_ar(); join
        check(ddr0_outstanding==2 && ddr1_outstanding==1,
            "local outstanding counters missed AR handshakes");

        request(OWNER_MLP);
        check(switch_pending && active_owner==OWNER_ATTN,
            "owner changed while ATTN was active");
        check(!attention_launch_enable && !mlp_launch_enable,
            "pending request must block all new command launches");

        // Existing ATTN work may still issue after the request was queued.
        ddr0_ar();
        check(ddr0_outstanding==3,"draining owner AR was not counted");
        repeat (4) core_tick();
        check(ddr0_active_owner==OWNER_ATTN && ddr1_active_owner==OWNER_ATTN,
            "CDC switch started before core quiescent");

        attention_quiescent=1'b1;
        fork ddr0_rlast(); ddr1_rlast(); join
        ddr0_rlast();
        repeat (5) core_tick();
        check(ddr0_active_owner==OWNER_ATTN,
            "DDR0 owner changed with one burst still outstanding");
        check(ddr1_active_owner==OWNER_MLP,
            "drained DDR1 channel did not independently acknowledge MLP");
        check(active_owner==OWNER_ATTN && !mlp_launch_enable,
            "core owner advanced before both DDR channels acknowledged");

        ddr0_rlast();
        wait_done();
        check(active_owner==OWNER_MLP && ddr0_active_owner==OWNER_MLP &&
            ddr1_active_owner==OWNER_MLP,"ATTN-to-MLP dual-domain switch failed");
        core_tick();
        check(mlp_launch_enable,"MLP launch not enabled after dual ack");

        request(OWNER_MLP);
        check(request_done && active_owner==OWNER_MLP,
            "same-owner request must acknowledge as a no-op");
        core_tick();

        request(OWNER_IDLE);
        wait_done();
        check(active_owner==OWNER_IDLE && ddr0_active_owner==OWNER_IDLE &&
            ddr1_active_owner==OWNER_IDLE,"MLP-to-IDLE dual-domain switch failed");
        core_tick();

        // Local response underflow crosses back as a sticky core error.
        ddr1_rlast();
        repeat (5) core_tick();
        check(protocol_error,"DDR-domain RLAST underflow did not cross to core");
        core_clear=1'b1; ddr0_clear=1'b1; ddr1_clear=1'b1;
        repeat (2) core_tick();
        core_clear=1'b0; ddr0_clear=1'b0; ddr1_clear=1'b0;
        repeat (5) core_tick();
        check(!protocol_error && active_owner==OWNER_IDLE,
            "safe three-domain clear did not reset guard");

        $display("PASS hap_ddr_read_owner_guard CDC checks=%0d",checks);
        $finish;
    end
endmodule
