`timescale 1ns / 1ps

module hap_mlp_down_activation_row_bank #(
    parameter integer GROUPS=448,
    parameter integer GROUP_W=(GROUPS<=2)?1:$clog2(GROUPS)
) (
    input wire clk,input wire write_enable,
    input wire [GROUP_W-1:0] write_address,input wire [279:0] write_data,
    input wire read_enable,input wire [GROUP_W-1:0] read_address,
    output reg [279:0] read_data
);
    (* ram_style="block" *)reg [279:0] memory[0:GROUPS-1];
    always @(posedge clk) begin
        if(write_enable)memory[write_address]<=write_data;
        if(read_enable)read_data<=memory[read_address];
    end
endmodule

// Phase-decoupling cache between gate/up and down.  The first full MLP
// implementation serializes the two DDR readers, therefore every product
// activation group must be retained until the gate/up reader (including its
// CDC FIFOs and statistics snapshot) has drained.  Sixteen independent
// 280-bit row memories keep the write/read ports local and infer block RAM
// instead of one physically impractical 4480-bit-wide memory.
module hap_mlp_down_activation_cache16 #(
    parameter integer GROUPS = 448,
    parameter integer GROUP_W = (GROUPS <= 2) ? 1 : $clog2(GROUPS)
) (
    input  wire                         clk,
    input  wire                         rst_n,
    input  wire                         clear,
    input  wire                         in_valid,
    output wire                         in_ready,
    input  wire [16*32*8-1:0]           in_u8x16x32,
    input  wire [16*24-1:0]             in_meta_u24x16,
    input  wire                         replay_enable,
    output wire                         out_valid,
    input  wire                         out_ready,
    output wire [16*32*8-1:0]           out_u8x16x32,
    output wire [16*24-1:0]             out_meta_u24x16,
    output wire                         full,
    output reg  [31:0]                  write_group_count,
    output reg  [31:0]                  read_group_count,
    output reg                          error
);

    wire [279:0] row_read_data[0:15];
    reg [GROUP_W-1:0] write_ptr_r;
    reg [GROUP_W-1:0] read_ptr_r;
    reg read_pending_r;
    reg [31:0] issued_group_count_r;
    reg output_valid_r;
    reg [16*32*8-1:0] output_u8_r;
    reg [16*24-1:0] output_meta_r;
    // One registered pending bit per row terminates the former global output
    // capture predicate.  All replicas are cycle aligned with read_pending_r:
    // the BRAM read is issued in cycle N and each row's 280-bit holding bank
    // captures in cycle N+1.  Bit-exact latency and output backpressure are
    // unchanged, while no predicate owns more than one 280-bit row.
    (* DONT_TOUCH = "yes" *) reg [15:0] output_capture_pending_bank_r;

    wire write_fire = in_valid && in_ready;
    wire output_fire = out_valid && out_ready;
    wire output_slot_available = !output_valid_r || out_ready;
    wire issue_read = replay_enable && !read_pending_r &&
        output_slot_available && issued_group_count_r < write_group_count;

    assign in_ready = rst_n && !clear && write_group_count < GROUPS;
    assign out_valid = rst_n && !clear && output_valid_r;
    assign out_u8x16x32 = output_u8_r;
    assign out_meta_u24x16 = output_meta_r;
    assign full = write_group_count == GROUPS;

    genvar bank_row;
    generate for(bank_row=0;bank_row<16;bank_row=bank_row+1)begin:gen_bank
        hap_mlp_down_activation_row_bank #(
            .GROUPS(GROUPS),.GROUP_W(GROUP_W))u_bank(
            .clk(clk),.write_enable(write_fire),.write_address(write_ptr_r),
            .write_data({in_meta_u24x16[bank_row*24+:24],
                in_u8x16x32[bank_row*32*8+:32*8]}),
            .read_enable(issue_read),.read_address(read_ptr_r),
            .read_data(row_read_data[bank_row]));
    end endgenerate

    integer row;
    always @(posedge clk) begin
        if (!rst_n || clear) begin
            write_ptr_r <= '0;
            read_ptr_r <= '0;
            read_pending_r <= 1'b0;
            output_capture_pending_bank_r <= 16'd0;
            issued_group_count_r <= 32'd0;
            output_valid_r <= 1'b0;
            write_group_count <= 32'd0;
            read_group_count <= 32'd0;
            error <= 1'b0;
        end else begin
            output_capture_pending_bank_r <= {16{issue_read}};
            if (write_fire) begin
                write_group_count <= write_group_count + 32'd1;
                if (write_ptr_r != GROUPS-1)
                    write_ptr_r <= write_ptr_r + 1'b1;
            end

            if (output_fire) begin
                output_valid_r <= 1'b0;
                read_group_count <= read_group_count + 32'd1;
            end

            // Bank data returns one cycle after issue and is then captured in
            // the output holding register.
            for (row = 0; row < 16; row = row + 1) begin
                if (output_capture_pending_bank_r[row]) begin
                    output_u8_r[row*32*8 +: 32*8] <=
                        row_read_data[row][255:0];
                    output_meta_r[row*24 +: 24] <=
                        row_read_data[row][279:256];
                end
            end
            if (read_pending_r) begin
                output_valid_r <= 1'b1;
                read_pending_r <= 1'b0;
            end
            if (issue_read) begin
                read_pending_r <= 1'b1;
                issued_group_count_r <= issued_group_count_r + 32'd1;
                if (read_ptr_r != GROUPS-1)
                    read_ptr_r <= read_ptr_r + 1'b1;
            end

            if (write_group_count > GROUPS ||
                read_group_count > write_group_count ||
                issued_group_count_r > write_group_count ||
                (replay_enable && read_group_count == GROUPS &&
                 (read_pending_r || output_valid_r)))
                error <= 1'b1;
        end
    end

    initial begin
        if (GROUPS <= 0)
            $error("down activation cache GROUPS must be positive");
    end

`ifndef SYNTHESIS
    always @(posedge clk) begin
        if (rst_n && !clear &&
            output_capture_pending_bank_r !=
            {16{output_capture_pending_bank_r[0]}})
            $error("down activation output capture banks diverged");
    end
`endif

endmodule
