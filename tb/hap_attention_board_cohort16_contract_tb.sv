`timescale 1ns / 1ps

module hap_attention_board_cohort16_contract_tb;
    reg core_clk = 1'b0;
    reg ddr0_clk = 1'b0;
    reg ddr1_clk = 1'b0;
    reg core_rst_n = 1'b0;
    reg ddr0_rst_n = 1'b0;
    reg ddr1_rst_n = 1'b0;
    reg engine_soft_clear = 1'b0;
    always #3.333 core_clk = ~core_clk;
    always #1.667 ddr0_clk = ~ddr0_clk;
    always #1.667 ddr1_clk = ~ddr1_clk;

    reg [11:0] s_axil_awaddr = 12'd0;
    reg s_axil_awvalid = 1'b0;
    wire s_axil_awready;
    reg [31:0] s_axil_wdata = 32'd0;
    reg [3:0] s_axil_wstrb = 4'd0;
    reg s_axil_wvalid = 1'b0;
    wire s_axil_wready;
    wire [1:0] s_axil_bresp;
    wire s_axil_bvalid;
    reg s_axil_bready = 1'b0;
    reg [11:0] s_axil_araddr = 12'd0;
    reg s_axil_arvalid = 1'b0;
    wire s_axil_arready;
    wire [31:0] s_axil_rdata;
    wire [1:0] s_axil_rresp;
    wire s_axil_rvalid;
    reg s_axil_rready = 1'b0;

    wire weight_source_quiescent;
    wire ddr_quiescent;
    wire data_axi_busy;
    wire irq;
    integer checks = 0;
    integer wait_cycles = 0;

    hap_attention_board_cohort16_core #(
        .COMMAND_TIMEOUT_CYCLES(120000)
    ) dut (
        .core_clk(core_clk), .core_rst_n(core_rst_n),
        .s_axil_awaddr(s_axil_awaddr), .s_axil_awvalid(s_axil_awvalid),
        .s_axil_awready(s_axil_awready), .s_axil_wdata(s_axil_wdata),
        .s_axil_wstrb(s_axil_wstrb), .s_axil_wvalid(s_axil_wvalid),
        .s_axil_wready(s_axil_wready), .s_axil_bresp(s_axil_bresp),
        .s_axil_bvalid(s_axil_bvalid), .s_axil_bready(s_axil_bready),
        .s_axil_araddr(s_axil_araddr), .s_axil_arvalid(s_axil_arvalid),
        .s_axil_arready(s_axil_arready), .s_axil_rdata(s_axil_rdata),
        .s_axil_rresp(s_axil_rresp), .s_axil_rvalid(s_axil_rvalid),
        .s_axil_rready(s_axil_rready),
        .m_axi_arvalid(), .m_axi_arready(1'b0), .m_axi_araddr(),
        .m_axi_arlen(), .m_axi_arsize(), .m_axi_arburst(),
        .m_axi_rvalid(1'b0), .m_axi_rready(), .m_axi_rdata(256'd0),
        .m_axi_rresp(2'b00), .m_axi_rlast(1'b0),
        .m_axi_awvalid(), .m_axi_awready(1'b0), .m_axi_awaddr(),
        .m_axi_awlen(), .m_axi_awsize(), .m_axi_awburst(),
        .m_axi_wvalid(), .m_axi_wready(1'b0), .m_axi_wdata(),
        .m_axi_wstrb(), .m_axi_wlast(), .m_axi_bvalid(1'b0),
        .m_axi_bready(), .m_axi_bresp(2'b00),
        .ddr0_clk(ddr0_clk), .ddr0_rst_n(ddr0_rst_n),
        .ddr0_axi_arvalid(), .ddr0_axi_arready(1'b0),
        .ddr0_axi_araddr(), .ddr0_axi_arlen(), .ddr0_axi_arsize(),
        .ddr0_axi_arburst(), .ddr0_axi_rvalid(1'b0),
        .ddr0_axi_rready(), .ddr0_axi_rdata(512'd0),
        .ddr0_axi_rresp(2'b00), .ddr0_axi_rlast(1'b0),
        .ddr1_clk(ddr1_clk), .ddr1_rst_n(ddr1_rst_n),
        .ddr1_axi_arvalid(), .ddr1_axi_arready(1'b0),
        .ddr1_axi_araddr(), .ddr1_axi_arlen(), .ddr1_axi_arsize(),
        .ddr1_axi_arburst(), .ddr1_axi_rvalid(1'b0),
        .ddr1_axi_rready(), .ddr1_axi_rdata(512'd0),
        .ddr1_axi_rresp(2'b00), .ddr1_axi_rlast(1'b0),
        .attention_launch_enable(1'b1),
        .engine_soft_clear(engine_soft_clear),
        .command_pause(1'b0),
        .weight_source_quiescent(weight_source_quiescent),
        .ddr_quiescent(ddr_quiescent), .data_axi_busy(data_axi_busy),
        .irq(irq)
    );

    task automatic tick;
        begin
            @(posedge core_clk);
            #1;
        end
    endtask

    task automatic expect32;
        input [31:0] actual;
        input [31:0] expected;
        input [8*56-1:0] label;
        begin
            checks = checks + 1;
            if (actual !== expected) begin
                $display("FAIL: %0s expected=%08x actual=%08x",
                    label, expected, actual);
                $finish;
            end
        end
    endtask

    task automatic axil_write;
        input [11:0] address;
        input [31:0] value;
        begin
            while (!s_axil_awready || !s_axil_wready)
                tick();
            s_axil_awaddr = address;
            s_axil_wdata = value;
            s_axil_wstrb = 4'hf;
            s_axil_awvalid = 1'b1;
            s_axil_wvalid = 1'b1;
            tick();
            s_axil_awvalid = 1'b0;
            s_axil_wvalid = 1'b0;
            while (!s_axil_bvalid)
                tick();
            checks = checks + 1;
            if (s_axil_bresp !== 2'b00) begin
                $display("FAIL: AXI-Lite write address=%03x data=%08x resp=%x",
                    address, value, s_axil_bresp);
                $finish;
            end
            s_axil_bready = 1'b1;
            tick();
            s_axil_bready = 1'b0;
        end
    endtask

    task automatic axil_read_expect;
        input [11:0] address;
        input [31:0] expected;
        input [8*56-1:0] label;
        begin
            while (!s_axil_arready)
                tick();
            s_axil_araddr = address;
            s_axil_arvalid = 1'b1;
            tick();
            s_axil_arvalid = 1'b0;
            while (!s_axil_rvalid)
                tick();
            expect32({30'd0, s_axil_rresp}, 32'd0,
                "AXI-Lite read response");
            expect32(s_axil_rdata, expected, label);
            s_axil_rready = 1'b1;
            tick();
            s_axil_rready = 1'b0;
        end
    endtask

    initial begin
        repeat (6)
            tick();
        core_rst_n = 1'b1;
        ddr0_rst_n = 1'b1;
        ddr1_rst_n = 1'b1;
        tick();

        axil_write(12'h070, 32'h1020_3040);
        axil_write(12'h010, 32'h5566_7788);
        axil_write(12'h074, 32'h00b2_0007);
        axil_write(12'h014, 32'd31);
        axil_write(12'h018, 32'h0010_2010);
        axil_write(12'h020, 32'h0100_0000);
        axil_write(12'h024, 32'h0200_0000);
        axil_write(12'h028, 32'h1000_0000);
        axil_write(12'h02c, 32'h2000_0000);
        axil_write(12'h030, 32'h3000_0000);
        axil_write(12'h034, 32'h4000_0000);

        // start + reload metadata + reload RoPE + preserve historical KV
        axil_write(12'h008, 32'h0000_001d);
        while (dut.state_r == 0)
            tick();

        // Rewrite every mutable descriptor while the first command runs.
        axil_write(12'h070, 32'hdead_beef);
        axil_write(12'h010, 32'h89ab_cdef);
        axil_write(12'h074, 32'h1234_5678);
        axil_write(12'h014, 32'd3);
        axil_write(12'h018, 32'h0010_1010);
        axil_write(12'h020, 32'h5100_0000);
        axil_write(12'h024, 32'h5200_0000);
        axil_write(12'h028, 32'h6000_0000);
        axil_write(12'h02c, 32'h7000_0000);
        axil_write(12'h030, 32'h8000_0000);
        axil_write(12'h034, 32'h9000_0000);
        axil_write(12'h008, 32'h0000_0000);

        expect32(dut.active_request_id_r, 32'h1020_3040,
            "active request id remains atomic");
        expect32(dut.active_command_id_r, 32'h5566_7788,
            "active command id remains atomic");
        expect32({dut.active_buffer_id_r, dut.active_cohort_id_r},
            32'h00b2_0007, "active owner identity remains atomic");
        expect32({26'd0, dut.active_layer_id_r}, 32'd31,
            "active layer remains atomic");
        expect32(dut.active_input_base_r, 32'h0100_0000,
            "active input address remains atomic");
        expect32(dut.active_output_base_r, 32'h0200_0000,
            "active output address remains atomic");
        expect32(dut.active_weight_c0_base_r, 32'h1000_0000,
            "active DDR0 address remains atomic");
        expect32(dut.active_weight_c1_base_r, 32'h2000_0000,
            "active DDR1 address remains atomic");
        expect32(dut.active_weight_meta_base_r, 32'h3000_0000,
            "active metadata address remains atomic");
        expect32(dut.active_rope_base_r, 32'h4000_0000,
            "active RoPE address remains atomic");
        expect32({29'd0, dut.active_preserve_historical_kv_r,
            dut.active_reload_rope_r, dut.active_reload_metadata_r},
            32'h0000_0007, "active command flags remain atomic");

        wait_cycles = 0;
        while (!irq && wait_cycles < 140000) begin
            tick();
            wait_cycles = wait_cycles + 1;
        end
        if (!irq) begin
            $display("FAIL: board command timeout state=%0d dma_commands=%0d",
                dut.state_r, dut.u_dma.command_count);
            $fatal(1);
        end

        expect32(dut.u_dma.command_count, 32'd4, "four DMA commands");
        expect32(dut.u_dma.cmd_base_log[0], 32'h3000_0000,
            "metadata DMA captured base");
        expect32(dut.u_dma.cmd_beats_log[0], 32'd81920,
            "metadata DMA beats");
        expect32(dut.u_dma.cmd_write_log[0], 32'd0,
            "metadata DMA direction");
        expect32(dut.u_dma.cmd_base_log[1], 32'h4000_0000,
            "RoPE DMA captured base");
        expect32(dut.u_dma.cmd_beats_log[1], 32'd256,
            "cohort16 RoPE DMA beats");
        expect32(dut.u_dma.cmd_base_log[2], 32'h0100_0000,
            "input DMA captured base");
        expect32(dut.u_dma.cmd_beats_log[2], 32'd6144,
            "cohort16 input DMA beats");
        expect32(dut.u_dma.cmd_base_log[3], 32'h0200_0000,
            "output DMA captured base");
        expect32(dut.u_dma.cmd_beats_log[3], 32'd6144,
            "cohort16 output DMA beats");
        expect32(dut.u_dma.cmd_write_log[3], 32'd1,
            "output DMA direction");
        expect32(dut.u_dma.read_beat_count, 32'd88320,
            "aggregate board read beats");
        expect32(dut.u_dma.write_beat_count, 32'd6144,
            "aggregate board write beats");

        expect32(dut.u_weight_frontend.command_count, 32'd1,
            "single physical W8 command");
        expect32(dut.u_weight_frontend.base0_seen, 32'h1000_0000,
            "weight DDR0 captured base");
        expect32(dut.u_weight_frontend.base1_seen, 32'h2000_0000,
            "weight DDR1 captured base");
        expect32({15'd0, dut.u_weight_frontend.group_count_seen},
            32'd81920, "physical W8 group count unchanged");
        expect32(dut.u_compute.start_count, 32'd1,
            "single cohort16 compute launch");
        expect32(dut.u_compute.request_id_seen, 32'h1020_3040,
            "compute captured original request");
        expect32({dut.u_compute.query_count_seen,
            dut.u_compute.valid_key_count_seen, 1'b0,
            dut.u_compute.query_start_seen}, 32'h0010_2010,
            "compute captured cohort16 query descriptor");

        axil_read_expect(12'h078, 32'h1020_3040,
            "completion request id");
        axil_read_expect(12'h07c, 32'h5566_7788,
            "completion command id");
        axil_read_expect(12'h080, 32'h00b2_0007,
            "completion owner identity");
        axil_read_expect(12'h084, 32'd31, "completion layer id");
        axil_read_expect(12'h088, 32'h0000_00b2,
            "successful Attention completion status");
        axil_read_expect(12'h00c, 32'h0000_003a,
            "loaded artifacts and done IRQ status");

        // A global clear while active must complete as maintenance abort and
        // invalidate the resident artifact flags that were physically cleared.
        axil_write(12'h008, 32'h0000_0002);
        axil_write(12'h070, 32'h2030_4050);
        axil_write(12'h010, 32'h6677_8899);
        axil_write(12'h074, 32'h00c3_0008);
        axil_write(12'h018, 32'h0010_2010);
        axil_write(12'h008, 32'h0000_0001);
        while (dut.state_r == 0)
            tick();
        engine_soft_clear = 1'b1;
        tick();
        engine_soft_clear = 1'b0;
        wait_cycles = 0;
        while (!irq && wait_cycles < 20) begin
            tick();
            wait_cycles = wait_cycles + 1;
        end
        if (!irq)
            $fatal(1, "FAIL: maintenance abort completion timeout");
        axil_read_expect(12'h078, 32'h2030_4050,
            "maintenance completion request id");
        axil_read_expect(12'h080, 32'h00c3_0008,
            "maintenance completion owner identity");
        axil_read_expect(12'h088, 32'h0028_00c3,
            "maintenance abort completion status");
        axil_read_expect(12'h04c, 32'h0001_0000,
            "maintenance abort error code");
        axil_read_expect(12'h00c, 32'h0000_0024,
            "maintenance invalidates artifacts");

        // Stall the first metadata payload beat and prove that the bounded
        // command watchdog aborts every child engine and returns the owner.
        axil_write(12'h008, 32'h0000_0002);
        axil_write(12'h070, 32'h3040_5060);
        axil_write(12'h010, 32'h7788_99aa);
        axil_write(12'h074, 32'h00d4_0009);
        force dut.u_dma.stall_r = 1'b1;
        axil_write(12'h008, 32'h0000_000d);
        wait_cycles = 0;
        while (!irq && wait_cycles < 130000) begin
            tick();
            wait_cycles = wait_cycles + 1;
        end
        release dut.u_dma.stall_r;
        if (!irq)
            $fatal(1, "FAIL: watchdog completion timeout");
        expect32({31'd0, data_axi_busy}, 32'd0,
            "watchdog clears active DMA");
        axil_read_expect(12'h078, 32'h3040_5060,
            "timeout completion request id");
        axil_read_expect(12'h080, 32'h00d4_0009,
            "timeout completion owner identity");
        axil_read_expect(12'h088, 32'h0020_00d4,
            "timeout completion status");
        axil_read_expect(12'h04c, 32'h0002_0000,
            "timeout error code");

        $display("PASS: hap_attention_board_cohort16_contract checks=%0d cycles=%0d",
            checks, wait_cycles);
        $finish;
    end
endmodule
