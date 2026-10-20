`timescale 1ns / 1ps

// Local 4-KiB AXI-Lite control plane.  Production address routing reserves
// 0x000..0x0ff for the signed-off Attention v3 ABI and sends 0x100..0x2ff to
// this block without changing the address value.
module hap_mlp_axil_control #(
    parameter integer PRODUCTION_INTEGRATION = 0,
    parameter integer COMMAND_TIMEOUT_CYCLES = 10000000
) (
    input  wire          clk,
    input  wire          rst_n,
    input  wire [11:0]   s_axil_awaddr,
    input  wire          s_axil_awvalid,
    output wire          s_axil_awready,
    input  wire [31:0]   s_axil_wdata,
    input  wire [3:0]    s_axil_wstrb,
    input  wire          s_axil_wvalid,
    output wire          s_axil_wready,
    output wire [1:0]    s_axil_bresp,
    output wire          s_axil_bvalid,
    input  wire          s_axil_bready,
    input  wire [11:0]   s_axil_araddr,
    input  wire          s_axil_arvalid,
    output wire          s_axil_arready,
    output wire [31:0]   s_axil_rdata,
    output wire [1:0]    s_axil_rresp,
    output wire          s_axil_rvalid,
    input  wire          s_axil_rready,

    output reg           owner_request_valid,
    input  wire          owner_request_ready,
    input  wire          admission_pause,
    output reg  [1:0]    owner_request,
    input  wire          owner_request_done,
    input  wire [1:0]    active_owner,
    input  wire          owner_switch_pending,
    input  wire          attention_launch_enable,
    input  wire          mlp_launch_enable,
    input  wire          owner_protocol_error,
    input  wire [7:0]    ddr0_outstanding,
    input  wire [7:0]    ddr1_outstanding,
    input  wire          maintenance_busy,
    input  wire          maintenance_request_pending,
    input  wire          mlp_abort_complete,
    input  wire          paired_quiescent,
    input  wire [31:0]   paired_attn_bursts,
    input  wire [31:0]   paired_mlp_bursts,
    input  wire [31:0]   paired_both_cycles,
    input  wire [31:0]   paired_hol0,
    input  wire [31:0]   paired_hol1,
    input  wire [31:0]   paired_hwm0,
    input  wire [31:0]   paired_hwm1,

    output reg           mlp_command_valid,
    input  wire          mlp_command_ready,
    output reg           mlp_clear_pulse,
    output wire          mlp_abort_pending,
    output reg           mlp_command_bank,
    output reg  [31:0]   mlp_gate_ddr0_base_addr,
    output reg  [31:0]   mlp_gate_ddr1_base_addr,
    output reg  [31:0]   mlp_down_ddr0_base_addr,
    output reg  [31:0]   mlp_down_ddr1_base_addr,
    output reg  [31:0]   mlp_input_base_addr,
    output reg  [31:0]   mlp_output_base_addr,
    output reg  [31:0]   mlp_command_id,
    output reg  [31:0]   mlp_layer_id,
    input  wire [1:0]    mlp_input_bank_ready,
    input  wire          mlp_busy,
    input  wire          mlp_done,
    input  wire          mlp_error,
    input  wire [2:0]    mlp_phase,
    input  wire [1567:0] mlp_telemetry,
    input  wire [31:0]   mlp_down_output_saturation_count,
    input  wire [31:0]   mlp_total_shift_format_count,
    input  wire [31:0]   mlp_numeric_status,

    output reg           tensor_load_valid,
    input  wire          tensor_load_ready,
    output reg           tensor_store_valid,
    input  wire          tensor_store_ready,
    input  wire          tensor_store_armed,
    input  wire          tensor_dma_busy,
    input  wire          tensor_dma_done,
    input  wire          tensor_dma_error,
    input  wire [2:0]    tensor_dma_phase,
    input  wire [31:0]   tensor_input_beat_count,
    input  wire [31:0]   tensor_input_group_count,
    input  wire [31:0]   tensor_output_beat_count,
    input  wire [31:0]   tensor_output_tile_count,

    output reg  [31:0]   meta_gate_base_addr,
    output reg  [31:0]   meta_down_base_addr,
    input  wire          meta_dma_busy,
    input  wire          meta_dma_done,
    input  wire          meta_dma_error,
    input  wire [2:0]    meta_dma_phase,
    input  wire [31:0]   meta_dma_gate_record_count,
    input  wire [31:0]   meta_dma_down_record_count,
    input  wire [63:0]   meta_dma_physical_bytes,

    output reg           meta_load_begin_valid,
    input  wire          meta_load_begin_ready,
    output reg           meta_load_bank,
    output reg           meta_commit_valid,
    input  wire          meta_commit_ready,
    output reg           meta_commit_bank,
    output reg  [31:0]   meta_commit_generation,
    input  wire          meta_active_bank,
    input  wire [31:0]   meta_active_generation,
    input  wire [1:0]    meta_bank_valid,
    input  wire [1:0]    meta_bank_loading,
    input  wire [31:0]   meta_gate_write_count_bank0,
    input  wire [31:0]   meta_gate_write_count_bank1,
    input  wire [31:0]   meta_down_write_count_bank0,
    input  wire [31:0]   meta_down_write_count_bank1,
    input  wire          meta_error,

    output wire          irq,
    output wire          done_sticky,
    output wire          error_sticky
);
    localparam [31:0] FULL_FORMAT_ID = 32'h4838_4605;
    localparam [31:0] ABI_VERSION = 32'h0005_0000;
    // Physical memory affinity is independent of the numerical format/ABI.
    localparam [31:0] MEMORY_LAYOUT_ID = 32'h4D30_3032; // ASCII M002
    localparam [1:0] OWNER_MLP = 2'd2;
    localparam [2:0] OP_ID_MLP = 3'd1;
    localparam [7:0] COMPLETION_SUCCESS = 8'h00;
    localparam [7:0] COMPLETION_PROTOCOL_ERROR = 8'h01;
    localparam [7:0] COMPLETION_DDR_ERROR = 8'h02;
    localparam [7:0] COMPLETION_FORMAT_ERROR = 8'h03;
    localparam [7:0] COMPLETION_TIMEOUT = 8'h04;
    localparam [7:0] COMPLETION_MAINTENANCE_ABORT = 8'h05;

    reg aw_hold_r;
    reg [11:0] awaddr_r;
    reg w_hold_r;
    reg [31:0] wdata_r;
    reg [3:0] wstrb_r;
    reg bvalid_r;
    reg [1:0] bresp_r;
    reg rvalid_r;
    reg [31:0] rdata_r;
    reg [1:0] rresp_r;
    reg done_sticky_r;
    reg error_sticky_r;
    reg irq_r;
    reg [31:0] error_code_r;
    reg [31:0] run_format_id_r;
    reg [31:0] expected_meta_generation_r;
    reg owner_done_sticky_r;
    reg [31:0] request_id_r;
    reg [15:0] cohort_id_r;
    reg [15:0] buffer_id_r;
    reg command_active_r;
    reg completion_valid_r;
    reg [31:0] active_request_id_r;
    reg [31:0] active_command_id_r;
    reg [15:0] active_cohort_id_r;
    reg [15:0] active_buffer_id_r;
    reg [5:0] active_layer_id_r;
    reg [31:0] completed_request_id_r;
    reg [31:0] completed_command_id_r;
    reg [15:0] completed_cohort_id_r;
    reg [15:0] completed_buffer_id_r;
    reg [5:0] completed_layer_id_r;
    reg [2:0] completed_op_id_r;
    reg [7:0] completed_status_r;
    reg diagnostic_error_pending_r;
    reg [31:0] command_cycle_count_r;
    reg command_abort_pending_r;
    reg [7:0] command_abort_status_r;
    reg [31:0] command_abort_error_code_r;

    wire aw_fire = s_axil_awvalid && s_axil_awready;
    wire w_fire = s_axil_wvalid && s_axil_wready;
    wire write_execute = aw_hold_r && w_hold_r && !bvalid_r;
    wire read_fire = s_axil_arvalid && s_axil_arready;
    wire mlp_command_fire = mlp_command_valid && mlp_command_ready;
    wire production_dma_error = PRODUCTION_INTEGRATION &&
        (tensor_dma_error || meta_dma_error);
    wire command_source_error = mlp_error || meta_error ||
        owner_protocol_error || production_dma_error;
    wire [7:0] command_error_status = owner_protocol_error ?
        COMPLETION_PROTOCOL_ERROR : production_dma_error ?
        COMPLETION_DDR_ERROR : COMPLETION_FORMAT_ERROR;
    wire [31:0] identity_config_merged = merge_wstrb(
        {buffer_id_r,cohort_id_r},wdata_r,wstrb_r);
    wire watchdog_timeout = command_active_r &&
        !command_abort_pending_r && !command_source_error && !mlp_done &&
        COMMAND_TIMEOUT_CYCLES > 0 &&
        command_cycle_count_r >= COMMAND_TIMEOUT_CYCLES-1;

    wire command_config_valid = run_format_id_r == FULL_FORMAT_ID &&
        (active_owner == OWNER_MLP || active_owner == 2'd3) &&
        mlp_launch_enable &&
        mlp_command_ready && !mlp_busy && !command_active_r &&
        !completion_valid_r &&
        !command_source_error &&
        (!PRODUCTION_INTEGRATION || tensor_store_armed) &&
        mlp_input_bank_ready[mlp_command_bank] &&
        meta_bank_valid[meta_active_bank] &&
        meta_active_generation == expected_meta_generation_r &&
        (mlp_layer_id[31:5] == 0) &&
        (mlp_input_base_addr[4:0] == 0) &&
        (mlp_output_base_addr[4:0] == 0) &&
        (mlp_gate_ddr0_base_addr[9:0] == 0) &&
        (mlp_gate_ddr1_base_addr[9:0] == 0) &&
        (mlp_down_ddr0_base_addr[9:0] == 0) &&
        (mlp_down_ddr1_base_addr[9:0] == 0);

    assign s_axil_awready = rst_n && !aw_hold_r && !bvalid_r;
    assign s_axil_wready = rst_n && !w_hold_r && !bvalid_r;
    assign s_axil_bvalid = bvalid_r;
    assign s_axil_bresp = bresp_r;
    assign s_axil_arready = rst_n && !rvalid_r;
    assign s_axil_rvalid = rvalid_r;
    assign s_axil_rdata = rdata_r;
    assign s_axil_rresp = rresp_r;
    assign done_sticky = done_sticky_r;
    assign error_sticky = error_sticky_r;
    assign irq = irq_r;
    assign mlp_abort_pending = command_abort_pending_r;

    function automatic [31:0] merge_wstrb;
        input [31:0] old_value;
        input [31:0] new_value;
        input [3:0] strobe;
        integer byte_index;
        begin
            merge_wstrb = old_value;
            for (byte_index=0;byte_index<4;byte_index=byte_index+1)
                if (strobe[byte_index])
                    merge_wstrb[byte_index*8 +: 8] =
                        new_value[byte_index*8 +: 8];
        end
    endfunction

    function automatic address_is_config_rw;
        input [11:0] address;
        begin
            case (address)
                12'h118,12'h11c,12'h120,12'h124,12'h128,
                12'h12c,12'h130,12'h134,12'h138,12'h13c,
                12'h140,12'h150,12'h158,12'h16c,12'h170,
                12'h280,12'h284:
                    address_is_config_rw=1'b1;
                default: address_is_config_rw=1'b0;
            endcase
        end
    endfunction

    integer telemetry_index;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            aw_hold_r<=1'b0;awaddr_r<=12'd0;w_hold_r<=1'b0;
            wdata_r<=32'd0;wstrb_r<=4'd0;bvalid_r<=1'b0;
            bresp_r<=2'b00;rvalid_r<=1'b0;rdata_r<=32'd0;
            rresp_r<=2'b00;done_sticky_r<=1'b0;error_sticky_r<=1'b0;
            irq_r<=1'b0;error_code_r<=32'd0;
            run_format_id_r<=FULL_FORMAT_ID;
            expected_meta_generation_r<=32'd0;
            owner_done_sticky_r<=1'b0;
            request_id_r<=32'd0;cohort_id_r<=16'd0;buffer_id_r<=16'd0;
            command_active_r<=1'b0;completion_valid_r<=1'b0;
            active_request_id_r<=32'd0;active_command_id_r<=32'd0;
            active_cohort_id_r<=16'd0;active_buffer_id_r<=16'd0;
            active_layer_id_r<=6'd0;completed_request_id_r<=32'd0;
            completed_command_id_r<=32'd0;completed_cohort_id_r<=16'd0;
            completed_buffer_id_r<=16'd0;completed_layer_id_r<=6'd0;
            completed_op_id_r<=3'd0;completed_status_r<=8'd0;
            diagnostic_error_pending_r<=1'b0;
            command_cycle_count_r<=32'd0;command_abort_pending_r<=1'b0;
            command_abort_status_r<=8'd0;
            command_abort_error_code_r<=32'd0;
            owner_request_valid<=1'b0;owner_request<=2'd0;
            mlp_command_valid<=1'b0;mlp_clear_pulse<=1'b0;
            mlp_command_bank<=1'b0;mlp_gate_ddr0_base_addr<=32'd0;
            mlp_gate_ddr1_base_addr<=32'd0;mlp_down_ddr0_base_addr<=32'd0;
            mlp_down_ddr1_base_addr<=32'd0;mlp_input_base_addr<=32'd0;
            mlp_output_base_addr<=32'd0;mlp_command_id<=32'd0;
            mlp_layer_id<=32'd0;meta_load_begin_valid<=1'b0;
            meta_load_bank<=1'b0;meta_commit_valid<=1'b0;
            meta_commit_bank<=1'b0;meta_commit_generation<=32'd0;
            tensor_load_valid<=1'b0;tensor_store_valid<=1'b0;
            meta_gate_base_addr<=32'd0;meta_down_base_addr<=32'd0;
        end else begin
            owner_request_valid<=1'b0;
            mlp_command_valid<=1'b0;
            mlp_clear_pulse<=1'b0;
            meta_load_begin_valid<=1'b0;
            meta_commit_valid<=1'b0;
            tensor_load_valid<=1'b0;
            tensor_store_valid<=1'b0;

            if (command_active_r && command_abort_pending_r &&
                mlp_abort_complete) begin
                command_active_r<=1'b0;completion_valid_r<=1'b1;
                command_abort_pending_r<=1'b0;
                completed_request_id_r<=active_request_id_r;
                completed_command_id_r<=active_command_id_r;
                completed_cohort_id_r<=active_cohort_id_r;
                completed_buffer_id_r<=active_buffer_id_r;
                completed_layer_id_r<=active_layer_id_r;
                completed_op_id_r<=OP_ID_MLP;
                completed_status_r<=command_abort_status_r;
                done_sticky_r<=1'b0;error_sticky_r<=1'b1;irq_r<=1'b1;
                error_code_r<=command_abort_error_code_r;
                diagnostic_error_pending_r<=1'b0;
            end else if (command_active_r && !command_abort_pending_r &&
                command_source_error) begin
                command_active_r<=1'b0;completion_valid_r<=1'b1;
                completed_request_id_r<=active_request_id_r;
                completed_command_id_r<=active_command_id_r;
                completed_cohort_id_r<=active_cohort_id_r;
                completed_buffer_id_r<=active_buffer_id_r;
                completed_layer_id_r<=active_layer_id_r;
                completed_op_id_r<=OP_ID_MLP;
                completed_status_r<=command_error_status;
            end else if (command_active_r && !command_abort_pending_r &&
                mlp_done) begin
                command_active_r<=1'b0;completion_valid_r<=1'b1;
                completed_request_id_r<=active_request_id_r;
                completed_command_id_r<=active_command_id_r;
                completed_cohort_id_r<=active_cohort_id_r;
                completed_buffer_id_r<=active_buffer_id_r;
                completed_layer_id_r<=active_layer_id_r;
                completed_op_id_r<=OP_ID_MLP;
                completed_status_r<=COMPLETION_SUCCESS;
                done_sticky_r<=1'b1;irq_r<=1'b1;
            end else if (watchdog_timeout) begin
                command_abort_pending_r<=1'b1;
                command_abort_status_r<=COMPLETION_TIMEOUT;
                command_abort_error_code_r<=32'h0002_0000;
                mlp_clear_pulse<=1'b1;
            end
            if (mlp_command_fire) begin
                command_active_r<=1'b1;
                active_request_id_r<=request_id_r;
                active_command_id_r<=mlp_command_id;
                active_cohort_id_r<=cohort_id_r;
                active_buffer_id_r<=buffer_id_r;
                active_layer_id_r<=mlp_layer_id[5:0];
                command_cycle_count_r<=32'd0;
                command_abort_pending_r<=1'b0;
                command_abort_status_r<=8'd0;
                command_abort_error_code_r<=32'd0;
            end
            if (!command_active_r || command_abort_pending_r ||
                command_source_error || mlp_done || watchdog_timeout)
                command_cycle_count_r<=32'd0;
            else
                command_cycle_count_r<=command_cycle_count_r+32'd1;
            if (owner_request_done)
                owner_done_sticky_r<=1'b1;
            if (!command_abort_pending_r &&
                (mlp_error || meta_error || owner_protocol_error ||
                (PRODUCTION_INTEGRATION &&
                 (tensor_dma_error || meta_dma_error)))) begin
                error_sticky_r<=1'b1;irq_r<=1'b1;
                if (!command_active_r)
                    diagnostic_error_pending_r<=1'b1;
                if (!error_sticky_r)
                    error_code_r<=owner_protocol_error?32'h0000_0103:
                        meta_error?32'h0000_0102:
                        production_dma_error&&tensor_dma_error?32'h0000_0104:
                        production_dma_error&&meta_dma_error?32'h0000_0105:
                        32'h0000_0101;
            end
            if (s_axil_bvalid&&s_axil_bready)bvalid_r<=1'b0;
            if (s_axil_rvalid&&s_axil_rready)rvalid_r<=1'b0;
            if (aw_fire)begin aw_hold_r<=1'b1;awaddr_r<=s_axil_awaddr;end
            if (w_fire)begin w_hold_r<=1'b1;wdata_r<=s_axil_wdata;
                wstrb_r<=s_axil_wstrb;end

            if (write_execute) begin
                aw_hold_r<=1'b0;w_hold_r<=1'b0;bvalid_r<=1'b1;
                bresp_r<=2'b00;
                case (awaddr_r)
                    12'h108: begin
                        if (wstrb_r[0]&&owner_request_ready&&
                            !admission_pause) begin
                            owner_request<=wdata_r[1:0];
                            owner_request_valid<=1'b1;
                            owner_done_sticky_r<=1'b0;
                        end else bresp_r<=2'b10;
                    end
                    12'h110: if (wstrb_r[0]) begin
                        if (wdata_r[1]) begin
                            // V4 clear is a maintenance request, not an
                            // immediate state reset. It is legal while busy;
                            // the production barrier lets the accepted whole
                            // command finish before issuing soft-clear.
                            if(!maintenance_request_pending&&
                                !maintenance_busy&&!owner_protocol_error&&
                                !(command_active_r&&(command_source_error||
                                    mlp_done||watchdog_timeout)))begin
                                mlp_clear_pulse<=1'b1;
                                owner_done_sticky_r<=1'b0;
                                if (command_active_r) begin
                                    command_abort_pending_r<=1'b1;
                                    command_abort_status_r<=
                                        COMPLETION_MAINTENANCE_ABORT;
                                    command_abort_error_code_r<=
                                        32'h0001_0000;
                                end else begin
                                    done_sticky_r<=1'b0;
                                    error_sticky_r<=1'b0;
                                    irq_r<=1'b0;error_code_r<=32'd0;
                                    diagnostic_error_pending_r<=1'b0;
                                    completion_valid_r<=1'b0;
                                end
                            end else bresp_r<=2'b10;
                        end
                        if (wdata_r[0]) begin
                            if (wdata_r[1]) begin
                                // Clear wins if both bits are written.
                                bresp_r<=2'b10;
                            end else if (command_config_valid&&
                                !admission_pause)
                                mlp_command_valid<=1'b1;
                            else begin
                                bresp_r<=2'b10;error_sticky_r<=1'b1;
                                irq_r<=1'b1;
                                diagnostic_error_pending_r<=1'b1;
                                if (!error_sticky_r)
                                    error_code_r<=32'h0000_0100;
                            end
                        end
                    end else bresp_r<=2'b10;
                    12'h154: if (wstrb_r[0]&&wstrb_r[1]) begin
                        if (wdata_r[0]&&!admission_pause&&
                            meta_load_begin_ready&&
                            meta_gate_base_addr[4:0]==0&&
                            meta_down_base_addr[4:0]==0) begin
                            meta_load_begin_valid<=1'b1;
                        end else if (wdata_r[0]) bresp_r<=2'b10;
                        if (wdata_r[1]&&!admission_pause&&
                            meta_commit_ready) begin
                            meta_commit_valid<=1'b1;
                        end else if (wdata_r[1]) bresp_r<=2'b10;
                    end else bresp_r<=2'b10;
                    12'h174: if (PRODUCTION_INTEGRATION&&wstrb_r[0]) begin
                        if (wdata_r[0]&&!admission_pause&&tensor_load_ready)
                            tensor_load_valid<=1'b1;
                        else if (wdata_r[0]) bresp_r<=2'b10;
                        if (wdata_r[1]&&!admission_pause&&tensor_store_ready)
                            tensor_store_valid<=1'b1;
                        else if (wdata_r[1]) bresp_r<=2'b10;
                        if (wdata_r[7:2]!=0) bresp_r<=2'b10;
                    end else bresp_r<=2'b10;
                    12'h2a0: begin
                        if (wstrb_r==4'hf && completion_valid_r &&
                            !command_active_r &&
                            !command_source_error &&
                            wdata_r==completed_command_id_r) begin
                            completion_valid_r<=1'b0;
                            done_sticky_r<=1'b0;
                            if (!diagnostic_error_pending_r) begin
                                error_sticky_r<=1'b0;
                                irq_r<=1'b0;
                                error_code_r<=32'd0;
                            end
                        end else bresp_r<=2'b10;
                    end
                    default: if (address_is_config_rw(awaddr_r)) begin
                        case (awaddr_r)
                            12'h118: mlp_command_id<=merge_wstrb(
                                mlp_command_id,wdata_r,wstrb_r);
                            12'h11c: mlp_layer_id<=merge_wstrb(
                                mlp_layer_id,wdata_r,wstrb_r);
                            12'h120: run_format_id_r<=merge_wstrb(
                                run_format_id_r,wdata_r,wstrb_r);
                            12'h124: mlp_input_base_addr<=merge_wstrb(
                                mlp_input_base_addr,wdata_r,wstrb_r);
                            12'h128: mlp_output_base_addr<=merge_wstrb(
                                mlp_output_base_addr,wdata_r,wstrb_r);
                            12'h12c: mlp_gate_ddr0_base_addr<=merge_wstrb(
                                mlp_gate_ddr0_base_addr,wdata_r,wstrb_r);
                            12'h130: mlp_gate_ddr1_base_addr<=merge_wstrb(
                                mlp_gate_ddr1_base_addr,wdata_r,wstrb_r);
                            12'h134: mlp_down_ddr0_base_addr<=merge_wstrb(
                                mlp_down_ddr0_base_addr,wdata_r,wstrb_r);
                            12'h138: mlp_down_ddr1_base_addr<=merge_wstrb(
                                mlp_down_ddr1_base_addr,wdata_r,wstrb_r);
                            12'h13c: if (wstrb_r[0])
                                mlp_command_bank<=wdata_r[0];
                            12'h140: expected_meta_generation_r<=merge_wstrb(
                                expected_meta_generation_r,wdata_r,wstrb_r);
                            12'h150: if (wstrb_r[0]) begin
                                meta_load_bank<=wdata_r[0];
                                meta_commit_bank<=wdata_r[0];
                            end
                            12'h158: meta_commit_generation<=merge_wstrb(
                                meta_commit_generation,wdata_r,wstrb_r);
                            12'h16c: meta_gate_base_addr<=merge_wstrb(
                                meta_gate_base_addr,wdata_r,wstrb_r);
                            12'h170: meta_down_base_addr<=merge_wstrb(
                                meta_down_base_addr,wdata_r,wstrb_r);
                            12'h280: request_id_r<=merge_wstrb(
                                request_id_r,wdata_r,wstrb_r);
                            12'h284: begin
                                cohort_id_r<=identity_config_merged[15:0];
                                buffer_id_r<=identity_config_merged[31:16];
                            end
                        endcase
                    end else bresp_r<=2'b10;
                endcase
            end

            if (read_fire) begin
                rvalid_r<=1'b1;rresp_r<=2'b00;
                case (s_axil_araddr)
                    12'h100:rdata_r<=FULL_FORMAT_ID;
                    12'h104:rdata_r<=ABI_VERSION;
                    12'h10c:rdata_r<={ddr1_outstanding,ddr0_outstanding,
                        9'd0,owner_done_sticky_r,owner_request_ready,mlp_launch_enable,
                        attention_launch_enable,owner_switch_pending,
                        active_owner};
                    12'h114:rdata_r<={19'd0,meta_error,
                        owner_protocol_error,meta_bank_valid,
                        meta_active_bank,mlp_input_bank_ready,mlp_phase,
                        error_sticky_r,done_sticky_r,mlp_busy};
                    12'h118:rdata_r<=mlp_command_id;
                    12'h11c:rdata_r<=mlp_layer_id;
                    12'h120:rdata_r<=run_format_id_r;
                    12'h124:rdata_r<=mlp_input_base_addr;
                    12'h128:rdata_r<=mlp_output_base_addr;
                    12'h12c:rdata_r<=mlp_gate_ddr0_base_addr;
                    12'h130:rdata_r<=mlp_gate_ddr1_base_addr;
                    12'h134:rdata_r<=mlp_down_ddr0_base_addr;
                    12'h138:rdata_r<=mlp_down_ddr1_base_addr;
                    12'h13c:rdata_r<={31'd0,mlp_command_bank};
                    12'h140:rdata_r<=expected_meta_generation_r;
                    12'h144:rdata_r<=meta_active_generation;
                    12'h148:rdata_r<=error_code_r;
                    12'h14c:rdata_r<={27'd0,meta_bank_loading,
                        meta_bank_valid,meta_active_bank};
                    12'h150:rdata_r<={31'd0,meta_commit_bank};
                    12'h158:rdata_r<=meta_commit_generation;
                    12'h15c:rdata_r<=meta_gate_write_count_bank0;
                    12'h160:rdata_r<=meta_gate_write_count_bank1;
                    12'h164:rdata_r<=meta_down_write_count_bank0;
                    12'h168:rdata_r<=meta_down_write_count_bank1;
                    12'h16c:rdata_r<=meta_gate_base_addr;
                    12'h170:rdata_r<=meta_down_base_addr;
                    12'h174:rdata_r<=32'd0;
                    12'h178:rdata_r<={16'd0,meta_dma_phase,
                        tensor_dma_phase,meta_dma_done,tensor_dma_done,
                        meta_dma_error,tensor_dma_error,meta_dma_busy,
                        tensor_store_armed,tensor_dma_busy};
                    12'h17c:rdata_r<=tensor_input_beat_count;
                    12'h244:rdata_r<=tensor_input_group_count;
                    12'h248:rdata_r<=tensor_output_beat_count;
                    12'h24c:rdata_r<=tensor_output_tile_count;
                    12'h250:rdata_r<=meta_dma_gate_record_count;
                    12'h254:rdata_r<=meta_dma_down_record_count;
                    12'h258:rdata_r<=meta_dma_physical_bytes[31:0];
                    12'h25c:rdata_r<=meta_dma_physical_bytes[63:32];
                    12'h260:rdata_r<={26'd0,paired_quiescent,
                        maintenance_busy,owner_protocol_error,
                        owner_switch_pending,active_owner};
                    12'h264:rdata_r<=paired_attn_bursts;
                    12'h268:rdata_r<=paired_mlp_bursts;
                    12'h26c:rdata_r<=paired_both_cycles;
                    12'h270:rdata_r<=paired_hol0;
                    12'h274:rdata_r<=paired_hol1;
                    12'h278:rdata_r<=paired_hwm0;
                    12'h27c:rdata_r<=paired_hwm1;
                    12'h280:rdata_r<=request_id_r;
                    12'h284:rdata_r<={buffer_id_r,cohort_id_r};
                    12'h288:rdata_r<=completed_request_id_r;
                    12'h28c:rdata_r<=completed_command_id_r;
                    12'h290:rdata_r<={completed_buffer_id_r,
                        completed_cohort_id_r};
                    12'h294:rdata_r<={26'd0,completed_layer_id_r};
                    12'h298:rdata_r<={5'd0,completed_status_r,
                        completed_op_id_r,completed_buffer_id_r};
                    12'h29c:rdata_r<={30'd0,command_active_r,
                        completion_valid_r};
                    12'h2a0:rdata_r<={31'd0,diagnostic_error_pending_r};
                    12'h2a4:rdata_r<=command_cycle_count_r;
                    12'h2a8:rdata_r<={30'd0,maintenance_request_pending,
                        command_abort_pending_r};
                    12'h2ac:rdata_r<=mlp_down_output_saturation_count;
                    12'h2b0:rdata_r<=mlp_total_shift_format_count;
                    12'h2b4:rdata_r<=mlp_numeric_status;
                    12'h2b8:rdata_r<=MEMORY_LAYOUT_ID;
                    default: begin
                        if (s_axil_araddr>=12'h180&&
                            s_axil_araddr<=12'h240&&
                            s_axil_araddr[1:0]==2'b00) begin
                            telemetry_index=(s_axil_araddr-12'h180)>>2;
                            rdata_r<=mlp_telemetry[telemetry_index*32 +: 32];
                        end else begin
                            rdata_r<=32'd0;rresp_r<=2'b10;
                        end
                    end
                endcase
            end
        end
    end
endmodule
