`timescale 1ns / 1ps

// Normalized Hadamard32 for the S32 Q16.16 SwiGLU product boundary.
// Five exact butterflies widen S32 -> S37.  Multiplication by the U14 Q0.16
// coefficient 11585 produces a mathematical S51 value, rounded half away
// from zero to S35 Q19.16.  FIFO credit reserves all in-flight pipeline data.
module hap_mlp_hadamard32_s32_norm_stream #(
    parameter integer FIFO_DEPTH = 8
) (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  clear,
    input  wire                  in_valid,
    output wire                  in_ready,
    input  wire [32*32-1:0]      in_s32,
    output wire                  out_valid,
    input  wire                  out_ready,
    output wire [32*35-1:0]      out_s35,
    output reg  [31:0]           input_group_count,
    output reg  [31:0]           output_group_count,
    output reg  [31:0]           saturation_count,
    output reg                   error
);

    localparam integer PTR_W = $clog2(FIFO_DEPTH);
    localparam integer COUNT_W = $clog2(FIFO_DEPTH + 1);
    localparam [13:0] INV_SQRT32_Q16 = 14'd11585;

    // Every butterfly level owns eight physically independent, cycle-aligned
    // valid FFs.  The banked enables split the former 1k-load scalar nets;
    // post-route topology auditing verifies the actual fanout and that no
    // data BUFG is inserted.  Bit zero is the protocol owner.  No valid stage
    // or arithmetic cycle is added; all replicas sample the preceding owner
    // on the same edge as the original scalar pipeline.
    (* DONT_TOUCH = "yes" *) reg [7:0] valid_s1_bank;
    (* DONT_TOUCH = "yes" *) reg [7:0] valid_s2_bank;
    (* DONT_TOUCH = "yes" *) reg [7:0] valid_s3_bank;
    (* DONT_TOUCH = "yes" *) reg [7:0] valid_s4_bank;
    (* DONT_TOUCH = "yes" *) reg [7:0] valid_s5_bank;
    reg valid_norm;
    reg signed [32:0] data_s1 [0:31];
    reg signed [33:0] data_s2 [0:31];
    reg signed [34:0] data_s3 [0:31];
    reg signed [35:0] data_s4 [0:31];
    reg signed [36:0] data_s5 [0:31];
    (* use_dsp = "yes" *) reg signed [50:0] norm_product [0:31];

    (* ram_style = "distributed" *)
    reg [32*35-1:0] fifo_mem [0:FIFO_DEPTH-1];
    reg [PTR_W-1:0] fifo_wr_ptr, fifo_rd_ptr;
    reg [COUNT_W-1:0] fifo_count, used_count;

    wire in_fire = in_valid && in_ready;
    wire out_fire = out_valid && out_ready;
    wire fifo_write = valid_norm;
    wire fifo_commit = fifo_write &&
        ((fifo_count != FIFO_DEPTH) || out_fire);

    assign in_ready = rst_n && !clear && (used_count < FIFO_DEPTH);
    assign out_valid = rst_n && !clear && (fifo_count != 0);
    assign out_s35 = fifo_mem[fifo_rd_ptr];

    // Range proof: max |H32(x)| <= 32*2^31 = 2^36 and
    // 2^36*11585/2^16 < 2^34.  Therefore rounded normalized output always
    // fits S35 for every legal S32 input and saturation hardware is invalid
    // overhead.  saturation_count remains a compatibility telemetry zero.
    function automatic signed [34:0] round_s51_to_s35;
        input signed [50:0] value;
        reg [51:0] magnitude;
        reg [51:0] rounded_magnitude;
        reg signed [51:0] rounded_value;
        begin
            if (value < 0) begin
                magnitude = -$signed({value[50], value});
                rounded_magnitude = (magnitude + 52'd32768) >> 16;
                rounded_value = -$signed(rounded_magnitude);
            end else begin
                magnitude = {1'b0, value};
                rounded_magnitude = (magnitude + 52'd32768) >> 16;
                rounded_value = $signed(rounded_magnitude);
            end
            round_s51_to_s35 = rounded_value[34:0];
        end
    endfunction

    integer lane, block_idx, offset;
    // Wide datapath registers have no reset; valid state makes stale values
    // unobservable and avoids high-fanout reset routing through the array.
    always @(posedge clk) begin
        for (lane = 0; lane < 16; lane = lane + 1)
            if (in_fire) begin
                data_s1[2*lane] <=
                    $signed(in_s32[(2*lane)*32 +: 32]) +
                    $signed(in_s32[(2*lane+1)*32 +: 32]);
                data_s1[2*lane+1] <=
                    $signed(in_s32[(2*lane)*32 +: 32]) -
                    $signed(in_s32[(2*lane+1)*32 +: 32]);
            end
        for (block_idx = 0; block_idx < 8; block_idx = block_idx + 1)
            if (valid_s1_bank[block_idx])
                for (offset = 0; offset < 2; offset = offset + 1) begin
                    data_s2[4*block_idx+offset] <=
                        data_s1[4*block_idx+offset] +
                        data_s1[4*block_idx+offset+2];
                    data_s2[4*block_idx+offset+2] <=
                        data_s1[4*block_idx+offset] -
                        data_s1[4*block_idx+offset+2];
                end
        for (block_idx = 0; block_idx < 4; block_idx = block_idx + 1)
            for (offset = 0; offset < 4; offset = offset + 1)
                if (valid_s2_bank[2*block_idx+offset/2]) begin
                    data_s3[8*block_idx+offset] <=
                        data_s2[8*block_idx+offset] +
                        data_s2[8*block_idx+offset+4];
                    data_s3[8*block_idx+offset+4] <=
                        data_s2[8*block_idx+offset] -
                        data_s2[8*block_idx+offset+4];
                end
        for (block_idx = 0; block_idx < 2; block_idx = block_idx + 1)
            for (offset = 0; offset < 8; offset = offset + 1)
                if (valid_s3_bank[4*block_idx+offset/2]) begin
                    data_s4[16*block_idx+offset] <=
                        data_s3[16*block_idx+offset] +
                        data_s3[16*block_idx+offset+8];
                    data_s4[16*block_idx+offset+8] <=
                        data_s3[16*block_idx+offset] -
                        data_s3[16*block_idx+offset+8];
                end
        for (offset = 0; offset < 16; offset = offset + 1)
            if (valid_s4_bank[offset/2]) begin
                data_s5[offset] <= data_s4[offset] + data_s4[offset+16];
                data_s5[offset+16] <= data_s4[offset] - data_s4[offset+16];
            end
        for (lane = 0; lane < 32; lane = lane + 1)
            if (valid_s5_bank[lane/4])
                norm_product[lane] <= data_s5[lane] *
                    $signed({1'b0, INV_SQRT32_Q16});
        if (fifo_commit)
            for (lane = 0; lane < 32; lane = lane + 1)
                fifo_mem[fifo_wr_ptr][lane*35 +: 35] <=
                    round_s51_to_s35(norm_product[lane]);
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            valid_s1_bank <= 8'd0; valid_s2_bank <= 8'd0;
            valid_s3_bank <= 8'd0; valid_s4_bank <= 8'd0;
            valid_s5_bank <= 8'd0; valid_norm <= 1'b0;
            fifo_wr_ptr <= '0; fifo_rd_ptr <= '0;
            fifo_count <= '0; used_count <= '0;
            input_group_count <= 32'd0; output_group_count <= 32'd0;
            saturation_count <= 32'd0; error <= 1'b0;
        end else if (clear) begin
            valid_s1_bank <= 8'd0; valid_s2_bank <= 8'd0;
            valid_s3_bank <= 8'd0; valid_s4_bank <= 8'd0;
            valid_s5_bank <= 8'd0; valid_norm <= 1'b0;
            fifo_wr_ptr <= '0; fifo_rd_ptr <= '0;
            fifo_count <= '0; used_count <= '0;
            input_group_count <= 32'd0; output_group_count <= 32'd0;
            saturation_count <= 32'd0; error <= 1'b0;
        end else begin
            valid_s1_bank <= {8{in_fire}};
            valid_s2_bank <= {8{valid_s1_bank[0]}};
            valid_s3_bank <= {8{valid_s2_bank[0]}};
            valid_s4_bank <= {8{valid_s3_bank[0]}};
            valid_s5_bank <= {8{valid_s4_bank[0]}};
            valid_norm <= valid_s5_bank[0];
            if (in_fire)
                input_group_count <= input_group_count + 32'd1;
            if (fifo_write) begin
                if ((fifo_count == FIFO_DEPTH) && !out_fire)
                    error <= 1'b1;
                else begin
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
            $error("MLP S32 Hadamard production FIFO_DEPTH must be 8");
    end
endmodule
