`timescale 1ns / 1ps

module hap_q24k12_group_dot_s40 #(
    parameter integer FIFO_DEPTH = 16
) (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  clear,
    input  wire                  in_valid,
    output wire                  in_ready,
    input  wire [32*24-1:0]      in_query_s24,
    input  wire [32*12-1:0]      in_key_s12,
    output wire                  out_valid,
    input  wire                  out_ready,
    output wire signed [39:0]    out_dot_s40,
    output reg  [31:0]           input_group_count,
    output reg  [31:0]           output_group_count,
    output reg                   error
);

    localparam integer PTR_W = $clog2(FIFO_DEPTH);
    localparam integer COUNT_W = $clog2(FIFO_DEPTH + 1);

    // The cache is implemented as four cascaded BRAM36 primitives for each
    // 400-bit record.  Feeding that BRAM output directly into the multiplier
    // made the BRAM cascade, inter-SLR route and DSP input one timing path.
    // Keep one complete accepted group in an elastic register and launch its
    // low/high halves on the following two cycles.  A replacement group can
    // be accepted while the high half is launched, so the external II stays
    // at two cycles while this register becomes a hard BRAM-to-DSP boundary.
    reg input_group_valid_r;
    reg input_group_high_r;
    (* shreg_extract = "no" *) reg [32*24-1:0] input_query_s24_r;
    (* shreg_extract = "no" *) reg [32*12-1:0] input_key_s12_r;

    reg product_valid_r;
    reg product_high_r;
    (* use_dsp = "yes" *) reg signed [34:0] product_s35_r [0:15];
    reg sum2_valid_r;
    reg sum2_high_r;
    (* use_dsp = "no" *) reg signed [35:0] sum2_s36_r [0:7];
    reg sum4_valid_r;
    reg sum4_high_r;
    (* use_dsp = "no" *) reg signed [36:0] sum4_s37_r [0:3];
    reg sum8_valid_r;
    reg sum8_high_r;
    (* use_dsp = "no" *) reg signed [37:0] sum8_s38_r [0:1];
    reg sum16_valid_r;
    reg sum16_high_r;
    (* use_dsp = "no" *) reg signed [38:0] sum16_s39_r;
    reg low_half_valid_r;
    reg signed [38:0] low_half_s39_r;
    reg dot_valid_r;
    reg signed [39:0] dot_s40_r;

    (* ram_style = "distributed" *) reg signed [39:0]
        fifo_mem [0:FIFO_DEPTH-1];
    reg [PTR_W-1:0] fifo_wr_ptr_r;
    reg [PTR_W-1:0] fifo_rd_ptr_r;
    reg [COUNT_W-1:0] fifo_count_r;
    reg [COUNT_W-1:0] used_count_r;

    wire in_fire = in_valid && in_ready;
    wire out_fire = out_valid && out_ready;
    wire launch_half = input_group_valid_r;
    wire launch_high = input_group_high_r;
    wire [16*24-1:0] launch_query_s24 = input_group_high_r ?
        input_query_s24_r[16*24 +: 16*24] :
        input_query_s24_r[0 +: 16*24];
    wire [16*12-1:0] launch_key_s12 = input_group_high_r ?
        input_key_s12_r[16*12 +: 16*12] :
        input_key_s12_r[0 +: 16*12];
    wire fifo_commit = dot_valid_r &&
        ((fifo_count_r != FIFO_DEPTH) || out_fire);

    assign in_ready = rst_n && !clear &&
        (!input_group_valid_r || input_group_high_r) &&
        (used_count_r < FIFO_DEPTH);
    assign out_valid = rst_n && !clear && (fifo_count_r != 0);
    assign out_dot_s40 = fifo_mem[fifo_rd_ptr_r];

    integer lane;
    integer reduce_idx;
    reg signed [35:0] product_full_s36;
    always @(posedge clk) begin
        if (in_fire) begin
            input_query_s24_r <= in_query_s24;
            input_key_s12_r <= in_key_s12;
        end
        if (launch_half) begin
            for (lane = 0; lane < 16; lane = lane + 1) begin
                product_full_s36 =
                    $signed(launch_query_s24[lane*24 +: 24]) *
                    $signed(launch_key_s12[lane*12 +: 12]);
                product_s35_r[lane] <= product_full_s36[34:0];
            end
            product_high_r <= launch_high;
        end
        if (product_valid_r) begin
            for (reduce_idx = 0; reduce_idx < 8;
                 reduce_idx = reduce_idx + 1)
                sum2_s36_r[reduce_idx] <=
                    $signed(product_s35_r[2*reduce_idx]) +
                    $signed(product_s35_r[2*reduce_idx+1]);
            sum2_high_r <= product_high_r;
        end
        if (sum2_valid_r) begin
            for (reduce_idx = 0; reduce_idx < 4;
                 reduce_idx = reduce_idx + 1)
                sum4_s37_r[reduce_idx] <=
                    $signed(sum2_s36_r[2*reduce_idx]) +
                    $signed(sum2_s36_r[2*reduce_idx+1]);
            sum4_high_r <= sum2_high_r;
        end
        if (sum4_valid_r) begin
            for (reduce_idx = 0; reduce_idx < 2;
                 reduce_idx = reduce_idx + 1)
                sum8_s38_r[reduce_idx] <=
                    $signed(sum4_s37_r[2*reduce_idx]) +
                    $signed(sum4_s37_r[2*reduce_idx+1]);
            sum8_high_r <= sum4_high_r;
        end
        if (sum8_valid_r) begin
            sum16_s39_r <= $signed(sum8_s38_r[0]) +
                $signed(sum8_s38_r[1]);
            sum16_high_r <= sum8_high_r;
        end
        if (sum16_valid_r) begin
            if (sum16_high_r && low_half_valid_r)
                dot_s40_r <=
                    $signed({low_half_s39_r[38], low_half_s39_r}) +
                    $signed({sum16_s39_r[38], sum16_s39_r});
            else if (!sum16_high_r)
                low_half_s39_r <= sum16_s39_r;
        end
        if (fifo_commit)
            fifo_mem[fifo_wr_ptr_r] <= dot_s40_r;
    end

    integer key_lane;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            input_group_valid_r <= 1'b0;
            input_group_high_r <= 1'b0;
            product_valid_r <= 1'b0;
            sum2_valid_r <= 1'b0;
            sum4_valid_r <= 1'b0;
            sum8_valid_r <= 1'b0;
            sum16_valid_r <= 1'b0;
            low_half_valid_r <= 1'b0;
            dot_valid_r <= 1'b0;
            fifo_wr_ptr_r <= '0;
            fifo_rd_ptr_r <= '0;
            fifo_count_r <= '0;
            used_count_r <= '0;
            input_group_count <= 32'd0;
            output_group_count <= 32'd0;
            error <= 1'b0;
        end else if (clear) begin
            input_group_valid_r <= 1'b0;
            input_group_high_r <= 1'b0;
            product_valid_r <= 1'b0;
            sum2_valid_r <= 1'b0;
            sum4_valid_r <= 1'b0;
            sum8_valid_r <= 1'b0;
            sum16_valid_r <= 1'b0;
            low_half_valid_r <= 1'b0;
            dot_valid_r <= 1'b0;
            fifo_wr_ptr_r <= '0;
            fifo_rd_ptr_r <= '0;
            fifo_count_r <= '0;
            used_count_r <= '0;
            input_group_count <= 32'd0;
            output_group_count <= 32'd0;
            error <= 1'b0;
        end else begin
            product_valid_r <= launch_half;
            sum2_valid_r <= product_valid_r;
            sum4_valid_r <= sum2_valid_r;
            sum8_valid_r <= sum4_valid_r;
            sum16_valid_r <= sum8_valid_r;
            dot_valid_r <= sum16_valid_r && sum16_high_r &&
                low_half_valid_r;
            if (sum16_valid_r) begin
                if (sum16_high_r)
                    low_half_valid_r <= 1'b0;
                else
                    low_half_valid_r <= 1'b1;
            end
            if (input_group_valid_r) begin
                if (input_group_high_r) begin
                    input_group_valid_r <= in_fire;
                    input_group_high_r <= 1'b0;
                end else begin
                    input_group_high_r <= 1'b1;
                end
            end else if (in_fire) begin
                input_group_valid_r <= 1'b1;
                input_group_high_r <= 1'b0;
            end

            if (in_fire) begin
                input_group_count <= input_group_count + 32'd1;
                for (key_lane = 0; key_lane < 32;
                     key_lane = key_lane + 1)
                    if (in_key_s12[key_lane*12 +: 12] == 12'h800)
                        error <= 1'b1;
            end
            if (dot_valid_r) begin
                if ((fifo_count_r == FIFO_DEPTH) && !out_fire)
                    error <= 1'b1;
                else
                    fifo_wr_ptr_r <= fifo_wr_ptr_r + 1'b1;
            end
            if (out_fire) begin
                fifo_rd_ptr_r <= fifo_rd_ptr_r + 1'b1;
                output_group_count <= output_group_count + 32'd1;
            end
            case ({fifo_commit, out_fire})
                2'b10: fifo_count_r <= fifo_count_r + 1'b1;
                2'b01: fifo_count_r <= fifo_count_r - 1'b1;
                default: fifo_count_r <= fifo_count_r;
            endcase
            case ({in_fire, out_fire})
                2'b10: used_count_r <= used_count_r + 1'b1;
                2'b01: used_count_r <= used_count_r - 1'b1;
                default: used_count_r <= used_count_r;
            endcase
            if ((used_count_r > FIFO_DEPTH) ||
                (fifo_count_r > FIFO_DEPTH) ||
                (fifo_count_r > used_count_r))
                error <= 1'b1;
        end
    end

    initial begin
        if (FIFO_DEPTH != 16)
            $error("hap_q24k12_group_dot_s40 FIFO_DEPTH must be 16");
    end

endmodule
