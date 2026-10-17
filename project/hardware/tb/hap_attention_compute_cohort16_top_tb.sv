`timescale 1ns / 1ps

module hap_attention_compute_cohort16_top_tb;
    reg clk = 1'b0;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    reg start = 1'b0;
    reg [31:0] format_id = 32'h4838_4103;
    reg [31:0] request_id = 32'h1020_3040;
    reg [15:0] cohort_id = 16'h1234;
    reg [5:0] layer_id = 6'd17;
    reg [6:0] query_start = 7'd0;
    reg [7:0] query_count = 8'd16;
    reg [7:0] valid_key_count = 8'd16;
    wire busy;
    wire done;
    wire error;

    reg rope_wr_valid = 1'b0;
    wire rope_wr_ready;
    reg [9:0] rope_wr_addr = 10'd0;
    reg signed [17:0] rope_wr_cos_s18 = 18'sd0;
    reg signed [17:0] rope_wr_sin_s18 = 18'sd0;
    reg activation_valid = 1'b0;
    wire activation_ready;
    reg activation_wave = 1'b0;
    reg [6:0] activation_group = 7'd0;
    reg [8*32*24-1:0] activation_s24 = '0;
    reg weight_valid = 1'b0;
    wire weight_ready;
    reg [9:0] weight_tile = 10'd0;
    reg [6:0] weight_group = 7'd0;
    reg [16*32*8-1:0] weight_s8 = '0;
    reg [16*16-1:0] weight_meta16 = '0;
    wire out_valid;
    reg out_ready = 1'b0;
    wire out_wave;
    wire [7:0] out_tile;
    wire [8*16*24-1:0] out_s24;

    wire [31:0] cycle_count;
    wire [31:0] accepted_weight_group_count;
    wire [31:0] consumed_wave_group_count;
    wire [31:0] released_weight_group_count;
    wire [31:0] completed_projection_wave_tile_count;
    wire [31:0] completed_projection_tile_count;
    wire [31:0] completed_attention_row_count;
    wire [31:0] completed_wo_tile_count;
    wire [31:0] input_frontend_cycle_count;
    wire [31:0] qkv_projection_cycle_count;
    wire [31:0] rope_cycle_count;
    wire [31:0] kv12_cycle_count;
    wire [31:0] attention_cycle_count;
    wire [31:0] context_frontend_cycle_count;
    wire [31:0] wo_projection_cycle_count;
    wire [31:0] control_overhead_cycle_count;

    integer sim_cycle = 0;
    integer checks = 0;
    integer rope_index;
    integer wave;
    integer group;
    integer tile;

    hap_attention_compute_cohort16_top #(
        .USE_PROJECTION_STUB(1)
    ) dut (
        .clk(clk), .rst_n(rst_n), .clear(clear), .start(start),
        .format_id(format_id), .request_id(request_id),
        .cohort_id(cohort_id), .layer_id(layer_id),
        .query_start(query_start), .query_count(query_count),
        .valid_key_count(valid_key_count), .busy(busy), .done(done),
        .error(error), .rope_wr_valid(rope_wr_valid),
        .rope_wr_ready(rope_wr_ready), .rope_wr_addr(rope_wr_addr),
        .rope_wr_cos_s18(rope_wr_cos_s18),
        .rope_wr_sin_s18(rope_wr_sin_s18),
        .kv_preload_valid(1'b0), .kv_preload_ready(),
        .kv_preload_is_v(1'b0), .kv_preload_addr(12'd0),
        .kv_preload_s12(384'd0), .kv_preload_meta16(16'd0),
        .activation_valid(activation_valid),
        .activation_ready(activation_ready),
        .activation_wave(activation_wave),
        .activation_group(activation_group),
        .activation_s24(activation_s24), .weight_valid(weight_valid),
        .weight_ready(weight_ready), .weight_tile(weight_tile),
        .weight_group(weight_group), .weight_s8(weight_s8),
        .weight_meta16(weight_meta16), .out_valid(out_valid),
        .out_ready(out_ready), .out_wave(out_wave), .out_tile(out_tile),
        .out_s24(out_s24), .cycle_count(cycle_count),
        .accepted_weight_group_count(accepted_weight_group_count),
        .consumed_wave_group_count(consumed_wave_group_count),
        .released_weight_group_count(released_weight_group_count),
        .completed_projection_wave_tile_count(
            completed_projection_wave_tile_count),
        .completed_projection_tile_count(completed_projection_tile_count),
        .completed_attention_row_count(completed_attention_row_count),
        .completed_wo_tile_count(completed_wo_tile_count),
        .input_frontend_cycle_count(input_frontend_cycle_count),
        .qkv_projection_cycle_count(qkv_projection_cycle_count),
        .rope_cycle_count(rope_cycle_count),
        .kv12_cycle_count(kv12_cycle_count),
        .attention_cycle_count(attention_cycle_count),
        .context_frontend_cycle_count(context_frontend_cycle_count),
        .wo_projection_cycle_count(wo_projection_cycle_count),
        .control_overhead_cycle_count(control_overhead_cycle_count)
    );

    always #3.333 clk = ~clk;
    always @(posedge clk)
        sim_cycle <= sim_cycle + 1;

    task automatic fail;
        input [8*200-1:0] reason;
        begin
            $display("FAIL: %0s at cycle %0d state=%0d tile=%0d",
                reason, sim_cycle, dut.state_r, dut.projection_tile_r);
            $display("top_control=%0b projection=%0b rope=%0b quant=%0b cache=%0b row=%0b stub_state=%0d stub_control=%0b act_valid=%0b act_ready=%0b act_wave=%0b act_group=%0d expected_wave=%0b expected_group=%0d",
                dut.control_error_r, dut.projection_error, dut.rope_error,
                dut.kv_quant_error, dut.cache_error, dut.row_error,
                dut.g_projection_stub.u_projection.state_r,
                dut.g_projection_stub.u_projection.control_error_r,
                activation_valid, activation_ready, activation_wave,
                activation_group, dut.expected_activation_wave_r,
                dut.expected_activation_group_r);
            $finish;
        end
    endtask

    task automatic load_rope;
        integer timeout;
        begin
            for (rope_index=0; rope_index<1024; rope_index=rope_index+1) begin
                timeout = 0;
                while (!rope_wr_ready) begin
                    @(posedge clk);
                    timeout = timeout + 1;
                    if (timeout > 5)
                        fail("RoPE write-ready timeout");
                end
                @(negedge clk);
                rope_wr_addr = rope_index[9:0];
                rope_wr_cos_s18 = 18'sd0;
                rope_wr_sin_s18 = 18'sd0;
                rope_wr_valid = 1'b1;
                @(posedge clk);
                if (!rope_wr_ready)
                    fail("RoPE ready dropped on handshake");
                @(negedge clk);
                rope_wr_valid = 1'b0;
            end
        end
    endtask

    task automatic feed_activations;
        integer timeout;
        integer local_wave;
        integer local_group;
        begin
            for (local_wave=0; local_wave<2;
                    local_wave=local_wave+1) begin
                for (local_group=0; local_group<128;
                        local_group=local_group+1) begin
                    @(negedge clk);
                    activation_wave = local_wave[0];
                    activation_group = local_group[6:0];
                    activation_s24 = '0;
                    activation_valid = 1'b1;
                    timeout = 0;
                    #1;
                    while (!activation_ready) begin
                        @(negedge clk);
                        #1;
                        timeout = timeout + 1;
                        if (timeout > 10)
                            fail("activation-ready timeout");
                    end
                    @(posedge clk);
                    @(negedge clk);
                    activation_valid = 1'b0;
                    @(posedge clk);
                    checks = checks + 1;
                end
            end
        end
    endtask

    task automatic feed_weights;
        integer timeout;
        integer local_tile;
        integer local_group;
        begin
            for (local_tile=0; local_tile<640;
                    local_tile=local_tile+1) begin
                for (local_group=0; local_group<128;
                        local_group=local_group+1) begin
                    @(negedge clk);
                    weight_tile = local_tile[9:0];
                    weight_group = local_group[6:0];
                    weight_s8 = '0;
                    weight_meta16 = '0;
                    weight_valid = 1'b1;
                    timeout = 0;
                    #1;
                    while (!weight_ready) begin
                        @(negedge clk);
                        #1;
                        timeout = timeout + 1;
                        if (timeout > 2000000)
                            fail("weight-ready timeout");
                    end
                    @(posedge clk);
                    @(negedge clk);
                    weight_valid = 1'b0;
                    @(posedge clk);
                    checks = checks + 1;
                end
            end
        end
    endtask

    task automatic consume_outputs;
        integer timeout;
        integer stall;
        integer local_tile;
        integer local_wave;
        reg [8*16*24-1:0] held_data;
        begin
            for (local_tile=0; local_tile<256;
                    local_tile=local_tile+1) begin
                for (local_wave=0; local_wave<2;
                        local_wave=local_wave+1) begin
                    timeout = 0;
                    while (!out_valid) begin
                        @(posedge clk);
                        timeout = timeout + 1;
                        if (timeout > 3000000)
                            fail("Wo output-valid timeout");
                    end
                    if (out_tile !== local_tile[7:0] ||
                            out_wave !== local_wave[0])
                        fail("Wo tile/wave sequence mismatch");
                    if (out_s24 !== '0)
                        fail("stubbed zero projection produced nonzero Wo");
                    held_data = out_s24;
                    stall = (local_tile + local_wave) % 4;
                    repeat (stall) begin
                        @(posedge clk);
                        if (!out_valid ||
                                out_tile !== local_tile[7:0] ||
                                out_wave !== local_wave[0] ||
                                out_s24 !== held_data)
                            fail("Wo output changed under backpressure");
                    end
                    @(negedge clk);
                    out_ready = 1'b1;
                    @(posedge clk);
                    @(negedge clk);
                    out_ready = 1'b0;
                    checks = checks + 1;
                end
            end
        end
    endtask

    always @(posedge clk) begin
        if (rst_n && error)
            fail("compute top asserted error");
    end

    initial begin
        repeat (6) @(posedge clk);
        @(negedge clk);
        rst_n = 1'b1;
        load_rope();

        @(negedge clk);
        start = 1'b1;
        @(posedge clk);
        @(negedge clk);
        start = 1'b0;
        // Mutate command inputs after acceptance. All projection descriptors
        // must continue to use the atomically captured command identity.
        request_id = 32'hdead_beef;
        cohort_id = 16'hffff;
        layer_id = 6'd31;
        query_start = 7'd112;
        valid_key_count = 8'd128;

        fork
            feed_activations();
            feed_weights();
            consume_outputs();
        join

        while (!done)
            @(posedge clk);
        if (busy || error)
            fail("done did not retire to clean idle");
        if (accepted_weight_group_count != 32'd81920)
            fail("accepted W8 group count mismatch");
        if (consumed_wave_group_count != 32'd163840)
            fail("wave-group consumption count mismatch");
        if (released_weight_group_count != 32'd81920)
            fail("released W8 group count mismatch");
        if (completed_projection_wave_tile_count != 32'd1280)
            fail("projection wave-output count mismatch");
        if (completed_projection_tile_count != 32'd640)
            fail("logical projection tile count mismatch");
        if (completed_attention_row_count != 32'd512)
            fail("Attention row-head count mismatch");
        if (completed_wo_tile_count != 32'd256)
            fail("logical Wo tile count mismatch");
        checks = checks + 7;

        $display("PASS: hap_attention_compute_cohort16_top %0d checks; weights=81920 wave_groups=163840 logical_tiles=640 wave_tiles=1280 attention_rows=512 wo_outputs=512 cycles=%0d",
            checks, cycle_count);
        $finish;
    end

    initial begin
        #100000000;
        fail("global timeout");
    end
endmodule
