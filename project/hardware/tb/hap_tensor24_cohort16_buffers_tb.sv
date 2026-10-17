`timescale 1ns / 1ps

module hap_tensor24_cohort16_buffers_tb;
    reg clk = 1'b0;
    reg rst_n = 1'b0;
    reg clear = 1'b0;

    reg input_wr_valid = 1'b0;
    wire input_wr_ready;
    reg [12:0] input_wr_addr = 13'd0;
    reg [255:0] input_wr_data = 256'd0;
    reg input_load_start = 1'b0;
    wire activation_valid;
    reg activation_ready = 1'b0;
    wire activation_wave;
    wire [6:0] activation_group;
    wire [8*32*24-1:0] activation_s24;
    wire input_busy;
    wire input_error;

    reg output_in_valid = 1'b0;
    wire output_in_ready;
    reg output_in_wave = 1'b0;
    reg [7:0] output_in_tile = 8'd0;
    reg [8*16*24-1:0] output_in_s24 = '0;
    wire output_image_ready;
    reg output_image_release = 1'b0;
    reg output_rd_valid = 1'b0;
    wire output_rd_ready;
    reg [12:0] output_rd_addr = 13'd0;
    wire output_rsp_valid;
    reg output_rsp_ready = 1'b0;
    wire [255:0] output_rsp_data;
    wire output_error;

    integer cycle_count = 0;
    integer checks = 0;
    integer address;
    integer wave;
    integer group;
    integer tile;

    hap_tensor24_input_buffer16 u_input (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .wr_valid(input_wr_valid), .wr_ready(input_wr_ready),
        .wr_addr(input_wr_addr), .wr_data(input_wr_data),
        .load_start(input_load_start),
        .activation_valid(activation_valid),
        .activation_ready(activation_ready),
        .activation_wave(activation_wave),
        .activation_group(activation_group),
        .activation_s24(activation_s24), .busy(input_busy),
        .error(input_error)
    );

    hap_tensor24_output_buffer16 u_output (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(output_in_valid), .in_ready(output_in_ready),
        .in_wave(output_in_wave), .in_tile(output_in_tile),
        .in_s24(output_in_s24), .image_ready(output_image_ready),
        .image_release(output_image_release), .rd_valid(output_rd_valid),
        .rd_ready(output_rd_ready), .rd_addr(output_rd_addr),
        .rsp_valid(output_rsp_valid), .rsp_ready(output_rsp_ready),
        .rsp_data(output_rsp_data), .error(output_error)
    );

    always #3.333 clk = ~clk;
    always @(posedge clk)
        cycle_count <= cycle_count + 1;

    task automatic fail;
        input [8*200-1:0] reason;
        begin
            $display("FAIL: %0s at cycle %0d", reason, cycle_count);
            $finish;
        end
    endtask

    function automatic [255:0] input_beat;
        input integer beat_address;
        integer word;
        reg [255:0] value;
        begin
            value = '0;
            for (word=0; word<8; word=word+1)
                value[word*32 +: 32] =
                    32'ha500_0000 ^ beat_address ^ (word << 20);
            input_beat = value;
        end
    endfunction

    function automatic [23:0] output_lane;
        input integer lane_wave;
        input integer lane_tile;
        input integer lane_row;
        input integer lane_index;
        integer global_col;
        begin
            global_col = lane_tile*16 + lane_index;
            output_lane = {lane_wave[0], lane_row[2:0],
                global_col[11:0],
                (8'h5a ^ lane_wave ^ lane_row ^ global_col)};
        end
    endfunction

    function automatic [8*16*24-1:0] make_output_tile;
        input integer tile_wave;
        input integer tile_index;
        integer row;
        integer lane;
        reg [8*16*24-1:0] value;
        begin
            value = '0;
            for (row=0; row<8; row=row+1)
                for (lane=0; lane<16; lane=lane+1)
                    value[(row*16+lane)*24 +: 24] =
                        output_lane(tile_wave, tile_index, row, lane);
            make_output_tile = value;
        end
    endfunction

    function automatic [255:0] expected_output_beat;
        input integer beat_address;
        integer beat_wave;
        integer local_address;
        integer beat_row;
        integer row_remainder;
        integer beat_group;
        integer beat_index;
        integer lane;
        reg [767:0] row_group;
        begin
            beat_wave = beat_address >= 3072;
            local_address = beat_wave ? beat_address - 3072 : beat_address;
            beat_row = local_address / 384;
            row_remainder = local_address % 384;
            beat_group = row_remainder / 3;
            beat_index = row_remainder % 3;
            row_group = '0;
            for (lane=0; lane<32; lane=lane+1)
                row_group[lane*24 +: 24] = output_lane(
                    beat_wave, beat_group*2 + lane/16,
                    beat_row, lane % 16);
            expected_output_beat = row_group[beat_index*256 +: 256];
        end
    endfunction

    task automatic write_input_beat;
        input integer beat_address;
        integer timeout;
        begin
            timeout = 0;
            while (!input_wr_ready) begin
                @(posedge clk);
                timeout = timeout + 1;
                if (timeout > 10)
                    fail("input write-ready timeout");
            end
            @(negedge clk);
            input_wr_addr = beat_address[12:0];
            input_wr_data = input_beat(beat_address);
            input_wr_valid = 1'b1;
            @(posedge clk);
            if (!input_wr_ready)
                fail("input write ready dropped on handshake");
            @(negedge clk);
            input_wr_valid = 1'b0;
            checks = checks + 1;
        end
    endtask

    task automatic check_activation;
        input integer expected_wave;
        input integer expected_group;
        integer timeout;
        integer stall;
        integer item;
        integer row;
        integer beat;
        integer source_address;
        reg [8*32*24-1:0] held_data;
        begin
            timeout = 0;
            while (!activation_valid) begin
                @(posedge clk);
                timeout = timeout + 1;
                if (timeout > 40)
                    fail("activation-valid timeout");
            end
            if (activation_wave !== expected_wave[0] ||
                    activation_group !== expected_group[6:0])
                fail("activation wave/group sequence mismatch");
            held_data = activation_s24;
            stall = (expected_wave + expected_group) % 4;
            repeat (stall) begin
                @(posedge clk);
                if (!activation_valid || activation_wave !== expected_wave[0] ||
                        activation_group !== expected_group[6:0] ||
                        activation_s24 !== held_data)
                    fail("activation payload changed under backpressure");
            end
            for (item=0; item<24; item=item+1) begin
                row = item / 3;
                beat = item % 3;
                source_address = expected_wave*3072 + row*384 +
                    expected_group*3 + beat;
                if (activation_s24[item*256 +: 256] !==
                        input_beat(source_address))
                    fail("cohort16 input transpose mismatch");
            end
            @(negedge clk);
            activation_ready = 1'b1;
            @(posedge clk);
            if (!activation_valid)
                fail("activation retired before handshake");
            @(negedge clk);
            activation_ready = 1'b0;
            checks = checks + 25;
        end
    endtask

    task automatic send_output_tile;
        input integer tile_wave;
        input integer tile_index;
        integer timeout;
        begin
            @(negedge clk);
            output_in_wave = tile_wave[0];
            output_in_tile = tile_index[7:0];
            output_in_s24 = make_output_tile(tile_wave, tile_index);
            timeout = 0;
            while (!output_in_ready) begin
                @(posedge clk);
                timeout = timeout + 1;
                if (timeout > 40)
                    fail("output tile ready timeout");
            end
            @(negedge clk);
            output_in_valid = 1'b1;
            @(posedge clk);
            if (!output_in_ready)
                fail("output ready dropped on tile handshake");
            @(negedge clk);
            output_in_valid = 1'b0;
            output_in_s24 = 'x;
            checks = checks + 1;
        end
    endtask

    task automatic read_output_beat;
        input integer beat_address;
        integer timeout;
        integer stall;
        reg [255:0] expected;
        begin
            expected = expected_output_beat(beat_address);
            timeout = 0;
            while (!output_rd_ready) begin
                @(posedge clk);
                timeout = timeout + 1;
                if (timeout > 10)
                    fail("output read-ready timeout");
            end
            @(negedge clk);
            output_rd_addr = beat_address[12:0];
            output_rd_valid = 1'b1;
            @(posedge clk);
            if (!output_rd_ready)
                fail("output read ready dropped on handshake");
            @(negedge clk);
            output_rd_valid = 1'b0;
            output_rd_addr = 'x;
            timeout = 0;
            while (!output_rsp_valid) begin
                @(posedge clk);
                timeout = timeout + 1;
                if (timeout > 5)
                    fail("output response timeout");
            end
            stall = beat_address % 3;
            repeat (stall) begin
                @(posedge clk);
                if (!output_rsp_valid || output_rsp_data !== expected)
                    fail("output response changed under backpressure");
            end
            if (output_rsp_data !== expected)
                fail("cohort16 output image mismatch");
            @(negedge clk);
            output_rsp_ready = 1'b1;
            @(posedge clk);
            if (!output_rsp_valid)
                fail("output response retired before handshake");
            @(negedge clk);
            output_rsp_ready = 1'b0;
            checks = checks + 1;
        end
    endtask

    initial begin
        repeat (4) @(posedge clk);
        @(negedge clk);
        rst_n = 1'b1;

        for (address=0; address<6144; address=address+1)
            write_input_beat(address);
        @(negedge clk);
        input_load_start = 1'b1;
        @(posedge clk);
        @(negedge clk);
        input_load_start = 1'b0;

        for (wave=0; wave<2; wave=wave+1)
            for (group=0; group<128; group=group+1)
                check_activation(wave, group);
        @(posedge clk);
        if (input_busy || input_error)
            fail("input buffer did not finish cleanly");

        // Match projection retirement: wave0 then wave1 for every tile.
        for (tile=0; tile<256; tile=tile+1) begin
            send_output_tile(0, tile);
            send_output_tile(1, tile);
        end
        while (!output_image_ready)
            @(posedge clk);
        if (output_error)
            fail("output buffer asserted error before readback");

        for (address=0; address<6144; address=address+1)
            read_output_beat(address);

        @(negedge clk);
        output_image_release = 1'b1;
        @(posedge clk);
        @(negedge clk);
        output_image_release = 1'b0;
        @(posedge clk);
        if (output_image_ready || output_error)
            fail("cohort16 output release failed");

        $display("PASS: hap_tensor24_cohort16_buffers %0d checks; 6144 input beats, 256 groups, 512 tiles, 6144 output beats", checks);
        $finish;
    end

    initial begin
        #5000000;
        fail("global timeout");
    end
endmodule
