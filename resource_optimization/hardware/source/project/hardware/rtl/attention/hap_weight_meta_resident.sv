`timescale 1ns / 1ps

// Complete Q/K/V/Wo meta16 store: 640 tiles x 128 groups x 16 columns.
// Data is only 2.5 MiB and fits comfortably in VU9P URAM; W8 data remains in
// the two external DDR channels.
module hap_weight_meta_resident #(
    parameter integer DEPTH = 81920,
    parameter integer ADDR_W = 17,
    parameter integer LOCAL_ADDR_COPIES = 0
) (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  clear,
    input  wire                  addr_system_clear,
    input  wire                  addr_launch,
    input  wire                  wr_valid,
    output wire                  wr_ready,
    input  wire [ADDR_W-1:0]     wr_addr,
    input  wire [255:0]          wr_meta16,
    input  wire                  rd_valid,
    output wire                  rd_ready,
    input  wire [ADDR_W-1:0]     rd_addr,
    output wire                  rsp_valid,
    input  wire                  rsp_ready,
    output wire [255:0]          rsp_meta16,
    output reg  [31:0]           write_count,
    output reg  [31:0]           read_count,
    output reg  [31:0]           format_error_count,
    output reg                   error
);

    reg [255:0] rsp_meta_r;
    reg rsp_valid_r;
    // This register is the bank-local copy consumed by every URAM cascade
    // enable.  It intentionally does not include rsp_ready or any projection
    // state; the board controller's one-pending contract makes that remote
    // dependency unnecessary.
    (* DONT_TOUCH = "yes" *) reg rd_port_open_r;
    wire wr_fire = wr_valid && wr_ready;
    wire rd_fire = rd_valid && rd_ready;
    wire rsp_fire = rsp_valid && rsp_ready;

    assign wr_ready = rst_n && !clear && (wr_addr < DEPTH);
    // Deliberately make the URAM request port non-fall-through.  The board
    // controller permits only one metadata request to be pending, therefore
    // accepting a replacement read in the same cycle as rsp_ready cannot
    // improve the architectural issue rate.  Allowing that fall-through did,
    // however, put the remote projection/DDR-join ready cone directly on the
    // enable of the complete 80-URAM cascade.  Keeping rd_ready dependent only
    // on this local registered token creates a real timing boundary at the
    // metadata bank without changing data, ordering, or command latency.
    assign rd_ready = rst_n && !clear && rd_port_open_r &&
        (rd_addr < DEPTH);
    assign rsp_valid = rst_n && !clear && rsp_valid_r;
    assign rsp_meta16 = rsp_meta_r;

    function automatic meta_has_format_error;
        input [255:0] value;
        integer column;
        reg invalid;
        reg [7:0] code;
        reg [5:0] shift;
        begin
            invalid = 1'b0;
            for (column = 0; column < 16; column = column + 1) begin
                code = value[column*16 +: 8];
                shift = value[column*16+8 +: 6];
                if ((value[column*16+14 +: 2] != 0) ||
                    ((code == 0) && (shift != 0)))
                    invalid = 1'b1;
            end
            meta_has_format_error = invalid;
        end
    endfunction

    generate
        if (LOCAL_ADDR_COPIES == 1) begin : g_m003_width_slices
            for (genvar slice_index = 0; slice_index < 2; slice_index = slice_index + 1) begin : g_slice
                wire [ADDR_W-1:0] local_rd_addr;
                (* keep_hierarchy = "yes" *)
                hap_weight_meta_read_addr_copy #(.ADDR_W(ADDR_W)) u_addr (
                    .clk(clk), .rst_n(rst_n),
                    .system_clear(addr_system_clear), .launch(addr_launch),
                    .rsp_fire(rsp_fire), .addr(local_rd_addr)
                );
                (* ram_style = "ultra" *) reg [127:0] meta_mem [0:DEPTH-1];
                always @(posedge clk) begin
                    if (wr_fire)
                        meta_mem[wr_addr] <= wr_meta16[slice_index*128 +: 128];
                    if (rd_fire)
                        rsp_meta_r[slice_index*128 +: 128] <= meta_mem[local_rd_addr];
                end
            end
        end else begin : g_original_store
            (* ram_style = "ultra" *) reg [255:0] meta_mem [0:DEPTH-1];
            always @(posedge clk) begin
                if (wr_fire)
                    meta_mem[wr_addr] <= wr_meta16;
                if (rd_fire)
                    rsp_meta_r <= meta_mem[rd_addr];
            end
        end
    endgenerate

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rsp_valid_r <= 1'b0;
            rd_port_open_r <= 1'b1;
            write_count <= 32'd0;
            read_count <= 32'd0;
            format_error_count <= 32'd0;
            error <= 1'b0;
        end else if (clear) begin
            rsp_valid_r <= 1'b0;
            rd_port_open_r <= 1'b1;
            write_count <= 32'd0;
            read_count <= 32'd0;
            format_error_count <= 32'd0;
            error <= 1'b0;
        end else begin
            // Registered occupancy token.  It changes only after a locally
            // observed request/response event and therefore keeps the URAM
            // enable cone entirely inside the metadata bank.
            if (rd_fire)
                rd_port_open_r <= 1'b0;
            else if (rsp_fire)
                rd_port_open_r <= 1'b1;
            if (rsp_fire)
                rsp_valid_r <= 1'b0;
            if (rd_fire)
                rsp_valid_r <= 1'b1;
            if (wr_fire) begin
                write_count <= write_count + 32'd1;
                if (meta_has_format_error(wr_meta16)) begin
                    format_error_count <= format_error_count + 32'd1;
                    error <= 1'b1;
                end
            end
            if (rsp_fire)
                read_count <= read_count + 32'd1;
            if ((wr_valid && (wr_addr >= DEPTH)) ||
                (rd_valid && (rd_addr >= DEPTH)))
                error <= 1'b1;
        end
    end

    initial begin
        if (DEPTH != 81920 || ADDR_W != 17)
            $error("hap_weight_meta_resident production shape must be 81920x256");
    end

endmodule


// M003 C-A3: independent same-edge memory-side address state.
// Only the address FF and the two local control LUTs are protected.
// system_clear intentionally excludes abort-only datapath_clear.
module hap_weight_meta_read_addr_copy #(
    parameter integer ADDR_W = 17
) (
    input wire clk,
    input wire rst_n,
    input wire system_clear,
    input wire launch,
    input wire rsp_fire,
    output wire [ADDR_W-1:0] addr
);
    (* KEEP = "yes" *) wire local_ce;
    (* KEEP = "yes" *) wire local_increment;
    (* DONT_TOUCH = "yes" *)
    LUT3 #(.INIT(8'hfe)) u_local_ce (
        .I0(system_clear), .I1(launch), .I2(rsp_fire), .O(local_ce)
    );
    (* DONT_TOUCH = "yes" *)
    LUT2 #(.INIT(4'h2)) u_local_increment (
        .I0(rsp_fire), .I1(system_clear), .O(local_increment)
    );
    (* DONT_TOUCH = "yes", KEEP = "yes", SHREG_EXTRACT = "NO" *)
    reg [ADDR_W-1:0] address_r;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            address_r <= {ADDR_W{1'b0}};
        else if (local_ce)
            address_r <= local_increment ? address_r + 1'b1 : {ADDR_W{1'b0}};
    end
    assign addr = address_r;
endmodule
