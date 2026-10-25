`timescale 1ns / 1ps

// One independently inferred pass-oriented gather lane.
//
// DEPTH=1024 and WIDTH=142 map to four RAMB36E2 primitives in 1024x36 true
// dual-port mode.  During bank fill both ports may write different pass
// addresses in the same cycle.  During bank drain port A performs one
// synchronous read and port B is idle.  Bank ownership guarantees that read
// and write modes never overlap.  Payload memory is intentionally resetless.
module hap_mlp_gate_up_gather_lane142_tdp #(
    parameter integer DEPTH = 1024,
    parameter integer ADDR_W = (DEPTH <= 2) ? 1 : $clog2(DEPTH)
) (
    input  wire                 clk,
    input  wire                 port_a_enable,
    input  wire                 port_a_write,
    input  wire [ADDR_W-1:0]    port_a_address,
    input  wire [141:0]         port_a_write_data,
    output reg  [141:0]         port_a_read_data,
    input  wire                 port_b_enable,
    input  wire                 port_b_write,
    input  wire [ADDR_W-1:0]    port_b_address,
    input  wire [141:0]         port_b_write_data
);

    (* ram_style = "block" *) reg [141:0] memory [0:DEPTH-1];

    // Canonical independent-clock-capable TDP template, with one shared clock
    // in this design.  No reset is allowed on either payload port.
    always @(posedge clk) begin
        if (port_a_enable) begin
            if (port_a_write)
                memory[port_a_address] <= port_a_write_data;
            else
                port_a_read_data <= memory[port_a_address];
        end
    end

    always @(posedge clk) begin
        if (port_b_enable && port_b_write)
            memory[port_b_address] <= port_b_write_data;
    end

endmodule

// V5 central shared gate/up gather.
//
// Input is the existing tile-major semantic order for one 48-column block:
//
//   record0 gate[g0..g127], record0 up[g0..g127],
//   record1 gate[g0..g127], record1 up[g0..g127],
//   record2 gate[g0..g127], record2 up[g0..g127].
//
// Each accepted 16-column source record is transposed on write into a
// pass-oriented bank.  A sealed bank drains as:
//
//   pass0 gate[g0..g127], pass0 up[g0..g127], ... pass3 up[g0..g127].
//
// The two banks decouple DDR/metadata fill from activation-cache/kernel
// replay.  This leaf carries only W4+ScaleCode; activation replay remains an
// integration responsibility.  No production V4 interface is modified.
module hap_mlp_gate_up_gather_pingpong12 #(
    parameter integer GROUPS = 128,
    parameter integer BLOCK_W = 10,
    parameter integer GROUP_W = (GROUPS <= 2) ? 1 : $clog2(GROUPS),
    parameter integer BANK_DEPTH = 8*GROUPS,
    parameter integer BANK_ADDR_W =
        (BANK_DEPTH <= 2) ? 1 : $clog2(BANK_DEPTH)
) (
    input  wire                           clk,
    input  wire                           rst_n,
    input  wire                           clear,

    input  wire                           in_valid,
    output wire                           in_ready,
    input  wire [BLOCK_W-1:0]             in_block_index,
    input  wire [5:0]                     in_block_valid_columns,
    input  wire                           in_matrix,
    input  wire [1:0]                     in_record_index,
    input  wire [GROUP_W-1:0]             in_k_group,
    input  wire signed [16*32*4-1:0]      in_weights_s4x16x32,
    input  wire [223:0]                   in_weight_meta_u224,
    input  wire [15:0]                    in_col_valid_u16,

    output wire                           out_valid,
    input  wire                           out_ready,
    output wire [BLOCK_W-1:0]             out_block_index,
    output wire                           out_matrix,
    output wire [1:0]                     out_pass_index,
    output wire [GROUP_W-1:0]             out_k_group,
    output wire                           out_first_group,
    output wire                           out_last_group,
    output wire                           out_last_pass,
    output wire                           out_last_block_transaction,
    output wire signed [12*32*4-1:0]      out_weights_s4x12x32,
    output wire [167:0]                   out_weight_meta_u168,
    output wire [11:0]                    out_col_valid_u12,

    output reg  [31:0]                    input_transaction_count,
    output reg  [31:0]                    input_block_count,
    output reg  [31:0]                    output_transaction_count,
    output reg  [31:0]                    output_block_count,
    output reg                            error
);

    localparam [1:0] BANK_EMPTY = 2'd0;
    localparam [1:0] BANK_FILL  = 2'd1;
    localparam [1:0] BANK_FULL  = 2'd2;
    localparam [1:0] BANK_DRAIN = 2'd3;

    reg [1:0] bank_state_r [0:1];
    reg [BLOCK_W-1:0] bank_block_r [0:1];
    reg [5:0] bank_valid_columns_r [0:1];
    reg [2:0] bank_pass_count_r [0:1];

    reg fill_active_r;
    reg fill_bank_r;
    reg fill_first_r;
    reg [BLOCK_W-1:0] next_fill_block_r;
    reg [5:0] fill_valid_columns_r;
    reg [1:0] fill_record_r;
    reg fill_matrix_r;
    reg [GROUP_W-1:0] fill_group_r;

    reg drain_active_r;
    reg drain_bank_r;
    reg [BLOCK_W-1:0] next_drain_block_r;
    reg [1:0] drain_pass_r;
    reg drain_matrix_r;
    reg [GROUP_W-1:0] drain_group_r;

    reg pipe_valid_r;
    reg pipe_bank_r;
    reg [BLOCK_W-1:0] pipe_block_r;
    reg pipe_matrix_r;
    reg [1:0] pipe_pass_r;
    reg [GROUP_W-1:0] pipe_group_r;
    reg [11:0] pipe_mask_r;
    reg pipe_last_pass_r;
    reg pipe_last_bank_r;

    reg out_valid_r;
    reg [BLOCK_W-1:0] out_block_r;
    reg out_matrix_r;
    reg [1:0] out_pass_r;
    reg [GROUP_W-1:0] out_group_r;
    reg out_first_group_r;
    reg out_last_group_r;
    reg out_last_pass_r;
    reg out_last_bank_r;
    reg signed [12*32*4-1:0] out_weights_r;
    reg [12*8-1:0] out_code_r;
    reg [12*6-1:0] out_shift_r;
    reg [11:0] out_mask_r;

    function automatic [2:0] pass_count_for_columns;
        input [5:0] columns;
        begin
            pass_count_for_columns = (columns + 6'd11) / 6'd12;
        end
    endfunction

    function automatic [1:0] record_count_for_columns;
        input [5:0] columns;
        begin
            record_count_for_columns = (columns + 6'd15) / 6'd16;
        end
    endfunction

    function automatic [15:0] source_mask_for_record;
        input [5:0] columns;
        input [1:0] record_index;
        integer remaining;
        begin
            remaining = columns - record_index*16;
            if (remaining >= 16)
                source_mask_for_record = 16'hffff;
            else if (remaining > 0)
                source_mask_for_record = (16'h0001 << remaining) - 1'b1;
            else
                source_mask_for_record = 16'h0000;
        end
    endfunction

    function automatic [11:0] compute_mask_for_pass;
        input [5:0] columns;
        input [1:0] pass_index;
        integer remaining;
        begin
            remaining = columns - pass_index*12;
            if (remaining >= 12)
                compute_mask_for_pass = 12'hfff;
            else if (remaining > 0)
                compute_mask_for_pass = (12'h001 << remaining) - 1'b1;
            else
                compute_mask_for_pass = 12'h000;
        end
    endfunction

    function automatic [BANK_ADDR_W-1:0] bank_address;
        input matrix;
        input [1:0] pass_index;
        input [GROUP_W-1:0] group_index;
        integer value;
        begin
            value = ((matrix*4 + pass_index)*GROUPS) + group_index;
            bank_address = value[BANK_ADDR_W-1:0];
        end
    endfunction

    wire [5:0] contract_columns = fill_first_r ?
        in_block_valid_columns : fill_valid_columns_r;
    wire block_shape_legal = contract_columns >= 1 &&
        contract_columns <= 48;
    wire [1:0] contract_record_count =
        record_count_for_columns(contract_columns);
    wire [15:0] contract_source_mask =
        source_mask_for_record(contract_columns, fill_record_r);
    wire tag_legal = in_block_index == next_fill_block_r &&
        in_record_index == fill_record_r &&
        in_matrix == fill_matrix_r && in_k_group == fill_group_r &&
        in_block_valid_columns == contract_columns &&
        in_col_valid_u16 == contract_source_mask;
    wire input_contract_legal = block_shape_legal &&
        fill_record_r < contract_record_count && tag_legal;
    wire input_capacity = rst_n && !clear && fill_active_r;
    wire in_fire = in_valid && in_ready;
    wire invalid_input_attempt = in_valid && input_capacity &&
        !input_contract_legal;
    assign in_ready = input_capacity && input_contract_legal;

    reg [11:0] fill_we_a;
    reg [11:0] fill_we_b;
    reg [1:0] fill_pass_a [0:11];
    reg [1:0] fill_pass_b [0:11];
    reg [3:0] fill_source_a [0:11];
    reg [3:0] fill_source_b [0:11];
    reg [BANK_ADDR_W-1:0] fill_address_a [0:11];
    reg [BANK_ADDR_W-1:0] fill_address_b [0:11];
    reg [141:0] fill_data_a [0:11];
    reg [141:0] fill_data_b [0:11];

    integer map_lane;
    integer source_column;
    always @* begin
        fill_we_a = 12'd0;
        fill_we_b = 12'd0;
        for (map_lane = 0; map_lane < 12; map_lane = map_lane + 1) begin
            fill_pass_a[map_lane] = 2'd0;
            fill_pass_b[map_lane] = 2'd0;
            fill_source_a[map_lane] = 4'd0;
            fill_source_b[map_lane] = 4'd0;
            case (fill_record_r)
                2'd0: begin
                    fill_pass_a[map_lane] = 2'd0;
                    fill_source_a[map_lane] = map_lane[3:0];
                    if (map_lane < 4) begin
                        fill_pass_b[map_lane] = 2'd1;
                        fill_source_b[map_lane] = map_lane[3:0] + 4'd12;
                    end
                end
                2'd1: begin
                    if (map_lane >= 4) begin
                        fill_pass_a[map_lane] = 2'd1;
                        fill_source_a[map_lane] = map_lane[3:0] - 4'd4;
                    end
                    if (map_lane < 8) begin
                        fill_pass_b[map_lane] = 2'd2;
                        fill_source_b[map_lane] = map_lane[3:0] + 4'd8;
                    end
                end
                default: begin
                    if (map_lane >= 8) begin
                        fill_pass_a[map_lane] = 2'd2;
                        fill_source_a[map_lane] = map_lane[3:0] - 4'd8;
                    end
                    fill_pass_b[map_lane] = 2'd3;
                    fill_source_b[map_lane] = map_lane[3:0] + 4'd4;
                end
            endcase

            source_column = fill_source_a[map_lane];
            fill_address_a[map_lane] = bank_address(
                fill_matrix_r, fill_pass_a[map_lane], fill_group_r);
            fill_data_a[map_lane] = {
                in_weight_meta_u224[128+source_column*6 +: 6],
                in_weight_meta_u224[source_column*8 +: 8],
                in_weights_s4x16x32[source_column*128 +: 128]};
            source_column = fill_source_b[map_lane];
            fill_address_b[map_lane] = bank_address(
                fill_matrix_r, fill_pass_b[map_lane], fill_group_r);
            fill_data_b[map_lane] = {
                in_weight_meta_u224[128+source_column*6 +: 6],
                in_weight_meta_u224[source_column*8 +: 8],
                in_weights_s4x16x32[source_column*128 +: 128]};

            case (fill_record_r)
                2'd0: begin
                    fill_we_a[map_lane] = in_fire &&
                        in_col_valid_u16[map_lane];
                    fill_we_b[map_lane] = in_fire && map_lane < 4 &&
                        in_col_valid_u16[map_lane+12];
                end
                2'd1: begin
                    fill_we_a[map_lane] = in_fire && map_lane >= 4 &&
                        in_col_valid_u16[map_lane-4];
                    fill_we_b[map_lane] = in_fire && map_lane < 8 &&
                        in_col_valid_u16[map_lane+8];
                end
                default: begin
                    fill_we_a[map_lane] = in_fire && map_lane >= 8 &&
                        in_col_valid_u16[map_lane-8];
                    fill_we_b[map_lane] = in_fire &&
                        in_col_valid_u16[map_lane+4];
                end
            endcase
        end
    end

    wire out_capacity = !out_valid_r || out_ready;
    wire pipe_ready = !pipe_valid_r || out_capacity;
    wire read_issue = rst_n && !clear && drain_active_r && pipe_ready;
    wire out_fire = out_valid && out_ready;
    wire [BANK_ADDR_W-1:0] drain_read_address = bank_address(
        drain_matrix_r, drain_pass_r, drain_group_r);

    wire [141:0] bank0_read_data [0:11];
    wire [141:0] bank1_read_data [0:11];

    genvar memory_lane;
    generate
        for (memory_lane = 0; memory_lane < 12;
             memory_lane = memory_lane + 1) begin : gen_gather_lane
            wire bank0_fill_a = fill_active_r && !fill_bank_r &&
                fill_we_a[memory_lane];
            wire bank0_fill_b = fill_active_r && !fill_bank_r &&
                fill_we_b[memory_lane];
            wire bank0_read = read_issue && !drain_bank_r;
            wire bank1_fill_a = fill_active_r && fill_bank_r &&
                fill_we_a[memory_lane];
            wire bank1_fill_b = fill_active_r && fill_bank_r &&
                fill_we_b[memory_lane];
            wire bank1_read = read_issue && drain_bank_r;

            hap_mlp_gate_up_gather_lane142_tdp #(
                .DEPTH(BANK_DEPTH), .ADDR_W(BANK_ADDR_W)
            ) u_bank0_lane (
                .clk(clk),
                .port_a_enable(bank0_fill_a || bank0_read),
                .port_a_write(bank0_fill_a),
                .port_a_address(bank0_fill_a ?
                    fill_address_a[memory_lane] : drain_read_address),
                .port_a_write_data(fill_data_a[memory_lane]),
                .port_a_read_data(bank0_read_data[memory_lane]),
                .port_b_enable(bank0_fill_b),
                .port_b_write(bank0_fill_b),
                .port_b_address(fill_address_b[memory_lane]),
                .port_b_write_data(fill_data_b[memory_lane])
            );

            hap_mlp_gate_up_gather_lane142_tdp #(
                .DEPTH(BANK_DEPTH), .ADDR_W(BANK_ADDR_W)
            ) u_bank1_lane (
                .clk(clk),
                .port_a_enable(bank1_fill_a || bank1_read),
                .port_a_write(bank1_fill_a),
                .port_a_address(bank1_fill_a ?
                    fill_address_a[memory_lane] : drain_read_address),
                .port_a_write_data(fill_data_a[memory_lane]),
                .port_a_read_data(bank1_read_data[memory_lane]),
                .port_b_enable(bank1_fill_b),
                .port_b_write(bank1_fill_b),
                .port_b_address(fill_address_b[memory_lane]),
                .port_b_write_data(fill_data_b[memory_lane])
            );
        end
    endgenerate

    assign out_valid = rst_n && !clear && out_valid_r;
    assign out_block_index = out_block_r;
    assign out_matrix = out_matrix_r;
    assign out_pass_index = out_pass_r;
    assign out_k_group = out_group_r;
    assign out_first_group = out_first_group_r;
    assign out_last_group = out_last_group_r;
    assign out_last_pass = out_last_pass_r;
    assign out_last_block_transaction = out_last_bank_r;
    assign out_weights_s4x12x32 = out_weights_r;
    assign out_weight_meta_u168 = {out_shift_r, out_code_r};
    assign out_col_valid_u12 = out_mask_r;

    integer output_lane;
    always @(posedge clk) begin
        if (!rst_n) begin
            bank_state_r[0] <= BANK_EMPTY;
            bank_state_r[1] <= BANK_EMPTY;
            bank_block_r[0] <= '0;
            bank_block_r[1] <= '0;
            bank_valid_columns_r[0] <= 6'd0;
            bank_valid_columns_r[1] <= 6'd0;
            bank_pass_count_r[0] <= 3'd0;
            bank_pass_count_r[1] <= 3'd0;
            fill_active_r <= 1'b0;
            fill_bank_r <= 1'b0;
            fill_first_r <= 1'b1;
            next_fill_block_r <= '0;
            fill_valid_columns_r <= 6'd0;
            fill_record_r <= 2'd0;
            fill_matrix_r <= 1'b0;
            fill_group_r <= '0;
            drain_active_r <= 1'b0;
            drain_bank_r <= 1'b0;
            next_drain_block_r <= '0;
            drain_pass_r <= 2'd0;
            drain_matrix_r <= 1'b0;
            drain_group_r <= '0;
            pipe_valid_r <= 1'b0;
            out_valid_r <= 1'b0;
            input_transaction_count <= 32'd0;
            input_block_count <= 32'd0;
            output_transaction_count <= 32'd0;
            output_block_count <= 32'd0;
            error <= 1'b0;
        end else if (clear) begin
            bank_state_r[0] <= BANK_EMPTY;
            bank_state_r[1] <= BANK_EMPTY;
            bank_block_r[0] <= '0;
            bank_block_r[1] <= '0;
            bank_valid_columns_r[0] <= 6'd0;
            bank_valid_columns_r[1] <= 6'd0;
            bank_pass_count_r[0] <= 3'd0;
            bank_pass_count_r[1] <= 3'd0;
            fill_active_r <= 1'b0;
            fill_bank_r <= 1'b0;
            fill_first_r <= 1'b1;
            next_fill_block_r <= '0;
            fill_valid_columns_r <= 6'd0;
            fill_record_r <= 2'd0;
            fill_matrix_r <= 1'b0;
            fill_group_r <= '0;
            drain_active_r <= 1'b0;
            drain_bank_r <= 1'b0;
            next_drain_block_r <= '0;
            drain_pass_r <= 2'd0;
            drain_matrix_r <= 1'b0;
            drain_group_r <= '0;
            pipe_valid_r <= 1'b0;
            out_valid_r <= 1'b0;
            input_transaction_count <= 32'd0;
            input_block_count <= 32'd0;
            output_transaction_count <= 32'd0;
            output_block_count <= 32'd0;
            error <= 1'b0;
        end else begin
            if (invalid_input_attempt)
                error <= 1'b1;

            // Allocate exactly one empty bank to the ordered fill stream.
            if (!fill_active_r) begin
                if (bank_state_r[0] == BANK_EMPTY) begin
                    bank_state_r[0] <= BANK_FILL;
                    fill_active_r <= 1'b1;
                    fill_bank_r <= 1'b0;
                    fill_first_r <= 1'b1;
                    fill_record_r <= 2'd0;
                    fill_matrix_r <= 1'b0;
                    fill_group_r <= '0;
                end else if (bank_state_r[1] == BANK_EMPTY) begin
                    bank_state_r[1] <= BANK_FILL;
                    fill_active_r <= 1'b1;
                    fill_bank_r <= 1'b1;
                    fill_first_r <= 1'b1;
                    fill_record_r <= 2'd0;
                    fill_matrix_r <= 1'b0;
                    fill_group_r <= '0;
                end
            end

            if (in_fire) begin
                input_transaction_count <= input_transaction_count + 1'b1;
                if (fill_first_r) begin
                    fill_first_r <= 1'b0;
                    fill_valid_columns_r <= in_block_valid_columns;
                    bank_block_r[fill_bank_r] <= in_block_index;
                    bank_valid_columns_r[fill_bank_r] <=
                        in_block_valid_columns;
                    bank_pass_count_r[fill_bank_r] <=
                        pass_count_for_columns(in_block_valid_columns);
                end

                if (fill_group_r == GROUPS-1) begin
                    fill_group_r <= '0;
                    if (!fill_matrix_r) begin
                        fill_matrix_r <= 1'b1;
                    end else begin
                        fill_matrix_r <= 1'b0;
                        if (fill_record_r + 1'b1 == contract_record_count) begin
                            bank_state_r[fill_bank_r] <= BANK_FULL;
                            fill_active_r <= 1'b0;
                            fill_first_r <= 1'b1;
                            fill_record_r <= 2'd0;
                            next_fill_block_r <= next_fill_block_r + 1'b1;
                            input_block_count <= input_block_count + 1'b1;
                        end else begin
                            fill_record_r <= fill_record_r + 1'b1;
                        end
                    end
                end else begin
                    fill_group_r <= fill_group_r + 1'b1;
                end
            end

            // Select only the next ordered sealed bank.  A later full bank
            // can never bypass an earlier block.
            if (!drain_active_r) begin
                if (bank_state_r[0] == BANK_FULL &&
                    bank_block_r[0] == next_drain_block_r) begin
                    bank_state_r[0] <= BANK_DRAIN;
                    drain_active_r <= 1'b1;
                    drain_bank_r <= 1'b0;
                    drain_pass_r <= 2'd0;
                    drain_matrix_r <= 1'b0;
                    drain_group_r <= '0;
                    next_drain_block_r <= next_drain_block_r + 1'b1;
                end else if (bank_state_r[1] == BANK_FULL &&
                    bank_block_r[1] == next_drain_block_r) begin
                    bank_state_r[1] <= BANK_DRAIN;
                    drain_active_r <= 1'b1;
                    drain_bank_r <= 1'b1;
                    drain_pass_r <= 2'd0;
                    drain_matrix_r <= 1'b0;
                    drain_group_r <= '0;
                    next_drain_block_r <= next_drain_block_r + 1'b1;
                end
            end

            if (read_issue) begin
                if (drain_group_r == GROUPS-1) begin
                    drain_group_r <= '0;
                    if (!drain_matrix_r) begin
                        drain_matrix_r <= 1'b1;
                    end else begin
                        drain_matrix_r <= 1'b0;
                        if (drain_pass_r + 1'b1 ==
                            bank_pass_count_r[drain_bank_r]) begin
                            drain_active_r <= 1'b0;
                            drain_pass_r <= 2'd0;
                        end else begin
                            drain_pass_r <= drain_pass_r + 1'b1;
                        end
                    end
                end else begin
                    drain_group_r <= drain_group_r + 1'b1;
                end
            end

            // One elastic synchronous-read stage followed by one registered
            // output stage.  Both freeze losslessly under out backpressure.
            if (out_capacity) begin
                out_valid_r <= pipe_valid_r;
                if (pipe_valid_r) begin
                    out_block_r <= pipe_block_r;
                    out_matrix_r <= pipe_matrix_r;
                    out_pass_r <= pipe_pass_r;
                    out_group_r <= pipe_group_r;
                    out_first_group_r <= pipe_group_r == 0;
                    out_last_group_r <= pipe_group_r == GROUPS-1;
                    out_last_pass_r <= pipe_last_pass_r;
                    out_last_bank_r <= pipe_last_bank_r;
                    out_mask_r <= pipe_mask_r;
                    for (output_lane = 0; output_lane < 12;
                         output_lane = output_lane + 1) begin
                        if (pipe_mask_r[output_lane]) begin
                            if (pipe_bank_r) begin
                                out_weights_r[output_lane*128 +: 128] <=
                                    bank1_read_data[output_lane][127:0];
                                out_code_r[output_lane*8 +: 8] <=
                                    bank1_read_data[output_lane][135:128];
                                out_shift_r[output_lane*6 +: 6] <=
                                    bank1_read_data[output_lane][141:136];
                            end else begin
                                out_weights_r[output_lane*128 +: 128] <=
                                    bank0_read_data[output_lane][127:0];
                                out_code_r[output_lane*8 +: 8] <=
                                    bank0_read_data[output_lane][135:128];
                                out_shift_r[output_lane*6 +: 6] <=
                                    bank0_read_data[output_lane][141:136];
                            end
                        end else begin
                            out_weights_r[output_lane*128 +: 128] <= '0;
                            out_code_r[output_lane*8 +: 8] <= '0;
                            out_shift_r[output_lane*6 +: 6] <= '0;
                        end
                    end
                    // Once the final synchronous response is copied, no
                    // payload state refers to this physical memory bank.
                    if (pipe_last_bank_r)
                        bank_state_r[pipe_bank_r] <= BANK_EMPTY;
                end
            end

            if (pipe_ready) begin
                pipe_valid_r <= read_issue;
                if (read_issue) begin
                    pipe_bank_r <= drain_bank_r;
                    pipe_block_r <= bank_block_r[drain_bank_r];
                    pipe_matrix_r <= drain_matrix_r;
                    pipe_pass_r <= drain_pass_r;
                    pipe_group_r <= drain_group_r;
                    pipe_mask_r <= compute_mask_for_pass(
                        bank_valid_columns_r[drain_bank_r], drain_pass_r);
                    pipe_last_pass_r <= drain_pass_r + 1'b1 ==
                        bank_pass_count_r[drain_bank_r];
                    pipe_last_bank_r <= drain_pass_r + 1'b1 ==
                        bank_pass_count_r[drain_bank_r] &&
                        drain_matrix_r && drain_group_r == GROUPS-1;
                end
            end

            if (out_fire) begin
                output_transaction_count <=
                    output_transaction_count + 1'b1;
                if (out_last_bank_r)
                    output_block_count <= output_block_count + 1'b1;
            end
        end
    end

`ifndef SYNTHESIS
    reg stalled_input_r;
    reg stalled_output_r;
    reg [BLOCK_W+6+1+2+GROUP_W+2048+224+16-1:0]
        stalled_input_payload_r;
    reg [BLOCK_W+1+2+GROUP_W+1+1+1+1+1536+168+12-1:0]
        stalled_output_payload_r;
    wire [BLOCK_W+6+1+2+GROUP_W+2048+224+16-1:0]
        input_payload = {in_block_index, in_block_valid_columns, in_matrix,
            in_record_index, in_k_group, in_weights_s4x16x32,
            in_weight_meta_u224, in_col_valid_u16};
    wire [BLOCK_W+1+2+GROUP_W+1+1+1+1+1536+168+12-1:0]
        output_payload = {out_block_index, out_matrix, out_pass_index,
            out_k_group, out_first_group, out_last_group, out_last_pass,
            out_last_block_transaction, out_weights_s4x12x32,
            out_weight_meta_u168, out_col_valid_u12};
    always @(posedge clk) begin
        if (!rst_n || clear) begin
            stalled_input_r <= 1'b0;
            stalled_output_r <= 1'b0;
        end else begin
            if (stalled_input_r &&
                (!in_valid || input_payload !== stalled_input_payload_r))
                $error("gate/up gather input changed under backpressure");
            if (stalled_output_r &&
                (!out_valid || output_payload !== stalled_output_payload_r))
                $error("gate/up gather output changed under backpressure");
            stalled_input_r <= in_valid && !in_ready;
            stalled_output_r <= out_valid && !out_ready;
            if (in_valid && !in_ready)
                stalled_input_payload_r <= input_payload;
            if (out_valid && !out_ready)
                stalled_output_payload_r <= output_payload;
            if (fill_active_r && drain_active_r &&
                fill_bank_r == drain_bank_r)
                $error("gate/up gather bank simultaneously fills and drains");
            if (|fill_we_a & |fill_we_b && !in_fire)
                $error("gate/up gather wrote memory without input handshake");
        end
    end
`endif

    initial begin
        if (GROUPS <= 0 || GROUPS > (1 << GROUP_W))
            $error("gate/up gather GROUPS/GROUP_W contract is invalid");
        if (BANK_DEPTH != 8*GROUPS)
            $error("gate/up gather bank depth must equal 2x4xGROUPS");
        if (BLOCK_W <= 0)
            $error("gate/up gather BLOCK_W must be positive");
    end

endmodule
