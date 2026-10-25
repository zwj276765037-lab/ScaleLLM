`timescale 1ns / 1ps

// Preserved local owners for the cohort16 Attention data path.  Keeping these
// stores out of the scheduler hierarchy gives physical planning complete RTL
// owners without changing any external tensor or DDR record.

(* KEEP_HIERARCHY = "yes" *)
module hap_attention_cohort16_query_store (
    input  wire                 clk,
    input  wire                 rst_n,
    input  wire                 clear,
    input  wire                 pair_valid,
    input  wire [8:0]           pair_index,
    input  wire [9:0]           projection_tile,
    input  wire signed [23:0]   pair_y0_s24,
    input  wire signed [23:0]   pair_y1_s24,
    input  wire                 read_addr_valid,
    input  wire                 read_data_valid,
    input  wire [3:0]           read_row,
    input  wire [4:0]           read_head,
    input  wire [1:0]           read_group,
    output reg  [767:0]         read_data_s24
);

    (* ram_style = "block" *) reg [191:0] query_mem_region0 [0:2047];
    (* ram_style = "block" *) reg [191:0] query_mem_region1 [0:2047];
    (* ram_style = "block" *) reg [191:0] query_mem_region2 [0:2047];
    (* ram_style = "block" *) reg [191:0] query_mem_region3 [0:2047];
    (* keep = "true", dont_touch = "yes" *)
    reg [10:0] read_addr_region_r [0:3];
    (* keep = "true", dont_touch = "yes" *)
    reg [10:0] write_addr_region_r [0:3];
    reg [767:0] write_word_buffer_r;
    reg [767:0] write_word_r;
    reg write_valid_r;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            write_valid_r <= 1'b0;
        else if (clear)
            write_valid_r <= 1'b0;
        else
            write_valid_r <= pair_valid && pair_index[3:0] == 4'd15;
    end

    always @(posedge clk) begin
        if (write_valid_r && rst_n && !clear) begin
            query_mem_region0[write_addr_region_r[0]] <= write_word_r[191:0];
            query_mem_region1[write_addr_region_r[1]] <= write_word_r[383:192];
            query_mem_region2[write_addr_region_r[2]] <= write_word_r[575:384];
            query_mem_region3[write_addr_region_r[3]] <= write_word_r[767:576];
        end

        if (pair_valid) begin
            write_word_buffer_r[pair_index[3:0]*48 +: 48] <=
                {pair_y1_s24, pair_y0_s24};
            if (pair_index[3:0] == 4'd15) begin
                write_word_r <= {
                    pair_y1_s24, pair_y0_s24, write_word_buffer_r[719:0]};
                write_addr_region_r[0] <=
                    pair_index[7:4]*128 + (projection_tile >> 3)*4 +
                    ((projection_tile & 10'd7) >> 1);
                write_addr_region_r[1] <=
                    pair_index[7:4]*128 + (projection_tile >> 3)*4 +
                    ((projection_tile & 10'd7) >> 1);
                write_addr_region_r[2] <=
                    pair_index[7:4]*128 + (projection_tile >> 3)*4 +
                    ((projection_tile & 10'd7) >> 1);
                write_addr_region_r[3] <=
                    pair_index[7:4]*128 + (projection_tile >> 3)*4 +
                    ((projection_tile & 10'd7) >> 1);
            end
        end

        if (read_addr_valid) begin
            read_addr_region_r[0] <= {read_row, read_head, read_group};
            read_addr_region_r[1] <= {read_row, read_head, read_group};
            read_addr_region_r[2] <= {read_row, read_head, read_group};
            read_addr_region_r[3] <= {read_row, read_head, read_group};
        end

        if (read_data_valid) begin
            read_data_s24[191:0] <= query_mem_region0[read_addr_region_r[0]];
            read_data_s24[383:192] <= query_mem_region1[read_addr_region_r[1]];
            read_data_s24[575:384] <= query_mem_region2[read_addr_region_r[2]];
            read_data_s24[767:576] <= query_mem_region3[read_addr_region_r[3]];
        end
    end

endmodule

(* KEEP_HIERARCHY = "yes" *)
module hap_attention_cohort16_postprocess_row_bank (
    input  wire                 clk,
    input  wire                 projection_capture_valid,
    input  wire                 projection_half,
    input  wire [383:0]         projection_half_s24,
    input  wire                 projection_post_capture_valid,
    input  wire                 rope_store_valid,
    input  wire [3:0]           rope_store_pair,
    input  wire [47:0]          rope_store_s24,
    input  wire [3:0]           rope_read_pair,
    output wire [47:0]          rope_read_s24,
    output wire [767:0]         post_group_s24
);

    reg [767:0] projection_pair_row_r;
    reg [767:0] post_group_s24_r;

    assign rope_read_s24 =
        projection_pair_row_r[rope_read_pair*48 +: 48];
    assign post_group_s24 = post_group_s24_r;

    always @(posedge clk) begin
        if (projection_capture_valid) begin
            if (!projection_half)
                projection_pair_row_r[0 +: 384] <= projection_half_s24;
            else
                projection_pair_row_r[384 +: 384] <= projection_half_s24;
        end

        if (projection_post_capture_valid)
            post_group_s24_r <= {
                projection_half_s24, projection_pair_row_r[0 +: 384]};

        if (rope_store_valid)
            post_group_s24_r[rope_store_pair*48 +: 48] <= rope_store_s24;
    end

endmodule

(* KEEP_HIERARCHY = "yes" *)
module hap_attention_cohort16_postprocess_store (
    input  wire                 clk,
    input  wire                 projection_capture_valid,
    input  wire [9:0]           projection_tile,
    input  wire                 projection_wave,
    input  wire [8*16*24-1:0]  projection_s24,
    input  wire                 rope_shift_valid,
    input  wire [3:0]           rope_input_row,
    input  wire                 rope_store_valid,
    input  wire [8:0]           rope_output_index,
    input  wire signed [23:0]   rope_y0_s24,
    input  wire signed [23:0]   rope_y1_s24,
    input  wire [3:0]           quant_row,
    output wire [47:0]          rope_input_pair_s24,
    output wire [4*768-1:0]     quant_s24
);

    reg [3:0] rope_read_pair_r;
    wire [47:0] rope_pair_by_row [0:15];
    wire [767:0] post_group_by_row [0:15];
    reg [47:0] rope_input_pair_s24_r;
    reg [4*768-1:0] quant_s24_r;

    genvar row_index;
    generate for (row_index = 0; row_index < 16; row_index = row_index + 1) begin : g_row_bank
        localparam integer LOCAL_ROW = row_index % 8;
        localparam WAVE = row_index >= 8;
        localparam [3:0] ROW_TAG = row_index;
        wire row_projection_capture = projection_capture_valid &&
            (projection_wave == WAVE);

        hap_attention_cohort16_postprocess_row_bank u_bank (
            .clk(clk),
            .projection_capture_valid(row_projection_capture),
            .projection_half(projection_tile[0]),
            .projection_half_s24(
                projection_s24[LOCAL_ROW*384 +: 384]),
            .projection_post_capture_valid(row_projection_capture &&
                projection_tile[0] && projection_tile >= 10'd320),
            .rope_store_valid(rope_store_valid &&
                rope_output_index[7:4] == ROW_TAG),
            .rope_store_pair(rope_output_index[3:0]),
            .rope_store_s24({rope_y1_s24, rope_y0_s24}),
            .rope_read_pair(rope_read_pair_r),
            .rope_read_s24(rope_pair_by_row[row_index]),
            .post_group_s24(post_group_by_row[row_index])
        );
    end endgenerate

    always @(posedge clk) begin
        if (projection_capture_valid && projection_tile[0])
            rope_read_pair_r <= 4'd0;
        else if (rope_shift_valid)
            rope_read_pair_r <= rope_read_pair_r + 1'b1;
    end

    always @* begin
        case (rope_input_row)
            4'd0: rope_input_pair_s24_r = rope_pair_by_row[0];
            4'd1: rope_input_pair_s24_r = rope_pair_by_row[1];
            4'd2: rope_input_pair_s24_r = rope_pair_by_row[2];
            4'd3: rope_input_pair_s24_r = rope_pair_by_row[3];
            4'd4: rope_input_pair_s24_r = rope_pair_by_row[4];
            4'd5: rope_input_pair_s24_r = rope_pair_by_row[5];
            4'd6: rope_input_pair_s24_r = rope_pair_by_row[6];
            4'd7: rope_input_pair_s24_r = rope_pair_by_row[7];
            4'd8: rope_input_pair_s24_r = rope_pair_by_row[8];
            4'd9: rope_input_pair_s24_r = rope_pair_by_row[9];
            4'd10: rope_input_pair_s24_r = rope_pair_by_row[10];
            4'd11: rope_input_pair_s24_r = rope_pair_by_row[11];
            4'd12: rope_input_pair_s24_r = rope_pair_by_row[12];
            4'd13: rope_input_pair_s24_r = rope_pair_by_row[13];
            4'd14: rope_input_pair_s24_r = rope_pair_by_row[14];
            default: rope_input_pair_s24_r = rope_pair_by_row[15];
        endcase
    end

    always @* begin
        case (quant_row)
            4'd0: quant_s24_r = {
                post_group_by_row[3], post_group_by_row[2],
                post_group_by_row[1], post_group_by_row[0]};
            4'd4: quant_s24_r = {
                post_group_by_row[7], post_group_by_row[6],
                post_group_by_row[5], post_group_by_row[4]};
            4'd8: quant_s24_r = {
                post_group_by_row[11], post_group_by_row[10],
                post_group_by_row[9], post_group_by_row[8]};
            default: quant_s24_r = {
                post_group_by_row[15], post_group_by_row[14],
                post_group_by_row[13], post_group_by_row[12]};
        endcase
    end

    assign rope_input_pair_s24 = rope_input_pair_s24_r;
    assign quant_s24 = quant_s24_r;

endmodule

(* KEEP_HIERARCHY = "yes" *)
module hap_attention_cohort16_context_store (
    input  wire                 clk,
    input  wire                 rst_n,
    input  wire                 clear,
    input  wire                 row_write_valid,
    input  wire [3:0]           row_write_row,
    input  wire [4:0]           row_write_head,
    input  wire [2:0]           row_write_tile,
    input  wire [383:0]         row_write_s24,
    input  wire                 read_issue,
    input  wire                 read_wave,
    input  wire [3:0]           read_slot,
    input  wire [6:0]           read_group,
    output wire [8*32*24-1:0]  activation_s24
);

    // Four fixed-width banks force the 96 KiB context image into block RAM.
    // A one-cycle drain after the final request is explicit in the parent FSM.
    (* ram_style = "block" *) reg [95:0] context_mem_region0 [0:4095];
    (* ram_style = "block" *) reg [95:0] context_mem_region1 [0:4095];
    (* ram_style = "block" *) reg [95:0] context_mem_region2 [0:4095];
    (* ram_style = "block" *) reg [95:0] context_mem_region3 [0:4095];
    reg [11:0] write_addr_r;
    reg [383:0] write_data_r;
    reg write_valid_r;
    reg [95:0] read_region0_r;
    reg [95:0] read_region1_r;
    reg [95:0] read_region2_r;
    reg [95:0] read_region3_r;
    reg [3:0] read_slot_r;
    reg read_pending_r;
    reg [8*32*24-1:0] activation_buffer_r;
    wire [11:0] read_addr = {
        read_wave, read_slot[3:1], read_group, read_slot[0]};

    assign activation_s24 = activation_buffer_r;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            write_valid_r <= 1'b0;
            read_pending_r <= 1'b0;
        end else if (clear) begin
            write_valid_r <= 1'b0;
            read_pending_r <= 1'b0;
        end else begin
            write_valid_r <= row_write_valid;
            read_pending_r <= read_issue;
        end
    end

    always @(posedge clk) begin
        if (write_valid_r && rst_n && !clear) begin
            context_mem_region0[write_addr_r] <= write_data_r[95:0];
            context_mem_region1[write_addr_r] <= write_data_r[191:96];
            context_mem_region2[write_addr_r] <= write_data_r[287:192];
            context_mem_region3[write_addr_r] <= write_data_r[383:288];
        end
        if (row_write_valid) begin
            write_addr_r <= {
                row_write_row, row_write_head, row_write_tile};
            write_data_r <= row_write_s24;
        end
        if (read_issue) begin
            read_region0_r <= context_mem_region0[read_addr];
            read_region1_r <= context_mem_region1[read_addr];
            read_region2_r <= context_mem_region2[read_addr];
            read_region3_r <= context_mem_region3[read_addr];
            read_slot_r <= read_slot;
        end
    end

    always @(posedge clk) begin
        if (read_pending_r)
            activation_buffer_r[
                read_slot_r[3:1]*768 + read_slot_r[0]*384 +: 384] <= {
                read_region3_r, read_region2_r,
                read_region1_r, read_region0_r};
    end

endmodule
