`timescale 1ns / 1ps

// Cohort16 Attention AXI4-Lite command and completion control.
module hap_attention_cohort16_axil_control (
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

    input  wire          engine_busy,
    input  wire          launch_enable,
    input  wire          maintenance_busy,
    input  wire          engine_done,
    input  wire          engine_error,
    input  wire [31:0]   engine_error_code,
    input  wire          metadata_loaded,
    input  wire          rope_loaded,
    input  wire [31:0]   cycle_count,
    input  wire [31:0]   weight_group_count,
    input  wire [31:0]   projection_tile_count,
    input  wire [31:0]   attention_row_count,
    input  wire [31:0]   wo_tile_count,
    input  wire [31:0]   input_frontend_cycle_count,
    input  wire [31:0]   qkv_projection_cycle_count,
    input  wire [31:0]   rope_cycle_count,
    input  wire [31:0]   kv12_cycle_count,
    input  wire [31:0]   attention_cycle_count,
    input  wire [31:0]   context_frontend_cycle_count,
    input  wire [31:0]   wo_projection_cycle_count,
    input  wire [31:0]   control_overhead_cycle_count,
    input  wire          completion_valid,
    input  wire [31:0]   completion_request_id,
    input  wire [31:0]   completion_command_id,
    input  wire [15:0]   completion_cohort_id,
    input  wire [15:0]   completion_buffer_id,
    input  wire [5:0]    completion_layer_id,
    input  wire [2:0]    completion_op_id,
    input  wire [7:0]    completion_status,

    output reg           start_pulse,
    output reg           clear_pulse,
    output reg           reload_metadata,
    output reg           reload_rope,
    output reg           preserve_historical_kv,
    output reg [31:0]    request_id,
    output reg [31:0]    command_id,
    output reg [15:0]    cohort_id,
    output reg [15:0]    buffer_id,
    output reg [31:0]    layer_id,
    output reg [6:0]     query_start,
    output reg [7:0]     valid_key_count,
    output reg [7:0]     query_count,
    output reg [31:0]    run_format_id,
    output reg [31:0]    input_base,
    output reg [31:0]    output_base,
    output reg [31:0]    weight_c0_base,
    output reg [31:0]    weight_c1_base,
    output reg [31:0]    weight_meta_base,
    output reg [31:0]    rope_base,
    output wire          irq,
    output wire          done_sticky,
    output wire          error_sticky
);

    localparam [31:0] FORMAT_ID = 32'h4838_4103;
    localparam [31:0] ABI_VERSION = 32'h0002_0000;
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
    reg [31:0] completed_request_id_r;
    reg [31:0] completed_command_id_r;
    reg [15:0] completed_cohort_id_r;
    reg [15:0] completed_buffer_id_r;
    reg [5:0] completed_layer_id_r;
    reg [2:0] completed_op_id_r;
    reg [7:0] completed_status_r;

    wire aw_fire = s_axil_awvalid && s_axil_awready;
    wire w_fire = s_axil_wvalid && s_axil_wready;
    wire write_execute = aw_hold_r && w_hold_r && !bvalid_r;
    wire read_fire = s_axil_arvalid && s_axil_arready;
    wire [31:0] query_config_merged = merge_wstrb(
        {8'd0, query_count, valid_key_count, 1'b0, query_start},
        wdata_r, wstrb_r);
    wire [31:0] identity_config_merged = merge_wstrb(
        {buffer_id, cohort_id}, wdata_r, wstrb_r);

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
    // Drive XDMA's asynchronous user-IRQ synchronizer directly from a source
    // register.  A combinational OR here is logically safe for sticky bits,
    // but report_cdc correctly flags logic before a synchronizer as CDC-10.
    assign irq = irq_r;

    function automatic [31:0] merge_wstrb;
        input [31:0] old_value;
        input [31:0] new_value;
        input [3:0] strobe;
        integer byte_index;
        begin
            merge_wstrb = old_value;
            for (byte_index=0; byte_index<4; byte_index=byte_index+1)
                if (strobe[byte_index])
                    merge_wstrb[byte_index*8 +: 8] =
                        new_value[byte_index*8 +: 8];
        end
    endfunction

    function automatic address_is_rw;
        input [11:0] address;
        begin
            case (address)
                12'h010, 12'h014, 12'h018, 12'h01c,
                12'h020, 12'h024, 12'h028, 12'h02c,
                12'h030, 12'h034, 12'h070, 12'h074:
                    address_is_rw = 1'b1;
                default: address_is_rw = 1'b0;
            endcase
        end
    endfunction

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            aw_hold_r <= 1'b0;
            awaddr_r <= 12'd0;
            w_hold_r <= 1'b0;
            wdata_r <= 32'd0;
            wstrb_r <= 4'd0;
            bvalid_r <= 1'b0;
            bresp_r <= 2'b00;
            rvalid_r <= 1'b0;
            rdata_r <= 32'd0;
            rresp_r <= 2'b00;
            done_sticky_r <= 1'b0;
            error_sticky_r <= 1'b0;
            irq_r <= 1'b0;
            error_code_r <= 32'd0;
            start_pulse <= 1'b0;
            clear_pulse <= 1'b0;
            reload_metadata <= 1'b0;
            reload_rope <= 1'b0;
            preserve_historical_kv <= 1'b0;
            request_id <= 32'd0;
            command_id <= 32'd0;
            cohort_id <= 16'd0;
            buffer_id <= 16'd0;
            layer_id <= 32'd0;
            query_start <= 7'd0;
            valid_key_count <= 8'd0;
            query_count <= 8'd16;
            run_format_id <= FORMAT_ID;
            input_base <= 32'd0;
            output_base <= 32'd0;
            weight_c0_base <= 32'd0;
            weight_c1_base <= 32'd0;
            weight_meta_base <= 32'd0;
            rope_base <= 32'd0;
            completed_request_id_r <= 32'd0;
            completed_command_id_r <= 32'd0;
            completed_cohort_id_r <= 16'd0;
            completed_buffer_id_r <= 16'd0;
            completed_layer_id_r <= 6'd0;
            completed_op_id_r <= 3'd0;
            completed_status_r <= 8'd0;
        end else begin
            start_pulse <= 1'b0;
            clear_pulse <= 1'b0;
            if (engine_done) begin
                done_sticky_r <= 1'b1;
                irq_r <= 1'b1;
            end
            if (engine_error) begin
                error_sticky_r <= 1'b1;
                irq_r <= 1'b1;
                if (!error_sticky_r)
                    error_code_r <= engine_error_code;
            end
            if (completion_valid) begin
                completed_request_id_r <= completion_request_id;
                completed_command_id_r <= completion_command_id;
                completed_cohort_id_r <= completion_cohort_id;
                completed_buffer_id_r <= completion_buffer_id;
                completed_layer_id_r <= completion_layer_id;
                completed_op_id_r <= completion_op_id;
                completed_status_r <= completion_status;
            end
            if (s_axil_bvalid && s_axil_bready)
                bvalid_r <= 1'b0;
            if (s_axil_rvalid && s_axil_rready)
                rvalid_r <= 1'b0;
            if (aw_fire) begin
                aw_hold_r <= 1'b1;
                awaddr_r <= s_axil_awaddr;
            end
            if (w_fire) begin
                w_hold_r <= 1'b1;
                wdata_r <= s_axil_wdata;
                wstrb_r <= s_axil_wstrb;
            end

            if (write_execute) begin
                aw_hold_r <= 1'b0;
                w_hold_r <= 1'b0;
                bvalid_r <= 1'b1;
                bresp_r <= 2'b00;
                if (awaddr_r == 12'h008) begin
                    if (wstrb_r[0]) begin
                        reload_metadata <= wdata_r[2];
                        reload_rope <= wdata_r[3];
                        preserve_historical_kv <= wdata_r[4];
                        if (wdata_r[1]) begin
                            // Legacy bit1 acknowledges sticky status only.
                            // Fabric maintenance is requested through the V4
                            // MLP control space and must not invalidate
                            // resident Attention metadata/RoPE every token.
                            clear_pulse <= 1'b1;
                            done_sticky_r <= 1'b0;
                            error_sticky_r <= 1'b0;
                            irq_r <= 1'b0;
                            error_code_r <= 32'd0;
                        end
                        if (wdata_r[0]) begin
                            if (launch_enable && !maintenance_busy &&
                                !engine_busy &&
                                (run_format_id == FORMAT_ID) &&
                                (layer_id < 32) &&
                                (query_count == 16) &&
                                (valid_key_count >= 1) &&
                                (valid_key_count <= 128) &&
                                ({1'b0, query_start} + 8'd16 <=
                                    valid_key_count) &&
                                (metadata_loaded || wdata_r[2]) &&
                                (rope_loaded || wdata_r[3]) &&
                                ((input_base & 31) == 0) &&
                                ((output_base & 31) == 0) &&
                                ((weight_c0_base & 1023) == 0) &&
                                ((weight_c1_base & 1023) == 0) &&
                                ((weight_meta_base & 31) == 0) &&
                                ((rope_base & 31) == 0)) begin
                                start_pulse <= 1'b1;
                            end else begin
                                bresp_r <= 2'b10;
                                error_sticky_r <= 1'b1;
                                irq_r <= 1'b1;
                                if (!error_sticky_r)
                                    error_code_r <= 32'h0000_0001;
                            end
                        end
                    end
                end else if (address_is_rw(awaddr_r)) begin
                    case (awaddr_r)
                        12'h010: command_id <= merge_wstrb(command_id,
                            wdata_r, wstrb_r);
                        12'h014: layer_id <= merge_wstrb(layer_id,
                            wdata_r, wstrb_r);
                        12'h018: begin
                            query_start <= query_config_merged[6:0];
                            valid_key_count <= query_config_merged[15:8];
                            query_count <= query_config_merged[23:16];
                        end
                        12'h01c: run_format_id <= merge_wstrb(
                            run_format_id, wdata_r, wstrb_r);
                        12'h020: input_base <= merge_wstrb(input_base,
                            wdata_r, wstrb_r);
                        12'h024: output_base <= merge_wstrb(output_base,
                            wdata_r, wstrb_r);
                        12'h028: weight_c0_base <= merge_wstrb(
                            weight_c0_base, wdata_r, wstrb_r);
                        12'h02c: weight_c1_base <= merge_wstrb(
                            weight_c1_base, wdata_r, wstrb_r);
                        12'h030: weight_meta_base <= merge_wstrb(
                            weight_meta_base, wdata_r, wstrb_r);
                        12'h034: rope_base <= merge_wstrb(rope_base,
                            wdata_r, wstrb_r);
                        12'h070: request_id <= merge_wstrb(request_id,
                            wdata_r, wstrb_r);
                        12'h074: begin
                            cohort_id <= identity_config_merged[15:0];
                            buffer_id <= identity_config_merged[31:16];
                        end
                    endcase
                end else begin
                    bresp_r <= 2'b10;
                end
            end

            if (read_fire) begin
                rvalid_r <= 1'b1;
                rresp_r <= 2'b00;
                case (s_axil_araddr)
                    12'h000: rdata_r <= FORMAT_ID;
                    12'h004: rdata_r <= ABI_VERSION;
                    12'h00c: rdata_r <= {26'd0, irq, rope_loaded,
                        metadata_loaded, error_sticky_r, done_sticky_r,
                        engine_busy};
                    12'h010: rdata_r <= command_id;
                    12'h014: rdata_r <= layer_id;
                    12'h018: rdata_r <= {8'd0, query_count,
                        valid_key_count, 1'b0, query_start};
                    12'h01c: rdata_r <= run_format_id;
                    12'h020: rdata_r <= input_base;
                    12'h024: rdata_r <= output_base;
                    12'h028: rdata_r <= weight_c0_base;
                    12'h02c: rdata_r <= weight_c1_base;
                    12'h030: rdata_r <= weight_meta_base;
                    12'h034: rdata_r <= rope_base;
                    12'h038: rdata_r <= cycle_count;
                    12'h03c: rdata_r <= weight_group_count;
                    12'h040: rdata_r <= projection_tile_count;
                    12'h044: rdata_r <= attention_row_count;
                    12'h048: rdata_r <= wo_tile_count;
                    12'h04c: rdata_r <= error_code_r;
                    12'h050: rdata_r <= input_frontend_cycle_count;
                    12'h054: rdata_r <= qkv_projection_cycle_count;
                    12'h058: rdata_r <= rope_cycle_count;
                    12'h05c: rdata_r <= kv12_cycle_count;
                    12'h060: rdata_r <= attention_cycle_count;
                    12'h064: rdata_r <= context_frontend_cycle_count;
                    12'h068: rdata_r <= wo_projection_cycle_count;
                    12'h06c: rdata_r <= control_overhead_cycle_count;
                    12'h070: rdata_r <= request_id;
                    12'h074: rdata_r <= {buffer_id, cohort_id};
                    12'h078: rdata_r <= completed_request_id_r;
                    12'h07c: rdata_r <= completed_command_id_r;
                    12'h080: rdata_r <= {completed_buffer_id_r,
                        completed_cohort_id_r};
                    12'h084: rdata_r <= {26'd0, completed_layer_id_r};
                    12'h088: rdata_r <= {5'd0, completed_status_r,
                        completed_op_id_r, completed_buffer_id_r};
                    default: begin
                        rdata_r <= 32'd0;
                        rresp_r <= 2'b10;
                    end
                endcase
            end
        end
    end
endmodule
