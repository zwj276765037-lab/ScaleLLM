`timescale 1ns / 1ps

module hap_mlp_down_activation_cache16_tb;
    localparam integer GROUPS=7;
    reg clk=1'b0;
    always #3.3335 clk=~clk;
    reg rst_n=1'b0, clear=1'b0, in_valid=1'b0, replay_enable=1'b0;
    wire in_ready, out_valid, full, error;
    reg out_ready=1'b0;
    reg [4095:0] in_u8='0;
    reg [383:0] in_meta='0;
    wire [4095:0] out_u8;
    wire [383:0] out_meta;
    wire [31:0] writes, reads;
    integer cycle=0, sent=0, received=0, row, lane;

    hap_mlp_down_activation_cache16 #(.GROUPS(GROUPS)) dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready),
        .in_u8x16x32(in_u8), .in_meta_u24x16(in_meta),
        .replay_enable(replay_enable), .out_valid(out_valid),
        .out_ready(out_ready), .out_u8x16x32(out_u8),
        .out_meta_u24x16(out_meta), .full(full),
        .write_group_count(writes), .read_group_count(reads), .error(error)
    );

    task automatic drive_group(input integer group);
        begin
            for (row=0; row<16; row=row+1) begin
                in_meta[row*24 +: 24] = (group<<12)|(row<<4)|3;
                for (lane=0; lane<32; lane=lane+1)
                    in_u8[(row*32+lane)*8 +: 8] =
                        (group*37+row*11+lane) & 8'hff;
            end
        end
    endtask

    task automatic check_group(input integer group);
        reg [23:0] expected_meta;
        reg [7:0] expected_u8;
        begin
            for (row=0; row<16; row=row+1) begin
                expected_meta=(group<<12)|(row<<4)|3;
                if (out_meta[row*24 +: 24] !== expected_meta)
                    $fatal(1,"FAIL meta group=%0d row=%0d",group,row);
                for (lane=0; lane<32; lane=lane+1) begin
                    expected_u8=(group*37+row*11+lane)&8'hff;
                    if (out_u8[(row*32+lane)*8 +: 8] !== expected_u8)
                        $fatal(1,"FAIL u8 group=%0d row=%0d lane=%0d",
                            group,row,lane);
                end
            end
        end
    endtask

    initial begin
        repeat(6) @(posedge clk);
        rst_n<=1'b1;
        repeat(2) @(posedge clk);
        for (sent=0; sent<GROUPS; sent=sent+1) begin
            @(negedge clk); drive_group(sent); in_valid<=1'b1;
            do @(posedge clk); while(!in_ready);
        end
        @(negedge clk); in_valid<=1'b0;
        if (!full || writes!=GROUPS)
            $fatal(1,"FAIL cache not full writes=%0d",writes);
        repeat(5) @(posedge clk);
        if (out_valid) $fatal(1,"FAIL replay began before enable");
        replay_enable<=1'b1;
    end

    always @(negedge clk)
        out_ready <= rst_n && replay_enable && cycle%5!=2;

    always @(posedge clk) if (rst_n) begin
        cycle<=cycle+1;
        if (out_valid&&out_ready) begin
            check_group(received);
            received<=received+1;
        end
        if (received==GROUPS) begin
            if (reads!=GROUPS || writes!=GROUPS || error)
                $fatal(1,"FAIL counters writes=%0d reads=%0d error=%0d",
                    writes,reads,error);
            $display("PASS: hap_mlp_down_activation_cache16 groups=%0d writes=%0d reads=%0d mismatches=0 cycles=%0d",
                GROUPS,writes,reads,cycle);
            $finish;
        end
        if (error) $fatal(1,"FAIL sticky error cycle=%0d",cycle);
        if (cycle>300) $fatal(1,"FAIL timeout sent=%0d received=%0d",
            sent,received);
    end
endmodule
