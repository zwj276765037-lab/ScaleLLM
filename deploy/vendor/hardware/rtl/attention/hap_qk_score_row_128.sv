`timescale 1ns / 1ps

module hap_qk_score_row_128 (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  clear,
    input  wire                  query_load_valid,
    output wire                  query_load_ready,
    input  wire [1:0]            query_load_group,
    input  wire [32*24-1:0]      query_load_s24,
    output wire                  query_ready,
    input  wire                  in_valid,
    output wire                  in_ready,
    input  wire                  in_first_key,
    input  wire                  in_last_key,
    input  wire [1:0]            in_group,
    input  wire                  in_mask,
    input  wire [32*12-1:0]      in_key_s12,
    input  wire [15:0]           in_key_meta16,
    output wire                  out_valid,
    input  wire                  out_ready,
    output wire signed [19:0]    out_score_q14_s20,
    output wire                  out_mask,
    output wire [6:0]            out_key_index,
    output wire                  out_last_key,
    output reg  [31:0]           input_group_count,
    output reg  [31:0]           output_score_count,
    output wire [31:0]           clip_count,
    output wire                  error
);

    // Four head groups are explicit registers.  An unpacked 4-deep array is
    // otherwise inferred as asynchronous RAMD32, creating hundreds of very
    // short RAM-to-DSP hold paths in OOC implementation.
    reg [32*24-1:0] query_group0_r;
    reg [32*24-1:0] query_group1_r;
    reg [32*24-1:0] query_group2_r;
    reg [32*24-1:0] query_group3_r;
    reg [32*24-1:0] selected_query_s24;
    reg [3:0] query_loaded_r;
    reg [6:0] input_key_index_r;
    reg [7:0] output_key_index_r;
    reg [6:0] row_last_key_r;
    reg row_input_complete_r;
    reg control_error_r;

    wire dot_in_ready;
    wire dot_out_valid;
    wire dot_out_ready;
    wire signed [39:0] dot_s40;
    wire [31:0] dot_input_count_unused;
    wire [31:0] dot_output_count_unused;
    wire dot_error;
    wire scale_in_ready;
    wire scale_out_valid;
    wire scale_out_ready;
    wire signed [34:0] scaled_s35;
    wire [31:0] scale_input_count_unused;
    wire [31:0] scale_output_count_unused;
    wire scale_error;
    wire accum_in_ready;
    wire accum_out_valid;
    wire accum_out_mask;
    wire signed [19:0] accum_out_score;
    wire [31:0] accum_input_count_unused;
    wire [31:0] accum_output_count_unused;
    wire accum_error;
    wire input_fire = in_valid && in_ready;
    wire output_fire = out_valid && out_ready;

    always @* begin
        case (in_group)
            2'd0: selected_query_s24 = query_group0_r;
            2'd1: selected_query_s24 = query_group1_r;
            2'd2: selected_query_s24 = query_group2_r;
            default: selected_query_s24 = query_group3_r;
        endcase
    end

    reg tag_first_mem [0:15];
    reg tag_last_mem [0:15];
    reg tag_mask_mem [0:15];
    reg [7:0] tag_code_mem [0:15];
    reg [5:0] tag_shift_mem [0:15];
    reg [3:0] tag_wr_ptr_r;
    reg [3:0] tag_rd_ptr_r;
    reg [4:0] tag_count_r;
    wire tag_first = tag_first_mem[tag_rd_ptr_r];
    wire tag_last = tag_last_mem[tag_rd_ptr_r];
    wire tag_mask = tag_mask_mem[tag_rd_ptr_r];
    wire [7:0] tag_code = tag_code_mem[tag_rd_ptr_r];
    wire [5:0] tag_shift = tag_shift_mem[tag_rd_ptr_r];
    wire tag_pop = dot_out_valid && dot_out_ready;

    reg accum_tag_first_mem [0:15];
    reg accum_tag_last_mem [0:15];
    reg accum_tag_mask_mem [0:15];
    reg [3:0] accum_tag_wr_ptr_r;
    reg [3:0] accum_tag_rd_ptr_r;
    reg [4:0] accum_tag_count_r;
    wire accum_tag_first = accum_tag_first_mem[accum_tag_rd_ptr_r];
    wire accum_tag_last = accum_tag_last_mem[accum_tag_rd_ptr_r];
    wire accum_tag_mask = accum_tag_mask_mem[accum_tag_rd_ptr_r];
    wire scaled_fire = scale_out_valid && scale_out_ready;

    assign query_load_ready = rst_n && !clear &&
        !query_loaded_r[query_load_group];
    assign query_ready = &query_loaded_r;
    assign in_ready = rst_n && !clear && query_ready &&
        !row_input_complete_r && dot_in_ready &&
        (tag_count_r < 16) && !control_error_r;
    assign dot_out_ready = scale_in_ready && (tag_count_r != 0) &&
        (accum_tag_count_r < 16);
    assign scale_out_ready = accum_in_ready && (accum_tag_count_r != 0);
    assign out_valid = accum_out_valid;
    assign out_score_q14_s20 = accum_out_score;
    assign out_mask = accum_out_mask;
    assign out_key_index = output_key_index_r[6:0];
    assign out_last_key = output_key_index_r[6:0] == row_last_key_r;
    assign error = control_error_r | dot_error | scale_error | accum_error;

    hap_q24k12_group_dot_s40 u_dot (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(input_fire), .in_ready(dot_in_ready),
        .in_query_s24(selected_query_s24), .in_key_s12(in_key_s12),
        .out_valid(dot_out_valid), .out_ready(dot_out_ready),
        .out_dot_s40(dot_s40), .input_group_count(dot_input_count_unused),
        .output_group_count(dot_output_count_unused), .error(dot_error)
    );

    hap_score_group_scale_s35 u_scale (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(tag_pop), .in_ready(scale_in_ready),
        .in_dot_s40(dot_s40), .in_key_code(tag_code),
        .in_key_shift(tag_shift), .out_valid(scale_out_valid),
        .out_ready(scale_out_ready), .out_group_q14_s35(scaled_s35),
        .input_group_count(scale_input_count_unused),
        .output_group_count(scale_output_count_unused), .error(scale_error)
    );

    hap_score_accum4_s20 u_accum (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(scale_out_valid && (accum_tag_count_r != 0)),
        .in_ready(accum_in_ready),
        .in_first_group(accum_tag_first), .in_last_group(accum_tag_last),
        .in_mask(accum_tag_mask), .in_group_q14_s35(scaled_s35),
        .out_valid(accum_out_valid), .out_ready(out_ready),
        .out_score_q14_s20(accum_out_score), .out_mask(accum_out_mask),
        .input_group_count(accum_input_count_unused),
        .output_score_count(accum_output_count_unused),
        .clip_count(clip_count), .error(accum_error)
    );

    always @(posedge clk) begin
        if (query_load_valid && query_load_ready) begin
            case (query_load_group)
                2'd0: query_group0_r <= query_load_s24;
                2'd1: query_group1_r <= query_load_s24;
                2'd2: query_group2_r <= query_load_s24;
                default: query_group3_r <= query_load_s24;
            endcase
        end
        if (input_fire) begin
            tag_first_mem[tag_wr_ptr_r] <= in_group == 0;
            tag_last_mem[tag_wr_ptr_r] <= in_group == 3;
            tag_mask_mem[tag_wr_ptr_r] <= in_mask;
            tag_code_mem[tag_wr_ptr_r] <= in_key_meta16[7:0];
            tag_shift_mem[tag_wr_ptr_r] <= in_key_meta16[13:8];
        end
        if (tag_pop) begin
            accum_tag_first_mem[accum_tag_wr_ptr_r] <= tag_first;
            accum_tag_last_mem[accum_tag_wr_ptr_r] <= tag_last;
            accum_tag_mask_mem[accum_tag_wr_ptr_r] <= tag_mask;
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            query_loaded_r <= 4'd0;
            input_key_index_r <= 7'd0;
            output_key_index_r <= 8'd0;
            row_last_key_r <= 7'd127;
            row_input_complete_r <= 1'b0;
            tag_wr_ptr_r <= 4'd0;
            tag_rd_ptr_r <= 4'd0;
            tag_count_r <= 5'd0;
            accum_tag_wr_ptr_r <= 4'd0;
            accum_tag_rd_ptr_r <= 4'd0;
            accum_tag_count_r <= 5'd0;
            input_group_count <= 32'd0;
            output_score_count <= 32'd0;
            control_error_r <= 1'b0;
        end else if (clear) begin
            query_loaded_r <= 4'd0;
            input_key_index_r <= 7'd0;
            output_key_index_r <= 8'd0;
            row_last_key_r <= 7'd127;
            row_input_complete_r <= 1'b0;
            tag_wr_ptr_r <= 4'd0;
            tag_rd_ptr_r <= 4'd0;
            tag_count_r <= 5'd0;
            accum_tag_wr_ptr_r <= 4'd0;
            accum_tag_rd_ptr_r <= 4'd0;
            accum_tag_count_r <= 5'd0;
            input_group_count <= 32'd0;
            output_score_count <= 32'd0;
            control_error_r <= 1'b0;
        end else begin
            if (query_load_valid && query_load_ready)
                query_loaded_r[query_load_group] <= 1'b1;
            if (input_fire) begin
                tag_wr_ptr_r <= tag_wr_ptr_r + 1'b1;
                input_group_count <= input_group_count + 32'd1;
                if (in_first_key != ((input_key_index_r == 0) &&
                    (in_group == 0)) ||
                    (in_last_key && (in_group != 3)) ||
                    in_key_meta16[15:14] != 0 ||
                    ((in_key_meta16[7:0] == 0) &&
                        (in_key_meta16[13:8] != 0)) ||
                    ((in_key_meta16[7:0] != 0) &&
                        ((in_key_meta16[13:8] < 8) ||
                         (in_key_meta16[13:8] > 32))))
                    control_error_r <= 1'b1;
                if (in_group == 3)
                    input_key_index_r <= input_key_index_r + 1'b1;
                if (in_last_key) begin
                    row_last_key_r <= input_key_index_r;
                    row_input_complete_r <= 1'b1;
                end
            end
            if (tag_pop)
                tag_rd_ptr_r <= tag_rd_ptr_r + 1'b1;
            case ({input_fire, tag_pop})
                2'b10: tag_count_r <= tag_count_r + 1'b1;
                2'b01: tag_count_r <= tag_count_r - 1'b1;
                default: tag_count_r <= tag_count_r;
            endcase
            if (tag_pop)
                accum_tag_wr_ptr_r <= accum_tag_wr_ptr_r + 1'b1;
            if (scaled_fire)
                accum_tag_rd_ptr_r <= accum_tag_rd_ptr_r + 1'b1;
            case ({tag_pop, scaled_fire})
                2'b10: accum_tag_count_r <= accum_tag_count_r + 1'b1;
                2'b01: accum_tag_count_r <= accum_tag_count_r - 1'b1;
                default: accum_tag_count_r <= accum_tag_count_r;
            endcase
            if (output_fire) begin
                output_score_count <= output_score_count + 32'd1;
                if (out_last_key) begin
                    output_key_index_r <= 8'd0;
                    input_key_index_r <= 7'd0;
                    row_input_complete_r <= 1'b0;
                    query_loaded_r <= 4'd0;
                end else begin
                    output_key_index_r <= output_key_index_r + 1'b1;
                end
            end
            if ((tag_count_r > 16) || (accum_tag_count_r > 16) ||
                (scale_out_valid && (accum_tag_count_r == 0)))
                control_error_r <= 1'b1;
        end
    end

endmodule
