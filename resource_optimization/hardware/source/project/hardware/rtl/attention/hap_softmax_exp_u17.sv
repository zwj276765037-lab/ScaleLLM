`timescale 1ns / 1ps

module hap_softmax_exp_u17 #(
    parameter integer FIFO_DEPTH = 16
) (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  clear,
    input  wire                  in_valid,
    output wire                  in_ready,
    input  wire signed [18:0]    in_delta_q14_s19,
    output wire                  out_valid,
    input  wire                  out_ready,
    output wire [16:0]           out_exp_u17,
    output reg  [31:0]           input_count,
    output reg  [31:0]           output_count,
    output reg                   error
);

    localparam integer PTR_W = $clog2(FIFO_DEPTH);
    localparam integer COUNT_W = $clog2(FIFO_DEPTH + 1);

    (* rom_style = "distributed" *) reg [16:0] exp_lut_u17 [0:256];
    // Keep one repository-relative path for simulation, OOC synthesis and
    // board synthesis.  The manifest registers the same file; using a stale
    // basename here made Vivado silently synthesize an undriven ROM.
    initial $readmemh("data/softmax_exp_u17.mem", exp_lut_u17);

    reg address_valid_r;
    reg [8:0] address_index_r;
    reg [9:0] address_fraction_r;
    reg lookup_valid_r;
    reg [16:0] lookup_high_r;
    reg [16:0] lookup_low_r;
    reg [9:0] lookup_fraction_r;
    reg product_valid_r;
    (* use_dsp = "yes" *) reg [26:0] interpolation_product_r;
    reg [16:0] product_high_r;
    reg result_valid_r;
    reg [16:0] result_u17_r;

    (* ram_style = "distributed" *) reg [16:0]
        fifo_mem [0:FIFO_DEPTH-1];
    reg [PTR_W-1:0] fifo_wr_ptr_r;
    reg [PTR_W-1:0] fifo_rd_ptr_r;
    reg [COUNT_W-1:0] fifo_count_r;
    reg [COUNT_W-1:0] used_count_r;

    wire in_fire = in_valid && in_ready;
    wire out_fire = out_valid && out_ready;
    wire fifo_commit = result_valid_r &&
        ((fifo_count_r != FIFO_DEPTH) || out_fire);
    wire [18:0] input_magnitude = -in_delta_q14_s19;
    wire [17:0] lookup_difference =
        {1'b0, lookup_high_r} - {1'b0, lookup_low_r};

    assign in_ready = rst_n && !clear && (used_count_r < FIFO_DEPTH);
    assign out_valid = rst_n && !clear && (fifo_count_r != 0);
    assign out_exp_u17 = fifo_mem[fifo_rd_ptr_r];

    always @(posedge clk) begin
        if (in_fire) begin
            address_index_r <= input_magnitude[18:10];
            address_fraction_r <= input_magnitude[9:0];
        end
        if (address_valid_r) begin
            lookup_high_r <= exp_lut_u17[address_index_r];
            lookup_low_r <= (address_index_r == 256) ?
                exp_lut_u17[256] : exp_lut_u17[address_index_r + 1'b1];
            lookup_fraction_r <= address_fraction_r;
        end
        if (lookup_valid_r) begin
            interpolation_product_r <=
                lookup_difference * lookup_fraction_r;
            product_high_r <= lookup_high_r;
        end
        if (product_valid_r)
            result_u17_r <= product_high_r -
                ((interpolation_product_r + 27'd512) >> 10);
        if (fifo_commit)
            fifo_mem[fifo_wr_ptr_r] <= result_u17_r;
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            address_valid_r <= 1'b0;
            lookup_valid_r <= 1'b0;
            product_valid_r <= 1'b0;
            result_valid_r <= 1'b0;
            fifo_wr_ptr_r <= '0;
            fifo_rd_ptr_r <= '0;
            fifo_count_r <= '0;
            used_count_r <= '0;
            input_count <= 32'd0;
            output_count <= 32'd0;
            error <= 1'b0;
        end else if (clear) begin
            address_valid_r <= 1'b0;
            lookup_valid_r <= 1'b0;
            product_valid_r <= 1'b0;
            result_valid_r <= 1'b0;
            fifo_wr_ptr_r <= '0;
            fifo_rd_ptr_r <= '0;
            fifo_count_r <= '0;
            used_count_r <= '0;
            input_count <= 32'd0;
            output_count <= 32'd0;
            error <= 1'b0;
        end else begin
            address_valid_r <= in_fire;
            lookup_valid_r <= address_valid_r;
            product_valid_r <= lookup_valid_r;
            result_valid_r <= product_valid_r;
            if (in_fire) begin
                input_count <= input_count + 32'd1;
                if ((in_delta_q14_s19 > 0) ||
                    (in_delta_q14_s19 < -19'sd262144))
                    error <= 1'b1;
            end
            if (result_valid_r) begin
                if ((fifo_count_r == FIFO_DEPTH) && !out_fire)
                    error <= 1'b1;
                else
                    fifo_wr_ptr_r <= fifo_wr_ptr_r + 1'b1;
            end
            if (out_fire) begin
                fifo_rd_ptr_r <= fifo_rd_ptr_r + 1'b1;
                output_count <= output_count + 32'd1;
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
            $error("hap_softmax_exp_u17 FIFO_DEPTH must be 16");
    end

endmodule
