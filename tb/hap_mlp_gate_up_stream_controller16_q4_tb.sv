`timescale 1ns / 1ps

module hap_mlp_gate_up_stream_controller16_q4_tb;
    localparam integer TILES=4, GROUPS=128, TOTAL=TILES*GROUPS;
    reg clk=1'b0;
    always #3.3335 clk=~clk;
    reg rst_n=1'b0, clear=1'b0, command_valid=1'b0;
    wire command_ready, busy, done, error;
    wire cache_rd_req_valid;
    reg cache_rd_req_ready=1'b0;
    wire cache_rd_req_bank;
    wire [6:0] cache_rd_req_group;
    reg cache_rd_rsp_valid=1'b0;
    wire cache_rd_rsp_ready;
    reg cache_rd_rsp_bank=1'b0;
    reg [6:0] cache_rd_rsp_group=7'd0;
    reg [4095:0] cache_rd_rsp_u8x16x32='0;
    reg [383:0] cache_rd_rsp_meta_u24x16='0;
    wire weight_valid;
    wire weight_ready;
    wire signed [2047:0] weights_s4x16x32;
    wire [223:0] weight_meta_u224;
    wire activation_out_valid;
    reg activation_out_ready=1'b0;
    wire [4095:0] activation_out_u8x16x32;
    wire [383:0] activation_out_meta_u24x16;
    wire [31:0] cache_request_count, weight_group_count;
    wire [31:0] projection_tile_count, product_group_count;
    wire [31:0] activation_group_count, saturation_count;

    reg [4095:0] cache_u8_mem [0:GROUPS-1];
    reg [383:0] cache_meta_mem [0:GROUPS-1];
    reg [2047:0] weights_mem [0:TOTAL-1];
    reg [223:0] weight_meta_mem [0:TOTAL-1];
    reg [4095:0] expected_u8_mem [0:0];
    reg [383:0] expected_meta_mem [0:0];
    integer cycle=0, request_index=0, weight_index=0, output_count=0;
    integer pending_request_count=0;
    reg [6:0] pending_group_mem [0:7];
    integer pending_wr=0, pending_rd=0;
    wire [9:0] weight_source = weight_index<TOTAL ? weight_index:TOTAL-1;

    assign weight_valid = weight_index<TOTAL && (cycle%7 != 2);
    assign weights_s4x16x32 = weights_mem[weight_source];
    assign weight_meta_u224 = weight_meta_mem[weight_source];

    hap_mlp_gate_up_stream_controller16_q4 #(
        .PROJECTION_TILES(TILES), .GROUPS(GROUPS)
    ) dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .command_valid(command_valid), .command_ready(command_ready),
        .activation_bank(1'b0), .activation_bank_ready(1'b1),
        .cache_rd_req_valid(cache_rd_req_valid),
        .cache_rd_req_ready(cache_rd_req_ready),
        .cache_rd_req_bank(cache_rd_req_bank),
        .cache_rd_req_group(cache_rd_req_group),
        .cache_rd_rsp_valid(cache_rd_rsp_valid),
        .cache_rd_rsp_ready(cache_rd_rsp_ready),
        .cache_rd_rsp_bank(cache_rd_rsp_bank),
        .cache_rd_rsp_group(cache_rd_rsp_group),
        .cache_rd_rsp_u8x16x32(cache_rd_rsp_u8x16x32),
        .cache_rd_rsp_meta_u24x16(cache_rd_rsp_meta_u24x16),
        .weight_valid(weight_valid), .weight_ready(weight_ready),
        .weights_s4x16x32(weights_s4x16x32),
        .weight_meta_u224(weight_meta_u224),
        .activation_out_valid(activation_out_valid),
        .activation_out_ready(activation_out_ready),
        .activation_out_u8x16x32(activation_out_u8x16x32),
        .activation_out_meta_u24x16(activation_out_meta_u24x16),
        .busy(busy), .done(done), .error(error),
        .cache_request_count(cache_request_count),
        .weight_group_count(weight_group_count),
        .projection_tile_count(projection_tile_count),
        .product_group_count(product_group_count),
        .activation_group_count(activation_group_count),
        .saturation_count(saturation_count)
    );

    initial begin
        $readmemh("data/mlp_gate_up_stream_controller16_q4/cache_u8x16x32.mem", cache_u8_mem);
        $readmemh("data/mlp_gate_up_stream_controller16_q4/cache_meta_u24x16.mem", cache_meta_mem);
        $readmemh("data/mlp_gate_up_stream_controller16_q4/weights_s4x16x32.mem", weights_mem);
        $readmemh("data/mlp_gate_up_stream_controller16_q4/weight_meta_u224.mem", weight_meta_mem);
        $readmemh("data/mlp_gate_up_stream_controller16_q4/expected_activation_u8x16x32.mem", expected_u8_mem);
        $readmemh("data/mlp_gate_up_stream_controller16_q4/expected_activation_meta_u24x16.mem", expected_meta_mem);
        repeat(8) @(posedge clk);
        rst_n<=1'b1;
        repeat(3) @(posedge clk);
        command_valid<=1'b1;
        do @(posedge clk); while(!command_ready);
        command_valid<=1'b0;
    end

    always @(negedge clk) begin
        cache_rd_req_ready <= rst_n && pending_request_count<8 &&
            (cycle%5 != 1);
        activation_out_ready <= rst_n && cycle%13 != 7;
        if (!(cache_rd_rsp_valid && !cache_rd_rsp_ready)) begin
            if (pending_request_count>0 && cycle%7 != 3) begin
                cache_rd_rsp_valid <= 1'b1;
                cache_rd_rsp_bank <= 1'b0;
                cache_rd_rsp_group <= pending_group_mem[pending_rd];
                cache_rd_rsp_u8x16x32 <=
                    cache_u8_mem[pending_group_mem[pending_rd]];
                cache_rd_rsp_meta_u24x16 <=
                    cache_meta_mem[pending_group_mem[pending_rd]];
            end else begin
                cache_rd_rsp_valid <= 1'b0;
            end
        end
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            cycle<=0; request_index<=0; weight_index<=0; output_count<=0;
            pending_request_count<=0; pending_wr<=0; pending_rd<=0;
        end else begin
            cycle<=cycle+1;
            if (cache_rd_req_valid && cache_rd_req_ready) begin
                if (cache_rd_req_bank!==0 ||
                    cache_rd_req_group!==request_index%GROUPS)
                    $fatal(1,"FAIL cache request index=%0d group=%0d",
                        request_index,cache_rd_req_group);
                pending_group_mem[pending_wr]<=cache_rd_req_group;
                pending_wr<=(pending_wr+1)%8;
                request_index<=request_index+1;
            end
            if (cache_rd_rsp_valid && cache_rd_rsp_ready) begin
                pending_rd<=(pending_rd+1)%8;
            end
            case ({cache_rd_req_valid&&cache_rd_req_ready,
                   cache_rd_rsp_valid&&cache_rd_rsp_ready})
                2'b10: pending_request_count<=pending_request_count+1;
                2'b01: pending_request_count<=pending_request_count-1;
                default: pending_request_count<=pending_request_count;
            endcase
            if (weight_valid&&weight_ready) weight_index<=weight_index+1;
            if (activation_out_valid&&activation_out_ready) begin
                if (activation_out_u8x16x32!==expected_u8_mem[0] ||
                    activation_out_meta_u24x16!==expected_meta_mem[0])
                    $fatal(1,"FAIL down activation mismatch");
                output_count<=output_count+1;
            end
            if (done) begin
                if (request_index!=TOTAL || weight_index!=TOTAL ||
                    output_count!=1 || cache_request_count!=TOTAL ||
                    weight_group_count!=TOTAL || projection_tile_count!=TILES ||
                    product_group_count!=1 || activation_group_count!=1 ||
                    saturation_count!=0 || error)
                    $fatal(1,"FAIL done req=%0d weight=%0d out=%0d counters=%0d/%0d/%0d/%0d/%0d sat=%0d error=%0d",
                        request_index,weight_index,output_count,
                        cache_request_count,weight_group_count,
                        projection_tile_count,product_group_count,
                        activation_group_count,saturation_count,error);
                $display("PASS: hap_mlp_gate_up_stream_controller16_q4 tiles=%0d groups_per_tile=%0d transactions=%0d down_groups=1 cycles=%0d mismatches=0",
                    TILES,GROUPS,TOTAL,cycle);
                $finish;
            end
            if(error) $fatal(1,"FAIL sticky error cycle=%0d",cycle);
            if(cycle>5000) $fatal(1,"FAIL timeout req=%0d weight=%0d projection=%0d product=%0d activation=%0d",
                request_index,weight_index,projection_tile_count,
                product_group_count,activation_group_count);
        end
    end
endmodule
