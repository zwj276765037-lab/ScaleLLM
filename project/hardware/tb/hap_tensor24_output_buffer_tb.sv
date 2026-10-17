`timescale 1ns / 1ps

module hap_tensor24_output_buffer_tb;
    reg clk = 1'b0;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    reg in_valid = 1'b0;
    wire in_ready;
    reg [7:0] in_tile = 8'd0;
    reg [3071:0] in_s24 = '0;
    wire image_ready;
    reg image_release = 1'b0;
    reg rd_valid = 1'b0;
    wire rd_ready;
    reg [11:0] rd_addr = 12'd0;
    wire rsp_valid;
    reg rsp_ready = 1'b0;
    wire [255:0] rsp_data;
    wire error;

    integer checks = 0;
    integer tile;
    integer row;
    integer beat;
    integer pair_accept_cycle;
    integer cycle_count = 0;
    reg [3071:0] even_reference;
    reg [3071:0] odd_reference;
    reg [255:0] expected_beat;

    hap_tensor24_output_buffer dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready), .in_tile(in_tile),
        .in_s24(in_s24), .image_ready(image_ready),
        .image_release(image_release), .rd_valid(rd_valid),
        .rd_ready(rd_ready), .rd_addr(rd_addr), .rsp_valid(rsp_valid),
        .rsp_ready(rsp_ready), .rsp_data(rsp_data), .error(error)
    );

    always #3.333 clk = ~clk;
    always @(posedge clk)
        cycle_count <= cycle_count + 1;

    task automatic fail;
        input [8*160-1:0] reason;
        begin
            $display("FAIL: %0s at cycle %0d", reason, cycle_count);
            $finish;
        end
    endtask

    function automatic [23:0] lane_value;
        input integer tile_index;
        input integer row_index;
        input integer lane_index;
        begin
            lane_value = {tile_index[7:0], row_index[2:0], lane_index[3:0],
                9'h155 ^ tile_index[8:0] ^ row_index[2:0] ^ lane_index[3:0]};
        end
    endfunction

    function automatic [3071:0] make_tile;
        input integer tile_index;
        integer make_row;
        integer lane;
        reg [3071:0] value;
        begin
            value = '0;
            for (make_row=0; make_row<8; make_row=make_row+1)
                for (lane=0; lane<16; lane=lane+1)
                    value[(make_row*16+lane)*24 +: 24] =
                        lane_value(tile_index, make_row, lane);
            make_tile = value;
        end
    endfunction

    task automatic send_tile;
        input integer tile_index;
        input [3071:0] tile_data;
        integer wait_cycles;
        begin
            wait_cycles = 0;
            while (!in_ready) begin
                @(posedge clk);
                wait_cycles = wait_cycles + 1;
                if (wait_cycles > 40)
                    fail("input ready timeout");
            end
            @(negedge clk);
            in_tile = tile_index[7:0];
            in_s24 = tile_data;
            in_valid = 1'b1;
            @(posedge clk);
            if (!in_ready)
                fail("ready dropped on tile handshake");
            @(negedge clk);
            in_valid = 1'b0;
            in_s24 = 'x;
            checks = checks + 1;
        end
    endtask

    task automatic read_and_check;
        input integer address;
        input [255:0] expected;
        input integer stall_cycles;
        integer wait_cycles;
        begin
            wait_cycles = 0;
            while (!rd_ready) begin
                @(posedge clk);
                wait_cycles = wait_cycles + 1;
                if (wait_cycles > 10)
                    fail("read ready timeout");
            end
            @(negedge clk);
            rd_addr = address[11:0];
            rd_valid = 1'b1;
            @(posedge clk);
            if (!rd_ready)
                fail("ready dropped on read handshake");
            @(negedge clk);
            rd_valid = 1'b0;
            rd_addr = 'x;
            wait_cycles = 0;
            while (!rsp_valid) begin
                @(posedge clk);
                wait_cycles = wait_cycles + 1;
                if (wait_cycles > 5)
                    fail("response timeout");
            end
            repeat (stall_cycles) begin
                @(posedge clk);
                if (!rsp_valid || rsp_data !== expected)
                    fail("response changed under backpressure");
            end
            if (rsp_data !== expected) begin
                $display("address=%0d expected=%064h actual=%064h",
                    address, expected, rsp_data);
                fail("row-major image mismatch");
            end
            @(negedge clk);
            rsp_ready = 1'b1;
            @(posedge clk);
            if (!rsp_valid)
                fail("response retired too early");
            @(negedge clk);
            rsp_ready = 1'b0;
            @(posedge clk);
            if (rsp_valid)
                fail("response did not retire");
            checks = checks + 1;
        end
    endtask

    initial begin
        repeat (4) @(posedge clk);
        @(negedge clk);
        rst_n = 1'b1;

        // First check illegal sequence detection and that clear restores the
        // exact tile-zero protocol state without altering the datapath II.
        send_tile(1, make_tile(1));
        if (!error)
            fail("out-of-order odd tile was not rejected");
        @(negedge clk);
        clear = 1'b1;
        @(posedge clk);
        @(negedge clk);
        clear = 1'b0;
        #1;
        if (error || !in_ready)
            fail("clear failed to restore idle state");
        checks = checks + 2;

        for (tile=0; tile<256; tile=tile+2) begin
            even_reference = make_tile(tile);
            odd_reference = make_tile(tile+1);
            send_tile(tile, even_reference);
            if (!dut.have_even_r)
                fail("even tile protocol state was not retained");
            send_tile(tile+1, odd_reference);
            pair_accept_cycle = cycle_count;
            if (!dut.write_active_r || dut.write_index_r != 0)
                fail("odd tile did not start write engine");

            // The odd banks are captured by the same handshake edge that
            // asserts write_active.  The first BRAM write is one edge later,
            // and therefore must observe the new nonblocking-assignment data.
            @(negedge clk);
            if (!dut.write_active_r || dut.write_index_r != 1)
                fail("first pair beat was not issued exactly one cycle later");
            while (dut.write_active_r)
                @(negedge clk);
            if (cycle_count - pair_accept_cycle != 24)
                fail("pair writer no longer emits exactly 24 beats");
            if ((tile != 254) && !in_ready)
                fail("input did not reopen immediately after pair write");
            checks = checks + 3;
        end

        if (!image_ready || error)
            fail("final expected_tile wrap did not assert image_ready cleanly");
        if (dut.expected_tile_r !== 8'd0)
            fail("final expected_tile did not wrap to zero");
        if (in_ready)
            fail("input accepted while completed image was held");
        checks = checks + 3;

        // Read all 3072 physical beats with deterministic response stalls.
        // Address layout is row*384 + group*3 + beat.
        for (tile=0; tile<256; tile=tile+2) begin
            even_reference = make_tile(tile);
            odd_reference = make_tile(tile+1);
            for (row=0; row<8; row=row+1)
                for (beat=0; beat<3; beat=beat+1) begin
                    case (beat)
                        0: expected_beat = even_reference[row*384 +: 256];
                        1: expected_beat = {
                            odd_reference[row*384 +: 128],
                            even_reference[row*384+256 +: 128]};
                        default: expected_beat =
                            odd_reference[row*384+128 +: 256];
                    endcase
                    read_and_check(row*384 + (tile/2)*3 + beat,
                        expected_beat, (tile + row + beat) % 3);
                end
        end

        @(negedge clk);
        image_release = 1'b1;
        @(posedge clk);
        @(negedge clk);
        image_release = 1'b0;
        #1;
        if (image_ready || !in_ready || dut.expected_tile_r != 0)
            fail("image release failed to reopen tile-zero input");
        checks = checks + 1;

        $display("PASS: hap_tensor24_output_buffer %0d checks; 256 tiles, 3072 bit-exact beats, fixed 24-cycle pair writer", checks);
        $finish;
    end

    initial begin
        #2000000;
        fail("global timeout");
    end
endmodule
