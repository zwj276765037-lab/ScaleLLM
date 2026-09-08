`timescale 1ns / 1ps

// Complete Q/K/V/Wo meta16 store: 640 tiles x 128 groups x 16 columns.
// Data is only 2.5 MiB and fits comfortably in VU9P URAM; W8 data remains in
// the two external DDR channels.
module hap_weight_meta_resident #(
    parameter integer DEPTH = 81920,
    parameter integer ADDR_W = 17
) (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  clear,
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

    (* ram_style = "ultra" *) reg [255:0] meta_mem [0:DEPTH-1];
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

    always @(posedge clk) begin
        if (wr_fire)
            meta_mem[wr_addr] <= wr_meta16;
        if (rd_fire)
            rsp_meta_r <= meta_mem[rd_addr];
    end

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
            // enable cone entirely inside the SLR2 metadata pblock.
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
