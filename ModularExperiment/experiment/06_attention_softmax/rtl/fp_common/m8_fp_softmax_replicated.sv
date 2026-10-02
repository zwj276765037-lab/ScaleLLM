`timescale 1ns/1ps

// Row-granular dispatcher for the equal-throughput FP baseline.  A row is
// kept on one core, completed rows are retired in input order, and the common
// output remains one U16 probability per cycle.  Scheduler/queue cost is
// intentionally part of the synthesized baseline.
module m8_fp_softmax_replicated #(
    parameter integer W = 32,
    parameter integer CASE_ID = 2,
    parameter integer NUM_CORES = 26,
    parameter integer INDEX_W = (NUM_CORES <= 2) ? 1 : $clog2(NUM_CORES)
) (
    input  wire                 clk,
    input  wire                 rst_n,
    input  wire                 clear,
    input  wire                 in_valid,
    output wire                 in_ready,
    input  wire                 in_first_key,
    input  wire                 in_last_key,
    input  wire                 in_mask,
    input  wire [W-1:0]         in_score,
    output wire                 out_valid,
    input  wire                 out_ready,
    output wire [15:0]          out_prob_u16,
    output wire [6:0]           out_key_index,
    output wire                 out_last_key,
    output reg  [31:0]          input_score_count,
    output reg  [31:0]          output_prob_count,
    output reg  [31:0]          row_count,
    output wire                 error
);
    wire [NUM_CORES-1:0] core_in_ready;
    wire [NUM_CORES-1:0] core_in_valid;
    wire [NUM_CORES-1:0] core_out_valid;
    wire [NUM_CORES-1:0] core_out_ready;
    wire [NUM_CORES-1:0] core_out_last;
    wire [NUM_CORES-1:0] core_error;
    wire [NUM_CORES*16-1:0] core_prob;
    wire [NUM_CORES*7-1:0] core_key_index;
    wire [NUM_CORES-1:0] core_buffer_full;
    wire [NUM_CORES*16-1:0] core_buffer_prob;
    wire [NUM_CORES*7-1:0] core_buffer_last_index;

    reg owner_active;
    reg [INDEX_W-1:0] owner_index;
    reg [NUM_CORES-1:0] core_busy;
    reg protocol_error;
    reg [INDEX_W-1:0] row_fifo [0:NUM_CORES-1];
    reg [INDEX_W-1:0] read_pointer;
    reg [INDEX_W-1:0] write_pointer;
    reg [INDEX_W:0] queued_rows;
    reg [6:0] retire_key_index;
    reg candidate_found;
    reg [INDEX_W-1:0] candidate_index;
    integer scan;

    always @* begin
        candidate_found = 1'b0;
        candidate_index = {INDEX_W{1'b0}};
        for (scan = 0; scan < NUM_CORES; scan = scan + 1) begin
            if (!candidate_found && !core_busy[scan] &&
                    core_in_ready[scan]) begin
                candidate_found = 1'b1;
                candidate_index = scan[INDEX_W-1:0];
            end
        end
    end

    wire [INDEX_W-1:0] selected_index = owner_active ?
        owner_index : candidate_index;
    wire can_start_row = candidate_found && in_first_key &&
        (queued_rows < NUM_CORES);
    assign in_ready = rst_n && !clear &&
        (owner_active ? core_in_ready[owner_index] : can_start_row);
    wire input_fire = in_valid && in_ready;
    wire push_row = input_fire && in_last_key;

    wire have_output_row = (queued_rows != 0);
    wire [INDEX_W-1:0] output_index = have_output_row ?
        row_fifo[read_pointer] : {INDEX_W{1'b0}};
    assign out_valid = have_output_row && core_buffer_full[output_index];
    assign out_prob_u16 = have_output_row ?
        core_buffer_prob[output_index*16 +: 16] : 16'd0;
    assign out_key_index = have_output_row ? retire_key_index : 7'd0;
    assign out_last_key = have_output_row &&
        (retire_key_index ==
            core_buffer_last_index[output_index*7 +: 7]);
    wire output_fire = out_valid && out_ready;
    wire pop_row = output_fire && out_last_key;
    assign error = protocol_error || (|core_error);

    genvar g;
    generate
        for (g = 0; g < NUM_CORES; g = g + 1) begin : cores
            reg [15:0] result_buffer [0:127];
            reg buffer_full;
            reg [6:0] buffer_last_index;

            assign core_in_valid[g] = input_fire && (selected_index == g);
            // Each FP leaf is drained into a complete row buffer immediately.
            // This decouples its multi-cycle per-probability pipeline from the
            // common one-probability/cycle retirement interface.  The buffer,
            // scheduler and mux are intentionally included in OOC resources.
            assign core_out_ready[g] = !buffer_full;
            assign core_buffer_full[g] = buffer_full;
            assign core_buffer_prob[g*16 +: 16] =
                result_buffer[retire_key_index];
            assign core_buffer_last_index[g*7 +: 7] = buffer_last_index;
            m8_fp_softmax #(.W(W), .CASE_ID(CASE_ID)) core (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(core_in_valid[g]),
                .in_ready(core_in_ready[g]),
                .in_first_key(in_first_key),
                .in_last_key(in_last_key),
                .in_mask(in_mask), .in_score(in_score),
                .out_valid(core_out_valid[g]),
                .out_ready(core_out_ready[g]),
                .out_prob_u16(core_prob[g*16 +: 16]),
                .out_key_index(core_key_index[g*7 +: 7]),
                .out_last_key(core_out_last[g]),
                .input_score_count(), .output_prob_count(), .row_count(),
                .error(core_error[g])
            );

            always @(posedge clk or negedge rst_n) begin
                if (!rst_n) begin
                    buffer_full <= 1'b0;
                    buffer_last_index <= 7'd0;
                end else if (clear) begin
                    buffer_full <= 1'b0;
                    buffer_last_index <= 7'd0;
                end else begin
                    if (core_out_valid[g] && core_out_ready[g]) begin
                        result_buffer[core_key_index[g*7 +: 7]] <=
                            core_prob[g*16 +: 16];
                        if (core_out_last[g]) begin
                            buffer_full <= 1'b1;
                            buffer_last_index <=
                                core_key_index[g*7 +: 7];
                        end
                    end
                    if (pop_row && (output_index == g))
                        buffer_full <= 1'b0;
                end
            end
        end
    endgenerate

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            owner_active <= 1'b0;
            owner_index <= {INDEX_W{1'b0}};
            core_busy <= {NUM_CORES{1'b0}};
            protocol_error <= 1'b0;
            read_pointer <= {INDEX_W{1'b0}};
            write_pointer <= {INDEX_W{1'b0}};
            queued_rows <= {(INDEX_W+1){1'b0}};
            retire_key_index <= 7'd0;
            input_score_count <= 32'd0;
            output_prob_count <= 32'd0;
            row_count <= 32'd0;
        end else if (clear) begin
            owner_active <= 1'b0;
            owner_index <= {INDEX_W{1'b0}};
            core_busy <= {NUM_CORES{1'b0}};
            protocol_error <= 1'b0;
            read_pointer <= {INDEX_W{1'b0}};
            write_pointer <= {INDEX_W{1'b0}};
            queued_rows <= {(INDEX_W+1){1'b0}};
            retire_key_index <= 7'd0;
            input_score_count <= 32'd0;
            output_prob_count <= 32'd0;
            row_count <= 32'd0;
        end else begin
            if (in_valid && !owner_active && !in_first_key)
                protocol_error <= 1'b1;
            if (input_fire) begin
                input_score_count <= input_score_count + 1'b1;
                if (owner_active && in_first_key)
                    protocol_error <= 1'b1;
                if (!owner_active) begin
                    owner_index <= candidate_index;
                    owner_active <= !in_last_key;
                    core_busy[candidate_index] <= 1'b1;
                end else if (in_last_key) begin
                    owner_active <= 1'b0;
                end
            end
            if (push_row) begin
                row_fifo[write_pointer] <= selected_index;
                if (write_pointer == NUM_CORES-1)
                    write_pointer <= {INDEX_W{1'b0}};
                else
                    write_pointer <= write_pointer + 1'b1;
            end
            if (output_fire) begin
                output_prob_count <= output_prob_count + 1'b1;
                if (out_last_key) begin
                    row_count <= row_count + 1'b1;
                    retire_key_index <= 7'd0;
                end else begin
                    retire_key_index <= retire_key_index + 1'b1;
                end
            end
            if (pop_row) begin
                core_busy[output_index] <= 1'b0;
                if (read_pointer == NUM_CORES-1)
                    read_pointer <= {INDEX_W{1'b0}};
                else
                    read_pointer <= read_pointer + 1'b1;
            end
            case ({push_row, pop_row})
                2'b10: queued_rows <= queued_rows + 1'b1;
                2'b01: queued_rows <= queued_rows - 1'b1;
                default: queued_rows <= queued_rows;
            endcase
        end
    end
endmodule

module m8_fp16_softmax_x22 (
    input wire clk,rst_n,clear,in_valid,output wire in_ready,
    input wire in_first_key,in_last_key,in_mask,input wire[15:0]in_score,
    output wire out_valid,input wire out_ready,output wire[15:0]out_prob_u16,
    output wire[6:0]out_key_index,output wire out_last_key,
    output wire[31:0]input_score_count,output wire[31:0]output_prob_count,row_count,
    output wire error
);
    m8_fp_softmax_replicated #(.W(16),.CASE_ID(1),.NUM_CORES(22)) u (.*);
endmodule

module m8_fp32_softmax_x26 (
    input wire clk,rst_n,clear,in_valid,output wire in_ready,
    input wire in_first_key,in_last_key,in_mask,input wire[31:0]in_score,
    output wire out_valid,input wire out_ready,output wire[15:0]out_prob_u16,
    output wire[6:0]out_key_index,output wire out_last_key,
    output wire[31:0]input_score_count,output wire[31:0]output_prob_count,row_count,
    output wire error
);
    m8_fp_softmax_replicated #(.W(32),.CASE_ID(2),.NUM_CORES(26)) u (.*);
endmodule
