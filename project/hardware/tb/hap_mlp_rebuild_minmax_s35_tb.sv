`timescale 1ns / 1ps

// Raw MinMax Group32 vectors from the selected v5_fullchain.py online A8
// method: include zero, do not preclip an outlier, divide ties to even.
module hap_mlp_rebuild_minmax_s35_tb;
    reg clk = 0;
    always #5 clk = ~clk;
    reg rst_n = 0;
    reg clear = 0;
    reg in_valid = 0;
    wire in_ready;
    reg [32*35-1:0] in_s35 = '0;
    wire out_valid;
    reg out_ready = 0;
    wire [255:0] out_u8;
    wire [23:0] out_meta;
    wire [31:0] input_group_count;
    wire [31:0] output_group_count;
    wire [31:0] cycle_count;
    wire [31:0] format_error_count;
    wire error;

    integer cycles = 0;
    integer received = 0;
    integer checks = 0;
    integer lane;
    reg held = 0;
    reg [255:0] held_data;
    reg [23:0] held_meta;
    reg saw_stall = 0;

    hap_mlp_robust_a8_quantizer_s35 dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready), .in_s35(in_s35),
        .out_valid(out_valid), .out_ready(out_ready),
        .out_u8(out_u8), .out_meta(out_meta),
        .input_group_count(input_group_count),
        .output_group_count(output_group_count),
        .cycle_count(cycle_count),
        .format_error_count(format_error_count), .error(error)
    );

    function automatic [23:0] expected_meta;
        input integer index;
        begin
            case (index)
                0: expected_meta = 24'h000000;
                1: expected_meta = 24'h1ca100; // d=10: shift28, code161, zp0.
                2: expected_meta = 24'h1ca1ff; // d=10: shift28, code161, zp255.
                3: expected_meta = 24'h16fb00; // d=1000: shift22, code251.
                4: expected_meta = 24'h1ba180; // d=20: shift27, code161, zp128.
                default: expected_meta = 'x;
            endcase
        end
    endfunction

    function automatic [7:0] expected_byte;
        input integer index;
        input integer lane_index;
        begin
            case (index)
                0: expected_byte = 0;
                1: expected_byte = lane_index == 1 ? 8'd76 :
                                   lane_index == 2 ? 8'd255 : 8'd0;
                2: expected_byte = lane_index == 0 ? 8'd0 :
                                   lane_index == 1 ? 8'd178 : 8'd230;
                3: expected_byte = lane_index == 1 ? 8'd3 :
                                   lane_index == 2 ? 8'd255 : 8'd0;
                4: expected_byte = lane_index == 0 ? 8'd0 :
                                   lane_index == 2 ? 8'd255 : 8'd128;
                default: expected_byte = 'x;
            endcase
        end
    endfunction

    task automatic send_group;
        input integer index;
        integer source_lane;
        reg signed [34:0] value;
        begin
            @(negedge clk);
            for (source_lane = 0; source_lane < 32;
                 source_lane = source_lane + 1) begin
                value = 0;
                case (index)
                    1: if (source_lane == 1) value = 3;
                       else if (source_lane == 2) value = 10;
                    2: if (source_lane == 0) value = -10;
                       else if (source_lane == 1) value = -3;
                       else value = -1;
                    3: if (source_lane == 1) value = 10;
                       else if (source_lane == 2) value = 1000;
                    4: if (source_lane == 0) value = -10;
                       else if (source_lane == 2) value = 10;
                endcase
                in_s35[source_lane*35 +: 35] = value;
            end
            in_valid = 1;
            do @(posedge clk); while (!in_ready);
            @(negedge clk);
            in_valid = 0;
        end
    endtask

    initial begin
        repeat (5) @(negedge clk);
        rst_n = 1;
        send_group(0);
        send_group(1);
        send_group(2);
        send_group(3);
        send_group(4);
        wait (received == 5);
        repeat (3) @(posedge clk);
        if (saw_stall !== 1'b1 || input_group_count !== 5 ||
            output_group_count !== 5 || format_error_count !== 0 ||
            error !== 1'b0)
            $fatal(1, "MinMax status mismatch in=%0d out=%0d format=%0d error=%0d",
                   input_group_count, output_group_count,
                   format_error_count, error);
        $display("checks=%0d raw_minmax=5 outlier_unclipped=1 tie_even=1", checks);
        $display("HARDWARE_AGENT_SIM_PASS");
        $finish;
    end

    always @(posedge clk) begin
        if (!rst_n || clear) begin
            cycles <= 0;
            out_ready <= 0;
            held <= 0;
        end else begin
            cycles <= cycles + 1;
            out_ready <= saw_stall && (cycles % 7) >= 3;
            if (held && (out_valid !== 1'b1 || out_u8 !== held_data ||
                         out_meta !== held_meta))
                $fatal(1, "MinMax output changed under backpressure");
            held <= out_valid && !out_ready;
            if (out_valid && !out_ready) begin
                held_data <= out_u8;
                held_meta <= out_meta;
                saw_stall <= 1;
            end
            if (out_valid && out_ready) begin
                if (received >= 5 || out_meta !== expected_meta(received))
                    $fatal(1, "MinMax metadata mismatch vector=%0d got=%h expected=%h",
                           received, out_meta, expected_meta(received));
                for (lane = 0; lane < 32; lane = lane + 1) begin
                    if (out_u8[lane*8 +: 8] !== expected_byte(received, lane))
                        $fatal(1, "MinMax U8 mismatch vector=%0d lane=%0d got=%0d",
                               received, lane, out_u8[lane*8 +: 8]);
                    checks = checks + 1;
                end
                received <= received + 1;
            end
            if (cycles > 10000)
                $fatal(1, "MinMax timeout received=%0d", received);
        end
    end
endmodule
