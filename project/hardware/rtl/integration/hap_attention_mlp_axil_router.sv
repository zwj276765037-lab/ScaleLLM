`timescale 1ns / 1ps

// One-outstanding AXI-Lite router for the production Attention+MLP control
// plane.  AW and W are captured independently because AXI-Lite does not
// require them to arrive in the same cycle.  The destination is decoded only
// from the captured AW address and remains fixed through the B response.
// Reads have an independent one-outstanding path.
module hap_attention_mlp_axil_router (
    input  wire         clk,
    input  wire         rst_n,

    input  wire [11:0]  s_awaddr,
    input  wire         s_awvalid,
    output wire         s_awready,
    input  wire [31:0]  s_wdata,
    input  wire [3:0]   s_wstrb,
    input  wire         s_wvalid,
    output wire         s_wready,
    output wire [1:0]   s_bresp,
    output wire         s_bvalid,
    input  wire         s_bready,
    input  wire [11:0]  s_araddr,
    input  wire         s_arvalid,
    output wire         s_arready,
    output wire [31:0]  s_rdata,
    output wire [1:0]   s_rresp,
    output wire         s_rvalid,
    input  wire         s_rready,

    output wire [11:0]  attn_awaddr,
    output wire         attn_awvalid,
    input  wire         attn_awready,
    output wire [31:0]  attn_wdata,
    output wire [3:0]   attn_wstrb,
    output wire         attn_wvalid,
    input  wire         attn_wready,
    input  wire [1:0]   attn_bresp,
    input  wire         attn_bvalid,
    output wire         attn_bready,
    output wire [11:0]  attn_araddr,
    output wire         attn_arvalid,
    input  wire         attn_arready,
    input  wire [31:0]  attn_rdata,
    input  wire [1:0]   attn_rresp,
    input  wire         attn_rvalid,
    output wire         attn_rready,

    output wire [11:0]  mlp_awaddr,
    output wire         mlp_awvalid,
    input  wire         mlp_awready,
    output wire [31:0]  mlp_wdata,
    output wire [3:0]   mlp_wstrb,
    output wire         mlp_wvalid,
    input  wire         mlp_wready,
    input  wire [1:0]   mlp_bresp,
    input  wire         mlp_bvalid,
    output wire         mlp_bready,
    output wire [11:0]  mlp_araddr,
    output wire         mlp_arvalid,
    input  wire         mlp_arready,
    input  wire [31:0]  mlp_rdata,
    input  wire [1:0]   mlp_rresp,
    input  wire         mlp_rvalid,
    output wire         mlp_rready
);
    reg aw_hold_r;
    reg [11:0] awaddr_r;
    reg w_hold_r;
    reg [31:0] wdata_r;
    reg [3:0] wstrb_r;
    reg write_active_r;
    reg write_to_mlp_r;
    reg write_aw_sent_r;
    reg write_w_sent_r;

    reg read_active_r;
    reg read_to_mlp_r;
    reg read_ar_sent_r;
    reg [11:0] araddr_r;

    wire capture_aw = s_awvalid && s_awready;
    wire capture_w = s_wvalid && s_wready;
    wire launch_write = !write_active_r &&
        (aw_hold_r || capture_aw) && (w_hold_r || capture_w);
    wire selected_attn_bvalid = attn_bvalid && !write_to_mlp_r;
    wire selected_mlp_bvalid = mlp_bvalid && write_to_mlp_r;
    wire selected_attn_rvalid = attn_rvalid && !read_to_mlp_r;
    wire selected_mlp_rvalid = mlp_rvalid && read_to_mlp_r;

    assign s_awready = rst_n && !aw_hold_r && !write_active_r;
    assign s_wready = rst_n && !w_hold_r && !write_active_r;
    assign s_bvalid = write_active_r && write_aw_sent_r &&
        write_w_sent_r && (selected_attn_bvalid || selected_mlp_bvalid);
    assign s_bresp = write_to_mlp_r ? mlp_bresp : attn_bresp;

    assign attn_awaddr = awaddr_r;
    assign mlp_awaddr = awaddr_r;
    assign attn_wdata = wdata_r;
    assign mlp_wdata = wdata_r;
    assign attn_wstrb = wstrb_r;
    assign mlp_wstrb = wstrb_r;
    assign attn_awvalid = write_active_r && !write_to_mlp_r &&
        !write_aw_sent_r;
    assign mlp_awvalid = write_active_r && write_to_mlp_r &&
        !write_aw_sent_r;
    assign attn_wvalid = write_active_r && !write_to_mlp_r &&
        !write_w_sent_r;
    assign mlp_wvalid = write_active_r && write_to_mlp_r &&
        !write_w_sent_r;
    assign attn_bready = s_bready && write_active_r &&
        !write_to_mlp_r && write_aw_sent_r && write_w_sent_r;
    assign mlp_bready = s_bready && write_active_r &&
        write_to_mlp_r && write_aw_sent_r && write_w_sent_r;

    assign s_arready = rst_n && !read_active_r;
    assign s_rvalid = read_active_r && read_ar_sent_r &&
        (selected_attn_rvalid || selected_mlp_rvalid);
    assign s_rdata = read_to_mlp_r ? mlp_rdata : attn_rdata;
    assign s_rresp = read_to_mlp_r ? mlp_rresp : attn_rresp;
    assign attn_araddr = araddr_r;
    assign mlp_araddr = araddr_r;
    assign attn_arvalid = read_active_r && !read_to_mlp_r &&
        !read_ar_sent_r;
    assign mlp_arvalid = read_active_r && read_to_mlp_r &&
        !read_ar_sent_r;
    assign attn_rready = s_rready && read_active_r &&
        !read_to_mlp_r && read_ar_sent_r;
    assign mlp_rready = s_rready && read_active_r &&
        read_to_mlp_r && read_ar_sent_r;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            aw_hold_r <= 1'b0;
            awaddr_r <= 12'd0;
            w_hold_r <= 1'b0;
            wdata_r <= 32'd0;
            wstrb_r <= 4'd0;
            write_active_r <= 1'b0;
            write_to_mlp_r <= 1'b0;
            write_aw_sent_r <= 1'b0;
            write_w_sent_r <= 1'b0;
            read_active_r <= 1'b0;
            read_to_mlp_r <= 1'b0;
            read_ar_sent_r <= 1'b0;
            araddr_r <= 12'd0;
        end else begin
            if (capture_aw) begin
                aw_hold_r <= 1'b1;
                awaddr_r <= s_awaddr;
            end
            if (capture_w) begin
                w_hold_r <= 1'b1;
                wdata_r <= s_wdata;
                wstrb_r <= s_wstrb;
            end

            if (launch_write) begin
                write_active_r <= 1'b1;
                write_to_mlp_r <= (capture_aw ? s_awaddr : awaddr_r) >=
                    12'h100;
                awaddr_r <= capture_aw ? s_awaddr : awaddr_r;
                wdata_r <= capture_w ? s_wdata : wdata_r;
                wstrb_r <= capture_w ? s_wstrb : wstrb_r;
                aw_hold_r <= 1'b0;
                w_hold_r <= 1'b0;
                write_aw_sent_r <= 1'b0;
                write_w_sent_r <= 1'b0;
            end else if (write_active_r) begin
                if ((attn_awvalid && attn_awready) ||
                    (mlp_awvalid && mlp_awready))
                    write_aw_sent_r <= 1'b1;
                if ((attn_wvalid && attn_wready) ||
                    (mlp_wvalid && mlp_wready))
                    write_w_sent_r <= 1'b1;
                if (s_bvalid && s_bready) begin
                    write_active_r <= 1'b0;
                    write_aw_sent_r <= 1'b0;
                    write_w_sent_r <= 1'b0;
                end
            end

            if (s_arvalid && s_arready) begin
                read_active_r <= 1'b1;
                read_to_mlp_r <= s_araddr >= 12'h100;
                read_ar_sent_r <= 1'b0;
                araddr_r <= s_araddr;
            end else if (read_active_r) begin
                if ((attn_arvalid && attn_arready) ||
                    (mlp_arvalid && mlp_arready))
                    read_ar_sent_r <= 1'b1;
                if (s_rvalid && s_rready) begin
                    read_active_r <= 1'b0;
                    read_ar_sent_r <= 1'b0;
                end
            end
        end
    end
endmodule
