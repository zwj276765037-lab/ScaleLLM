`timescale 1ns/1ps
// GU-only format05 engine: one sealed 128-group activation tensor,
// real dual 8x12/S37/S44 kernels, and interleaved S24 Gate/Up records.
module hap_mlp_gu_compute16_s44 #(
    parameter integer AXI_ADDR_W=32,
    parameter integer INTERMEDIATE_COLUMNS=14336,
    parameter integer HIDDEN_COLUMNS=4096,
    parameter integer HIDDEN_GROUPS=128,
    parameter integer GATE_SOURCE_RECORDS=2*((INTERMEDIATE_COLUMNS+15)/16),
    parameter integer OUTSTANDING_DEPTH=8,
    parameter integer ENFORCE_PRODUCTION_SHAPE=1,
    parameter integer CACHE_GROUP_W=9
)(
    input  wire                          core_clk,
    input  wire                          core_rst_n,
    input  wire                          core_clear,
    input  wire                          command_pause,
    output wire                          weight_source_quiescent,
    input  wire                          command_valid,
    output wire                          command_ready,
    input  wire [1:0]                    command_opcode,
    input  wire                          cache_sealed,
    input  wire [AXI_ADDR_W-1:0]         gate_ddr0_base_addr,
    input  wire [AXI_ADDR_W-1:0]         gate_ddr1_base_addr,

    output wire                          cache_rd_req_valid,
    input  wire                          cache_rd_req_ready,
    output wire                          cache_rd_req_bank,
    output wire [8:0]                    cache_rd_req_group,
    input  wire                          cache_rd_rsp_valid,
    output wire                          cache_rd_rsp_ready,
    input  wire                          cache_rd_rsp_bank,
    input  wire [8:0]                    cache_rd_rsp_group,
    input  wire [16*32*8-1:0]            cache_rd_rsp_u8x16x32,
    input  wire [16*24-1:0]              cache_rd_rsp_meta_u24x16,

    input  wire                          gate_meta_valid,
    output wire                          gate_meta_ready,
    input  wire [223:0]                  gate_meta_u224,

    input  wire                          ddr0_clk,
    input  wire                          ddr0_rst_n,
    output wire                          ddr0_axi_arvalid,
    input  wire                          ddr0_axi_arready,
    output wire [AXI_ADDR_W-1:0]         ddr0_axi_araddr,
    output wire [7:0]                    ddr0_axi_arlen,
    output wire [2:0]                    ddr0_axi_arsize,
    output wire [1:0]                    ddr0_axi_arburst,
    input  wire                          ddr0_axi_rvalid,
    output wire                          ddr0_axi_rready,
    input  wire [511:0]                  ddr0_axi_rdata,
    input  wire [1:0]                    ddr0_axi_rresp,
    input  wire                          ddr0_axi_rlast,
    input  wire                          ddr1_clk,
    input  wire                          ddr1_rst_n,
    output wire                          ddr1_axi_arvalid,
    input  wire                          ddr1_axi_arready,
    output wire [AXI_ADDR_W-1:0]         ddr1_axi_araddr,
    output wire [7:0]                    ddr1_axi_arlen,
    output wire [2:0]                    ddr1_axi_arsize,
    output wire [1:0]                    ddr1_axi_arburst,
    input  wire                          ddr1_axi_rvalid,
    output wire                          ddr1_axi_rready,
    input  wire [511:0]                  ddr1_axi_rdata,
    input  wire [1:0]                    ddr1_axi_rresp,
    input  wire                          ddr1_axi_rlast,

    output wire                          gu_out_valid,
    input  wire                          gu_out_ready,
    output wire [6143:0]                  gu_out_s24x16x16,
    output wire [9:0]                     gu_out_tile,
    output wire                          gu_out_matrix,
    output wire                          gu_out_last,
    output wire                          compute_quiescent,
    output wire                          flow_stall,
    output wire                          busy,
    output reg                           done,
    output wire                          error,
    output wire [2:0]                    phase,

    output reg  [31:0]                   gate_ddr0_raw_beats,
    output reg  [31:0]                   gate_ddr1_raw_beats,
    output reg  [31:0]                   gate_ddr0_elapsed_cycles,
    output reg  [31:0]                   gate_ddr1_elapsed_cycles,
    output reg  [31:0]                   gate_ddr0_bursts,
    output reg  [31:0]                   gate_ddr1_bursts,
    output reg  [31:0]                   gate_ddr0_ar_stalls,
    output reg  [31:0]                   gate_ddr1_ar_stalls,
    output reg  [31:0]                   gate_ddr0_r_backpressure,
    output reg  [31:0]                   gate_ddr1_r_backpressure,
    output reg  [31:0]                   gate_ddr0_response_idle,
    output reg  [31:0]                   gate_ddr1_response_idle,
    output reg  [31:0]                   gate_ddr0_max_outstanding,
    output reg  [31:0]                   gate_ddr1_max_outstanding,
    output reg  [63:0]                   gate_physical_bytes,
    output reg  [63:0]                   gate_useful_bytes,
    output wire [31:0]                   gate_cache_request_count,
    output wire [31:0]                   gate_weight_group_count,
    output wire [31:0]                   gate_projection_tile_count,
    output wire [31:0]                   saturation_count,
    output wire [31:0]                   total_shift_format_count,
    output wire [31:0]                   numeric_status
);

    localparam integer GATE_SOURCE_TRANSACTIONS=GATE_SOURCE_RECORDS*HIDDEN_GROUPS;
    localparam [2:0] P_IDLE=0,P_GATE_LAUNCH=1,P_GATE_RUN=2;
    reg [2:0] state_r;
    reg [AXI_ADDR_W-1:0] gate_base0_r,gate_base1_r;
    reg gate_compute_done_r,gate_ddr_done_r,sticky_error_r;
    (* DONT_TOUCH="yes", KEEP="yes" *) wire control_reset,gate_metrics_reset;
    (* DONT_TOUCH="yes", KEEP="yes" *) LUT2 #(.INIT(4'hd))
    u_control_reset(.I0(core_rst_n),.I1(core_clear),.O(control_reset));
    (* DONT_TOUCH="yes", KEEP="yes" *) LUT2 #(.INIT(4'hd))
    u_gate_metrics_reset(.I0(core_rst_n),.I1(core_clear),.O(gate_metrics_reset));
    wire command_fire=command_valid&&command_ready;
    assign command_ready=core_rst_n&&!core_clear&&!command_pause&&
        state_r==P_IDLE&&cache_sealed&&command_opcode==1;
    assign busy=state_r!=P_IDLE;
    assign phase=state_r;
    assign error=sticky_error_r;
    wire frontend_command_ready,gate_command_ready;
    wire frontend_command_valid=state_r==P_GATE_LAUNCH&&gate_command_ready;
    wire gate_command_valid=state_r==P_GATE_LAUNCH&&frontend_command_ready;
    wire frontend_command_fire=frontend_command_valid&&frontend_command_ready;
    wire [19:0] frontend_group_count=GATE_SOURCE_TRANSACTIONS;
    wire [AXI_ADDR_W-1:0] frontend_base0=gate_base0_r,frontend_base1=gate_base1_r;
    wire frontend_busy,frontend_done,frontend_error,frontend_out_valid,frontend_out_ready;
    wire signed [16*32*4-1:0] frontend_weights;
    wire [223:0] frontend_weight_meta;
    wire frontend_meta_valid=state_r==P_GATE_RUN&&gate_meta_valid;
    wire [223:0] frontend_meta=gate_meta_u224;
    wire frontend_meta_ready;
    wire [31:0] f_d0_raw;
    wire [31:0] f_d1_raw;
    wire [31:0] f_d0_elapsed;
    wire [31:0] f_d1_elapsed;
    wire [31:0] f_d0_bursts;
    wire [31:0] f_d1_bursts;
    wire [31:0] f_d0_ar_stall;
    wire [31:0] f_d1_ar_stall;
    wire [31:0] f_d0_r_back;
    wire [31:0] f_d1_r_back;
    wire [31:0] f_d0_idle;
    wire [31:0] f_d1_idle;
    wire [31:0] f_d0_max;
    wire [31:0] f_d1_max;
    wire [31:0] f_useful_groups;
    wire [63:0] f_physical_bytes;
    wire [63:0] f_useful_bytes;

    assign gate_meta_ready=state_r==P_GATE_RUN&&frontend_meta_ready;
    hap_mlp_w4_dual_ddr_frontend #(
        .AXI_ADDR_W(AXI_ADDR_W),
        .OUTSTANDING_DEPTH(OUTSTANDING_DEPTH)
    ) u_w4_frontend (
        .core_clk(core_clk), .core_rst_n(core_rst_n),
        .core_clear(core_clear), .command_valid(frontend_command_valid),
        .command_ready(frontend_command_ready),
        .ddr0_base_addr(frontend_base0), .ddr1_base_addr(frontend_base1),
        .group_count(frontend_group_count),
        .ddr0_clk(ddr0_clk), .ddr0_rst_n(ddr0_rst_n),
        .ddr0_axi_arvalid(ddr0_axi_arvalid),
        .ddr0_axi_arready(ddr0_axi_arready),
        .ddr0_axi_araddr(ddr0_axi_araddr), .ddr0_axi_arlen(ddr0_axi_arlen),
        .ddr0_axi_arsize(ddr0_axi_arsize),
        .ddr0_axi_arburst(ddr0_axi_arburst),
        .ddr0_axi_rvalid(ddr0_axi_rvalid), .ddr0_axi_rready(ddr0_axi_rready),
        .ddr0_axi_rdata(ddr0_axi_rdata), .ddr0_axi_rresp(ddr0_axi_rresp),
        .ddr0_axi_rlast(ddr0_axi_rlast),
        .ddr1_clk(ddr1_clk), .ddr1_rst_n(ddr1_rst_n),
        .ddr1_axi_arvalid(ddr1_axi_arvalid),
        .ddr1_axi_arready(ddr1_axi_arready),
        .ddr1_axi_araddr(ddr1_axi_araddr), .ddr1_axi_arlen(ddr1_axi_arlen),
        .ddr1_axi_arsize(ddr1_axi_arsize),
        .ddr1_axi_arburst(ddr1_axi_arburst),
        .ddr1_axi_rvalid(ddr1_axi_rvalid), .ddr1_axi_rready(ddr1_axi_rready),
        .ddr1_axi_rdata(ddr1_axi_rdata), .ddr1_axi_rresp(ddr1_axi_rresp),
        .ddr1_axi_rlast(ddr1_axi_rlast),
        .meta_valid(frontend_meta_valid), .meta_ready(frontend_meta_ready),
        .meta_u224(frontend_meta), .out_valid(frontend_out_valid),
        .out_ready(frontend_out_ready),
        .weights_s4x16x32(frontend_weights),
        .weight_meta_u224(frontend_weight_meta),
        .busy(frontend_busy), .done(frontend_done), .error(frontend_error),
        .ddr0_raw_beat_snapshot(f_d0_raw),
        .ddr1_raw_beat_snapshot(f_d1_raw),
        .ddr0_elapsed_cycle_snapshot(f_d0_elapsed),
        .ddr1_elapsed_cycle_snapshot(f_d1_elapsed),
        .ddr0_burst_snapshot(f_d0_bursts),
        .ddr1_burst_snapshot(f_d1_bursts),
        .ddr0_ar_stall_snapshot(f_d0_ar_stall),
        .ddr1_ar_stall_snapshot(f_d1_ar_stall),
        .ddr0_r_backpressure_snapshot(f_d0_r_back),
        .ddr1_r_backpressure_snapshot(f_d1_r_back),
        .ddr0_response_idle_snapshot(f_d0_idle),
        .ddr1_response_idle_snapshot(f_d1_idle),
        .ddr0_max_outstanding_snapshot(f_d0_max),
        .ddr1_max_outstanding_snapshot(f_d1_max),
        .physical_read_byte_count(f_physical_bytes),
        .useful_weight_byte_count(f_useful_bytes),
        .useful_group_count(f_useful_groups)
    );

    assign weight_source_quiescent = !frontend_command_valid && !frontend_busy;

    wire gate_compute_valid;
    wire gate_compute_ready;
    wire gate_weight_ready;
    wire gate_compute_first;
    wire gate_compute_last;
    wire signed [16*32*9-1:0] gate_compute_activation;
    wire signed [12*32*4-1:0] gate_compute_weights;
    wire [16*8-1:0] gate_compute_acode;
    wire [16*6-1:0] gate_compute_ashift;
    wire [12*8-1:0] gate_compute_wcode;
    wire [12*6-1:0] gate_compute_wshift;
    wire [11:0] gate_compute_mask;
    wire shared_gate_valid;
    wire shared_gate_ready;
    wire signed [16*12*24-1:0] shared_gate_s24;
    wire gate_req_valid,gate_req_ready,gate_rsp_ready,gate_req_bank;
    wire [6:0] gate_req_group;
    wire gate_quiescent;
    wire gate_busy;
    wire gate_done;
    wire gate_error;
    wire [31:0] gate_source_count;
    wire [31:0] gate_compute_count;
    wire [31:0] gate_internal_projection_count;
    wire [31:0] gate_external_projection_count;
    wire [31:0] gate_activation_count;
    wire [31:0] gate_scheduler_saturation;
    wire gate_format_error;

    hap_mlp_linear_gate_up_scheduler16_s24 #(
        .INTERMEDIATE_COLUMNS(INTERMEDIATE_COLUMNS),
        .GROUPS(HIDDEN_GROUPS),
        .ENFORCE_PRODUCTION_SHAPE(ENFORCE_PRODUCTION_SHAPE)
    ) u_gate_scheduler (
        .clk(core_clk), .rst_n(core_rst_n), .clear(core_clear),
        .command_valid(gate_command_valid),
        .command_ready(gate_command_ready),
        .activation_bank(1'b0),
        .activation_bank_ready(cache_sealed),
        .cache_rd_req_valid(gate_req_valid),
        .cache_rd_req_ready(gate_req_ready),
        .cache_rd_req_bank(gate_req_bank),
        .cache_rd_req_group(gate_req_group),
        .cache_rd_rsp_valid(cache_rd_rsp_valid && state_r==P_GATE_RUN),
        .cache_rd_rsp_ready(gate_rsp_ready),
        .cache_rd_rsp_bank(cache_rd_rsp_bank),
        .cache_rd_rsp_group(cache_rd_rsp_group[6:0]),
        .cache_rd_rsp_u8x16x32(cache_rd_rsp_u8x16x32),
        .cache_rd_rsp_meta_u24x16(cache_rd_rsp_meta_u24x16),
        .weight_valid(state_r == P_GATE_RUN && frontend_out_valid),
        .weight_ready(gate_weight_ready),
        .weights_s4x16x32(frontend_weights),
        .weight_meta_u224(frontend_weight_meta),
        .compute_valid(gate_compute_valid),
        .compute_ready(gate_compute_ready),
        .compute_first(gate_compute_first),
        .compute_last(gate_compute_last),
        .compute_activation_s9x16x32(gate_compute_activation),
        .compute_weights_s4x12x32(gate_compute_weights),
        .compute_activation_code_u8x16(gate_compute_acode),
        .compute_activation_shift_u6x16(gate_compute_ashift),
        .compute_weight_code_u8x12(gate_compute_wcode),
        .compute_weight_shift_u6x12(gate_compute_wshift),
        .compute_column_valid_u12(gate_compute_mask),
        .projection_valid(shared_gate_valid),
        .projection_ready(shared_gate_ready),
        .projection_s24x16x12(shared_gate_s24),
        .out_valid(gu_out_valid), .out_ready(gu_out_ready),
        .out_s24x16x16(gu_out_s24x16x16), .out_tile(gu_out_tile),
        .out_matrix(gu_out_matrix), .out_last(gu_out_last),
        .quiescent(gate_quiescent),
        .busy(gate_busy), .done(gate_done), .error(gate_error),
        .source_transaction_count(gate_source_count),
        .cache_request_count(gate_cache_request_count),
        .compute_transaction_count(gate_compute_count),
        .internal_projection_pass_count(gate_internal_projection_count),
        .external_projection_record_count(gate_external_projection_count),
        .saturation_count(gate_scheduler_saturation),
        .format_error(gate_format_error)
    );

    assign gate_weight_group_count = gate_source_count;
    assign gate_projection_tile_count = gate_external_projection_count;


    assign cache_rd_req_valid=state_r==P_GATE_RUN&&gate_req_valid;
    assign cache_rd_req_group={2'b0,gate_req_group};
    assign cache_rd_req_bank=1'b0;
    assign gate_req_ready=state_r==P_GATE_RUN&&cache_rd_req_ready;
    assign cache_rd_rsp_ready=state_r==P_GATE_RUN&&gate_rsp_ready;
    wire shared_error,shared_guard_overflow,shared_accumulator_overflow,shared_format_error;
    wire [31:0] shared_gate_saturation,shared_input_count,shared_gate_output_count;
    assign gate_compute_ready=state_r==P_GATE_RUN&&shared_input_ready;
    wire shared_input_ready;
    hap_mlp_gu_dual_slice16x12_s44 u_shared_compute(
        .clk(core_clk),.rst_n(core_rst_n),.clear(core_clear),
        .in_valid(state_r==P_GATE_RUN&&gate_compute_valid),.in_ready(shared_input_ready),
        .in_first(gate_compute_first),.in_last(gate_compute_last),
        .activation_s9x16x32(gate_compute_activation),.weights_s4x12x32(gate_compute_weights),
        .activation_code_u8x16(gate_compute_acode),.activation_shift_u6x16(gate_compute_ashift),
        .weight_code_u8x12(gate_compute_wcode),.weight_shift_u6x12(gate_compute_wshift),
        .column_valid_u12(gate_compute_mask),.gate_valid(shared_gate_valid),
        .gate_ready(shared_gate_ready),.gate_s24x16x12(shared_gate_s24),
        .gate_saturation(shared_gate_saturation),.guard_overflow(shared_guard_overflow),
        .accumulator_overflow(shared_accumulator_overflow),
        .total_shift_format_count(total_shift_format_count),.format_error(shared_format_error),
        .input_transaction_count(shared_input_count),.gate_output_pass_count(shared_gate_output_count),
        .error(shared_error));
    assign compute_quiescent=state_r==P_IDLE&&!frontend_busy&&gate_quiescent&&!shared_gate_valid;
    assign flow_stall=busy&&(
        (cache_rd_req_valid&&!cache_rd_req_ready)||(cache_rd_rsp_valid&&!cache_rd_rsp_ready)||
        (frontend_command_valid&&!frontend_command_ready)||(gate_command_valid&&!gate_command_ready)||
        (frontend_meta_valid&&!frontend_meta_ready)||(frontend_out_valid&&!frontend_out_ready)||
        (gate_compute_valid&&!gate_compute_ready)||(shared_gate_valid&&!shared_gate_ready)||
        (gu_out_valid&&!gu_out_ready));
    assign saturation_count=shared_gate_saturation;
    assign numeric_status={29'd0,shared_format_error||gate_format_error,
        shared_accumulator_overflow,shared_guard_overflow};
    assign frontend_out_ready=state_r==P_GATE_RUN&&gate_weight_ready;
    always @(posedge core_clk) begin
        if(control_reset)begin
            state_r<=P_IDLE;gate_base0_r<=0;gate_base1_r<=0;
            gate_compute_done_r<=0;gate_ddr_done_r<=0;sticky_error_r<=0;done<=0;
        end else begin
            done<=0;
            if(command_fire)begin
                gate_base0_r<=gate_ddr0_base_addr;gate_base1_r<=gate_ddr1_base_addr;
                gate_compute_done_r<=0;gate_ddr_done_r<=0;sticky_error_r<=0;
                state_r<=P_GATE_LAUNCH;
            end
            if(state_r==P_GATE_LAUNCH&&frontend_command_fire&&gate_command_valid&&gate_command_ready)
                state_r<=P_GATE_RUN;
            if(state_r==P_GATE_RUN)begin
                if(gate_done)gate_compute_done_r<=1;
                if(frontend_done)gate_ddr_done_r<=1;
                if((gate_compute_done_r||gate_done)&&(gate_ddr_done_r||frontend_done)&&
                    gate_quiescent&&!frontend_busy)begin state_r<=P_IDLE;done<=1;end
            end
            if(frontend_error||gate_error||shared_error||shared_guard_overflow||shared_accumulator_overflow||
                (state_r==P_GATE_RUN&&cache_rd_rsp_valid&&cache_rd_rsp_ready&&
                    (cache_rd_rsp_group[8:7]!=0||cache_rd_rsp_bank))||
                (state_r==P_GATE_RUN&&f_useful_groups>GATE_SOURCE_TRANSACTIONS)||
                gate_source_count>GATE_SOURCE_TRANSACTIONS||
                gate_compute_count>2*((INTERMEDIATE_COLUMNS+11)/12)*HIDDEN_GROUPS)
                sticky_error_r<=1;
        end
    end
    always @(posedge core_clk) begin
        if (gate_metrics_reset) begin
            gate_ddr0_raw_beats <= 32'd0;
            gate_ddr1_raw_beats <= 32'd0;
            gate_ddr0_elapsed_cycles <= 32'd0;
            gate_ddr1_elapsed_cycles <= 32'd0;
            gate_ddr0_bursts <= 32'd0;
            gate_ddr1_bursts <= 32'd0;
            gate_ddr0_ar_stalls <= 32'd0;
            gate_ddr1_ar_stalls <= 32'd0;
            gate_ddr0_r_backpressure <= 32'd0;
            gate_ddr1_r_backpressure <= 32'd0;
            gate_ddr0_response_idle <= 32'd0;
            gate_ddr1_response_idle <= 32'd0;
            gate_ddr0_max_outstanding <= 32'd0;
            gate_ddr1_max_outstanding <= 32'd0;
            gate_physical_bytes <= 64'd0;
            gate_useful_bytes <= 64'd0;
        end else if (state_r == P_GATE_RUN && frontend_done) begin
            gate_ddr0_raw_beats <= f_d0_raw;
            gate_ddr1_raw_beats <= f_d1_raw;
            gate_ddr0_elapsed_cycles <= f_d0_elapsed;
            gate_ddr1_elapsed_cycles <= f_d1_elapsed;
            gate_ddr0_bursts <= f_d0_bursts;
            gate_ddr1_bursts <= f_d1_bursts;
            gate_ddr0_ar_stalls <= f_d0_ar_stall;
            gate_ddr1_ar_stalls <= f_d1_ar_stall;
            gate_ddr0_r_backpressure <= f_d0_r_back;
            gate_ddr1_r_backpressure <= f_d1_r_back;
            gate_ddr0_response_idle <= f_d0_idle;
            gate_ddr1_response_idle <= f_d1_idle;
            gate_ddr0_max_outstanding <= f_d0_max;
            gate_ddr1_max_outstanding <= f_d1_max;
            gate_physical_bytes <= f_physical_bytes;
            gate_useful_bytes <= f_useful_bytes;
        end
    end

    initial begin
        if(ENFORCE_PRODUCTION_SHAPE&&(INTERMEDIATE_COLUMNS!=14336||HIDDEN_COLUMNS!=4096||
            HIDDEN_GROUPS!=128||GATE_SOURCE_RECORDS!=1792||GATE_SOURCE_TRANSACTIONS!=229376))
            $error("GU production shape mismatch");
        if(INTERMEDIATE_COLUMNS<=0||INTERMEDIATE_COLUMNS>14336||(INTERMEDIATE_COLUMNS%32)!=0||
            HIDDEN_COLUMNS!=4096||HIDDEN_GROUPS!=128||GATE_SOURCE_RECORDS!=2*((INTERMEDIATE_COLUMNS+15)/16)||
            CACHE_GROUP_W!=9||GATE_SOURCE_TRANSACTIONS<=0||GATE_SOURCE_TRANSACTIONS>1048575)
            $error("GU structural shape mismatch");
    end
endmodule
