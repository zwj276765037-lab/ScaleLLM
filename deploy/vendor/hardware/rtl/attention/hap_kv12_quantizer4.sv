`timescale 1ns / 1ps

// Four-group ABI implemented with four parallel bit-exact workers.
//
// The earlier two-worker/two-wave resource closure passed xsim projection but
// measured 12,257,413 cycles over 32 real board layers (97.90 token/s).  Four
// workers remove the second quantization wave while preserving the external
// ready/valid contract, tagged lane identity and every numeric operation.
module hap_kv12_quantizer4 (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  clear,
    input  wire                  in_valid,
    output wire                  in_ready,
    input  wire [4*32*24-1:0]    in_s24,
    output wire                  out_valid,
    input  wire                  out_ready,
    output wire [1:0]            out_lane,
    output wire                  out_batch_last,
    output wire [32*12-1:0]      out_s12,
    output wire [15:0]           out_meta,
    output reg  [31:0]           input_batch_count,
    output reg  [31:0]           output_group_count,
    output wire                  error
);

    wire [3:0] worker_in_ready;
    wire [3:0] worker_in_valid;
    wire [3:0] worker_out_valid;
    wire [3:0] worker_out_ready;
    wire [4*384-1:0] worker_out_s12;
    wire [4*16-1:0] worker_out_meta;
    wire [3:0] worker_error;

    reg batch_active_r;
    reg [3:0] worker_done_r;
    reg [1:0] selected_worker_r;

    assign in_ready = rst_n && !clear && !batch_active_r &&
        (&worker_in_ready);
    wire in_fire = in_valid && in_ready;
    assign worker_in_valid = {4{in_fire}};

    always @* begin
        if (worker_out_valid[0] && !worker_done_r[0])
            selected_worker_r = 2'd0;
        else if (worker_out_valid[1] && !worker_done_r[1])
            selected_worker_r = 2'd1;
        else if (worker_out_valid[2] && !worker_done_r[2])
            selected_worker_r = 2'd2;
        else
            selected_worker_r = 2'd3;
    end

    wire [3:0] selected_onehot = 4'b0001 << selected_worker_r;
    wire selected_valid = |(worker_out_valid & ~worker_done_r);
    assign out_valid = batch_active_r && selected_valid;
    assign out_lane = selected_worker_r;
    assign out_batch_last =
        ((worker_done_r | selected_onehot) == 4'b1111);
    assign out_s12 = worker_out_s12[selected_worker_r*384 +: 384];
    assign out_meta = worker_out_meta[selected_worker_r*16 +: 16];
    assign error = |worker_error;
    wire out_fire = out_valid && out_ready;

    generate
        genvar worker;
        for (worker = 0; worker < 4; worker = worker + 1) begin : g_worker
            assign worker_out_ready[worker] = out_ready && out_valid &&
                (selected_worker_r == worker);
            hap_kv12_quantizer u_quantizer (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(worker_in_valid[worker]),
                .in_ready(worker_in_ready[worker]),
                .in_s24(in_s24[worker*768 +: 768]),
                .out_valid(worker_out_valid[worker]),
                .out_ready(worker_out_ready[worker]),
                .out_s12(worker_out_s12[worker*384 +: 384]),
                .out_meta(worker_out_meta[worker*16 +: 16]),
                .input_group_count(), .output_group_count(),
                .clip_count(), .cycle_count(), .error(worker_error[worker])
            );
        end
    endgenerate

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            batch_active_r <= 1'b0;
            worker_done_r <= 4'b0000;
            input_batch_count <= 32'd0;
            output_group_count <= 32'd0;
        end else if (clear) begin
            batch_active_r <= 1'b0;
            worker_done_r <= 4'b0000;
            input_batch_count <= 32'd0;
            output_group_count <= 32'd0;
        end else begin
            if (in_fire) begin
                batch_active_r <= 1'b1;
                worker_done_r <= 4'b0000;
                input_batch_count <= input_batch_count + 32'd1;
            end

            if (out_fire) begin
                output_group_count <= output_group_count + 32'd1;
                if ((worker_done_r | selected_onehot) == 4'b1111) begin
                    worker_done_r <= 4'b0000;
                    batch_active_r <= 1'b0;
                end else begin
                    worker_done_r <= worker_done_r | selected_onehot;
                end
            end
        end
    end

endmodule
