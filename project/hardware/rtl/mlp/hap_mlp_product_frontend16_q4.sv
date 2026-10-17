`timescale 1ns / 1ps

// Cohort16 SwiGLU-product transform/quantization frontend.
//
// One complete 16-request x group32 S32 Q16.16 product group is buffered.
// A shared II=1 Hadamard32 engine serializes the 16 rows; four independent
// robust A8 quantizers consume rows round-robin.  Each quantizer therefore
// handles four rows rather than eight, avoiding the <100 aggregate token/s
// ceiling of the old two-quantizer cohort16 extrapolation.
module hap_mlp_product_frontend16_q4 (
    input  wire                           clk,
    input  wire                           rst_n,
    input  wire                           clear,
    input  wire                           in_valid,
    output wire                           in_ready,
    input  wire signed [16*32*32-1:0]     product_s32x16x32,
    output wire                           out_valid,
    input  wire                           out_ready,
    output wire [16*32*8-1:0]             activation_u8x16x32,
    output wire [16*24-1:0]               activation_meta_u24x16,
    output reg  [31:0]                    input_group_count,
    output reg  [31:0]                    output_group_count,
    output reg  [31:0]                    busy_cycle_count,
    output reg                            error
);

    reg active_r;
    reg out_valid_r;
    reg signed [16*32*32-1:0] product_buffer_r;
    // The old monolithic input handshake drove the clock-enable of almost
    // every bit in product_buffer_r (16,322 placed sinks), so phys_opt
    // promoted that data predicate onto a BUFG.  Keep 64 real, bank-local
    // capture controls instead.  A bank is open only while this endpoint is
    // idle; qualifying it with in_valid captures the accepted payload on the
    // original handshake edge without adding a staging cycle.  Each local
    // control owns at most 256 data FFs, while in_valid only reaches the 64
    // local predicates.
    (* DONT_TOUCH = "yes" *) reg [63:0] product_capture_open_bank_r;
    reg [4:0] source_row_r;
    reg [4:0] dispatch_row_r;
    reg [2:0] quant_output_wave_r [0:3];
    reg [5:0] completed_row_count_r;
    reg [16*32*8-1:0] activation_u8_r;
    reg [16*24-1:0] activation_meta_r;

    wire hadamard_in_valid = active_r && source_row_r < 16;
    wire hadamard_in_ready;
    wire hadamard_in_fire = hadamard_in_valid && hadamard_in_ready;
    wire [32*32-1:0] hadamard_in_s32 =
        product_buffer_r[source_row_r*32*32 +: 32*32];
    wire hadamard_out_valid;
    wire hadamard_out_ready;
    wire [32*35-1:0] hadamard_out_s35;
    wire hadamard_error;

    wire [3:0] quant_in_ready;
    wire [3:0] quant_out_valid;
    wire [3:0] quant_out_ready;
    wire [4*32*8-1:0] quant_out_u8;
    wire [4*24-1:0] quant_out_meta;
    wire [3:0] quant_error;
    wire [1:0] dispatch_quantizer = dispatch_row_r[1:0];
    wire hadamard_out_fire = hadamard_out_valid && hadamard_out_ready;
    wire [3:0] quant_out_fire = quant_out_valid & quant_out_ready;
    wire [2:0] quant_fire_count =
        {2'd0, quant_out_fire[0]} + {2'd0, quant_out_fire[1]} +
        {2'd0, quant_out_fire[2]} + {2'd0, quant_out_fire[3]};
    wire in_fire = in_valid && in_ready;
    wire out_fire = out_valid && out_ready;

    assign in_ready = rst_n && !clear && !active_r && !out_valid_r;
    assign out_valid = rst_n && !clear && out_valid_r;
    assign activation_u8x16x32 = activation_u8_r;
    assign activation_meta_u24x16 = activation_meta_r;
    assign hadamard_out_ready = quant_in_ready[dispatch_quantizer];

    integer capture_bank;
    // The payload registers intentionally have no reset.  Their contents are
    // consumed only after in_fire, when all 64 banks have captured the valid
    // input in this same clock edge.
    always @(posedge clk) begin
        for (capture_bank = 0; capture_bank < 64;
             capture_bank = capture_bank + 1)
            if (product_capture_open_bank_r[capture_bank] && in_valid)
                product_buffer_r[capture_bank*256 +: 256] <=
                    product_s32x16x32[capture_bank*256 +: 256];
    end

    hap_mlp_hadamard32_s32_norm_stream u_hadamard (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(hadamard_in_valid), .in_ready(hadamard_in_ready),
        .in_s32(hadamard_in_s32),
        .out_valid(hadamard_out_valid), .out_ready(hadamard_out_ready),
        .out_s35(hadamard_out_s35),
        .input_group_count(), .output_group_count(),
        .saturation_count(), .error(hadamard_error)
    );

    genvar quantizer;
    generate
        for (quantizer = 0; quantizer < 4;
             quantizer = quantizer + 1) begin : gen_quantizer
            hap_mlp_robust_a8_quantizer_s35 u_quantizer (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(hadamard_out_valid &&
                    dispatch_quantizer == quantizer),
                .in_ready(quant_in_ready[quantizer]),
                .in_s35(hadamard_out_s35),
                .out_valid(quant_out_valid[quantizer]),
                .out_ready(quant_out_ready[quantizer]),
                .out_u8(quant_out_u8[quantizer*32*8 +: 32*8]),
                .out_meta(quant_out_meta[quantizer*24 +: 24]),
                .input_group_count(), .output_group_count(),
                .cycle_count(), .format_error_count(),
                .error(quant_error[quantizer])
            );
            assign quant_out_ready[quantizer] = active_r &&
                quant_output_wave_r[quantizer] < 4;
        end
    endgenerate

    integer q;
    integer output_row;
    always @(posedge clk) begin
        if (!rst_n) begin
            active_r <= 1'b0;
            out_valid_r <= 1'b0;
            product_capture_open_bank_r <= {64{1'b1}};
            source_row_r <= '0;
            dispatch_row_r <= '0;
            completed_row_count_r <= '0;
            input_group_count <= 32'd0;
            output_group_count <= 32'd0;
            busy_cycle_count <= 32'd0;
            error <= 1'b0;
            for (q = 0; q < 4; q = q + 1)
                quant_output_wave_r[q] <= '0;
        end else if (clear) begin
            active_r <= 1'b0;
            out_valid_r <= 1'b0;
            product_capture_open_bank_r <= {64{1'b1}};
            source_row_r <= '0;
            dispatch_row_r <= '0;
            completed_row_count_r <= '0;
            input_group_count <= 32'd0;
            output_group_count <= 32'd0;
            busy_cycle_count <= 32'd0;
            error <= 1'b0;
            for (q = 0; q < 4; q = q + 1)
                quant_output_wave_r[q] <= '0;
        end else begin
            if (active_r)
                busy_cycle_count <= busy_cycle_count + 32'd1;

            if (in_fire) begin
                active_r <= 1'b1;
                product_capture_open_bank_r <= 64'd0;
                source_row_r <= '0;
                dispatch_row_r <= '0;
                completed_row_count_r <= '0;
                input_group_count <= input_group_count + 32'd1;
                for (q = 0; q < 4; q = q + 1)
                    quant_output_wave_r[q] <= '0;
            end

            if (hadamard_in_fire)
                source_row_r <= source_row_r + 1'b1;
            if (hadamard_out_fire)
                dispatch_row_r <= dispatch_row_r + 1'b1;

            for (q = 0; q < 4; q = q + 1) begin
                if (quant_out_fire[q]) begin
                    output_row = q + 4*quant_output_wave_r[q];
                    activation_u8_r[output_row*32*8 +: 32*8] <=
                        quant_out_u8[q*32*8 +: 32*8];
                    activation_meta_r[output_row*24 +: 24] <=
                        quant_out_meta[q*24 +: 24];
                    quant_output_wave_r[q] <=
                        quant_output_wave_r[q] + 1'b1;
                end
            end
            if (quant_fire_count != 0) begin
                completed_row_count_r <= completed_row_count_r +
                    quant_fire_count;
                if (completed_row_count_r + quant_fire_count == 16)
                    out_valid_r <= 1'b1;
            end

            if (out_fire) begin
                out_valid_r <= 1'b0;
                active_r <= 1'b0;
                product_capture_open_bank_r <= {64{1'b1}};
                output_group_count <= output_group_count + 32'd1;
            end

            if (hadamard_error || |quant_error ||
                source_row_r > 16 || dispatch_row_r > 16 ||
                completed_row_count_r > 16)
                error <= 1'b1;
        end
    end

endmodule
