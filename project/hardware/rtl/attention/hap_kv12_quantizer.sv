`timescale 1ns / 1ps

module hap_kv12_quantizer (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  clear,
    input  wire                  in_valid,
    output wire                  in_ready,
    input  wire [32*24-1:0]      in_s24,
    output wire                  out_valid,
    input  wire                  out_ready,
    output wire [32*12-1:0]      out_s12,
    output wire [15:0]           out_meta,
    output reg  [31:0]           input_group_count,
    output reg  [31:0]           output_group_count,
    output reg  [31:0]           clip_count,
    output reg  [31:0]           cycle_count,
    output reg                   error
);

    localparam [3:0] ST_IDLE        = 4'd0;
    localparam [3:0] ST_MAX_SCAN    = 4'd1;
    localparam [3:0] ST_SCALE_INIT  = 4'd2;
    localparam [3:0] ST_SCALE_SCAN  = 4'd3;
    localparam [3:0] ST_SCALE_START = 4'd4;
    localparam [3:0] ST_SCALE_WAIT  = 4'd5;
    localparam [3:0] ST_QUANT_PREP  = 4'd6;
    localparam [3:0] ST_QUANT_START = 4'd7;
    localparam [3:0] ST_QUANT_WAIT  = 4'd8;
    localparam [3:0] ST_OUTPUT      = 4'd9;

    localparam [27:0] SCALE_DENOM = 28'd134152192;
    localparam [26:0] SCALE_HALF = 27'd67076096;
    localparam [35:0] SCALE_THRESHOLD = 36'd34275885055;

    reg [3:0] state_r;
    reg [5:0] scan_lane_r;
    reg [5:0] quant_base_r;
    reg [5:0] scale_shift_r;
    reg [7:0] scale_code_r;
    reg [23:0] max_abs_r;
    reg [35:0] shifted_scale_r;
    reg signed [23:0] source_mem [0:31];
    reg [383:0] quant_data_r;

    reg scale_div_start_r;
    wire scale_div_done_w;
    wire scale_div_error_w;
    wire [8:0] scale_div_quotient_w;

    reg [7:0] quant_div_start_r;
    reg [7:0] quant_div_active_r;
    reg [8*35-1:0] quant_numerator_r;
    reg [7:0] quant_negative_r;
    wire [7:0] quant_div_done_w;
    wire [7:0] quant_div_error_w;
    wire [8*12-1:0] quant_quotient_w;

    wire in_fire = in_valid && in_ready;
    wire out_fire = out_valid && out_ready;
    wire quant_batch_done = &((~quant_div_active_r) | quant_div_done_w);
    wire quant_batch_error = |(quant_div_active_r & quant_div_error_w);

    assign in_ready = rst_n && !clear && (state_r == ST_IDLE);
    assign out_valid = rst_n && !clear && (state_r == ST_OUTPUT);
    assign out_s12 = quant_data_r;
    assign out_meta = (max_abs_r == 0) ? 16'd0 :
        {2'b00, scale_shift_r, scale_code_r};

    function automatic [23:0] abs_s24;
        input signed [23:0] value;
        begin
            abs_s24 = value[23] ? -$signed({value[23], value}) : value;
        end
    endfunction

    function automatic [34:0] quant_numerator;
        input signed [23:0] value;
        input [23:0] max_abs;
        reg [23:0] magnitude;
        begin
            magnitude = abs_s24(value);
            quant_numerator = ({11'd0, magnitude} << 11) -
                {11'd0, magnitude} + {12'd0, max_abs[23:1]};
        end
    endfunction

    hap_unsigned_div_seq #(
        .NUM_W(36), .DEN_W(28), .QUOT_W(9)
    ) u_scale_div (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .start(scale_div_start_r),
        .numerator(shifted_scale_r + SCALE_HALF),
        .denominator(SCALE_DENOM), .busy(),
        .done(scale_div_done_w), .error(scale_div_error_w),
        .quotient(scale_div_quotient_w)
    );

    genvar div_lane;
    generate
        for (div_lane = 0; div_lane < 8; div_lane = div_lane + 1) begin : g_div
            hap_unsigned_div_seq #(
                .NUM_W(35), .DEN_W(24), .QUOT_W(12)
            ) u_quant_div (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .start(quant_div_start_r[div_lane]),
                .numerator(quant_numerator_r[div_lane*35 +: 35]),
                .denominator(max_abs_r), .busy(),
                .done(quant_div_done_w[div_lane]),
                .error(quant_div_error_w[div_lane]),
                .quotient(quant_quotient_w[div_lane*12 +: 12])
            );
        end
    endgenerate

    integer lane;
    integer output_lane;
    reg [23:0] magnitude;
    reg [11:0] quotient_magnitude;
    reg signed [12:0] signed_quant;
    always @(posedge clk) begin
        if (in_fire) begin
            for (lane = 0; lane < 32; lane = lane + 1)
                source_mem[lane] <= in_s24[lane*24 +: 24];
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state_r <= ST_IDLE;
            scan_lane_r <= 6'd0;
            quant_base_r <= 6'd0;
            scale_shift_r <= 6'd0;
            scale_code_r <= 8'd0;
            max_abs_r <= 24'd0;
            shifted_scale_r <= 36'd0;
            quant_data_r <= '0;
            scale_div_start_r <= 1'b0;
            quant_div_start_r <= 8'd0;
            quant_div_active_r <= 8'd0;
            quant_numerator_r <= '0;
            quant_negative_r <= 8'd0;
            input_group_count <= 32'd0;
            output_group_count <= 32'd0;
            clip_count <= 32'd0;
            cycle_count <= 32'd0;
            error <= 1'b0;
        end else if (clear) begin
            state_r <= ST_IDLE;
            scan_lane_r <= 6'd0;
            quant_base_r <= 6'd0;
            scale_shift_r <= 6'd0;
            scale_code_r <= 8'd0;
            max_abs_r <= 24'd0;
            shifted_scale_r <= 36'd0;
            quant_data_r <= '0;
            scale_div_start_r <= 1'b0;
            quant_div_start_r <= 8'd0;
            quant_div_active_r <= 8'd0;
            input_group_count <= 32'd0;
            output_group_count <= 32'd0;
            clip_count <= 32'd0;
            cycle_count <= 32'd0;
            error <= 1'b0;
        end else begin
            scale_div_start_r <= 1'b0;
            quant_div_start_r <= 8'd0;
            if (state_r != ST_IDLE && state_r != ST_OUTPUT)
                cycle_count <= cycle_count + 32'd1;

            case (state_r)
                ST_IDLE: begin
                    if (in_fire) begin
                        input_group_count <= input_group_count + 32'd1;
                        scan_lane_r <= 6'd0;
                        max_abs_r <= 24'd0;
                        quant_data_r <= '0;
                        state_r <= ST_MAX_SCAN;
                    end
                end
                ST_MAX_SCAN: begin
                    magnitude = abs_s24(source_mem[scan_lane_r]);
                    if (magnitude > max_abs_r)
                        max_abs_r <= magnitude;
                    if (scan_lane_r == 31)
                        state_r <= ST_SCALE_INIT;
                    else
                        scan_lane_r <= scan_lane_r + 1'b1;
                end
                ST_SCALE_INIT: begin
                    if (max_abs_r == 0) begin
                        scale_code_r <= 8'd0;
                        scale_shift_r <= 6'd0;
                        state_r <= ST_OUTPUT;
                    end else begin
                        scale_shift_r <= 6'd8;
                        shifted_scale_r <= {4'd0, max_abs_r, 8'd0};
                        state_r <= ST_SCALE_SCAN;
                    end
                end
                ST_SCALE_SCAN: begin
                    if ((scale_shift_r == 32) ||
                        ((shifted_scale_r << 1) > SCALE_THRESHOLD)) begin
                        state_r <= ST_SCALE_START;
                    end else begin
                        shifted_scale_r <= shifted_scale_r << 1;
                        scale_shift_r <= scale_shift_r + 1'b1;
                    end
                end
                ST_SCALE_START: begin
                    scale_div_start_r <= 1'b1;
                    state_r <= ST_SCALE_WAIT;
                end
                ST_SCALE_WAIT: begin
                    if (scale_div_done_w) begin
                        scale_code_r <= scale_div_quotient_w[7:0];
                        if (scale_div_error_w ||
                            (scale_div_quotient_w == 0) ||
                            (scale_div_quotient_w > 255))
                            error <= 1'b1;
                        quant_base_r <= 6'd0;
                        state_r <= ST_QUANT_PREP;
                    end
                end
                ST_QUANT_PREP: begin
                    quant_div_active_r <= 8'hff;
                    for (lane = 0; lane < 8; lane = lane + 1) begin
                        quant_numerator_r[lane*35 +: 35] <= quant_numerator(
                            source_mem[quant_base_r + lane], max_abs_r);
                        quant_negative_r[lane] <=
                            source_mem[quant_base_r + lane][23];
                    end
                    state_r <= ST_QUANT_START;
                end
                ST_QUANT_START: begin
                    quant_div_start_r <= quant_div_active_r;
                    state_r <= ST_QUANT_WAIT;
                end
                ST_QUANT_WAIT: begin
                    if (quant_batch_done) begin
                        if (quant_batch_error)
                            error <= 1'b1;
                        for (lane = 0; lane < 8; lane = lane + 1) begin
                            output_lane = quant_base_r + lane;
                            quotient_magnitude =
                                quant_quotient_w[lane*12 +: 12];
                            if (quotient_magnitude > 2047) begin
                                quotient_magnitude = 12'd2047;
                                clip_count <= clip_count + 32'd1;
                            end
                            signed_quant = quant_negative_r[lane] ?
                                -$signed({1'b0, quotient_magnitude}) :
                                $signed({1'b0, quotient_magnitude});
                            quant_data_r[output_lane*12 +: 12] <=
                                signed_quant[11:0];
                        end
                        if (quant_base_r == 24) begin
                            state_r <= ST_OUTPUT;
                        end else begin
                            quant_base_r <= quant_base_r + 6'd8;
                            state_r <= ST_QUANT_PREP;
                        end
                    end
                end
                ST_OUTPUT: begin
                    if (out_fire) begin
                        output_group_count <= output_group_count + 32'd1;
                        state_r <= ST_IDLE;
                    end
                end
                default: begin
                    state_r <= ST_IDLE;
                    error <= 1'b1;
                end
            endcase
        end
    end

endmodule
