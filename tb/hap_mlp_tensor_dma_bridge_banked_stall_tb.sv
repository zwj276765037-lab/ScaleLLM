`timescale 1ns / 1ps

// Independent stress test for the banked tensor buffers in
// hap_mlp_tensor_dma_bridge.  It deliberately changes the producer payload
// as soon as a tile is accepted, stalls every ready/valid boundary, and
// aborts partial transfers with both reset and clear before completing a
// fresh load/store transaction.
module hap_mlp_tensor_dma_bridge_banked_stall_tb;
  localparam integer INPUT_GROUPS = 4;
  localparam integer OUTPUT_TILES = 7;

  reg clk = 1'b0;
  reg rst_n = 1'b0;
  reg clear = 1'b0;
  always #3.333 clk = ~clk;

  reg load_valid = 1'b0;
  wire load_ready;
  reg load_bank = 1'b1;
  reg [31:0] input_base_addr = 32'h0000_1f20;
  reg store_valid = 1'b0;
  wire store_ready;
  reg [31:0] output_base_addr = 32'h0000_2fa0;

  wire mlp_input_valid;
  wire mlp_input_ready;
  wire mlp_input_bank;
  wire [6:0] mlp_input_group;
  wire [12287:0] mlp_input_s24x16x32;
  reg mlp_out_valid = 1'b0;
  wire mlp_out_ready;
  reg [7:0] mlp_out_tile = 8'd0;
  reg [6143:0] mlp_out_s24x16x16 = '0;

  wire busy, done, load_done, store_done, store_armed, axi_active, error;
  wire [2:0] phase;
  wire [31:0] input_beat_count, input_group_count;
  wire [31:0] output_beat_count, output_tile_count;

  wire m_axi_arvalid;
  wire m_axi_arready;
  wire [31:0] m_axi_araddr;
  wire [7:0] m_axi_arlen;
  wire [2:0] m_axi_arsize;
  wire [1:0] m_axi_arburst;
  wire m_axi_rvalid;
  wire m_axi_rready;
  wire [255:0] m_axi_rdata;
  wire [1:0] m_axi_rresp;
  wire m_axi_rlast;
  wire m_axi_awvalid;
  wire m_axi_awready;
  wire [31:0] m_axi_awaddr;
  wire [7:0] m_axi_awlen;
  wire [2:0] m_axi_awsize;
  wire [1:0] m_axi_awburst;
  wire m_axi_wvalid;
  wire m_axi_wready;
  wire [255:0] m_axi_wdata;
  wire [31:0] m_axi_wstrb;
  wire m_axi_wlast;
  wire m_axi_bvalid;
  wire m_axi_bready;
  wire [1:0] m_axi_bresp;

  hap_mlp_tensor_dma_bridge #(
    .INPUT_GROUPS(INPUT_GROUPS),
    .OUTPUT_TILES(OUTPUT_TILES),
    .PRODUCTION_SHAPE(0)
  ) dut (
    .clk(clk), .rst_n(rst_n), .clear(clear),
    .load_valid(load_valid), .load_ready(load_ready),
    .load_bank(load_bank), .input_base_addr(input_base_addr),
    .store_valid(store_valid), .store_ready(store_ready),
    .output_base_addr(output_base_addr),
    .mlp_input_valid(mlp_input_valid),
    .mlp_input_ready(mlp_input_ready),
    .mlp_input_bank(mlp_input_bank),
    .mlp_input_group(mlp_input_group),
    .mlp_input_s24x16x32(mlp_input_s24x16x32),
    .mlp_out_valid(mlp_out_valid), .mlp_out_ready(mlp_out_ready),
    .mlp_out_tile(mlp_out_tile),
    .mlp_out_s24x16x16(mlp_out_s24x16x16),
    .busy(busy), .done(done), .load_done(load_done),
    .store_done(store_done), .store_armed(store_armed),
    .axi_active(axi_active), .error(error), .phase(phase),
    .input_beat_count(input_beat_count),
    .input_group_count(input_group_count),
    .output_beat_count(output_beat_count),
    .output_tile_count(output_tile_count),
    .m_axi_arvalid(m_axi_arvalid), .m_axi_arready(m_axi_arready),
    .m_axi_araddr(m_axi_araddr), .m_axi_arlen(m_axi_arlen),
    .m_axi_arsize(m_axi_arsize), .m_axi_arburst(m_axi_arburst),
    .m_axi_rvalid(m_axi_rvalid), .m_axi_rready(m_axi_rready),
    .m_axi_rdata(m_axi_rdata), .m_axi_rresp(m_axi_rresp),
    .m_axi_rlast(m_axi_rlast),
    .m_axi_awvalid(m_axi_awvalid), .m_axi_awready(m_axi_awready),
    .m_axi_awaddr(m_axi_awaddr), .m_axi_awlen(m_axi_awlen),
    .m_axi_awsize(m_axi_awsize), .m_axi_awburst(m_axi_awburst),
    .m_axi_wvalid(m_axi_wvalid), .m_axi_wready(m_axi_wready),
    .m_axi_wdata(m_axi_wdata), .m_axi_wstrb(m_axi_wstrb),
    .m_axi_wlast(m_axi_wlast),
    .m_axi_bvalid(m_axi_bvalid), .m_axi_bready(m_axi_bready),
    .m_axi_bresp(m_axi_bresp)
  );

  integer checks = 0;
  integer cycles = 0;
  integer input_transactions = 0;
  integer output_transactions = 0;
  integer input_groups_seen = 0;
  integer read_index = 0;
  integer write_index = 0;
  integer read_epoch = 0;
  integer write_epoch = 0;
  integer ar_stall_cycles = 0;
  integer r_stall_cycles = 0;
  integer input_stall_cycles = 0;
  integer aw_stall_cycles = 0;
  integer w_stall_cycles = 0;
  integer producer_stall_cycles = 0;
  reg input_ready_enable = 1'b0;
  reg force_input_stall = 1'b0;
  reg [31:0] lfsr = 32'h1ace_b00c;

  task automatic check;
    input condition;
    input [8*120-1:0] message;
    begin
      checks = checks + 1;
      if (!condition) begin
        $display("FAIL %0s cycle=%0d phase=%0d", message, cycles, phase);
        $fatal(1);
      end
    end
  endtask

  task automatic tick;
    begin
      @(posedge clk);
      #1;
    end
  endtask

  function automatic [31:0] read_word;
    input integer epoch;
    input integer beat;
    input integer lane;
    begin
      read_word = 32'ha500_0000 ^ (epoch << 20) ^ (beat << 3) ^ lane;
    end
  endfunction

  function automatic [255:0] read_payload;
    input integer epoch;
    input integer beat;
    integer lane;
    begin
      for (lane = 0; lane < 8; lane = lane + 1)
        read_payload[lane*32 +: 32] = read_word(epoch, beat, lane);
    end
  endfunction

  function automatic [31:0] output_word;
    input integer epoch;
    input integer tile;
    input integer beat;
    input integer lane;
    begin
      output_word = 32'h5a00_0000 ^ (epoch << 20) ^
                    (tile << 11) ^ (beat << 3) ^ lane;
    end
  endfunction

  function automatic [255:0] output_payload;
    input integer epoch;
    input integer tile;
    input integer beat;
    integer lane;
    begin
      for (lane = 0; lane < 8; lane = lane + 1)
        output_payload[lane*32 +: 32] =
          output_word(epoch, tile, beat, lane);
    end
  endfunction

  function automatic [6143:0] output_tile_payload;
    input integer epoch;
    input integer tile;
    integer beat;
    begin
      for (beat = 0; beat < 24; beat = beat + 1)
        output_tile_payload[beat*256 +: 256] =
          output_payload(epoch, tile, beat);
    end
  endfunction

  task automatic issue_load;
    input integer epoch;
    input [31:0] base;
    begin
      read_epoch = epoch;
      input_base_addr = base;
      load_valid = 1'b1;
      while (!load_ready) tick();
      tick();
      load_valid = 1'b0;
      input_transactions = input_transactions + 1;
      check(busy && phase == 1, "load command did not enter P_LOAD");
    end
  endtask

  task automatic issue_store;
    input integer epoch;
    input [31:0] base;
    begin
      write_epoch = epoch;
      output_base_addr = base;
      store_valid = 1'b1;
      while (!store_ready) tick();
      tick();
      store_valid = 1'b0;
      output_transactions = output_transactions + 1;
      check(busy && store_armed && phase == 3,
            "store command did not enter P_STORE_ARM");
    end
  endtask

  task automatic send_tile;
    input integer epoch;
    input integer tile;
    begin
      mlp_out_tile = tile[7:0];
      mlp_out_s24x16x16 = output_tile_payload(epoch, tile);
      mlp_out_valid = 1'b1;
      while (!mlp_out_ready) tick();
      tick();
      mlp_out_valid = 1'b0;
      // Change every payload bit pattern immediately after acceptance.  A
      // bank that was not frozen by output_fire will be caught downstream.
      mlp_out_tile = 8'hee;
      mlp_out_s24x16x16 = {6144{1'b1}};
    end
  endtask

  assign mlp_input_ready = rst_n && !clear && input_ready_enable &&
                           !force_input_stall && (lfsr[2:0] != 3'b000);

  // Read slave: one outstanding burst, registered RVALID, and stable payload
  // across arbitrary bridge backpressure.
  reg read_active = 1'b0;
  integer read_remaining = 0;
  reg rvalid_r = 1'b0;
  reg [255:0] rdata_r = '0;
  reg rlast_r = 1'b0;
  assign m_axi_arready = rst_n && !clear && !read_active && !rvalid_r &&
                         (lfsr[5:3] != 3'b000);
  assign m_axi_rvalid = rvalid_r;
  assign m_axi_rdata = rdata_r;
  assign m_axi_rlast = rlast_r;
  assign m_axi_rresp = 2'b00;

  integer expected_addr;
  integer expected_burst;
  integer beats_to_4k;
  integer beats_left;
  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      read_active <= 1'b0;
      read_remaining <= 0;
      rvalid_r <= 1'b0;
      rdata_r <= '0;
      rlast_r <= 1'b0;
      read_index <= 0;
    end else if (clear) begin
      read_active <= 1'b0;
      read_remaining <= 0;
      rvalid_r <= 1'b0;
      rlast_r <= 1'b0;
      read_index <= 0;
    end else begin
      if (m_axi_arvalid && m_axi_arready) begin
        expected_addr = input_base_addr + read_index*32;
        beats_to_4k = (4096 - (expected_addr & 4095))/32;
        beats_left = INPUT_GROUPS*48 - read_index;
        expected_burst = beats_left < 16 ? beats_left : 16;
        if (beats_to_4k < expected_burst)
          expected_burst = beats_to_4k;
        check(m_axi_araddr === expected_addr[31:0],
              "read burst address/order mismatch");
        check(m_axi_arlen + 1 === expected_burst,
              "read burst length/4KiB split mismatch");
        check(m_axi_arsize == 3'd5 && m_axi_arburst == 2'b01,
              "read AXI attributes mismatch");
        read_active <= 1'b1;
        read_remaining <= m_axi_arlen + 1;
      end
      if (rvalid_r && m_axi_rready) begin
        rvalid_r <= 1'b0;
        read_index <= read_index + 1;
        read_remaining <= read_remaining - 1;
        if (read_remaining == 1)
          read_active <= 1'b0;
      end
      if (read_active && !rvalid_r && lfsr[8:6] != 3'b000) begin
        rvalid_r <= 1'b1;
        rdata_r <= read_payload(read_epoch, read_index);
        rlast_r <= read_remaining == 1;
      end
    end
  end

  // Write slave: random AW/W acceptance and random B response latency.
  reg write_active = 1'b0;
  integer write_remaining = 0;
  reg response_pending = 1'b0;
  reg bvalid_r = 1'b0;
  assign m_axi_awready = rst_n && !clear && !write_active &&
                         !response_pending && !bvalid_r &&
                         (lfsr[11:9] != 3'b000);
  assign m_axi_wready = rst_n && !clear && write_active &&
                        (lfsr[14:12] != 3'b000);
  assign m_axi_bvalid = bvalid_r;
  assign m_axi_bresp = 2'b00;

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      write_active <= 1'b0;
      write_remaining <= 0;
      response_pending <= 1'b0;
      bvalid_r <= 1'b0;
      write_index <= 0;
    end else if (clear) begin
      write_active <= 1'b0;
      write_remaining <= 0;
      response_pending <= 1'b0;
      bvalid_r <= 1'b0;
      write_index <= 0;
    end else begin
      if (m_axi_awvalid && m_axi_awready) begin
        expected_addr = output_base_addr + write_index*32;
        beats_to_4k = (4096 - (expected_addr & 4095))/32;
        beats_left = OUTPUT_TILES*24 - write_index;
        expected_burst = beats_left < 16 ? beats_left : 16;
        if (beats_to_4k < expected_burst)
          expected_burst = beats_to_4k;
        check(m_axi_awaddr === expected_addr[31:0],
              "write burst address/order mismatch");
        check(m_axi_awlen + 1 === expected_burst,
              "write burst length/4KiB split mismatch");
        check(m_axi_awsize == 3'd5 && m_axi_awburst == 2'b01,
              "write AXI attributes mismatch");
        write_active <= 1'b1;
        write_remaining <= m_axi_awlen + 1;
      end
      if (m_axi_wvalid && m_axi_wready) begin
        check(m_axi_wdata === output_payload(
                write_epoch, write_index/24, write_index%24),
              "write tile bank payload/order mismatch");
        check(m_axi_wstrb === 32'hffff_ffff,
              "write byte strobes mismatch");
        check(m_axi_wlast === (write_remaining == 1),
              "write WLAST mismatch");
        write_index <= write_index + 1;
        write_remaining <= write_remaining - 1;
        if (write_remaining == 1) begin
          write_active <= 1'b0;
          response_pending <= 1'b1;
        end
      end
      if (response_pending && !bvalid_r && lfsr[17:15] != 3'b000) begin
        response_pending <= 1'b0;
        bvalid_r <= 1'b1;
      end
      if (bvalid_r && m_axi_bready)
        bvalid_r <= 1'b0;
    end
  end

  // Scoreboard every one of the 48 input banks, not merely lane zero.
  integer input_beat;
  integer input_lane;
  always @(posedge clk or negedge rst_n) begin
    if (!rst_n)
      input_groups_seen <= 0;
    else if (clear)
      input_groups_seen <= 0;
    else if (mlp_input_valid && mlp_input_ready) begin
      check(mlp_input_bank === load_bank,
            "input bank tag mismatch");
      check(mlp_input_group === input_groups_seen[6:0],
            "input group order mismatch");
      for (input_beat = 0; input_beat < 48; input_beat = input_beat + 1)
        for (input_lane = 0; input_lane < 8; input_lane = input_lane + 1)
          check(mlp_input_s24x16x32[input_beat*256+input_lane*32 +: 32] ===
                read_word(read_epoch, input_groups_seen*48+input_beat,
                          input_lane),
                "input beat-bank payload mismatch");
      input_groups_seen <= input_groups_seen + 1;
    end
  end

  // Ready/valid stability checks for both newly banked boundaries.
  reg input_hold = 1'b0;
  reg input_hold_bank = 1'b0;
  reg [6:0] input_hold_group = 7'd0;
  reg [12287:0] input_hold_data = '0;
  reg write_hold = 1'b0;
  reg [255:0] write_hold_data = '0;
  reg write_hold_last = 1'b0;
  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      input_hold <= 1'b0;
      write_hold <= 1'b0;
    end else if (clear) begin
      input_hold <= 1'b0;
      write_hold <= 1'b0;
    end else begin
      if (input_hold) begin
        check(mlp_input_valid, "input valid dropped under backpressure");
        check(mlp_input_bank === input_hold_bank &&
              mlp_input_group === input_hold_group &&
              mlp_input_s24x16x32 === input_hold_data,
              "input bank payload changed under backpressure");
      end
      input_hold <= mlp_input_valid && !mlp_input_ready;
      if (mlp_input_valid && !mlp_input_ready) begin
        input_hold_bank <= mlp_input_bank;
        input_hold_group <= mlp_input_group;
        input_hold_data <= mlp_input_s24x16x32;
      end
      if (write_hold) begin
        check(m_axi_wvalid, "WVALID dropped under backpressure");
        check(m_axi_wdata === write_hold_data &&
              m_axi_wlast === write_hold_last,
              "registered output stream changed under backpressure");
      end
      write_hold <= m_axi_wvalid && !m_axi_wready;
      if (m_axi_wvalid && !m_axi_wready) begin
        write_hold_data <= m_axi_wdata;
        write_hold_last <= m_axi_wlast;
      end
    end
  end

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      lfsr <= 32'h1ace_b00c;
      cycles <= 0;
      ar_stall_cycles <= 0;
      r_stall_cycles <= 0;
      input_stall_cycles <= 0;
      aw_stall_cycles <= 0;
      w_stall_cycles <= 0;
      producer_stall_cycles <= 0;
    end else begin
      lfsr <= {lfsr[30:0], lfsr[31]^lfsr[21]^lfsr[1]^lfsr[0]};
      cycles <= cycles + 1;
      if (m_axi_arvalid && !m_axi_arready)
        ar_stall_cycles <= ar_stall_cycles + 1;
      if (m_axi_rvalid && !m_axi_rready)
        r_stall_cycles <= r_stall_cycles + 1;
      if (mlp_input_valid && !mlp_input_ready)
        input_stall_cycles <= input_stall_cycles + 1;
      if (m_axi_awvalid && !m_axi_awready)
        aw_stall_cycles <= aw_stall_cycles + 1;
      if (m_axi_wvalid && !m_axi_wready)
        w_stall_cycles <= w_stall_cycles + 1;
      if (mlp_out_valid && !mlp_out_ready)
        producer_stall_cycles <= producer_stall_cycles + 1;
      if (cycles > 20000) begin
        $display("FAIL timeout phase=%0d read=%0d write=%0d error=%0d",
                 phase, read_index, write_index, error);
        $fatal(1);
      end
    end
  end

  initial begin
    integer tile;
    repeat (4) tick();
    rst_n = 1'b1;
    tick();
    check(!busy && !mlp_input_valid && !mlp_out_ready &&
          !m_axi_wvalid && !done && !load_done && !store_done,
          "reset did not mask bank payload state");

    // Abort a partial input group with asynchronous reset.
    input_ready_enable = 1'b0;
    issue_load(1, 32'h0000_1f20);
    while (read_index < 19) tick();
    #1 rst_n = 1'b0;
    #1;
    check(!busy && !mlp_input_valid && !mlp_out_ready &&
          !m_axi_arvalid && !m_axi_rready && !m_axi_wvalid,
          "asynchronous reset exposed stale bank state");
    repeat (2) tick();
    rst_n = 1'b1;
    tick();
    check(input_beat_count == 0 && input_group_count == 0,
          "reset did not clear input accounting");

    // Fill a complete group, hold it at the consumer, then clear.  This is
    // the boundary at which all 48 bank CEs switch ownership.
    issue_load(2, 32'h0000_3f40);
    while (!mlp_input_valid) tick();
    repeat (5) tick();
    check(mlp_input_valid && input_group_count == 0,
          "directed full-group backpressure was not reached");
    clear = 1'b1;
    tick();
    check(!busy && !mlp_input_valid && !m_axi_rready &&
          input_beat_count == 0 && input_group_count == 0,
          "clear did not discard held input group");
    clear = 1'b0;
    tick();

    // Complete a fresh randomized load and prove every lane of every bank.
    load_bank = 1'b0;
    input_ready_enable = 1'b1;
    issue_load(3, 32'h0000_5f60);
    while (!done) tick();
    check(load_done && !store_done, "load completion pulse mismatch");
    check(input_beat_count == INPUT_GROUPS*48 &&
          input_group_count == INPUT_GROUPS &&
          input_groups_seen == INPUT_GROUPS &&
          read_index == INPUT_GROUPS*48,
          "completed load accounting mismatch");
    check(!error, "completed load raised sticky error");
    input_ready_enable = 1'b0;
    tick();
    check(!done && !load_done, "load completion pulse was not one cycle");

    // Abort a buffered output tile while AXI W is stalled/partially drained.
    issue_store(4, 32'h0000_2fa0);
    send_tile(4, 0);
    while (write_index < 7) tick();
    clear = 1'b1;
    tick();
    check(!busy && !store_armed && !mlp_out_ready && !m_axi_wvalid &&
          output_beat_count == 0 && output_tile_count == 0,
          "clear did not discard partial output tile");
    clear = 1'b0;
    tick();

    // Complete a fresh store.  send_tile corrupts its source immediately
    // after each handshake, so all 24 protected banks must really hold.
    issue_store(5, 32'h0000_6f80);
    for (tile = 0; tile < OUTPUT_TILES; tile = tile + 1)
      send_tile(5, tile);
    while (!done) tick();
    check(store_done && !load_done, "store completion pulse mismatch");
    check(output_beat_count == OUTPUT_TILES*24 &&
          output_tile_count == OUTPUT_TILES &&
          write_index == OUTPUT_TILES*24,
          "completed store accounting mismatch");
    check(!error, "completed store raised sticky error");
    tick();
    check(!done && !store_done, "store completion pulse was not one cycle");

    check(ar_stall_cycles > 0 && r_stall_cycles > 0 &&
          input_stall_cycles > 0 && aw_stall_cycles > 0 &&
          w_stall_cycles > 0 && producer_stall_cycles > 0,
          "random-stall coverage counter remained zero");
    $display("PASS hap_mlp_tensor_dma_bridge_banked_stall checks=%0d cycles=%0d input_txn=%0d output_txn=%0d stalls(ar/r/in/aw/w/out)=%0d/%0d/%0d/%0d/%0d/%0d",
             checks, cycles, input_transactions, output_transactions,
             ar_stall_cycles, r_stall_cycles, input_stall_cycles,
             aw_stall_cycles, w_stall_cycles, producer_stall_cycles);
    $finish;
  end
endmodule
