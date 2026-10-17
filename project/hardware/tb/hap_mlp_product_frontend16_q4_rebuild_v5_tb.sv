`timescale 1ns / 1ps

module hap_mlp_product_frontend16_q4_rebuild_v5_tb;
    localparam integer GROUPS = 4;
    reg clk = 1'b0;
    always #5 clk = ~clk;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    wire in_valid, in_ready, out_valid;
    reg out_ready = 1'b1;
    wire signed [16383:0] product_s32x16x32;
    wire [4095:0] activation_u8x16x32;
    wire [383:0] activation_meta_u24x16;
    wire [31:0] input_group_count, output_group_count, busy_cycle_count;
    wire error;
    reg [16383:0] product_mem [0:GROUPS-1];
    reg [4095:0] expected_u8_mem [0:GROUPS-1];
    reg [383:0] expected_meta_mem [0:GROUPS-1];
    integer send_index = 0;
    integer receive_index = 0;
    integer cycle_count = 0;
    integer mismatch_count = 0;
    integer q_byte_checks = 0;
    integer meta_word_checks = 0;
    integer group_start_cycle [0:GROUPS-1];
    integer observed_cycles = 0;
    integer max_group_cycles = 0;
    integer loaded_index;
    reg held_pending = 1'b0;
    reg [4095:0] held_u8;
    reg [383:0] held_meta;
    wire [1:0] source_index = send_index < GROUPS ? send_index : GROUPS-1;

    assign in_valid = send_index < GROUPS;
    assign product_s32x16x32 = product_mem[source_index];
    hap_mlp_product_frontend16_q4 dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready),
        .product_s32x16x32(product_s32x16x32),
        .out_valid(out_valid), .out_ready(out_ready),
        .activation_u8x16x32(activation_u8x16x32),
        .activation_meta_u24x16(activation_meta_u24x16),
        .input_group_count(input_group_count), .output_group_count(output_group_count),
        .busy_cycle_count(busy_cycle_count), .error(error)
    );

    task automatic compare_group(input integer group_index);
        integer row_index, lane_index;
        reg [7:0] actual_q, expected_q;
        reg [23:0] actual_meta, expected_meta;
        begin
            for (row_index = 0; row_index < 16; row_index = row_index + 1) begin
                actual_meta = activation_meta_u24x16[row_index*24 +: 24];
                expected_meta = expected_meta_mem[group_index][row_index*24 +: 24];
                if (actual_meta !== expected_meta || $isunknown(actual_meta)) begin
                    $display("MISMATCH kind=meta group=%0d row=%0d lane=-1 expected_meta=%06h actual_meta=%06h unknown=%0d cycles=%0d group_cycles=%0d q_checked=%0d meta_checked=%0d",
                        group_index, row_index, expected_meta, actual_meta,
                        $isunknown(actual_meta), cycle_count, observed_cycles,
                        q_byte_checks, meta_word_checks);
                    mismatch_count = mismatch_count + 1;
                    $fatal(1, "FAIL: V5 Product metadata");
                end
                meta_word_checks = meta_word_checks + 1;
                for (lane_index = 0; lane_index < 32; lane_index = lane_index + 1) begin
                    actual_q = activation_u8x16x32[(row_index*32+lane_index)*8 +: 8];
                    expected_q = expected_u8_mem[group_index][(row_index*32+lane_index)*8 +: 8];
                    if (actual_q !== expected_q || $isunknown(actual_q)) begin
                        $display("MISMATCH kind=q group=%0d row=%0d lane=%0d byte_offset=%0d expected_byte=%02h actual_byte=%02h expected_meta=%06h actual_meta=%06h unknown=%0d cycles=%0d group_cycles=%0d q_checked=%0d meta_checked=%0d",
                            group_index, row_index, lane_index,
                            group_index*512+row_index*32+lane_index, expected_q,
                            actual_q, expected_meta, actual_meta, $isunknown(actual_q),
                            cycle_count, observed_cycles, q_byte_checks, meta_word_checks);
                        mismatch_count = mismatch_count + 1;
                        $fatal(1, "FAIL: V5 Product q byte");
                    end
                    q_byte_checks = q_byte_checks + 1;
                end
            end
        end
    endtask

    task automatic compare_held(input integer group_index);
        integer row_index, lane_index;
        reg [7:0] actual_q, previous_q;
        reg [23:0] actual_meta, previous_meta;
        begin
            for (row_index = 0; row_index < 16; row_index = row_index + 1) begin
                actual_meta = activation_meta_u24x16[row_index*24 +: 24];
                previous_meta = held_meta[row_index*24 +: 24];
                if (actual_meta !== previous_meta) begin
                    $display("MISMATCH kind=held_meta group=%0d row=%0d lane=-1 expected_meta=%06h actual_meta=%06h unknown=%0d cycles=%0d",
                        group_index, row_index, previous_meta, actual_meta,
                        $isunknown(actual_meta), cycle_count);
                    $fatal(1, "FAIL: held metadata changed");
                end
                for (lane_index = 0; lane_index < 32; lane_index = lane_index + 1) begin
                    actual_q = activation_u8x16x32[(row_index*32+lane_index)*8 +: 8];
                    previous_q = held_u8[(row_index*32+lane_index)*8 +: 8];
                    if (actual_q !== previous_q) begin
                        $display("MISMATCH kind=held_q group=%0d row=%0d lane=%0d byte_offset=%0d expected_byte=%02h actual_byte=%02h expected_meta=%06h actual_meta=%06h unknown=%0d cycles=%0d",
                            group_index, row_index, lane_index,
                            group_index*512+row_index*32+lane_index, previous_q,
                            actual_q, previous_meta, actual_meta,
                            $isunknown(actual_q), cycle_count);
                        $fatal(1, "FAIL: held q byte changed");
                    end
                end
            end
        end
    endtask


    initial begin
        for (loaded_index = 0; loaded_index < GROUPS; loaded_index = loaded_index + 1) begin
            product_mem[loaded_index] = 'x;
            expected_u8_mem[loaded_index] = 'x;
            expected_meta_mem[loaded_index] = 'x;
            group_start_cycle[loaded_index] = 0;
        end
        $readmemh("data/rebuild_v5_frontend/product/product_s32x16x32.mem", product_mem);
        $readmemh("data/rebuild_v5_frontend/product/expected_u8x16x32.mem", expected_u8_mem);
        $readmemh("data/rebuild_v5_frontend/product/expected_meta_u24x16.mem", expected_meta_mem);
        for (loaded_index = 0; loaded_index < GROUPS; loaded_index = loaded_index + 1)
            if ($isunknown(product_mem[loaded_index]) || $isunknown(expected_u8_mem[loaded_index]) ||
                $isunknown(expected_meta_mem[loaded_index]))
                $fatal(1, "FAIL: unknown loaded Product record group=%0d", loaded_index);
        repeat (5) @(posedge clk);
        rst_n <= 1'b1;
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            out_ready <= 1'b1;
            send_index <= 0;
            receive_index <= 0;
            cycle_count <= 0;
            mismatch_count <= 0;
            q_byte_checks <= 0;
            meta_word_checks <= 0;
            max_group_cycles <= 0;
            held_pending <= 1'b0;
        end else begin
            if (cycle_count > 5000)
                $fatal(1, "FAIL: Product timeout cycles=%0d send=%0d receive=%0d q=%0d meta=%0d health=%b",
                    cycle_count, send_index, receive_index, q_byte_checks, meta_word_checks, error);
            if (error !== 1'b0)
                $fatal(1, "FAIL: Product health must be known-zero health=%b", error);
            if ($isunknown({in_valid, in_ready, out_valid, out_ready}))
                $fatal(1, "FAIL: unknown Product handshake");
            if (in_valid && $isunknown(product_s32x16x32))
                $fatal(1, "FAIL: unknown actual Product input");
            if (out_valid && $isunknown({activation_u8x16x32, activation_meta_u24x16})) begin
                observed_cycles = cycle_count-group_start_cycle[receive_index];
                compare_group(receive_index);
                $fatal(1, "FAIL: unknown Product output");
            end
            if (held_pending) begin
                if (out_valid !== 1'b1)
                    $fatal(1, "FAIL: Product held valid changed");
                if (activation_u8x16x32 !== held_u8 || activation_meta_u24x16 !== held_meta) begin
                    compare_held(receive_index);
                    $fatal(1, "FAIL: Product held payload changed group=%0d cycles=%0d", receive_index, cycle_count);
                end
            end
            held_pending <= out_valid && !out_ready;
            if (out_valid && !out_ready) begin
                held_u8 <= activation_u8x16x32;
                held_meta <= activation_meta_u24x16;
            end
            cycle_count <= cycle_count + 1;
            out_ready <= ((cycle_count % 7) != 3 && (cycle_count % 11) != 5);
            if (in_valid && in_ready) begin
                group_start_cycle[send_index] <= cycle_count;
                send_index <= send_index + 1;
            end
            if (out_valid && out_ready) begin
                observed_cycles = cycle_count-group_start_cycle[receive_index];
                compare_group(receive_index);
                if (observed_cycles > max_group_cycles)
                    max_group_cycles <= observed_cycles;
                $display("GROUP kind=product group=%0d accepted_input_cycle=%0d accepted_output_cycle=%0d group_cycles=%0d q_bytes=%0d meta_words=%0d clock_period_ns=10 stall_moduli=7,11",
                    receive_index, group_start_cycle[receive_index], cycle_count,
                    observed_cycles, q_byte_checks, meta_word_checks);
                receive_index <= receive_index + 1;
                if (receive_index + 1 == GROUPS) begin
                    $display("NUMERICAL kind=product q_bytes=%0d meta_words=%0d rows=64 cycles=%0d max_group_cycles=%0d historical_900_final_group_met=%0d clock_period_ns=10",
                        q_byte_checks, meta_word_checks, cycle_count,
                        observed_cycles > max_group_cycles ? observed_cycles : max_group_cycles,
                        observed_cycles <= 900);
                    if (mismatch_count !== 0 || error !== 1'b0 ||
                        input_group_count !== 32'd4 || output_group_count+32'd1 !== 32'd4 ||
                        q_byte_checks !== 2048 || meta_word_checks !== 64)
                        $fatal(1, "FAIL: Product full counts q=%0d meta=%0d in=%0d out=%0d busy=%0d",
                            q_byte_checks, meta_word_checks, input_group_count,
                            output_group_count+1, busy_cycle_count);
                    $display("HARDWARE_AGENT_SIM_PASS");
                    $finish;
                end
            end
        end
    end
endmodule
