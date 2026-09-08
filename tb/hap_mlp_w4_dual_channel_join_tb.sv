`timescale 1ns / 1ps

module hap_mlp_w4_dual_channel_join_tb;
    localparam integer GROUPS = 12;
    localparam integer BEATS = GROUPS*2;
    reg clk = 1'b0;
    always #3.333 clk = ~clk;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    wire beat0_valid;
    wire beat0_ready;
    wire [511:0] beat0_data;
    wire beat0_last;
    wire beat1_valid;
    wire beat1_ready;
    wire [511:0] beat1_data;
    wire beat1_last;
    wire half0_valid;
    wire half0_ready;
    wire [1023:0] half0_data;
    wire half1_valid;
    wire half1_ready;
    wire [1023:0] half1_data;
    wire meta_valid;
    wire meta_ready;
    wire [223:0] meta_u224;
    wire out_valid;
    reg out_ready = 1'b1;
    wire [2047:0] weights_s4x16x32;
    wire [223:0] weight_meta_u224;
    wire [31:0] useful_group_count;
    wire [63:0] useful_weight_byte_count;
    wire half0_error;
    wire half1_error;
    wire join_error;

    integer beat0_index = 0;
    integer beat1_index = 0;
    integer meta_index = 0;
    integer output_index = 0;
    integer cycle_count = 0;
    wire [31:0] half0_word = 32'h1000_0000 + beat0_index;
    wire [31:0] half1_word = 32'h2000_0000 + beat1_index;
    assign beat0_valid = beat0_index < BEATS && cycle_count % 5 != 1;
    assign beat1_valid = beat1_index < BEATS && cycle_count % 7 != 2;
    assign beat0_data = {16{half0_word}};
    assign beat1_data = {16{half1_word}};
    assign beat0_last = beat0_index[0];
    assign beat1_last = beat1_index[0];
    assign meta_valid = meta_index < GROUPS && cycle_count % 11 != 4;
    assign meta_u224 = {7{32'h3000_0000 + meta_index}};

    hap_w4_halfgroup2_assembler u_half0 (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .beat_valid(beat0_valid), .beat_ready(beat0_ready),
        .beat_data(beat0_data), .beat_group_last(beat0_last),
        .half_valid(half0_valid), .half_ready(half0_ready),
        .half_data(half0_data), .beat_count(), .half_count(),
        .error(half0_error)
    );
    hap_w4_halfgroup2_assembler u_half1 (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .beat_valid(beat1_valid), .beat_ready(beat1_ready),
        .beat_data(beat1_data), .beat_group_last(beat1_last),
        .half_valid(half1_valid), .half_ready(half1_ready),
        .half_data(half1_data), .beat_count(), .half_count(),
        .error(half1_error)
    );
    hap_mlp_w4_dual_channel_join u_join (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .half0_valid(half0_valid), .half0_ready(half0_ready),
        .half0_data(half0_data),
        .half1_valid(half1_valid), .half1_ready(half1_ready),
        .half1_data(half1_data),
        .meta_valid(meta_valid), .meta_ready(meta_ready),
        .meta_u224(meta_u224),
        .out_valid(out_valid), .out_ready(out_ready),
        .weights_s4x16x32(weights_s4x16x32),
        .weight_meta_u224(weight_meta_u224),
        .useful_group_count(useful_group_count),
        .useful_weight_byte_count(useful_weight_byte_count),
        .error(join_error)
    );

    initial begin
        repeat (5) @(posedge clk);
        rst_n <= 1'b1;
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            beat0_index <= 0;
            beat1_index <= 0;
            meta_index <= 0;
            output_index <= 0;
            cycle_count <= 0;
            out_ready <= 1'b1;
        end else begin
            cycle_count <= cycle_count + 1;
            out_ready <= cycle_count % 9 != 5;
            if (beat0_valid && beat0_ready)
                beat0_index <= beat0_index + 1;
            if (beat1_valid && beat1_ready)
                beat1_index <= beat1_index + 1;
            if (meta_valid && meta_ready)
                meta_index <= meta_index + 1;
            if (out_valid && out_ready) begin
                if (weights_s4x16x32[31:0] !==
                        32'h1000_0000 + output_index*2 ||
                    weights_s4x16x32[1024 +: 32] !==
                        32'h2000_0000 + output_index*2 ||
                    weight_meta_u224[31:0] !==
                        32'h3000_0000 + output_index)
                    $fatal(1, "FAIL output group=%0d", output_index);
                output_index <= output_index + 1;
                if (output_index + 1 == GROUPS) begin
                    if (!half0_error && !half1_error && !join_error &&
                        useful_group_count + 1 == GROUPS &&
                        useful_weight_byte_count + 256 == GROUPS*256) begin
                        $display("PASS: hap_mlp_w4_dual_channel_join groups=%0d raw_bytes=%0d useful_bytes=%0d cycles=%0d",
                            GROUPS, GROUPS*256,
                            useful_weight_byte_count + 256, cycle_count);
                        $finish;
                    end else begin
                        $fatal(1,
                            "FAIL errors=%0d%0d%0d groups=%0d bytes=%0d",
                            half0_error, half1_error, join_error,
                            useful_group_count + 1,
                            useful_weight_byte_count + 256);
                    end
                end
            end
            if (cycle_count > 500)
                $fatal(1, "FAIL timeout output=%0d", output_index);
        end
    end
endmodule
