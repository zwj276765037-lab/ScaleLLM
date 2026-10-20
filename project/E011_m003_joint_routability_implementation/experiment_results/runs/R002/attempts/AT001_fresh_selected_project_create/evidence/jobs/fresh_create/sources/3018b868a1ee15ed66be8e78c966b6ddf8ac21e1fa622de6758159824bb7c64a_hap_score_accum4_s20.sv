`timescale 1ns / 1ps

module hap_score_accum4_s20 (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  clear,
    input  wire                  in_valid,
    output wire                  in_ready,
    input  wire                  in_first_group,
    input  wire                  in_last_group,
    input  wire                  in_mask,
    input  wire signed [34:0]    in_group_q14_s35,
    output wire                  out_valid,
    input  wire                  out_ready,
    output wire signed [19:0]    out_score_q14_s20,
    output wire                  out_mask,
    output reg  [31:0]           input_group_count,
    output reg  [31:0]           output_score_count,
    output reg  [31:0]           clip_count,
    output reg                   error
);

    reg signed [36:0] accum_s37_r;
    reg [2:0] group_count_r;
    reg current_mask_r;
    reg out_valid_r;
    reg signed [19:0] out_score_s20_r;
    reg out_mask_r;

    wire in_fire = in_valid && in_ready;
    wire out_fire = out_valid && out_ready;
    wire signed [36:0] group_ext_s37 =
        {{2{in_group_q14_s35[34]}}, in_group_q14_s35};
    wire signed [36:0] next_accum_s37 = in_first_group ?
        group_ext_s37 : (accum_s37_r + group_ext_s37);

    assign in_ready = rst_n && !clear && (!out_valid_r || out_ready);
    assign out_valid = rst_n && !clear && out_valid_r;
    assign out_score_q14_s20 = out_score_s20_r;
    assign out_mask = out_mask_r;

    function automatic signed [19:0] clip_score_s37_to_s20;
        input signed [36:0] value;
        begin
            if (value > 37'sd262144)
                clip_score_s37_to_s20 = 20'sd262144;
            else if (value < -37'sd262144)
                clip_score_s37_to_s20 = -20'sd262144;
            else
                clip_score_s37_to_s20 = value[19:0];
        end
    endfunction

    function automatic score_s37_clips;
        input signed [36:0] value;
        begin
            score_s37_clips = (value > 37'sd262144) ||
                (value < -37'sd262144);
        end
    endfunction

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            accum_s37_r <= 37'sd0;
            group_count_r <= 3'd0;
            current_mask_r <= 1'b0;
            out_valid_r <= 1'b0;
            out_score_s20_r <= 20'sd0;
            out_mask_r <= 1'b0;
            input_group_count <= 32'd0;
            output_score_count <= 32'd0;
            clip_count <= 32'd0;
            error <= 1'b0;
        end else if (clear) begin
            accum_s37_r <= 37'sd0;
            group_count_r <= 3'd0;
            current_mask_r <= 1'b0;
            out_valid_r <= 1'b0;
            input_group_count <= 32'd0;
            output_score_count <= 32'd0;
            clip_count <= 32'd0;
            error <= 1'b0;
        end else begin
            if (out_fire) begin
                out_valid_r <= 1'b0;
                output_score_count <= output_score_count + 32'd1;
            end
            if (in_fire) begin
                input_group_count <= input_group_count + 32'd1;
                accum_s37_r <= next_accum_s37;
                if (in_first_group) begin
                    group_count_r <= 3'd1;
                    current_mask_r <= in_mask;
                    if (in_last_group)
                        error <= 1'b1;
                end else begin
                    group_count_r <= group_count_r + 3'd1;
                    if (in_mask != current_mask_r)
                        error <= 1'b1;
                end
                if (in_last_group) begin
                    if (group_count_r != 3)
                        error <= 1'b1;
                    out_score_s20_r <= clip_score_s37_to_s20(next_accum_s37);
                    out_mask_r <= current_mask_r;
                    out_valid_r <= 1'b1;
                    if (score_s37_clips(next_accum_s37))
                        clip_count <= clip_count + 32'd1;
                    group_count_r <= 3'd0;
                end
                if (!in_first_group && (group_count_r == 0))
                    error <= 1'b1;
            end
        end
    end

endmodule
