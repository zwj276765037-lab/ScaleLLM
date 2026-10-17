`timescale 1ns / 1ps

// Unstalled cadence gate.  Two full supertiles are sent at the maximum legal
// input rate.  The source pauses one cycle for each internal tail pass, but
// after the first output appears the compute stream must have eight
// consecutive valid cycles: pass 0/1/2/3 for each supertile with no bubble.
module hap_mlp_w4_repack48_to12_throughput_tb;
    reg clk = 1'b0;
    always #3.333 clk = ~clk;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    reg in_valid = 1'b0;
    wire in_ready;
    reg [2047:0] in_weights = '0;
    reg [223:0] in_meta = '0;
    reg [31:0] in_tag = '0;
    reg [1:0] in_record = 0;
    reg [15:0] in_mask = 16'hffff;
    reg in_flush = 1'b0;
    wire out_valid;
    wire [1535:0] out_weights;
    wire [167:0] out_meta;
    wire [31:0] out_tag;
    wire [1:0] out_pass;
    wire [11:0] out_mask;
    wire out_last;
    wire [31:0] input_records;
    wire [31:0] input_supertiles;
    wire [31:0] output_passes;
    wire error;
    integer output_index = 0;
    integer cycles = 0;
    reg stream_started = 1'b0;

    hap_mlp_w4_repack48_to12 dut (
        .clk(clk),.rst_n(rst_n),.clear(clear),
        .in_valid(in_valid),.in_ready(in_ready),
        .in_weights_s4x16x32(in_weights),
        .in_weight_meta_u224(in_meta),.in_tag(in_tag),
        .in_record_index(in_record),.in_col_valid_u16(in_mask),
        .in_flush(in_flush),.out_valid(out_valid),.out_ready(1'b1),
        .out_weights_s4x12x32(out_weights),
        .out_weight_meta_u168(out_meta),.out_tag(out_tag),
        .out_pass_index(out_pass),.out_col_valid_u12(out_mask),
        .out_last_pass(out_last),.input_record_count(input_records),
        .input_supertile_count(input_supertiles),
        .output_pass_count(output_passes),.error(error)
    );

    task automatic send_record;
        input [31:0] tag;
        input [1:0] record_index;
        begin
            @(negedge clk);
            in_tag <= tag;
            in_record <= record_index;
            in_flush <= record_index == 2;
            in_weights <= {512{tag[3:0] + record_index}};
            in_meta <= {7{tag + record_index}};
            in_valid <= 1'b1;
            do @(posedge clk); while (!in_ready);
            in_valid <= 1'b0;
        end
    endtask

    always @(posedge clk) begin
        if (!rst_n || clear) begin
            output_index <= 0;
            cycles <= 0;
            stream_started <= 1'b0;
        end else begin
            cycles <= cycles + 1;
            if (stream_started && output_index < 8 && !out_valid)
                $fatal(1,"compute bubble at output_index=%0d",output_index);
            if (out_valid) begin
                stream_started <= 1'b1;
                if (out_tag !== (output_index < 4 ?
                        32'h5100_0000 : 32'h5200_0000) ||
                    out_pass !== output_index[1:0] ||
                    out_mask !== 12'hfff ||
                    out_last !== (output_index[1:0] == 2'd3))
                    $fatal(1,
                        "throughput order mismatch index=%0d tag=%08x pass=%0d mask=%03x last=%0d",
                        output_index,out_tag,out_pass,out_mask,out_last);
                output_index <= output_index + 1;
            end
            if (cycles > 60)
                $fatal(1,"throughput timeout output=%0d",output_index);
        end
    end

    initial begin
        repeat (5) @(posedge clk);
        rst_n <= 1'b1;
        fork
            begin
                send_record(32'h5100_0000,2'd0);
                send_record(32'h5100_0000,2'd1);
                send_record(32'h5100_0000,2'd2);
                send_record(32'h5200_0000,2'd0);
                send_record(32'h5200_0000,2'd1);
                send_record(32'h5200_0000,2'd2);
            end
            begin
                wait(output_index == 8);
                @(posedge clk);
                if (error || input_records != 6 ||
                    input_supertiles != 2 || output_passes != 8)
                    $fatal(1,
                        "throughput counters/error records=%0d supertiles=%0d passes=%0d error=%0d",
                        input_records,input_supertiles,output_passes,error);
                $display("PASS: repack48 compute stream 8 consecutive II=1 passes, input cadence 3 records + 1 internal tail");
                $finish;
            end
        join
    end
endmodule
