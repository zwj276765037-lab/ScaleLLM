`timescale 1ns/1ps

// Equal-throughput FP PV baseline.  The production SC input can accept one
// key/cycle, while one FP core cannot.  Each replicated core therefore owns a
// complete 128-key row buffer.  Buffering, dispatch, ordered retirement and
// arbitration are all intentionally included in synthesis.
module m9_fp_pv_replicated #(
    parameter integer W = 32,
    parameter integer CASE_ID = 2,
    parameter integer NUM_CORES = 20,
    parameter integer INDEX_W = (NUM_CORES <= 2) ? 1 : $clog2(NUM_CORES),
    parameter integer PAYLOAD_W = 17 * W
) (
    input  wire                 clk,
    input  wire                 rst_n,
    input  wire                 clear,
    input  wire                 in_valid,
    output wire                 in_ready,
    input  wire                 in_first_key,
    input  wire                 in_last_key,
    input  wire [W-1:0]         in_prob,
    input  wire [16*W-1:0]      in_v,
    output wire                 out_valid,
    input  wire                 out_ready,
    output wire [383:0]         out_context16_s24,
    output reg  [31:0]          input_key_count,
    output reg  [31:0]          output_row_count,
    output reg  [31:0]          saturation_count,
    output wire                 error
);
    wire [NUM_CORES-1:0] core_in_ready;
    wire [NUM_CORES-1:0] core_in_valid;
    wire [NUM_CORES-1:0] core_out_valid;
    wire [NUM_CORES-1:0] core_out_ready;
    wire [NUM_CORES-1:0] core_error;
    wire [NUM_CORES*384-1:0] core_context;
    wire [NUM_CORES*32-1:0] core_saturation_count;
    wire [NUM_CORES-1:0] replay_first;
    wire [NUM_CORES-1:0] replay_last;
    wire [NUM_CORES*W-1:0] replay_prob;
    wire [NUM_CORES*16*W-1:0] replay_v;

    reg [NUM_CORES-1:0] bank_busy;
    reg [NUM_CORES-1:0] bank_full;
    reg owner_active;
    reg [INDEX_W-1:0] owner_index;
    reg [6:0] load_key_index;
    reg protocol_error;
    reg candidate_found;
    reg [INDEX_W-1:0] candidate_index;
    reg [INDEX_W-1:0] row_fifo [0:NUM_CORES-1];
    reg [INDEX_W-1:0] read_pointer;
    reg [INDEX_W-1:0] write_pointer;
    reg [INDEX_W:0] queued_rows;
    integer scan;

    always @* begin
        candidate_found = 1'b0;
        candidate_index = {INDEX_W{1'b0}};
        for (scan = 0; scan < NUM_CORES; scan = scan + 1) begin
            if (!candidate_found && !bank_busy[scan]) begin
                candidate_found = 1'b1;
                candidate_index = scan[INDEX_W-1:0];
            end
        end
    end

    wire [INDEX_W-1:0] selected_index = owner_active ?
        owner_index : candidate_index;
    assign in_ready = rst_n && !clear &&
        (owner_active || (candidate_found && in_first_key));
    wire input_fire = in_valid && in_ready;
    wire push_row = input_fire && in_last_key;

    wire have_output_row = queued_rows != 0;
    wire [INDEX_W-1:0] output_index = row_fifo[read_pointer];
    assign out_valid = have_output_row && core_out_valid[output_index];
    assign out_context16_s24 = have_output_row ?
        core_context[output_index*384 +: 384] : 384'd0;
    wire output_fire = out_valid && out_ready;
    // Every PV core emits exactly one context vector per row.
    wire pop_row = output_fire;
    assign error = protocol_error || (|core_error);

    genvar g;
    generate
        for (g = 0; g < NUM_CORES; g = g + 1) begin : banks
            // Keep the payload store in a reset-free RAM process.  Placing the
            // read/write statements in the asynchronously-reset replay FSM
            // makes Vivado dissolve every 128xPAYLOAD_W bank into flip-flops.
            // The memory contents are don't-care until bank_full is asserted,
            // so the RAM itself neither needs nor should have reset logic.
            (* ram_style = "block" *) reg [PAYLOAD_W-1:0] row_memory [0:127];
            reg [PAYLOAD_W-1:0] replay_data;
            reg [6:0] replay_index;
            reg replay_active;
            reg replay_valid;
            reg replay_started;
            wire bank_write = input_fire && (selected_index == g);
            wire replay_fire = replay_valid && core_in_ready[g];

            assign core_in_valid[g] = replay_valid;
            assign replay_first[g] = replay_index == 0;
            assign replay_last[g] = replay_index == 127;
            assign replay_prob[g*W +: W] = replay_data[W-1:0];
            assign replay_v[g*16*W +: 16*W] = replay_data[PAYLOAD_W-1:W];
            assign core_out_ready[g] = have_output_row &&
                (output_index == g) && out_ready;

            always @(posedge clk) begin
                if (bank_write)
                    row_memory[load_key_index] <= {in_v,in_prob};
                if (replay_active && !replay_valid)
                    replay_data <= row_memory[replay_index];
            end

            m9_fp_pv #(.W(W), .CASE_ID(CASE_ID)) core (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(core_in_valid[g]), .in_ready(core_in_ready[g]),
                .in_first_key(replay_first[g]),
                .in_last_key(replay_last[g]),
                .in_prob(replay_prob[g*W +: W]),
                .in_v(replay_v[g*16*W +: 16*W]),
                .out_valid(core_out_valid[g]),
                .out_ready(core_out_ready[g]),
                .out_context16_s24(core_context[g*384 +: 384]),
                .input_key_count(), .output_row_count(),
                .saturation_count(core_saturation_count[g*32 +: 32]),
                .error(core_error[g])
            );

            always @(posedge clk or negedge rst_n) begin
                if (!rst_n) begin
                    replay_index <= 7'd0;
                    replay_active <= 1'b0;
                    replay_valid <= 1'b0;
                    replay_started <= 1'b0;
                end else if (clear) begin
                    replay_index <= 7'd0;
                    replay_active <= 1'b0;
                    replay_valid <= 1'b0;
                    replay_started <= 1'b0;
                end else begin
                    if (!bank_busy[g]) begin
                        replay_index <= 7'd0;
                        replay_active <= 1'b0;
                        replay_valid <= 1'b0;
                        replay_started <= 1'b0;
                    end else if (bank_full[g] && !replay_started) begin
                        replay_index <= 7'd0;
                        replay_active <= 1'b1;
                        replay_valid <= 1'b0;
                        replay_started <= 1'b1;
                    end else begin
                        if (replay_active && !replay_valid) begin
                            replay_valid <= 1'b1;
                        end
                        if (replay_fire) begin
                            replay_valid <= 1'b0;
                            if (replay_index == 127)
                                replay_active <= 1'b0;
                            else
                                replay_index <= replay_index + 1'b1;
                        end
                    end
                end
            end
        end
    endgenerate

    integer lane;
    integer output_saturations;
    always @* begin
        output_saturations = 0;
        for (lane = 0; lane < 16; lane = lane + 1) begin
            if ((out_context16_s24[lane*24 +: 24] == 24'h7fffff) ||
                (out_context16_s24[lane*24 +: 24] == 24'h800000))
                output_saturations = output_saturations + 1;
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            bank_busy <= {NUM_CORES{1'b0}};
            bank_full <= {NUM_CORES{1'b0}};
            owner_active <= 1'b0;
            owner_index <= {INDEX_W{1'b0}};
            load_key_index <= 7'd0;
            protocol_error <= 1'b0;
            read_pointer <= {INDEX_W{1'b0}};
            write_pointer <= {INDEX_W{1'b0}};
            queued_rows <= {(INDEX_W+1){1'b0}};
            input_key_count <= 32'd0;
            output_row_count <= 32'd0;
            saturation_count <= 32'd0;
        end else if (clear) begin
            bank_busy <= {NUM_CORES{1'b0}};
            bank_full <= {NUM_CORES{1'b0}};
            owner_active <= 1'b0;
            owner_index <= {INDEX_W{1'b0}};
            load_key_index <= 7'd0;
            protocol_error <= 1'b0;
            read_pointer <= {INDEX_W{1'b0}};
            write_pointer <= {INDEX_W{1'b0}};
            queued_rows <= {(INDEX_W+1){1'b0}};
            input_key_count <= 32'd0;
            output_row_count <= 32'd0;
            saturation_count <= 32'd0;
        end else begin
            if (in_valid && !owner_active && !in_first_key)
                protocol_error <= 1'b1;
            if (input_fire) begin
                input_key_count <= input_key_count + 1'b1;
                if (!owner_active) begin
                    bank_busy[candidate_index] <= 1'b1;
                    owner_index <= candidate_index;
                    owner_active <= !in_last_key;
                    load_key_index <= in_last_key ? 7'd0 : 7'd1;
                end else begin
                    if (in_first_key)
                        protocol_error <= 1'b1;
                    if (in_last_key) begin
                        owner_active <= 1'b0;
                        load_key_index <= 7'd0;
                    end else begin
                        load_key_index <= load_key_index + 1'b1;
                    end
                end
            end
            if (push_row) begin
                bank_full[selected_index] <= 1'b1;
                row_fifo[write_pointer] <= selected_index;
                if (write_pointer == NUM_CORES-1)
                    write_pointer <= {INDEX_W{1'b0}};
                else
                    write_pointer <= write_pointer + 1'b1;
            end
            if (pop_row) begin
                bank_busy[output_index] <= 1'b0;
                bank_full[output_index] <= 1'b0;
                output_row_count <= output_row_count + 1'b1;
                saturation_count <= saturation_count + output_saturations;
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

module m9_fp16_pv_x18 (
    input wire clk,rst_n,clear,in_valid,output wire in_ready,
    input wire in_first_key,in_last_key,input wire[15:0]in_prob,
    input wire[255:0]in_v,output wire out_valid,input wire out_ready,
    output wire[383:0]out_context16_s24,output wire[31:0]input_key_count,
    output wire[31:0]output_row_count,saturation_count,output wire error
);
    m9_fp_pv_replicated #(.W(16),.CASE_ID(1),.NUM_CORES(18)) u (.*);
endmodule

module m9_fp32_pv_x20 (
    input wire clk,rst_n,clear,in_valid,output wire in_ready,
    input wire in_first_key,in_last_key,input wire[31:0]in_prob,
    input wire[511:0]in_v,output wire out_valid,input wire out_ready,
    output wire[383:0]out_context16_s24,output wire[31:0]input_key_count,
    output wire[31:0]output_row_count,saturation_count,output wire error
);
    m9_fp_pv_replicated #(.W(32),.CASE_ID(2),.NUM_CORES(20)) u (.*);
endmodule

module m9_fp16_pv_x19 (
    input wire clk,rst_n,clear,in_valid,output wire in_ready,
    input wire in_first_key,in_last_key,input wire[15:0]in_prob,
    input wire[255:0]in_v,output wire out_valid,input wire out_ready,
    output wire[383:0]out_context16_s24,output wire[31:0]input_key_count,
    output wire[31:0]output_row_count,saturation_count,output wire error
);
    m9_fp_pv_replicated #(.W(16),.CASE_ID(1),.NUM_CORES(19)) u (.*);
endmodule

module m9_fp32_pv_x21 (
    input wire clk,rst_n,clear,in_valid,output wire in_ready,
    input wire in_first_key,in_last_key,input wire[31:0]in_prob,
    input wire[511:0]in_v,output wire out_valid,input wire out_ready,
    output wire[383:0]out_context16_s24,output wire[31:0]input_key_count,
    output wire[31:0]output_row_count,saturation_count,output wire error
);
    m9_fp_pv_replicated #(.W(32),.CASE_ID(2),.NUM_CORES(21)) u (.*);
endmodule
