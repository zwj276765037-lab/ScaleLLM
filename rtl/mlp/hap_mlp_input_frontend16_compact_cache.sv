`timescale 1ns / 1ps

// Resource-compact cohort16 MLP input frontend.  One Hadamard32 pipeline and
// four robust A8 quantizers are time-multiplexed across all 16 requests.  The
// resulting bundle is committed atomically into two independent eight-row
// ping-pong caches.  This path runs while the other bank is consumed, so input
// latency is traded for the LUT/DSP headroom needed by the full board.
module hap_mlp_input_frontend16_compact_cache (
    input  wire                          clk,
    input  wire                          rst_n,
    input  wire                          clear,
    input  wire                          in_valid,
    output wire                          in_ready,
    input  wire                          in_bank,
    input  wire [6:0]                    in_group,
    input  wire [16*32*24-1:0]           in_s24x16x32,

    input  wire                          rd_req_valid,
    output wire                          rd_req_ready,
    input  wire                          rd_req_bank,
    input  wire [6:0]                    rd_req_group,
    output wire                          rd_rsp_valid,
    input  wire                          rd_rsp_ready,
    output wire                          rd_rsp_bank,
    output wire [6:0]                    rd_rsp_group,
    output wire [16*32*8-1:0]            rd_rsp_u8x16x32,
    output wire [16*24-1:0]              rd_rsp_meta_u24x16,

    input  wire                          release_valid,
    output wire                          release_ready,
    input  wire                          release_bank,
    output wire [1:0]                    bank_ready,
    output reg  [31:0]                   input_group_count,
    output reg  [31:0]                   read_group_count,
    output reg  [31:0]                   release_count,
    output wire [31:0]                   hadamard_saturation_count,
    output reg                           error
);

    reg active_r;
    reg bundle_valid_r;
    reg active_bank_r;
    reg [6:0] active_group_r;
    // The complete S24 transaction is retained while the folded Hadamard
    // visits its sixteen rows.  Keep the same 12288 payload FFs, but give each
    // physical row its own protected capture predicate.  A single in_fire CE
    // previously reached all payload bits and Vivado promoted that data net to
    // a BUFGCE (12373 non-clock loads in Run 0147).
    reg [32*24-1:0] input_buffer_row_r [0:15];
    // Net protection is required here: post-place phys_opt preserved the LUT1
    // cells but reconnected their equivalent outputs into six device-wide CE
    // trees.  Three independent 256-bit domains per row keep every protected
    // CE below the data-BUFG promotion threshold.
    (* DONT_TOUCH = "yes", KEEP = "yes" *)
    wire [47:0] input_capture_enable;
    reg [4:0] source_row_r;
    reg [4:0] dispatch_row_r;
    reg [2:0] quant_output_wave_r[0:3];
    reg [5:0] completed_row_count_r;
    // Keep completed rows in their final physical banks.  The previous
    // variable part-select on one 4096-bit register caused Vivado to build
    // multi-thousand-load write predicates (three data BUFG candidates in
    // the first V5 place).  Sixteen explicit row banks make each payload
    // write local; payload storage is intentionally not cleared because all
    // sixteen rows are overwritten before bundle_valid_r may be asserted.
    reg [32*8-1:0] bundle_u8_bank_r [0:15];
    reg [23:0] bundle_meta_bank_r [0:15];
    wire [16*32*8-1:0] bundle_u8;
    wire [16*24-1:0] bundle_meta;
    wire [15:0] row_write_fire;
    (* DONT_TOUCH = "yes", KEEP = "yes" *)
    wire [15:0] row_u8_write_enable;
    (* DONT_TOUCH = "yes", KEEP = "yes" *)
    wire [15:0] row_meta_write_enable;

    wire hadamard_in_valid = active_r && source_row_r < 16;
    wire hadamard_in_ready;
    wire hadamard_in_fire = hadamard_in_valid && hadamard_in_ready;
    wire hadamard_out_valid, hadamard_out_ready;
    wire [32*27-1:0] hadamard_out_s27;
    wire hadamard_error;
    wire [31:0] hadamard_input_unused, hadamard_output_unused;

    wire [3:0] quant_in_ready;
    wire [3:0] quant_out_valid;
    wire [3:0] quant_out_ready;
    wire [4*32*8-1:0] quant_out_u8;
    wire [4*24-1:0] quant_out_meta;
    wire [3:0] quant_error;
    // Quantizers 0/1 own rows 0..7 and quantizers 2/3 own rows 8..15.
    // This preserves four-way issue bandwidth while making each completed
    // row half physically local to its corresponding eight-row cache.
    wire [1:0] dispatch_quantizer =
        {dispatch_row_r[3], dispatch_row_r[0]};
    wire hadamard_out_fire = hadamard_out_valid && hadamard_out_ready;
    wire [3:0] quant_out_fire = quant_out_valid & quant_out_ready;
    wire [2:0] quant_fire_count =
        {2'd0,quant_out_fire[0]} + {2'd0,quant_out_fire[1]} +
        {2'd0,quant_out_fire[2]} + {2'd0,quant_out_fire[3]};

    wire half0_wr_ready, half1_wr_ready;
    wire [1:0] half0_bank_ready, half1_bank_ready;
    wire half0_rd_req_ready, half1_rd_req_ready;
    wire half0_rsp_valid, half1_rsp_valid;
    wire half0_rsp_bank, half1_rsp_bank;
    wire [6:0] half0_rsp_group, half1_rsp_group;
    wire [8*32*8-1:0] half0_rsp_u8, half1_rsp_u8;
    wire [8*24-1:0] half0_rsp_meta, half1_rsp_meta;
    wire half0_release_ready, half1_release_ready;
    wire half0_error, half1_error;
    wire cache_write_fire = bundle_valid_r && half0_wr_ready &&
        half1_wr_ready;
    wire release_fire = release_valid && release_ready;
    wire response_fire = rd_rsp_valid && rd_rsp_ready;
    wire in_fire = in_valid && in_ready;

    assign in_ready = rst_n && !clear && !active_r && !bundle_valid_r;
    assign hadamard_out_ready = quant_in_ready[dispatch_quantizer];
    assign rd_req_ready = rst_n && !clear && half0_rd_req_ready &&
        half1_rd_req_ready;
    assign rd_rsp_valid = rst_n && !clear && half0_rsp_valid &&
        half1_rsp_valid;
    assign rd_rsp_bank = half0_rsp_bank;
    assign rd_rsp_group = half0_rsp_group;
    assign rd_rsp_u8x16x32[0+:8*32*8] = half0_rsp_u8;
    assign rd_rsp_u8x16x32[8*32*8+:8*32*8] = half1_rsp_u8;
    assign rd_rsp_meta_u24x16[0+:8*24] = half0_rsp_meta;
    assign rd_rsp_meta_u24x16[8*24+:8*24] = half1_rsp_meta;
    assign release_ready = rst_n && !clear && half0_release_ready &&
        half1_release_ready;
    assign bank_ready = half0_bank_ready & half1_bank_ready;

    // Both cache halves begin from identical state and receive identical tags.
    // Present each transaction locally so no half-ready/half-valid signal must
    // cross an SLR to qualify the other half.  The public ready/valid join and
    // sticky mismatch checks below retain the atomic lockstep contract.

    genvar row_bank;
    generate for(row_bank=0;row_bank<16;row_bank=row_bank+1)begin:g_bundle_row
        localparam integer ROW_QUANTIZER =
            ((row_bank / 8) * 2) + (row_bank % 2);
        localparam integer ROW_WAVE = (row_bank % 8) / 2;
        assign row_write_fire[row_bank] =
            quant_out_fire[ROW_QUANTIZER] &&
            quant_output_wave_r[ROW_QUANTIZER] == ROW_WAVE;
        // Separate protected leaves keep the 256-bit payload and 24-bit
        // metadata controls local even if synthesis sees identical logic.
        (* DONT_TOUCH = "yes", KEEP = "yes" *) LUT1 #(.INIT(2'h2))
        u_row_u8_write_enable (
            .I0(row_write_fire[row_bank]),
            .O(row_u8_write_enable[row_bank])
        );
        (* DONT_TOUCH = "yes", KEEP = "yes" *) LUT1 #(.INIT(2'h2))
        u_row_meta_write_enable (
            .I0(row_write_fire[row_bank]),
            .O(row_meta_write_enable[row_bank])
        );
        assign bundle_u8[row_bank*32*8+:32*8] =
            bundle_u8_bank_r[row_bank];
        assign bundle_meta[row_bank*24+:24] =
            bundle_meta_bank_r[row_bank];

    end endgenerate

    genvar capture_domain;
    generate for(capture_domain=0;capture_domain<48;
                 capture_domain=capture_domain+1)begin:g_input_capture
        // These leaves are transaction-local CE endpoints.  Both the cells and
        // their output nets are protected so implementation cannot merge the
        // 48 equivalent controls back into a global tree.
        (* DONT_TOUCH = "yes", KEEP = "yes" *) LUT1 #(.INIT(2'h2))
        u_input_capture_enable (
            .I0(in_fire),
            .O(input_capture_enable[capture_domain])
        );
    end endgenerate

    hap_mlp_hadamard32_s24_fold4 u_hadamard (
        .clk(clk),.rst_n(rst_n),.clear(clear),
        .in_valid(hadamard_in_valid),.in_ready(hadamard_in_ready),
        .in_s24(input_buffer_row_r[source_row_r]),
        .out_valid(hadamard_out_valid),.out_ready(hadamard_out_ready),
        .out_s27(hadamard_out_s27),
        .input_group_count(hadamard_input_unused),
        .output_group_count(hadamard_output_unused),
        .saturation_count(hadamard_saturation_count),.error(hadamard_error)
    );

    genvar quantizer;
    generate for(quantizer=0;quantizer<4;quantizer=quantizer+1)begin:g_quant
        hap_robust_a8_quantizer u_quantizer (
            .clk(clk),.rst_n(rst_n),.clear(clear),
            .in_valid(hadamard_out_valid &&
                dispatch_quantizer==quantizer[1:0]),
            .in_ready(quant_in_ready[quantizer]),.in_s27(hadamard_out_s27),
            .out_valid(quant_out_valid[quantizer]),
            .out_ready(quant_out_ready[quantizer]),
            .out_u8(quant_out_u8[quantizer*32*8+:32*8]),
            .out_meta(quant_out_meta[quantizer*24+:24]),
            .input_group_count(),.output_group_count(),.cycle_count(),
            .error(quant_error[quantizer])
        );
        assign quant_out_ready[quantizer] = active_r &&
            quant_output_wave_r[quantizer] < 4;
    end endgenerate

    hap_activation_cache_8row u_cache0 (
        .clk(clk),.rst_n(rst_n),.clear(clear),
        .wr_valid(bundle_valid_r),.wr_ready(half0_wr_ready),
        .wr_bank(active_bank_r),.wr_group(active_group_r),
        .wr_u8(bundle_u8[0+:8*32*8]),
        .wr_meta(bundle_meta[0+:8*24]),
        .rd_req_valid(rd_req_valid),
        .rd_req_ready(half0_rd_req_ready),.rd_req_bank(rd_req_bank),
        .rd_req_group(rd_req_group),.rd_rsp_valid(half0_rsp_valid),
        .rd_rsp_ready(rd_rsp_ready),.rd_rsp_bank(half0_rsp_bank),
        .rd_rsp_group(half0_rsp_group),.rd_rsp_u8(half0_rsp_u8),
        .rd_rsp_meta(half0_rsp_meta),
        .release_valid(release_valid),.release_ready(half0_release_ready),
        .release_bank(release_bank),.bank_ready(half0_bank_ready),
        .write_count(),.read_count(),.release_count(),.error(half0_error)
    );

    hap_activation_cache_8row u_cache1 (
        .clk(clk),.rst_n(rst_n),.clear(clear),
        .wr_valid(bundle_valid_r),.wr_ready(half1_wr_ready),
        .wr_bank(active_bank_r),.wr_group(active_group_r),
        .wr_u8(bundle_u8[8*32*8+:8*32*8]),
        .wr_meta(bundle_meta[8*24+:8*24]),
        .rd_req_valid(rd_req_valid),
        .rd_req_ready(half1_rd_req_ready),.rd_req_bank(rd_req_bank),
        .rd_req_group(rd_req_group),.rd_rsp_valid(half1_rsp_valid),
        .rd_rsp_ready(rd_rsp_ready),.rd_rsp_bank(half1_rsp_bank),
        .rd_rsp_group(half1_rsp_group),.rd_rsp_u8(half1_rsp_u8),
        .rd_rsp_meta(half1_rsp_meta),
        .release_valid(release_valid),.release_ready(half1_release_ready),
        .release_bank(release_bank),.bank_ready(half1_bank_ready),
        .write_count(),.read_count(),.release_count(),.error(half1_error)
    );

    integer q;
    integer row;
    integer capture_chunk;
    always @(posedge clk) begin
        if(!rst_n||clear)begin
            active_r<=0;bundle_valid_r<=0;source_row_r<='0;
            dispatch_row_r<='0;completed_row_count_r<='0;
            input_group_count<=0;read_group_count<=0;release_count<=0;
            error<=0;
            for(q=0;q<4;q=q+1)quant_output_wave_r[q]<='0;
        end else begin
            if(in_fire)begin
                active_r<=1;active_bank_r<=in_bank;active_group_r<=in_group;
                source_row_r<='0;
                dispatch_row_r<='0;completed_row_count_r<='0;
                input_group_count<=input_group_count+1;
                for(q=0;q<4;q=q+1)quant_output_wave_r[q]<='0;
            end
            for(row=0;row<16;row=row+1)
                for(capture_chunk=0;capture_chunk<3;
                    capture_chunk=capture_chunk+1)
                    if(input_capture_enable[row*3+capture_chunk])
                        input_buffer_row_r[row][capture_chunk*256+:256] <=
                            in_s24x16x32[row*32*24+
                                capture_chunk*256+:256];
            if(hadamard_in_fire)source_row_r<=source_row_r+1'b1;
            if(hadamard_out_fire)dispatch_row_r<=dispatch_row_r+1'b1;
            for(row=0;row<16;row=row+1)begin
                if(row_u8_write_enable[row])
                    bundle_u8_bank_r[row] <=
                        quant_out_u8[
                            (((row/8)*2)+(row%2))*32*8+:32*8];
                if(row_meta_write_enable[row])
                    bundle_meta_bank_r[row] <=
                        quant_out_meta[
                            (((row/8)*2)+(row%2))*24+:24];
            end
            for(q=0;q<4;q=q+1)if(quant_out_fire[q])begin
                quant_output_wave_r[q]<=quant_output_wave_r[q]+1'b1;
            end
            if(quant_fire_count!=0)begin
                completed_row_count_r<=completed_row_count_r+quant_fire_count;
                if(completed_row_count_r+quant_fire_count==16)
                    bundle_valid_r<=1;
            end
            if(cache_write_fire)begin
                bundle_valid_r<=0;active_r<=0;
            end
            if(response_fire)read_group_count<=read_group_count+1;
            if(release_fire)release_count<=release_count+1;
            if(hadamard_error||(|quant_error)||half0_error||half1_error||
               source_row_r>16||dispatch_row_r>16||
               completed_row_count_r>16||
               (bundle_valid_r&&(half0_wr_ready!=half1_wr_ready))||
               (rd_req_valid&&(half0_rd_req_ready!=half1_rd_req_ready))||
               (half0_rsp_valid!=half1_rsp_valid)||
               (release_valid&&
                (half0_release_ready!=half1_release_ready))||
               (half0_bank_ready!=half1_bank_ready)||
               (half0_rsp_valid&&half1_rsp_valid&&
                (half0_rsp_bank!=half1_rsp_bank||
                 half0_rsp_group!=half1_rsp_group)))error<=1;
        end
    end
endmodule
