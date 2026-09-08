`timescale 1ns / 1ps

// Assemble two 512-bit beats into one channel's eight-column W4 half-group.
module hap_w4_halfgroup2_assembler (
    input  wire          clk,
    input  wire          rst_n,
    input  wire          clear,
    input  wire          beat_valid,
    output wire          beat_ready,
    input  wire [511:0]  beat_data,
    input  wire          beat_group_last,
    output wire          half_valid,
    input  wire          half_ready,
    output wire [1023:0] half_data,
    output reg  [31:0]   beat_count,
    output reg  [31:0]   half_count,
    output reg           error
);

    reg first_valid_r;
    reg [511:0] first_data_r;
    reg half_valid_r;
    reg [1023:0] half_data_r;
    wire output_capacity = !half_valid_r || half_ready;
    wire beat_fire = beat_valid && beat_ready;
    wire half_fire = half_valid && half_ready;

    assign beat_ready = rst_n && !clear &&
        (!first_valid_r || output_capacity);
    assign half_valid = rst_n && !clear && half_valid_r;
    assign half_data = half_data_r;

    always @(posedge clk) begin
        if (!rst_n || clear) begin
            first_valid_r <= 1'b0;
            half_valid_r <= 1'b0;
            beat_count <= 32'd0;
            half_count <= 32'd0;
            error <= 1'b0;
        end else begin
            if (half_fire)
                half_valid_r <= 1'b0;
            if (beat_fire) begin
                beat_count <= beat_count + 32'd1;
                if (!first_valid_r) begin
                    first_valid_r <= 1'b1;
                    first_data_r <= beat_data;
                    if (beat_group_last)
                        error <= 1'b1;
                end else begin
                    first_valid_r <= 1'b0;
                    half_valid_r <= 1'b1;
                    half_data_r <= {beat_data, first_data_r};
                    if (!beat_group_last)
                        error <= 1'b1;
                end
            end
            if (half_fire)
                half_count <= half_count + 32'd1;
        end
    end

endmodule
