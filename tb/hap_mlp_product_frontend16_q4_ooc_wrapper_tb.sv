`timescale 1ns / 1ps

module hap_mlp_product_frontend16_q4_ooc_wrapper_tb;
    localparam integer GROUPS = 1;
    reg clk = 1'b0;
    always #3.333 clk = ~clk;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    wire load_valid;
    wire load_ready;
    wire [31:0] load_product_s32;
    wire result_valid;
    reg result_ready = 1'b1;
    wire [31:0] result_data;
    wire result_last;
    wire [31:0] busy_cycle_count;
    wire error;
    reg [16383:0] product_mem [0:GROUPS-1];
    reg [4095:0] expected_u8_mem [0:GROUPS-1];
    reg [383:0] expected_meta_mem [0:GROUPS-1];
    wire [4479:0] expected_payload =
        {expected_meta_mem[0], expected_u8_mem[0]};
    integer load_word = 0;
    integer result_word = 0;
    integer cycle_count = 0;
    integer mismatch_count = 0;

    assign load_valid = load_word < 512;
    assign load_product_s32 = product_mem[0][load_word*32 +: 32];

    hap_mlp_product_frontend16_q4_ooc_wrapper dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .load_valid(load_valid), .load_ready(load_ready),
        .load_product_s32(load_product_s32),
        .result_valid(result_valid), .result_ready(result_ready),
        .result_data(result_data), .result_last(result_last),
        .busy_cycle_count(busy_cycle_count), .error(error)
    );

    initial begin
        $readmemh("data/mlp_product_frontend16_q4/product_s32x16x32.mem",
            product_mem);
        $readmemh("data/mlp_product_frontend16_q4/expected_u8x16x32.mem",
            expected_u8_mem);
        $readmemh("data/mlp_product_frontend16_q4/expected_meta_u24x16.mem",
            expected_meta_mem);
        repeat (5) @(posedge clk);
        rst_n <= 1'b1;
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            load_word <= 0;
            result_word <= 0;
            cycle_count <= 0;
            mismatch_count <= 0;
            result_ready <= 1'b1;
        end else begin
            cycle_count <= cycle_count + 1;
            result_ready <= (cycle_count % 9) != 4;
            if (load_valid && load_ready)
                load_word <= load_word + 1;
            if (result_valid && result_ready) begin
                if (result_data !==
                    expected_payload[result_word*32 +: 32])
                    mismatch_count <= mismatch_count + 1;
                if (result_last !== (result_word == 139))
                    $fatal(1, "FAIL: result_last word=%0d", result_word);
                result_word <= result_word + 1;
                if (result_last) begin
                    if (mismatch_count == 0 && !error &&
                        result_word == 139) begin
                        $display("PASS: hap_mlp_product_frontend16_q4_ooc_wrapper words=140 cycles=%0d mismatches=0",
                            cycle_count);
                        $finish;
                    end else begin
                        $fatal(1, "FAIL: mismatch=%0d error=%0d words=%0d",
                            mismatch_count, error, result_word+1);
                    end
                end
            end
            if (cycle_count > 3000)
                $fatal(1, "FAIL: timeout load=%0d result=%0d error=%0d",
                    load_word, result_word, error);
        end
    end
endmodule
