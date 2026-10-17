`timescale 1ns / 1ps

module hap_v4_ddr_mode_controller_tb;
    localparam [1:0] MODE_IDLE=2'd0, MODE_ATTN_ONLY=2'd1,
        MODE_MLP_ONLY=2'd2, MODE_SHARED=2'd3;

    reg core_clk=1'b0;
    reg core_rst_n=1'b0;
    reg mode_request_valid=1'b0;
    reg [1:0] mode_request=MODE_IDLE;
    reg attention_quiescent=1'b1;
    reg mlp_quiescent=1'b1;
    reg paired_leaf_quiescent=1'b1;
    reg paired_leaf_error=1'b0;
    reg maintenance_busy=1'b0;

    wire mode_request_ready;
    wire [1:0] active_mode;
    wire attention_launch_enable,mlp_launch_enable;
    wire core_enable,ddr0_enable,ddr1_enable;
    wire switch_pending,request_done,error;

    integer checks=0;
    integer done_pulses=0;

    always #3.333 core_clk=~core_clk;

    hap_v4_ddr_mode_controller dut (
        .core_clk(core_clk),.core_rst_n(core_rst_n),
        .mode_request_valid(mode_request_valid),
        .mode_request_ready(mode_request_ready),
        .mode_request(mode_request),
        .attention_quiescent(attention_quiescent),
        .mlp_quiescent(mlp_quiescent),
        .paired_leaf_quiescent(paired_leaf_quiescent),
        .paired_leaf_error(paired_leaf_error),
        .maintenance_busy(maintenance_busy),
        .active_mode(active_mode),
        .attention_launch_enable(attention_launch_enable),
        .mlp_launch_enable(mlp_launch_enable),
        .core_enable(core_enable),.ddr0_enable(ddr0_enable),
        .ddr1_enable(ddr1_enable),.switch_pending(switch_pending),
        .request_done(request_done),.error(error)
    );

    always @(posedge core_clk)
        if (core_rst_n && request_done)
            done_pulses <= done_pulses + 1;

    task automatic tick;
        begin @(posedge core_clk); #1; end
    endtask

    task automatic check;
        input condition;
        input [8*112-1:0] message;
        begin
            checks=checks+1;
            if (!condition) begin
                $display("FAIL check=%0d %0s",checks,message);
                $fatal(1);
            end
        end
    endtask

    task automatic send_request;
        input [1:0] target;
        begin
            while (!mode_request_ready) tick();
            @(negedge core_clk);
            mode_request=target;
            mode_request_valid=1'b1;
            #1;
            // A request accepted on the next edge must close launch admission
            // during that same cycle, before pending_r is registered.
            check(!attention_launch_enable && !mlp_launch_enable,
                "request_fire did not close same-cycle launch admission");
            tick();
            @(negedge core_clk);
            mode_request_valid=1'b0;
            #1;
        end
    endtask

    task automatic wait_done;
        integer timeout;
        begin
            timeout=0;
            while (!request_done && timeout<40) begin
                tick();
                timeout=timeout+1;
            end
            check(request_done,"mode request timed out");
        end
    endtask

    initial begin
        repeat (4) tick();
        check(active_mode==MODE_IDLE,"reset active mode was not IDLE");
        check(!mode_request_ready,"request_ready asserted during reset");
        check(!attention_launch_enable && !mlp_launch_enable,
            "reset unexpectedly enabled an engine");
        check(!core_enable && !ddr0_enable && !ddr1_enable,
            "IDLE unexpectedly enabled paired datapath");
        check(!switch_pending && !request_done && !error,
            "reset status outputs were not clear");

        @(negedge core_clk); core_rst_n=1'b1; #1;
        check(mode_request_ready,"request_ready did not assert after reset");

        // IDLE -> ATTN: every quiescence input and maintenance_busy is an
        // independent commit barrier.  IDLE keeps all datapath enables low.
        attention_quiescent=1'b0;
        send_request(MODE_ATTN_ONLY);
        check(switch_pending && active_mode==MODE_IDLE,
            "IDLE-to-ATTN was not queued");
        check(!core_enable && !ddr0_enable && !ddr1_enable,
            "IDLE-to-ATTN enabled datapath before commit");
        check(!mode_request_ready,"pending controller accepted a second request");
        repeat (2) tick();
        check(active_mode==MODE_IDLE && !request_done,
            "ATTN committed before attention quiescent");

        attention_quiescent=1'b1;
        mlp_quiescent=1'b0;
        repeat (2) tick();
        check(active_mode==MODE_IDLE,"ATTN committed before MLP quiescent");

        mlp_quiescent=1'b1;
        paired_leaf_quiescent=1'b0;
        repeat (2) tick();
        check(active_mode==MODE_IDLE,"ATTN committed before paired leaf quiescent");

        paired_leaf_quiescent=1'b1;
        maintenance_busy=1'b1;
        repeat (2) tick();
        check(active_mode==MODE_IDLE,"ATTN committed during maintenance");

        maintenance_busy=1'b0;
        wait_done();
        check(active_mode==MODE_ATTN_ONLY && !switch_pending,
            "IDLE-to-ATTN commit failed");
        check(attention_launch_enable && !mlp_launch_enable,
            "ATTN_ONLY launch decode failed");
        check(core_enable && ddr0_enable && ddr1_enable,
            "ATTN_ONLY did not enable all paired datapath domains");
        tick();
        check(!request_done,"request_done was not a one-cycle pulse");

        // A same-mode request is acknowledged without entering pending.  It
        // still blocks launch on the request handshake edge.
        send_request(MODE_ATTN_ONLY);
        check(request_done && !switch_pending && active_mode==MODE_ATTN_ONLY,
            "same-mode no-op did not complete immediately");
        check(attention_launch_enable,"same-mode launch did not reopen after fire");
        tick();
        check(!request_done,"same-mode request_done was wider than one cycle");

        // ATTN -> SHARED: a pending request blocks both launches but preserves
        // active-mode enables so accepted work can drain.
        attention_quiescent=1'b0;
        send_request(MODE_SHARED);
        check(switch_pending && active_mode==MODE_ATTN_ONLY,
            "ATTN-to-SHARED did not preserve active mode while pending");
        check(!attention_launch_enable && !mlp_launch_enable,
            "pending SHARED request left a launch enabled");
        check(core_enable && ddr0_enable && ddr1_enable,
            "pending SHARED request withdrew drain enables");
        repeat (2) tick();
        check(active_mode==MODE_ATTN_ONLY,"SHARED committed before drain");
        attention_quiescent=1'b1;
        wait_done();
        check(active_mode==MODE_SHARED,"ATTN-to-SHARED commit failed");
        check(attention_launch_enable && mlp_launch_enable,
            "SHARED did not enable both engines");

        // maintenance_busy blocks request acceptance and engine launch, but
        // leaves the already-active datapath enabled for maintenance drain.
        maintenance_busy=1'b1; #1;
        check(!mode_request_ready,"request accepted during maintenance");
        check(!attention_launch_enable && !mlp_launch_enable,
            "maintenance did not block both launches");
        check(core_enable && ddr0_enable && ddr1_enable,
            "maintenance withdrew active datapath enables");
        repeat (2) tick();
        maintenance_busy=1'b0; #1;
        check(mode_request_ready && attention_launch_enable && mlp_launch_enable,
            "controller did not recover after maintenance");

        // SHARED -> MLP still requires both engines and the paired leaf to be
        // quiescent; target-mode quiescence alone is insufficient.
        attention_quiescent=1'b0;
        mlp_quiescent=1'b1;
        paired_leaf_quiescent=1'b1;
        send_request(MODE_MLP_ONLY);
        repeat (2) tick();
        check(active_mode==MODE_SHARED && switch_pending,
            "SHARED-to-MLP ignored attention quiescence");
        attention_quiescent=1'b1;
        wait_done();
        check(active_mode==MODE_MLP_ONLY,"SHARED-to-MLP commit failed");
        check(!attention_launch_enable && mlp_launch_enable,
            "MLP_ONLY launch decode failed");

        // MLP -> IDLE keeps all enables high until the last outstanding leaf
        // state has drained, then withdraws them atomically with active_mode.
        mlp_quiescent=1'b0;
        send_request(MODE_IDLE);
        check(core_enable && ddr0_enable && ddr1_enable,
            "MLP-to-IDLE withdrew enables before quiescence");
        repeat (2) tick();
        check(active_mode==MODE_MLP_ONLY,"IDLE committed while MLP busy");
        mlp_quiescent=1'b1;
        wait_done();
        check(active_mode==MODE_IDLE && !switch_pending,
            "MLP-to-IDLE commit failed");
        check(!core_enable && !ddr0_enable && !ddr1_enable,
            "IDLE did not withdraw all datapath enables");
        check(!attention_launch_enable && !mlp_launch_enable,
            "IDLE left an engine launch enabled");

        // Re-enter SHARED and inject an error while a later switch is pending.
        // The error must immediately block launch/ready, remain sticky after
        // the source deasserts, and prevent the pending mode from committing.
        send_request(MODE_SHARED);
        wait_done();
        check(active_mode==MODE_SHARED && attention_launch_enable &&
            mlp_launch_enable,"second SHARED entry failed");
        attention_quiescent=1'b0;
        send_request(MODE_ATTN_ONLY);
        paired_leaf_error=1'b1; #1;
        check(error,"paired leaf error was not reported immediately");
        check(!mode_request_ready && !attention_launch_enable &&
            !mlp_launch_enable,"error did not freeze request/launch admission");
        check(core_enable && ddr0_enable && ddr1_enable,
            "error unexpectedly changed active datapath mode");
        tick();
        paired_leaf_error=1'b0;
        attention_quiescent=1'b1;
        repeat (3) tick();
        check(error,"paired leaf error did not remain sticky");
        check(switch_pending && active_mode==MODE_SHARED && !request_done,
            "pending request committed after a fatal error");

        // Hard reset is the only error recovery and always returns to IDLE.
        @(negedge core_clk); core_rst_n=1'b0; #1;
        check(active_mode==MODE_IDLE && !switch_pending && !error,
            "hard reset did not clear mode/error state");
        check(!mode_request_ready && !core_enable && !ddr0_enable &&
            !ddr1_enable,"reset output gating failed after error");
        repeat (2) tick();
        @(negedge core_clk); core_rst_n=1'b1; #1;
        check(mode_request_ready && active_mode==MODE_IDLE,
            "controller did not recover from hard reset");

        check(done_pulses==6,"unexpected request_done pulse count");
        $display("PASS hap_v4_ddr_mode_controller checks=%0d done_pulses=%0d",
            checks,done_pulses);
        $finish;
    end
endmodule
