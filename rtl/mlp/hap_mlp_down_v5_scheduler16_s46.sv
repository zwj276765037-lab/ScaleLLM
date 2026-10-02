`timescale 1ns / 1ps

// V5 group-major down scheduler.  The external weight stream remains 256
// dense 16-column records for each of 448 product groups.  A local streaming
// gearbox converts every 48 source columns into four 12-column kernel passes;
// the final 16 source columns become 12/4.  Completed final-group S24 passes
// are inversely repacked to the legacy 256x16-column tensor ABI.
module hap_mlp_down_v5_scheduler16_s46 #(
    parameter integer OUTPUT_COLUMNS = 4096,
    parameter integer GROUPS = 448,
    parameter integer ENFORCE_PRODUCTION_SHAPE = 1,
    parameter integer SOURCE_RECORDS = (OUTPUT_COLUMNS+15)/16,
    parameter integer COMPUTE_TILES = (OUTPUT_COLUMNS+11)/12,
    parameter integer BLOCKS = (OUTPUT_COLUMNS+47)/48,
    parameter integer GROUP_W = (GROUPS <= 2) ? 1 : $clog2(GROUPS),
    parameter integer SOURCE_W =
        (SOURCE_RECORDS <= 2) ? 1 : $clog2(SOURCE_RECORDS),
    parameter integer TILE_W =
        (COMPUTE_TILES <= 2) ? 1 : $clog2(COMPUTE_TILES),
    parameter integer BLOCK_W = (BLOCKS <= 2) ? 1 : $clog2(BLOCKS),
    parameter integer TAG_W = GROUP_W + BLOCK_W
) (
    input  wire                          clk,
    input  wire                          rst_n,
    input  wire                          clear,
    input  wire                          enable,

    input  wire                          activation_valid,
    output wire                          activation_ready,
    input  wire [16*32*8-1:0]            activation_u8x16x32,
    input  wire [16*24-1:0]              activation_meta_u24x16,

    input  wire                          weight_valid,
    output wire                          weight_ready,
    input  wire signed [16*32*4-1:0]     weights_s4x16x32,
    input  wire [223:0]                  weight_meta_u224,

    output wire                          compute_valid,
    input  wire                          compute_ready,
    output wire                          compute_first,
    output wire                          compute_last,
    output wire [TILE_W-1:0]             compute_tile,
    output wire signed [16*32*9-1:0]     compute_activation_s9x16x32,
    output wire signed [12*32*4-1:0]     compute_weights_s4x12x32,
    output wire [16*8-1:0]               compute_activation_code_u8x16,
    output wire [16*6-1:0]               compute_activation_shift_u6x16,
    output wire [12*8-1:0]               compute_weight_code_u8x12,
    output wire [12*6-1:0]               compute_weight_shift_u6x12,
    output wire [11:0]                    compute_column_valid_u12,

    input  wire                          projection_valid,
    output wire                          projection_ready,
    input  wire [TILE_W-1:0]             projection_tile,
    input  wire signed [16*12*24-1:0]    projection_s24x16x12,

    output wire                          out_valid,
    input  wire                          out_ready,
    output wire [SOURCE_W-1:0]           out_record_index,
    output wire signed [16*16*24-1:0]    out_projection_s24x16x16,
    output wire                          busy,
    output reg                           done,
    output wire                          error,

    output reg  [31:0]                   activation_group_count,
    output reg  [31:0]                   source_record_count,
    output reg  [31:0]                   compute_transaction_count,
    output reg  [31:0]                   projection_pass_count,
    output reg  [31:0]                   output_record_count
);

    // Four cycle-aligned state replicas keep the activation owner, weight
    // ingress, repacker ingress and compute egress controls physically local.
    // The old single active_r predicate reached 1,118 placed loads and was
    // promoted to a data BUFG.  All four bits change on the original state
    // transition edge; no transaction or pipeline cycle is added.
    (* DONT_TOUCH = "yes" *) reg [3:0] active_endpoint_bank_r;
    reg [GROUP_W-1:0] group_r;
    reg [SOURCE_W-1:0] source_record_r;
    reg [BLOCK_W-1:0] source_block_r;
    reg [1:0] source_record_in_block_r;
    reg source_complete_r;
    reg signed [16*32*9-1:0] activation_s9_r;
    reg [16*8-1:0] activation_code_r;
    reg [16*6-1:0] activation_shift_r;
    reg sticky_error_r;
    (* DONT_TOUCH = "yes", KEEP = "yes" *)
    wire [15:0] activation_capture_enable;

    wire activation_fire = activation_valid && activation_ready;
    assign activation_ready = rst_n && !clear && enable &&
        !active_endpoint_bank_r[0] &&
        activation_group_count < GROUPS;
    assign busy = active_endpoint_bank_r[0];

    wire repack_in_ready;
    wire repack_out_valid;
    wire repack_out_ready;
    wire signed [12*32*4-1:0] repack_out_weights;
    wire [167:0] repack_out_meta;
    wire [TAG_W-1:0] repack_out_tag;
    wire [1:0] repack_out_pass;
    wire [11:0] repack_out_mask;
    wire repack_out_last;
    wire [31:0] repack_input_records;
    wire [31:0] repack_input_supertiles;
    wire [31:0] repack_output_passes;
    wire repack_error;
    wire [TAG_W-1:0] source_tag = {group_r, source_block_r};
    wire source_is_final_record = source_record_r == SOURCE_RECORDS-1;
    wire source_fire = weight_valid && weight_ready;
    wire compute_fire = compute_valid && compute_ready;

    // Capture payload and local metadata with one protected CE per physical
    // row.  Each domain owns 288 centered-data FFs plus 14 metadata FFs; the
    // previous common activation_fire CE reached 4,832 placed registers.
    genvar activation_capture_row;
    generate for (activation_capture_row = 0;
                  activation_capture_row < 16;
                  activation_capture_row = activation_capture_row + 1)
    begin : g_activation_capture
        (* DONT_TOUCH = "yes", KEEP = "yes" *) LUT1 #(.INIT(2'h2))
        u_capture_enable (
            .I0(activation_fire),
            .O(activation_capture_enable[activation_capture_row])
        );

        integer capture_lane;
        always @(posedge clk) begin
            if (activation_capture_enable[activation_capture_row]) begin
                activation_code_r[activation_capture_row*8 +: 8] <=
                    activation_meta_u24x16[
                        activation_capture_row*24+8 +: 8];
                activation_shift_r[activation_capture_row*6 +: 6] <=
                    activation_meta_u24x16[
                        activation_capture_row*24+16 +: 6];
                for (capture_lane = 0; capture_lane < 32;
                     capture_lane = capture_lane + 1)
                    activation_s9_r[
                        (activation_capture_row*32+capture_lane)*9 +: 9] <=
                        $signed({1'b0, activation_u8x16x32[
                            (activation_capture_row*32+capture_lane)*8 +: 8]}) -
                        $signed({1'b0, activation_meta_u24x16[
                            activation_capture_row*24 +: 8]});
            end
        end
    end endgenerate

    assign weight_ready = rst_n && !clear && enable &&
        active_endpoint_bank_r[1] &&
        !source_complete_r && repack_in_ready;

    hap_mlp_w4_repack48_to12 #(.TAG_W(TAG_W)) u_weight_repack (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(enable && active_endpoint_bank_r[2] &&
            !source_complete_r && weight_valid),
        .in_ready(repack_in_ready),
        .in_weights_s4x16x32(weights_s4x16x32),
        .in_weight_meta_u224(weight_meta_u224), .in_tag(source_tag),
        .in_record_index(source_record_in_block_r),
        .in_col_valid_u16(16'hffff),
        .in_flush(source_is_final_record),
        .out_valid(repack_out_valid), .out_ready(repack_out_ready),
        .out_weights_s4x12x32(repack_out_weights),
        .out_weight_meta_u168(repack_out_meta),
        .out_tag(repack_out_tag), .out_pass_index(repack_out_pass),
        .out_col_valid_u12(repack_out_mask),
        .out_last_pass(repack_out_last),
        .input_record_count(repack_input_records),
        .input_supertile_count(repack_input_supertiles),
        .output_pass_count(repack_output_passes), .error(repack_error)
    );

    wire [GROUP_W-1:0] repack_group =
        repack_out_tag[TAG_W-1 -: GROUP_W];
    wire [BLOCK_W-1:0] repack_block = repack_out_tag[BLOCK_W-1:0];
    wire [TILE_W:0] repack_tile_full =
        repack_block*4 + repack_out_pass;

    assign compute_valid = enable && active_endpoint_bank_r[3] &&
        repack_out_valid;
    assign repack_out_ready = enable && active_endpoint_bank_r[3] &&
        compute_ready;
    assign compute_first = group_r == 0;
    assign compute_last = group_r == GROUPS-1;
    assign compute_tile = repack_tile_full[TILE_W-1:0];
    assign compute_activation_s9x16x32 = activation_s9_r;
    assign compute_weights_s4x12x32 = repack_out_weights;
    assign compute_activation_code_u8x16 = activation_code_r;
    assign compute_activation_shift_u6x16 = activation_shift_r;
    assign compute_weight_code_u8x12 = repack_out_meta[95:0];
    assign compute_weight_shift_u6x12 = repack_out_meta[167:96];
    assign compute_column_valid_u12 = repack_out_mask;

    // Only the last group emits completed projection passes.  Its tile index
    // uniquely reconstructs the 48-column block/pass tags needed by the
    // inverse gearbox; no central per-transaction S37 tag bus is required.
    wire [BLOCK_W-1:0] projection_block = projection_tile >> 2;
    wire [1:0] projection_pass = projection_tile[1:0];
    wire projection_last_pass = projection_tile == COMPUTE_TILES-1 ||
        projection_pass == 2'd3;
    localparam integer FINAL_VALID_COLUMNS =
        OUTPUT_COLUMNS - (COMPUTE_TILES-1)*12;
    localparam [11:0] FINAL_COLUMN_MASK =
        (12'h001 << FINAL_VALID_COLUMNS) - 1'b1;
    wire [11:0] projection_mask = projection_tile == COMPUTE_TILES-1 ?
        FINAL_COLUMN_MASK : 12'hfff;
    wire inverse_in_ready;
    wire inverse_error;
    wire [BLOCK_W-1:0] inverse_out_block;
    wire [1:0] inverse_out_record;
    wire inverse_out_matrix;
    wire [15:0] inverse_out_mask;
    wire inverse_out_last;
    wire [31:0] inverse_input_passes;
    wire [31:0] inverse_output_records;
    wire projection_fire = projection_valid && projection_ready;
    wire out_fire = out_valid && out_ready;

    assign projection_ready = enable && inverse_in_ready;

    hap_mlp_projection_repack12_to16_s24_history2 #(
        .ROWS(16), .MATRICES(1), .TAG_W(BLOCK_W)
    ) u_projection_repack (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(enable && projection_valid), .in_ready(inverse_in_ready),
        .in_projection_s24xrowsx12(projection_s24x16x12),
        .in_block_tag(projection_block), .in_pass_index(projection_pass),
        .in_matrix(1'b0), .in_col_valid_u12(projection_mask),
        .in_last_pass(projection_last_pass), .out_valid(out_valid),
        .out_ready(out_ready),
        .out_projection_s24xrowsx16(out_projection_s24x16x16),
        .out_block_tag(inverse_out_block),
        .out_record_index(inverse_out_record),
        .out_matrix(inverse_out_matrix),
        .out_col_valid_u16(inverse_out_mask),
        .out_last_record(inverse_out_last),
        .input_pass_count(inverse_input_passes),
        .output_record_count(inverse_output_records), .error(inverse_error)
    );

    wire [SOURCE_W:0] global_output_record =
        inverse_out_block*3 + inverse_out_record;
    assign out_record_index = global_output_record[SOURCE_W-1:0];
    assign error = sticky_error_r || repack_error || inverse_error;

    integer row;
    always @(posedge clk) begin
        if (!rst_n || clear) begin
            active_endpoint_bank_r <= 4'd0;
            group_r <= '0;
            source_record_r <= '0;
            source_block_r <= '0;
            source_record_in_block_r <= 2'd0;
            source_complete_r <= 1'b0;
            sticky_error_r <= 1'b0;
            activation_group_count <= 32'd0;
            source_record_count <= 32'd0;
            compute_transaction_count <= 32'd0;
            projection_pass_count <= 32'd0;
            output_record_count <= 32'd0;
            done <= 1'b0;
        end else begin
            done <= 1'b0;
            if (activation_fire) begin
                active_endpoint_bank_r <= 4'hf;
                source_record_r <= '0;
                source_block_r <= '0;
                source_record_in_block_r <= 2'd0;
                source_complete_r <= 1'b0;
                activation_group_count <= activation_group_count + 1'b1;
                for (row = 0; row < 16; row = row + 1) begin
                    if (activation_meta_u24x16[row*24+22 +: 2] != 0 ||
                        (activation_meta_u24x16[row*24+8 +: 8] == 0 &&
                         activation_meta_u24x16[row*24+16 +: 6] != 0))
                        sticky_error_r <= 1'b1;
                end
            end

            if (source_fire) begin
                source_record_count <= source_record_count + 1'b1;
                if (source_is_final_record) begin
                    source_complete_r <= 1'b1;
                end else begin
                    source_record_r <= source_record_r + 1'b1;
                    if (source_record_in_block_r == 2'd2) begin
                        source_record_in_block_r <= 2'd0;
                        source_block_r <= source_block_r + 1'b1;
                    end else begin
                        source_record_in_block_r <=
                            source_record_in_block_r + 1'b1;
                    end
                end
            end

            if (compute_fire) begin
                compute_transaction_count <=
                    compute_transaction_count + 1'b1;
                if (repack_group != group_r ||
                    repack_tile_full >= COMPUTE_TILES ||
                    (repack_out_last !=
                     (repack_tile_full == COMPUTE_TILES-1 ||
                      repack_out_pass == 2'd3)))
                    sticky_error_r <= 1'b1;
                if (repack_tile_full == COMPUTE_TILES-1) begin
                    if (!source_complete_r ||
                        compute_transaction_count + 1'b1 !=
                        (group_r+1)*COMPUTE_TILES)
                        sticky_error_r <= 1'b1;
                    active_endpoint_bank_r <= 4'd0;
                    if (group_r != GROUPS-1)
                        group_r <= group_r + 1'b1;
                end
            end

            if (projection_fire) begin
                projection_pass_count <= projection_pass_count + 1'b1;
                if (projection_tile >= COMPUTE_TILES)
                    sticky_error_r <= 1'b1;
            end

            if (out_fire) begin
                output_record_count <= output_record_count + 1'b1;
                if (inverse_out_mask != 16'hffff || inverse_out_matrix != 0 ||
                    global_output_record != output_record_count)
                    sticky_error_r <= 1'b1;
                if (output_record_count + 1'b1 == SOURCE_RECORDS) begin
                    done <= 1'b1;
                end
            end

            if (repack_input_records < source_record_count ||
                repack_output_passes < compute_transaction_count ||
                inverse_input_passes < projection_pass_count ||
                inverse_output_records < output_record_count ||
                activation_group_count > GROUPS ||
                source_record_count > GROUPS*SOURCE_RECORDS ||
                compute_transaction_count > GROUPS*COMPUTE_TILES ||
                projection_pass_count > COMPUTE_TILES ||
                output_record_count > SOURCE_RECORDS)
                sticky_error_r <= 1'b1;
        end
    end

    initial begin
        if (ENFORCE_PRODUCTION_SHAPE &&
            (OUTPUT_COLUMNS != 4096 || GROUPS != 448 ||
             SOURCE_RECORDS != 256 || COMPUTE_TILES != 342 || BLOCKS != 86))
            $error("V5 down scheduler frozen shape mismatch");
        if (OUTPUT_COLUMNS <= 0 || GROUPS <= 0 ||
            FINAL_VALID_COLUMNS <= 0 || FINAL_VALID_COLUMNS > 12)
            $error("V5 down scheduler test shape is invalid");
    end

`ifndef SYNTHESIS
    always @(posedge clk) begin
        if (rst_n && !clear &&
            active_endpoint_bank_r !=
            {4{active_endpoint_bank_r[0]}})
            $error("V5 down active endpoint banks diverged");
    end
`endif

endmodule
