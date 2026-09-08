`timescale 1ns / 1ps

module hap_axi512_w4_weight_reader_tb;
    localparam integer GROUPS = 24;
    localparam integer BEATS = GROUPS*2;
    reg clk = 1'b0;
    always #2.5 clk = ~clk;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    reg cmd_valid = 1'b0;
    wire cmd_ready;
    wire beat_valid;
    reg beat_ready = 1'b1;
    wire [511:0] beat_data;
    wire beat_group_last;
    wire arvalid;
    reg arready = 1'b1;
    wire [31:0] araddr;
    wire [7:0] arlen;
    wire [2:0] arsize;
    wire [1:0] arburst;
    reg rvalid = 1'b0;
    wire rready;
    wire [511:0] rdata;
    reg [1:0] rresp = 2'b00;
    wire rlast;
    wire busy;
    wire done;
    wire error;
    wire [31:0] command_count;
    wire [31:0] issued_burst_count;
    wire [31:0] received_burst_count;
    wire [31:0] received_beat_count;
    wire [31:0] emitted_group_count;
    wire [31:0] protocol_error_count;
    wire [31:0] max_outstanding_count;
    wire [31:0] reader_elapsed_cycle_count;
    wire [31:0] ar_stall_cycle_count;
    wire [31:0] r_backpressure_cycle_count;
    wire [31:0] response_idle_cycle_count;

    integer sent_beat = 0;
    integer accepted_beat = 0;
    integer accepted_group = 0;
    integer cycle_count = 0;
    integer next_burst_last = 15;
    reg command_sent = 1'b0;
    assign rdata = {{480{1'b0}}, sent_beat[31:0]};
    assign rlast = sent_beat[3:0] == 15;

    hap_axi512_w4_weight_reader dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .cmd_valid(cmd_valid), .cmd_ready(cmd_ready),
        .cmd_base_addr(32'h0010_0000),
        .cmd_group_count(20'(GROUPS)),
        .beat_valid(beat_valid), .beat_ready(beat_ready),
        .beat_data(beat_data), .beat_group_last(beat_group_last),
        .m_axi_arvalid(arvalid), .m_axi_arready(arready),
        .m_axi_araddr(araddr), .m_axi_arlen(arlen),
        .m_axi_arsize(arsize), .m_axi_arburst(arburst),
        .m_axi_rvalid(rvalid), .m_axi_rready(rready),
        .m_axi_rdata(rdata), .m_axi_rresp(rresp), .m_axi_rlast(rlast),
        .busy(busy), .done(done), .error(error),
        .command_count(command_count),
        .issued_burst_count(issued_burst_count),
        .received_burst_count(received_burst_count),
        .received_beat_count(received_beat_count),
        .emitted_group_count(emitted_group_count),
        .protocol_error_count(protocol_error_count),
        .max_outstanding_count(max_outstanding_count),
        .reader_elapsed_cycle_count(reader_elapsed_cycle_count),
        .ar_stall_cycle_count(ar_stall_cycle_count),
        .r_backpressure_cycle_count(r_backpressure_cycle_count),
        .response_idle_cycle_count(response_idle_cycle_count)
    );

    initial begin
        repeat (5) @(posedge clk);
        rst_n <= 1'b1;
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            cycle_count <= 0;
            sent_beat <= 0;
            accepted_beat <= 0;
            accepted_group <= 0;
            command_sent <= 1'b0;
            cmd_valid <= 1'b0;
            rvalid <= 1'b0;
            beat_ready <= 1'b1;
        end else begin
            cycle_count <= cycle_count + 1;
            cmd_valid <= !command_sent;
            if (cmd_valid && cmd_ready)
                command_sent <= 1'b1;
            beat_ready <= (cycle_count % 7) != 3;
            rvalid <= busy && sent_beat < BEATS &&
                (cycle_count % 5) != 2;
            if (rvalid && rready)
                sent_beat <= sent_beat + 1;
            if (beat_valid && beat_ready) begin
                if (beat_data[31:0] !== accepted_beat ||
                    beat_group_last !== accepted_beat[0])
                    $fatal(1,
                        "FAIL beat=%0d data=%0d group_last=%0d",
                        accepted_beat, beat_data[31:0],
                        beat_group_last);
                accepted_beat <= accepted_beat + 1;
                if (beat_group_last)
                    accepted_group <= accepted_group + 1;
            end
            if (done) begin
                if (!error && accepted_beat == BEATS &&
                    accepted_group == GROUPS &&
                    command_count == 1 && issued_burst_count == 3 &&
                    received_burst_count == 3 &&
                    received_beat_count == BEATS &&
                    emitted_group_count == GROUPS &&
                    protocol_error_count == 0 &&
                    reader_elapsed_cycle_count >= BEATS &&
                    r_backpressure_cycle_count != 0 &&
                    response_idle_cycle_count != 0 &&
                    arlen == 15 && arsize == 6 && arburst == 1) begin
                    $display("PASS: hap_axi512_w4_weight_reader groups=%0d beats=%0d bursts=%0d raw_bytes=%0d cycles=%0d elapsed=%0d ar_stall=%0d r_backpressure=%0d response_idle=%0d",
                        GROUPS, BEATS, received_burst_count,
                        received_beat_count*64, cycle_count,
                        reader_elapsed_cycle_count, ar_stall_cycle_count,
                        r_backpressure_cycle_count,
                        response_idle_cycle_count);
                    $finish;
                end else begin
                    $fatal(1,
                        "FAIL error=%0d accepted=%0d groups=%0d bursts=%0d/%0d beats=%0d emitted=%0d protocol=%0d",
                        error, accepted_beat, accepted_group,
                        issued_burst_count, received_burst_count,
                        received_beat_count, emitted_group_count,
                        protocol_error_count);
                end
            end
            if (cycle_count > 1000)
                $fatal(1, "FAIL timeout");
        end
    end
endmodule
