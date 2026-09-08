`timescale 1ns / 1ps

// Targeted regression for the production Attention metadata URAM boundary.
// In particular, a remote response-ready transition must not fall through to
// the URAM read enable while a response is occupied.  The board controller
// has one pending slot, so the next request is accepted on the following
// cycle with no command-level throughput loss.
module hap_weight_meta_resident_ready_boundary_tb;
    localparam integer DEPTH = 81920;
    localparam integer ADDR_W = 17;

    reg clk = 1'b0;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    reg wr_valid = 1'b0;
    wire wr_ready;
    reg [ADDR_W-1:0] wr_addr = '0;
    reg [255:0] wr_meta16 = '0;
    reg rd_valid = 1'b0;
    wire rd_ready;
    reg [ADDR_W-1:0] rd_addr = '0;
    wire rsp_valid;
    reg rsp_ready = 1'b0;
    wire [255:0] rsp_meta16;
    wire [31:0] write_count;
    wire [31:0] read_count;
    wire [31:0] format_error_count;
    wire error;

    integer checks = 0;
    integer cycles = 0;
    reg [255:0] value0;
    reg [255:0] value1;

    always #3.333 clk = ~clk;
    always @(posedge clk) begin
        cycles <= cycles + 1;
        if (cycles == 200) begin
            $display("FAIL timeout");
            $fatal(1);
        end
    end

    hap_weight_meta_resident dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .wr_valid(wr_valid), .wr_ready(wr_ready), .wr_addr(wr_addr),
        .wr_meta16(wr_meta16), .rd_valid(rd_valid), .rd_ready(rd_ready),
        .rd_addr(rd_addr), .rsp_valid(rsp_valid), .rsp_ready(rsp_ready),
        .rsp_meta16(rsp_meta16), .write_count(write_count),
        .read_count(read_count), .format_error_count(format_error_count),
        .error(error)
    );

    task tick;
        begin @(posedge clk); #1; end
    endtask

    task check;
        input condition;
        input [8*96-1:0] message;
        begin
            checks = checks + 1;
            if (!condition) begin
                $display("FAIL check=%0d %0s", checks, message);
                $fatal(1);
            end
        end
    endtask

    task write_one;
        input [ADDR_W-1:0] addr;
        input [255:0] value;
        begin
            wr_addr = addr;
            wr_meta16 = value;
            wr_valid = 1'b1;
            #0.1;
            check(wr_ready, "valid metadata write was not ready");
            tick();
            wr_valid = 1'b0;
        end
    endtask

    initial begin
        // Legal ScaleCode metadata: low code byte nonzero, reserved bits zero.
        value0 = 256'd0;
        value1 = 256'd0;
        value0[7:0] = 8'h11;
        value1[7:0] = 8'h22;

        repeat (4) tick();
        rst_n = 1'b1;
        tick();
        check(rd_ready && !rsp_valid,
            "reset response state was not empty/ready");

        write_one(17'd7, value0);
        write_one(17'd8, value1);
        check(write_count == 2, "write count mismatch");
        check(!error && format_error_count == 0,
            "legal metadata raised a format error");

        // Request address 7 and retain its response under backpressure.
        rd_addr = 17'd7;
        rd_valid = 1'b1;
        #0.1;
        check(rd_ready, "first request was not accepted");
        tick();
        rd_valid = 1'b0;
        tick();
        check(rsp_valid && rsp_meta16 === value0,
            "first response payload mismatch");

        // A ready pulse and a new valid request in the same occupied cycle
        // consume only the response.  rd_ready must remain low independently
        // of remote rsp_ready; otherwise the old combinational path returns.
        rd_addr = 17'd8;
        rd_valid = 1'b1;
        rsp_ready = 1'b1;
        #0.1;
        check(!rd_ready,
            "rsp_ready fell through to occupied URAM request enable");
        tick();
        rsp_ready = 1'b0;
        #0.1;
        check(!rsp_valid && rd_ready,
            "local response boundary did not reopen after consume");

        // Keep rd_valid asserted: address 8 is accepted now, exactly once.
        tick();
        rd_valid = 1'b0;
        tick();
        check(rsp_valid && rsp_meta16 === value1,
            "second response payload/order mismatch");
        check(read_count == 1,
            "response read counter advanced before second consume");
        rsp_ready = 1'b1;
        tick();
        rsp_ready = 1'b0;
        check(read_count == 2 && !rsp_valid,
            "final response count/valid mismatch");
        check(!error, "unexpected sticky error");

        // Clear must close both local request and response boundaries.
        clear = 1'b1;
        #0.1;
        check(!rd_ready && !rsp_valid, "clear did not close boundary");
        tick();
        clear = 1'b0;
        tick();
        check(read_count == 0 && write_count == 0,
            "clear did not reset counters");

        $display("PASS hap_weight_meta_resident_ready_boundary checks=%0d cycles=%0d",
            checks, cycles);
        $finish;
    end
endmodule
