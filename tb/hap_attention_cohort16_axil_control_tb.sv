`timescale 1ns / 1ps

module hap_attention_cohort16_axil_control_tb;
    reg clk = 1'b0;
    reg rst_n = 1'b0;
    always #3.333 clk = ~clk;

    reg [11:0] awaddr = 12'd0;
    reg awvalid = 1'b0;
    wire awready;
    reg [31:0] wdata = 32'd0;
    reg [3:0] wstrb = 4'd0;
    reg wvalid = 1'b0;
    wire wready;
    wire [1:0] bresp;
    wire bvalid;
    reg bready = 1'b0;
    reg [11:0] araddr = 12'd0;
    reg arvalid = 1'b0;
    wire arready;
    wire [31:0] rdata;
    wire [1:0] rresp;
    wire rvalid;
    reg rready = 1'b0;

    reg engine_busy = 1'b0;
    reg launch_enable = 1'b1;
    reg maintenance_busy = 1'b0;
    reg engine_done = 1'b0;
    reg engine_error = 1'b0;
    reg completion_valid = 1'b0;
    reg [31:0] completion_request_id = 32'd0;
    reg [31:0] completion_command_id = 32'd0;
    reg [15:0] completion_cohort_id = 16'd0;
    reg [15:0] completion_buffer_id = 16'd0;
    reg [5:0] completion_layer_id = 6'd0;
    reg [2:0] completion_op_id = 3'd0;
    reg [7:0] completion_status = 8'd0;

    wire start_pulse;
    wire clear_pulse;
    wire reload_metadata;
    wire reload_rope;
    wire preserve_historical_kv;
    wire [31:0] request_id;
    wire [31:0] command_id;
    wire [15:0] cohort_id;
    wire [15:0] buffer_id;
    wire [31:0] layer_id;
    wire [6:0] query_start;
    wire [7:0] valid_key_count;
    wire [7:0] query_count;
    wire [31:0] run_format_id;
    wire [31:0] input_base;
    wire [31:0] output_base;
    wire [31:0] weight_c0_base;
    wire [31:0] weight_c1_base;
    wire [31:0] weight_meta_base;
    wire [31:0] rope_base;
    wire irq;
    wire done_sticky;
    wire error_sticky;

    integer checks = 0;
    integer starts = 0;

    hap_attention_cohort16_axil_control dut (
        .clk(clk), .rst_n(rst_n),
        .s_axil_awaddr(awaddr), .s_axil_awvalid(awvalid),
        .s_axil_awready(awready), .s_axil_wdata(wdata),
        .s_axil_wstrb(wstrb), .s_axil_wvalid(wvalid),
        .s_axil_wready(wready), .s_axil_bresp(bresp),
        .s_axil_bvalid(bvalid), .s_axil_bready(bready),
        .s_axil_araddr(araddr), .s_axil_arvalid(arvalid),
        .s_axil_arready(arready), .s_axil_rdata(rdata),
        .s_axil_rresp(rresp), .s_axil_rvalid(rvalid),
        .s_axil_rready(rready), .engine_busy(engine_busy),
        .launch_enable(launch_enable), .maintenance_busy(maintenance_busy),
        .engine_done(engine_done), .engine_error(engine_error),
        .engine_error_code(32'h4000_1234), .metadata_loaded(1'b1),
        .rope_loaded(1'b1), .cycle_count(32'h101),
        .weight_group_count(32'd81920), .projection_tile_count(32'd640),
        .attention_row_count(32'd512), .wo_tile_count(32'd256),
        .input_frontend_cycle_count(32'h102),
        .qkv_projection_cycle_count(32'h103), .rope_cycle_count(32'h104),
        .kv12_cycle_count(32'h105), .attention_cycle_count(32'h106),
        .context_frontend_cycle_count(32'h107),
        .wo_projection_cycle_count(32'h108),
        .control_overhead_cycle_count(32'h109),
        .completion_valid(completion_valid),
        .completion_request_id(completion_request_id),
        .completion_command_id(completion_command_id),
        .completion_cohort_id(completion_cohort_id),
        .completion_buffer_id(completion_buffer_id),
        .completion_layer_id(completion_layer_id),
        .completion_op_id(completion_op_id),
        .completion_status(completion_status), .start_pulse(start_pulse),
        .clear_pulse(clear_pulse), .reload_metadata(reload_metadata),
        .reload_rope(reload_rope),
        .preserve_historical_kv(preserve_historical_kv),
        .request_id(request_id), .command_id(command_id),
        .cohort_id(cohort_id), .buffer_id(buffer_id), .layer_id(layer_id),
        .query_start(query_start), .valid_key_count(valid_key_count),
        .query_count(query_count), .run_format_id(run_format_id),
        .input_base(input_base), .output_base(output_base),
        .weight_c0_base(weight_c0_base), .weight_c1_base(weight_c1_base),
        .weight_meta_base(weight_meta_base), .rope_base(rope_base),
        .irq(irq), .done_sticky(done_sticky), .error_sticky(error_sticky)
    );

    always @(posedge clk)
        if (start_pulse)
            starts <= starts + 1;

    task automatic tick;
        begin
            @(posedge clk);
            #1;
        end
    endtask

    task automatic expect32;
        input [31:0] actual;
        input [31:0] expected;
        input [8*48-1:0] label;
        begin
            checks = checks + 1;
            if (actual !== expected) begin
                $display("FAIL: %0s expected=%08x actual=%08x",
                    label, expected, actual);
                $fatal(1);
            end
        end
    endtask

    task automatic axil_write;
        input [11:0] address;
        input [31:0] value;
        input [3:0] strobe;
        input [1:0] expected_resp;
        begin
            while (!awready || !wready)
                tick();
            awaddr = address;
            wdata = value;
            wstrb = strobe;
            awvalid = 1'b1;
            wvalid = 1'b1;
            tick();
            awvalid = 1'b0;
            wvalid = 1'b0;
            while (!bvalid)
                tick();
            expect32({30'd0, bresp}, {30'd0, expected_resp},
                "AXI-Lite write response");
            bready = 1'b1;
            tick();
            bready = 1'b0;
        end
    endtask

    task automatic axil_read_expect;
        input [11:0] address;
        input [31:0] expected;
        input [1:0] expected_resp;
        input [8*48-1:0] label;
        begin
            while (!arready)
                tick();
            araddr = address;
            arvalid = 1'b1;
            tick();
            arvalid = 1'b0;
            while (!rvalid)
                tick();
            expect32(rdata, expected, label);
            expect32({30'd0, rresp}, {30'd0, expected_resp},
                "AXI-Lite read response");
            rready = 1'b1;
            tick();
            rready = 1'b0;
        end
    endtask

    initial begin
        repeat (5)
            tick();
        rst_n = 1'b1;
        tick();

        axil_read_expect(12'h000, 32'h4838_4103, 2'b00, "format id");
        axil_read_expect(12'h004, 32'h0002_0000, 2'b00, "ABI version");
        axil_read_expect(12'h018, 32'h0010_0000, 2'b00,
            "cohort16 reset query count");

        axil_write(12'h010, 32'h1122_3344, 4'hf, 2'b00);
        axil_write(12'h014, 32'd31, 4'hf, 2'b00);
        axil_write(12'h020, 32'h0000_2000, 4'hf, 2'b00);
        axil_write(12'h024, 32'h0004_0000, 4'hf, 2'b00);
        axil_write(12'h028, 32'h1000_0000, 4'hf, 2'b00);
        axil_write(12'h02c, 32'h2000_0000, 4'hf, 2'b00);
        axil_write(12'h030, 32'h3000_0000, 4'hf, 2'b00);
        axil_write(12'h034, 32'h4000_0000, 4'hf, 2'b00);
        axil_write(12'h070, 32'hdead_beef, 4'hf, 2'b00);
        axil_write(12'h070, 32'h0000_00a5, 4'b0001, 2'b00);
        axil_write(12'h074, 32'h55aa_0123, 4'hf, 2'b00);
        axil_read_expect(12'h070, 32'hdead_bea5, 2'b00,
            "request id byte strobe merge");
        axil_read_expect(12'h074, 32'h55aa_0123, 2'b00,
            "cohort and buffer identity");

        axil_write(12'h018, 32'h0008_2010, 4'hf, 2'b00);
        axil_write(12'h008, 32'h0000_0001, 4'hf, 2'b10);
        expect32(starts, 0, "query_count=8 must not launch");
        axil_write(12'h008, 32'h0000_0002, 4'hf, 2'b00);

        axil_write(12'h018, 32'h0010_8100, 4'hf, 2'b00);
        axil_write(12'h008, 32'h0000_0001, 4'hf, 2'b10);
        expect32(starts, 0, "valid_key_count>128 must not launch");
        axil_write(12'h008, 32'h0000_0002, 4'hf, 2'b00);

        axil_write(12'h018, 32'h0010_2010, 4'hf, 2'b00);
        maintenance_busy = 1'b1;
        axil_write(12'h008, 32'h0000_0001, 4'hf, 2'b10);
        expect32(starts, 0, "maintenance must block launch");
        maintenance_busy = 1'b0;
        axil_write(12'h008, 32'h0000_0002, 4'hf, 2'b00);

        axil_write(12'h008, 32'h0000_0001, 4'hf, 2'b00);
        expect32(starts, 1, "legal cohort16 command launch");

        engine_busy = 1'b1;
        axil_write(12'h008, 32'h0000_0001, 4'hf, 2'b10);
        expect32(starts, 1, "busy engine must reject second launch");
        engine_busy = 1'b0;
        axil_write(12'h008, 32'h0000_0002, 4'hf, 2'b00);

        completion_request_id = 32'hdead_bea5;
        completion_command_id = 32'h1122_3344;
        completion_cohort_id = 16'h0123;
        completion_buffer_id = 16'h55aa;
        completion_layer_id = 6'd31;
        completion_op_id = 3'd5;
        completion_status = 8'ha5;
        completion_valid = 1'b1;
        engine_done = 1'b1;
        tick();
        completion_valid = 1'b0;
        engine_done = 1'b0;

        axil_read_expect(12'h078, 32'hdead_bea5, 2'b00,
            "completed request id");
        axil_read_expect(12'h07c, 32'h1122_3344, 2'b00,
            "completed command id");
        axil_read_expect(12'h080, 32'h55aa_0123, 2'b00,
            "completed cohort and buffer");
        axil_read_expect(12'h084, 32'd31, 2'b00,
            "completed layer id");
        axil_read_expect(12'h088,
            {5'd0, 8'ha5, 3'd5, 16'h55aa}, 2'b00,
            "completed status and op");
        expect32({29'd0, irq, error_sticky, done_sticky}, 32'h0000_0005,
            "completion sticky status");

        axil_write(12'h008, 32'h0000_0002, 4'hf, 2'b00);
        expect32({29'd0, irq, error_sticky, done_sticky}, 32'd0,
            "clear sticky completion");
        axil_read_expect(12'h08c, 32'd0, 2'b10,
            "undefined register fails closed");

        $display("PASS: hap_attention_cohort16_axil_control checks=%0d starts=%0d",
            checks, starts);
        $finish;
    end
endmodule
