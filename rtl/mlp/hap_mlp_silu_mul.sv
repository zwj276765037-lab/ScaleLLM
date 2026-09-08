`timescale 1ns / 1ps

// One-element-per-cycle SiLU(gate) * up leaf for the Llama SwiGLU MLP.
//
// Input gate/up are S24 Q8.16 projection boundaries.  SiLU uses a 2^-8-step
// table only on (-16,+16); x<=-16 returns zero and x>=+16 returns x.  The
// product is rounded half away from zero from S48 Q16.32 to S32 Q16.16.
// This leaf deliberately does not saturate the S32 product to S24.
//
// The mathematical LUT has 8193 samples, including both -16 and +16.  Only
// samples 0..8191 are stored: rounded address 8192 is exactly +16 Q8.16 and
// is supplied as a constant.  Keeping the physical ROM at 8192 words avoids
// doubling the BRAM depth for one endpoint.  A local input register separates
// the upstream tile-select mux from the ROM address arithmetic.  The ROM and
// multiply are subsequent synchronous pipeline stages.  A single clock-enable
// stalls the complete four-stage pipe under output backpressure without losing
// alignment; after filling it still accepts and produces one element/cycle.
module hap_mlp_silu_mul #(
    parameter LUT_FILE = "data/mlp_silu_q16.mem"
) (
    input  wire                 clk,
    input  wire                 rst_n,
    input  wire                 clear,
    input  wire                 in_valid,
    output wire                 in_ready,
    input  wire signed [23:0]   gate_s24,
    input  wire signed [23:0]   up_s24,
    output reg                  out_valid,
    input  wire                 out_ready,
    output reg signed [31:0]    out_product_s32
);

    localparam signed [24:0] NEGATIVE_ZERO_Q16 = -25'sd1048576;
    localparam signed [24:0] POSITIVE_BYPASS_Q16 = 25'sd1048576;

    (* rom_style = "block", ram_style = "block" *)
    reg signed [23:0] silu_rom [0:8191];
    initial $readmemh(LUT_FILE, silu_rom);

    // Intentional timing boundary: in the cohort frontend, gate_s24/up_s24 are
    // selected from a 16x16 tile by issue_pair_r.  Registering that selection
    // keeps its large variable mux out of the fixed-site BRAM address path.
    reg signed [23:0] input_gate_r;
    reg signed [23:0] input_up_r;
    reg               input_valid_r;

    wire signed [24:0] gate_ext = {input_gate_r[23], input_gate_r};
    wire gate_zero = gate_ext <= NEGATIVE_ZERO_Q16;
    wire gate_bypass = gate_ext >= POSITIVE_BYPASS_Q16;
    wire [24:0] gate_offset = gate_ext + 25'sd1048576;
    wire [13:0] rounded_address = (gate_offset + 25'd128) >> 8;
    wire gate_top_entry = !gate_zero && !gate_bypass &&
        (rounded_address >= 14'd8192);
    wire [12:0] lut_address = (gate_zero || gate_bypass || gate_top_entry) ?
        13'd0 : rounded_address[12:0];

    reg signed [23:0] rom_q;
    reg signed [23:0] s0_gate;
    reg signed [23:0] s0_up;
    reg               s0_zero;
    reg               s0_bypass;
    reg               s0_top_entry;
    reg               s0_valid;
    reg signed [47:0] s1_product;
    reg               s1_valid;

    wire signed [23:0] s0_silu = s0_zero ? 24'sd0 :
        s0_bypass ? s0_gate :
        s0_top_entry ? 24'sd1048576 : rom_q;
    wire signed [47:0] s0_product = s0_silu * s0_up;

    function automatic signed [31:0] round_q32_to_q16;
        input signed [47:0] value;
        reg signed [48:0] extended;
        reg [48:0] magnitude;
        reg signed [48:0] rounded;
        begin
            extended = {value[47], value};
            if (!value[47]) begin
                rounded = (extended + 49'sd32768) >>> 16;
            end else begin
                magnitude = -extended;
                rounded = -$signed((magnitude + 49'd32768) >> 16);
            end
            round_q32_to_q16 = rounded[31:0];
        end
    endfunction

    // Global pipeline enable.  This creates one local ready boundary and
    // permits one accepted/output element per cycle when the sink drains.
    wire pipe_advance = !out_valid || out_ready;
    assign in_ready = pipe_advance;

    // No reset is applied to ROM data.  Valid state makes its initial value a
    // don't-care and preserves synchronous block-ROM inference.
    always @(posedge clk) begin
        if (pipe_advance)
            rom_q <= silu_rom[lut_address];
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            input_valid_r <= 1'b0;
            s0_valid <= 1'b0;
            s1_valid <= 1'b0;
            out_valid <= 1'b0;
        end else if (clear) begin
            input_valid_r <= 1'b0;
            s0_valid <= 1'b0;
            s1_valid <= 1'b0;
            out_valid <= 1'b0;
        end else if (pipe_advance) begin
            input_valid_r <= in_valid;
            s0_valid <= input_valid_r;
            s1_valid <= s0_valid;
            out_valid <= s1_valid;

            if (in_valid) begin
                input_gate_r <= gate_s24;
                input_up_r <= up_s24;
            end
            if (input_valid_r) begin
                s0_gate <= input_gate_r;
                s0_up <= input_up_r;
                s0_zero <= gate_zero;
                s0_bypass <= gate_bypass;
                s0_top_entry <= gate_top_entry;
            end
            if (s0_valid)
                s1_product <= s0_product;
            if (s1_valid)
                out_product_s32 <= round_q32_to_q16(s1_product);
        end
    end

endmodule
