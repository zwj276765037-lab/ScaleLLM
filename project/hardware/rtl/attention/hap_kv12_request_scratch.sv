`timescale 1ns / 1ps

// One request/layer scratch. RAM has no reset: an exact, validated load seals
// the owner and length, and only that sealed owner can issue reads.
module hap_kv12_request_scratch (
    input wire clk, input wire rst_n, input wire clear,
    input wire begin_valid, output wire begin_ready,
    input wire [31:0] begin_command, input wire [4:0] begin_layer,
    input wire [3:0] begin_slot, input wire [31:0] begin_epoch,
    input wire [7:0] begin_length,

    input wire load_valid, output wire load_ready,
    input wire [31:0] load_command, input wire [4:0] load_layer,
    input wire [3:0] load_slot, input wire [31:0] load_epoch,
    input wire [6:0] load_position, input wire load_is_v,
    input wire [2:0] load_head, input wire [1:0] load_group,
    input wire [383:0] load_s12, input wire [15:0] load_meta,
    input wire load_last, input wire load_error,
    output reg sealed,

    input wire [31:0] read_command, input wire [4:0] read_layer,
    input wire [3:0] read_slot, input wire [31:0] read_epoch,
    input wire k_rd_valid, output wire k_rd_ready,
    input wire [11:0] k_rd_addr,
    output wire k_rsp_valid, input wire k_rsp_ready,
    output wire [383:0] k_rsp_s12, output wire [15:0] k_rsp_meta,
    input wire v_rd_valid, output wire v_rd_ready,
    input wire [11:0] v_rd_addr,
    output wire v_rsp_valid, input wire v_rsp_ready,
    output wire [383:0] v_rsp_s12, output wire [15:0] v_rsp_meta,
    output reg [13:0] loaded_count,
    output reg error
);
    (* ram_style = "block" *) reg [399:0] k_mem [0:4095];
    (* ram_style = "block" *) reg [399:0] v_mem [0:4095];
    reg [399:0] k_response, v_response;
    reg k_pending, v_pending, loading;
    reg [31:0] command_r, epoch_r;
    reg [4:0] layer_r;
    reg [3:0] slot_r;
    reg [7:0] length_r;

    wire enabled = rst_n && !clear && !error;
    wire begin_fire = begin_valid && begin_ready;
    assign begin_ready = enabled && !loading && !k_pending && !v_pending;
    assign load_ready = enabled && loading;
    wire load_fire = load_valid && load_ready;
    wire owner_ok = read_command == command_r && read_layer == layer_r &&
        read_slot == slot_r && read_epoch == epoch_r;
    wire k_read_ok = sealed && owner_ok && {1'b0,k_rd_addr[8:2]} < length_r;
    wire v_read_ok = sealed && owner_ok && {1'b0,v_rd_addr[8:2]} < length_r;
    assign k_rd_ready = enabled && !begin_valid && k_read_ok && (!k_pending || k_rsp_ready);
    assign v_rd_ready = enabled && !begin_valid && v_read_ok && (!v_pending || v_rsp_ready);
    assign k_rsp_valid = enabled && k_pending;
    assign v_rsp_valid = enabled && v_pending;
    assign k_rsp_s12 = k_response[383:0];
    assign k_rsp_meta = k_response[399:384];
    assign v_rsp_s12 = v_response[383:0];
    assign v_rsp_meta = v_response[399:384];
    wire k_read_fire = k_rd_valid && k_rd_ready;
    wire v_read_fire = v_rd_valid && v_rd_ready;

    function automatic format_bad;
        input [383:0] samples; input [15:0] meta;
        integer lane; reg bad;
        begin
            bad = meta[15:14] != 0 || (meta[7:0] == 0 && meta[13:8] != 0) ||
                (meta[7:0] != 0 && (meta[13:8] < 8 || meta[13:8] > 32));
            for (lane=0; lane<32; lane=lane+1) begin
                if (samples[lane*12 +: 12] == 12'h800) bad=1;
                if (meta[7:0] == 0 && samples[lane*12 +: 12] != 0) bad=1;
            end
            format_bad=bad;
        end
    endfunction
    wire expected_last = loaded_count + 14'd1 == {length_r,6'd0};
    wire load_bad = load_error || load_command != command_r || load_layer != layer_r ||
        load_slot != slot_r || load_epoch != epoch_r ||
        load_position != loaded_count[12:6] || load_is_v != loaded_count[5] ||
        load_head != loaded_count[4:2] || load_group != loaded_count[1:0] ||
        load_last != expected_last || format_bad(load_s12,load_meta);
    wire [11:0] load_address = {load_head,load_position,load_group};
    // Keep synchronous RAM read/write paths free of asynchronous reset.
    always @(posedge clk) begin
        if (load_fire && !load_bad) begin
            if (load_is_v) v_mem[load_address] <= {load_meta,load_s12};
            else k_mem[load_address] <= {load_meta,load_s12};
        end
        if (k_read_fire) k_response <= k_mem[k_rd_addr];
        if (v_read_fire) v_response <= v_mem[v_rd_addr];
    end
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sealed<=0; loading<=0; k_pending<=0; v_pending<=0; error<=0;
            loaded_count<=0; command_r<=0; epoch_r<=0; layer_r<=0; slot_r<=0; length_r<=0;
        end else if (clear) begin
            sealed<=0; loading<=0; k_pending<=0; v_pending<=0; error<=0;
            loaded_count<=0; command_r<=0; epoch_r<=0; layer_r<=0; slot_r<=0; length_r<=0;
        end else begin
            if (k_rsp_valid && k_rsp_ready) k_pending<=0;
            if (v_rsp_valid && v_rsp_ready) v_pending<=0;
            if (k_read_fire) k_pending<=1;
            if (v_read_fire) v_pending<=1;
            if (begin_fire) begin
                sealed<=0; loaded_count<=0;
                command_r<=begin_command; layer_r<=begin_layer; slot_r<=begin_slot;
                epoch_r<=begin_epoch; length_r<=begin_length;
                if (begin_epoch == 0 || begin_length == 0 || begin_length > 128) begin
                    error<=1; loading<=0;
                end else loading<=1;
            end
            if (load_fire) begin
                if (load_bad) begin error<=1; sealed<=0; loading<=0; end
                else begin
                    loaded_count<=loaded_count+14'd1;
                    if (expected_last) begin loading<=0; sealed<=1; end
                end
            end
            if ((k_rd_valid && (!k_read_ok || begin_valid)) ||
                (v_rd_valid && (!v_read_ok || begin_valid))) begin
                error<=1; sealed<=0; k_pending<=0; v_pending<=0;
            end
            // A late record after the exact final record is a protocol error.
            if (load_valid && !loading) begin error<=1; sealed<=0; end
        end
    end
endmodule
