`timescale 1ns / 1ps

// Directed protocol test for the branch-local completed-down queue.  It fills
// both entries under sink stall, proves stable tile/payload, then releases the
// sink while a third item is pending.  The two stored items cover the queue's
// intentionally registered full-credit recovery, so the output remains II=1.
// A second full/stalled epoch is discarded by clear before fresh traffic.
module hap_mlp_down_branch_elastic2_s24_tb;
    localparam integer ROWS = 8;
    localparam integer COLS = 12;
    localparam integer TILE_W = 5;
    localparam integer PAYLOAD_W = ROWS*COLS*24;

    reg clk = 1'b0;
    always #3.333 clk = ~clk;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    reg in_valid = 1'b0;
    wire in_ready;
    reg [TILE_W-1:0] in_tile = '0;
    reg signed [PAYLOAD_W-1:0] in_projection_s24 = '0;
    wire out_valid;
    reg out_ready = 1'b0;
    wire [TILE_W-1:0] out_tile;
    wire signed [PAYLOAD_W-1:0] out_projection_s24;

    hap_mlp_down_branch_elastic2_s24 #(
        .ROWS(ROWS), .COLS(COLS), .TILE_W(TILE_W)
    ) dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready), .in_tile(in_tile),
        .in_projection_s24(in_projection_s24),
        .out_valid(out_valid), .out_ready(out_ready), .out_tile(out_tile),
        .out_projection_s24(out_projection_s24)
    );

    function automatic [PAYLOAD_W-1:0] make_payload;
        input integer item;
        integer lane;
        begin
            make_payload = '0;
            for (lane = 0; lane < ROWS*COLS; lane = lane + 1)
                make_payload[lane*24 +: 24] =
                    ((item+1)*24'h010101) ^ (lane*24'h000103);
        end
    endfunction

    reg [TILE_W-1:0] expected_tile [0:31];
    reg [PAYLOAD_W-1:0] expected_payload [0:31];
    integer expected_write_count = 0;
    integer expected_read_count = 0;
    integer cycle_count = 0;
    integer last_output_cycle = -1;
    integer contiguous_output_checks = 0;
    reg require_contiguous_output = 1'b0;
    reg stalled_previous = 1'b0;
    reg [TILE_W-1:0] stalled_tile;
    reg [PAYLOAD_W-1:0] stalled_payload;
    integer stability_checks = 0;

    task automatic send_item;
        input integer item;
        reg accepted;
        begin
            @(negedge clk);
            in_tile = item[TILE_W-1:0];
            in_projection_s24 = make_payload(item);
            in_valid = 1'b1;
            accepted = 1'b0;
            while (!accepted) begin
                @(posedge clk);
                if (in_ready)
                    accepted = 1'b1;
            end
            @(negedge clk);
            in_valid = 1'b0;
        end
    endtask

    task automatic send_burst;
        input integer first_item;
        input integer item_count;
        integer sent;
        begin
            sent = 0;
            @(negedge clk);
            in_tile = first_item[TILE_W-1:0];
            in_projection_s24 = make_payload(first_item);
            in_valid = 1'b1;
            while (sent < item_count) begin
                @(posedge clk);
                if (in_ready) begin
                    sent = sent + 1;
                    if (sent < item_count) begin
                        @(negedge clk);
                        in_tile = (first_item+sent);
                        in_projection_s24 = make_payload(first_item+sent);
                    end
                end
            end
            @(negedge clk);
            in_valid = 1'b0;
        end
    endtask

    always @(posedge clk) begin
        if (!rst_n || clear) begin
            expected_write_count <= 0;
            expected_read_count <= 0;
            last_output_cycle <= -1;
            stalled_previous <= 1'b0;
        end else begin
            cycle_count <= cycle_count + 1;
            if (in_valid && in_ready) begin
                expected_tile[expected_write_count] <= in_tile;
                expected_payload[expected_write_count] <=
                    in_projection_s24;
                expected_write_count <= expected_write_count + 1;
            end

            if (out_valid && !out_ready) begin
                if (stalled_previous) begin
                    if (out_tile !== stalled_tile ||
                        out_projection_s24 !== stalled_payload)
                        $fatal(1, "FAIL down queue output changed under stall");
                    stability_checks <= stability_checks + 1;
                end
                stalled_previous <= 1'b1;
                stalled_tile <= out_tile;
                stalled_payload <= out_projection_s24;
            end else begin
                stalled_previous <= 1'b0;
            end

            if (out_valid && out_ready) begin
                if (expected_read_count >= expected_write_count)
                    $fatal(1, "FAIL down queue emitted unaccepted item");
                if (out_tile !== expected_tile[expected_read_count] ||
                    out_projection_s24 !==
                        expected_payload[expected_read_count])
                    $fatal(1,
                        "FAIL down queue mismatch output=%0d tile=%0d expected=%0d",
                        expected_read_count, out_tile,
                        expected_tile[expected_read_count]);
                if (require_contiguous_output && last_output_cycle >= 0) begin
                    if (cycle_count-last_output_cycle != 1)
                        $fatal(1,
                            "FAIL down queue drain II=%0d at output=%0d",
                            cycle_count-last_output_cycle,
                            expected_read_count);
                    contiguous_output_checks <=
                        contiguous_output_checks + 1;
                end
                last_output_cycle <= cycle_count;
                expected_read_count <= expected_read_count + 1;
            end

            if (expected_write_count > 32 ||
                expected_read_count > expected_write_count)
                $fatal(1, "FAIL down queue scoreboard ordering");
        end
    end

    integer wait_cycles;
    initial begin
        repeat (5) @(posedge clk);
        rst_n <= 1'b1;

        // Epoch 0: two resident entries, a pending third source and a long
        // sink stall.  Release must produce all six items on adjacent cycles.
        out_ready = 1'b0;
        send_item(0);
        send_item(1);
        if (in_ready !== 1'b0 || out_valid !== 1'b1)
            $fatal(1, "FAIL down queue did not reach full/valid state");
        fork
            begin
                send_burst(2, 4);
            end
            begin
                repeat (7) @(posedge clk);
                if (in_ready !== 1'b0)
                    $fatal(1, "FAIL full down queue exposed upstream credit");
                @(negedge clk);
                require_contiguous_output = 1'b1;
                out_ready = 1'b1;
            end
        join

        wait_cycles = 0;
        while (expected_read_count != 6 && wait_cycles < 30) begin
            @(posedge clk);
            wait_cycles = wait_cycles + 1;
        end
        if (expected_read_count != 6 || expected_write_count != 6 ||
            contiguous_output_checks != 5 || stability_checks == 0)
            $fatal(1,
                "FAIL down queue epoch0 counts=%0d/%0d contiguous=%0d stable=%0d",
                expected_write_count, expected_read_count,
                contiguous_output_checks, stability_checks);

        // Epoch 1: clear while a full queue is visibly stalled.  Both stored
        // items must disappear; no stale tile/payload may escape afterward.
        @(negedge clk);
        require_contiguous_output = 1'b0;
        out_ready = 1'b0;
        send_item(10);
        send_item(11);
        repeat (3) @(posedge clk);
        if (!out_valid || in_ready)
            $fatal(1, "FAIL clear setup did not hold a full queue");
        @(negedge clk);
        clear = 1'b1;
        repeat (2) @(posedge clk);
        if (out_valid || in_ready)
            $fatal(1, "FAIL down queue boundary open during clear");
        @(negedge clk);
        clear = 1'b0;
        @(posedge clk);
        if (out_valid || !in_ready)
            $fatal(1, "FAIL down queue did not return empty after clear");

        // Fresh traffic after clear proves that no pre-clear queue entry is
        // observed and that row/tile pointers restart coherently.
        @(negedge clk);
        out_ready = 1'b1;
        fork
            begin
                send_burst(20, 4);
            end
        join
        wait_cycles = 0;
        while (expected_read_count != 4 && wait_cycles < 20) begin
            @(posedge clk);
            wait_cycles = wait_cycles + 1;
        end
        if (expected_write_count != 4 || expected_read_count != 4)
            $fatal(1, "FAIL down queue post-clear counts=%0d/%0d",
                expected_write_count, expected_read_count);

        $display(
            "PASS: V5 branch-local down elastic2 full-stall stable, release II=1, tile/payload ordered and clear-mid-stall discarded stale entries");
        $finish;
    end

endmodule
