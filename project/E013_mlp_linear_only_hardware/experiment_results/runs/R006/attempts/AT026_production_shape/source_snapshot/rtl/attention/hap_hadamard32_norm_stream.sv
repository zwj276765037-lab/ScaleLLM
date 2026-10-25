`timescale 1ns / 1ps

module hap_hadamard32_norm_stream #(
    parameter integer FIFO_DEPTH = 8
) (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  clear,
    input  wire                  in_valid,
    output wire                  in_ready,
    input  wire [32*24-1:0]      in_s24,
    output wire                  out_valid,
    input  wire                  out_ready,
    output wire [32*27-1:0]      out_s27,
    output reg  [31:0]           input_group_count,
    output reg  [31:0]           output_group_count,
    output reg  [31:0]           saturation_count,
    output reg                   error
);

    localparam integer PTR_W = $clog2(FIFO_DEPTH);
    localparam integer COUNT_W = $clog2(FIFO_DEPTH + 1);
    localparam [13:0] INV_SQRT32_Q16 = 14'd11585;

    reg valid_s1;
    reg valid_s2;
    reg valid_s3;
    reg valid_s4;
    reg valid_s5;
    reg valid_norm;

    reg signed [24:0] data_s1 [0:31];
    reg signed [25:0] data_s2 [0:31];
    reg signed [26:0] data_s3 [0:31];
    reg signed [27:0] data_s4 [0:31];
    reg signed [28:0] data_s5 [0:31];
    (* use_dsp = "yes" *) reg signed [42:0] norm_product [0:31];

    (* ram_style = "distributed" *) reg [32*27-1:0] fifo_mem [0:FIFO_DEPTH-1];
    reg [PTR_W-1:0] fifo_wr_ptr;
    reg [PTR_W-1:0] fifo_rd_ptr;
    reg [COUNT_W-1:0] fifo_count;
    reg [COUNT_W-1:0] used_count;

    wire in_fire = in_valid && in_ready;
    wire out_fire = out_valid && out_ready;
    wire fifo_write = valid_norm;
    wire fifo_commit = fifo_write &&
        ((fifo_count != FIFO_DEPTH) || out_fire);

    assign in_ready = rst_n && !clear && (used_count < FIFO_DEPTH);
    assign out_valid = rst_n && !clear && (fifo_count != 0);
    assign out_s27 = fifo_mem[fifo_rd_ptr];

    function automatic signed [26:0] round_sat_s43_to_s27;
        input signed [42:0] value;
        reg [43:0] magnitude;
        reg [43:0] rounded_magnitude;
        reg signed [43:0] rounded_value;
        begin
            if (value < 0) begin
                magnitude = -$signed({value[42], value});
                rounded_magnitude = (magnitude + 44'd32768) >> 16;
                rounded_value = -$signed(rounded_magnitude);
            end else begin
                magnitude = {1'b0, value};
                rounded_magnitude = (magnitude + 44'd32768) >> 16;
                rounded_value = $signed(rounded_magnitude);
            end

            if (rounded_value > 44'sd67108863)
                round_sat_s43_to_s27 = 27'sh3ff_ffff;
            else if (rounded_value < -44'sd67108864)
                round_sat_s43_to_s27 = -27'sd67108864;
            else
                round_sat_s43_to_s27 = rounded_value[26:0];
        end
    endfunction

    function automatic norm_saturates;
        input signed [42:0] value;
        reg [43:0] magnitude;
        reg [43:0] rounded_magnitude;
        reg signed [43:0] rounded_value;
        begin
            if (value < 0) begin
                magnitude = -$signed({value[42], value});
                rounded_magnitude = (magnitude + 44'd32768) >> 16;
                rounded_value = -$signed(rounded_magnitude);
            end else begin
                magnitude = {1'b0, value};
                rounded_magnitude = (magnitude + 44'd32768) >> 16;
                rounded_value = $signed(rounded_magnitude);
            end
            norm_saturates = (rounded_value > 44'sd67108863) ||
                (rounded_value < -44'sd67108864);
        end
    endfunction

    integer lane;
    integer block_idx;
    integer offset;
    // Wide arithmetic storage deliberately has no reset.  Cleared valid bits
    // make stale data unobservable and keep reset off the high-fanout datapath.
    always @(posedge clk) begin
        if (in_fire) begin
            for (lane = 0; lane < 16; lane = lane + 1) begin
                data_s1[2*lane] <=
                    $signed(in_s24[(2*lane)*24 +: 24]) +
                    $signed(in_s24[(2*lane+1)*24 +: 24]);
                data_s1[2*lane+1] <=
                    $signed(in_s24[(2*lane)*24 +: 24]) -
                    $signed(in_s24[(2*lane+1)*24 +: 24]);
            end
        end

        if (valid_s1) begin
            for (block_idx = 0; block_idx < 8; block_idx = block_idx + 1)
                for (offset = 0; offset < 2; offset = offset + 1) begin
                    data_s2[4*block_idx+offset] <=
                        data_s1[4*block_idx+offset] +
                        data_s1[4*block_idx+offset+2];
                    data_s2[4*block_idx+offset+2] <=
                        data_s1[4*block_idx+offset] -
                        data_s1[4*block_idx+offset+2];
                end
        end

        if (valid_s2) begin
            for (block_idx = 0; block_idx < 4; block_idx = block_idx + 1)
                for (offset = 0; offset < 4; offset = offset + 1) begin
                    data_s3[8*block_idx+offset] <=
                        data_s2[8*block_idx+offset] +
                        data_s2[8*block_idx+offset+4];
                    data_s3[8*block_idx+offset+4] <=
                        data_s2[8*block_idx+offset] -
                        data_s2[8*block_idx+offset+4];
                end
        end

        if (valid_s3) begin
            for (block_idx = 0; block_idx < 2; block_idx = block_idx + 1)
                for (offset = 0; offset < 8; offset = offset + 1) begin
                    data_s4[16*block_idx+offset] <=
                        data_s3[16*block_idx+offset] +
                        data_s3[16*block_idx+offset+8];
                    data_s4[16*block_idx+offset+8] <=
                        data_s3[16*block_idx+offset] -
                        data_s3[16*block_idx+offset+8];
                end
        end

        if (valid_s4) begin
            for (offset = 0; offset < 16; offset = offset + 1) begin
                data_s5[offset] <= data_s4[offset] + data_s4[offset+16];
                data_s5[offset+16] <= data_s4[offset] - data_s4[offset+16];
            end
        end

        if (valid_s5) begin
            for (lane = 0; lane < 32; lane = lane + 1)
                // The explicit leading zero makes the U14 coefficient a
                // positive signed operand.  The mathematical S43 result
                // has one redundant sign bit in the S29xS15 expression.
                norm_product[lane] <= data_s5[lane] *
                    $signed({1'b0, INV_SQRT32_Q16});
        end

        if (fifo_commit) begin
            for (lane = 0; lane < 32; lane = lane + 1)
                fifo_mem[fifo_wr_ptr][lane*27 +: 27] <=
                    round_sat_s43_to_s27(norm_product[lane]);
        end
    end

    integer saturation_increment;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            valid_s1 <= 1'b0;
            valid_s2 <= 1'b0;
            valid_s3 <= 1'b0;
            valid_s4 <= 1'b0;
            valid_s5 <= 1'b0;
            valid_norm <= 1'b0;
            fifo_wr_ptr <= '0;
            fifo_rd_ptr <= '0;
            fifo_count <= '0;
            used_count <= '0;
            input_group_count <= 32'd0;
            output_group_count <= 32'd0;
            saturation_count <= 32'd0;
            error <= 1'b0;
        end else if (clear) begin
            valid_s1 <= 1'b0;
            valid_s2 <= 1'b0;
            valid_s3 <= 1'b0;
            valid_s4 <= 1'b0;
            valid_s5 <= 1'b0;
            valid_norm <= 1'b0;
            fifo_wr_ptr <= '0;
            fifo_rd_ptr <= '0;
            fifo_count <= '0;
            used_count <= '0;
            input_group_count <= 32'd0;
            output_group_count <= 32'd0;
            saturation_count <= 32'd0;
            error <= 1'b0;
        end else begin
            valid_s1 <= in_fire;
            valid_s2 <= valid_s1;
            valid_s3 <= valid_s2;
            valid_s4 <= valid_s3;
            valid_s5 <= valid_s4;
            valid_norm <= valid_s5;

            if (in_fire) begin
                input_group_count <= input_group_count + 32'd1;
            end

            if (fifo_write) begin
                if ((fifo_count == FIFO_DEPTH) && !out_fire) begin
                    error <= 1'b1;
                end else begin
                    saturation_increment = 0;
                    for (lane = 0; lane < 32; lane = lane + 1) begin
                        if (norm_saturates(norm_product[lane]))
                            saturation_increment = saturation_increment + 1;
                    end
                    saturation_count <= saturation_count + saturation_increment;
                    fifo_wr_ptr <= fifo_wr_ptr + 1'b1;
                end
            end

            if (out_fire) begin
                fifo_rd_ptr <= fifo_rd_ptr + 1'b1;
                output_group_count <= output_group_count + 32'd1;
            end

            case ({fifo_commit, out_fire})
                2'b10: fifo_count <= fifo_count + 1'b1;
                2'b01: fifo_count <= fifo_count - 1'b1;
                default: fifo_count <= fifo_count;
            endcase

            case ({in_fire, out_fire})
                2'b10: used_count <= used_count + 1'b1;
                2'b01: used_count <= used_count - 1'b1;
                default: used_count <= used_count;
            endcase

            if ((used_count > FIFO_DEPTH) || (fifo_count > FIFO_DEPTH) ||
                (fifo_count > used_count))
                error <= 1'b1;
        end
    end

    initial begin
        if (FIFO_DEPTH != 8)
            $error("hap_hadamard32_norm_stream production FIFO_DEPTH must be 8");
    end

endmodule
