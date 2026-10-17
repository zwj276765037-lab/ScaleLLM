`timescale 1ns / 1ps

// Two 8-row tensor banks expose one cohort16 DMA image without changing the
// row-major S24 format within either physical wave.
module hap_tensor24_input_buffer16_frozen (
    input  wire                 clk,
    input  wire                 rst_n,
    input  wire                 clear,
    input  wire                 wr_valid,
    output wire                 wr_ready,
    input  wire [12:0]          wr_addr,
    input  wire [255:0]         wr_data,
    input  wire                 load_start,
    output wire                 activation_valid,
    input  wire                 activation_ready,
    output wire                 activation_wave,
    output wire [6:0]           activation_group,
    output wire [8*32*24-1:0]  activation_s24,
    output wire                 busy,
    output wire                 error
);
    wire wr_bank = wr_addr >= 13'd3072;
    wire wr_addr_legal = wr_addr < 13'd6144;
    wire [11:0] wr_local_addr = wr_bank ?
        wr_addr - 13'd3072 : wr_addr[11:0];

    wire wave0_wr_ready;
    wire wave1_wr_ready;
    wire wave0_valid;
    wire wave1_valid;
    wire [6:0] wave0_group;
    wire [6:0] wave1_group;
    wire [8*32*24-1:0] wave0_s24;
    wire [8*32*24-1:0] wave1_s24;
    wire wave0_busy;
    wire wave1_busy;
    wire wave0_error;
    wire wave1_error;

    reg emit_wave_r;
    reg [6:0] expected_group_r;
    reg control_error_r;
    wire selected_valid = emit_wave_r ? wave1_valid : wave0_valid;
    wire [6:0] selected_group = emit_wave_r ? wave1_group : wave0_group;
    wire [8*32*24-1:0] selected_s24 = emit_wave_r ?
        wave1_s24 : wave0_s24;
    wire activation_fire = activation_valid && activation_ready;

    assign wr_ready = wr_addr_legal &&
        (wr_bank ? wave1_wr_ready : wave0_wr_ready);
    assign activation_valid = selected_valid;
    assign activation_wave = emit_wave_r;
    assign activation_group = selected_group;
    assign activation_s24 = selected_s24;
    assign busy = wave0_busy || wave1_busy;
    assign error = control_error_r || wave0_error || wave1_error;

    hap_tensor24_input_buffer_frozen u_wave0 (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .wr_valid(wr_valid && wr_addr_legal && !wr_bank),
        .wr_ready(wave0_wr_ready), .wr_addr(wr_local_addr),
        .wr_data(wr_data), .load_start(load_start),
        .activation_valid(wave0_valid),
        .activation_ready(activation_ready && !emit_wave_r),
        .activation_group(wave0_group), .activation_s24(wave0_s24),
        .busy(wave0_busy), .error(wave0_error)
    );

    hap_tensor24_input_buffer_frozen u_wave1 (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .wr_valid(wr_valid && wr_addr_legal && wr_bank),
        .wr_ready(wave1_wr_ready), .wr_addr(wr_local_addr),
        .wr_data(wr_data), .load_start(load_start),
        .activation_valid(wave1_valid),
        .activation_ready(activation_ready && emit_wave_r),
        .activation_group(wave1_group), .activation_s24(wave1_s24),
        .busy(wave1_busy), .error(wave1_error)
    );

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            emit_wave_r <= 1'b0;
            expected_group_r <= 7'd0;
            control_error_r <= 1'b0;
        end else if (clear) begin
            emit_wave_r <= 1'b0;
            expected_group_r <= 7'd0;
            control_error_r <= 1'b0;
        end else begin
            if (load_start) begin
                emit_wave_r <= 1'b0;
                expected_group_r <= 7'd0;
                if (busy)
                    control_error_r <= 1'b1;
            end
            if (activation_fire) begin
                if (selected_group != expected_group_r)
                    control_error_r <= 1'b1;
                if (expected_group_r == 7'd127) begin
                    expected_group_r <= 7'd0;
                    if (!emit_wave_r)
                        emit_wave_r <= 1'b1;
                    else
                        emit_wave_r <= 1'b0;
                end else begin
                    expected_group_r <= expected_group_r + 1'b1;
                end
            end
            if (wr_valid && !wr_addr_legal)
                control_error_r <= 1'b1;
        end
    end
endmodule
