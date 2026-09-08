`timescale 1ns / 1ps

module hap_mlp_full_command16_s45_tb;
    localparam integer GATE_TILES=4, HIDDEN_GROUPS=128;
    localparam integer GATE_TX=GATE_TILES*HIDDEN_GROUPS;
    localparam integer DOWN_GROUPS=1, DOWN_TILES=8;
    localparam integer DOWN_TX=DOWN_GROUPS*DOWN_TILES;
    localparam integer TOTAL_TX=GATE_TX+DOWN_TX;
    localparam integer TOTAL_BEATS=TOTAL_TX*2;

    reg core_clk=0, ddr0_clk=0, ddr1_clk=0;
    always #3.3335 core_clk=~core_clk;
    always #1.6665 ddr0_clk=~ddr0_clk;
    always #1.6675 ddr1_clk=~ddr1_clk;
    reg core_rst_n=0, ddr0_rst_n=0, ddr1_rst_n=0;
    reg core_clear=0;

    reg input_valid=0,input_bank=0;
    wire input_ready;
    reg [6:0] input_group=0;
    reg [12287:0] input_s24='0;
    wire [1:0] input_bank_ready;
    reg command_valid=0;
    wire command_ready,busy,done,error;
    wire [2:0] phase;

    wire gate_meta_ready,down_meta_ready;
    wire gate_meta_valid,down_meta_valid;
    wire [223:0] gate_meta,down_meta;
    wire d0_arvalid,d0_rready;
    reg d0_arready=0,d0_rvalid=0,d0_rlast=0;
    wire [31:0] d0_araddr; wire [7:0] d0_arlen;
    wire [2:0] d0_arsize; wire [1:0] d0_arburst;
    reg [511:0] d0_rdata='0;
    wire d1_arvalid,d1_rready;
    reg d1_arready=0,d1_rvalid=0,d1_rlast=0;
    wire [31:0] d1_araddr; wire [7:0] d1_arlen;
    wire [2:0] d1_arsize; wire [1:0] d1_arburst;
    reg [511:0] d1_rdata='0;

    wire out_valid; reg out_ready=0;
    wire [2:0] out_tile_index;
    wire signed [6143:0] projection_s24;
    wire [31:0] input_groups,input_reads,input_releases,input_saturation;
    wire [31:0] gate_cache_requests,gate_weights,gate_tiles;
    wire [31:0] product_groups,act_writes,act_reads;
    wire [31:0] down_weights,output_tiles,saturation_count;
    wire [31:0] g_d0_raw,g_d1_raw,g_d0_elapsed,g_d1_elapsed;
    wire [31:0] d_d0_raw,d_d1_raw,d_d0_elapsed,d_d1_elapsed;
    wire [63:0] gate_physical,gate_useful,down_physical,down_useful;

    reg [12287:0] input_mem[0:HIDDEN_GROUPS-1];
    reg [2047:0] gate_weight_mem[0:GATE_TX-1];
    reg [223:0] gate_meta_mem[0:GATE_TX-1];
    reg [2047:0] down_weight_mem[0:DOWN_TX-1];
    reg [223:0] down_meta_mem[0:DOWN_TX-1];
    reg [6143:0] expected_mem[0:DOWN_TILES-1];
    integer cycle=0,send_group=0,gate_meta_index=0,down_meta_index=0;
    integer outputs=0,command_count=0;
    integer d0_cycle=0,d0_ar_count=0,d0_response=0,d0_beat=0,d0_out=0;
    integer d1_cycle=0,d1_ar_count=0,d1_response=0,d1_beat=0,d1_out=0;

    assign gate_meta_valid=gate_meta_index<GATE_TX && cycle%7!=2;
    assign down_meta_valid=down_meta_index<DOWN_TX && cycle%5!=1;
    assign gate_meta=gate_meta_mem[gate_meta_index<GATE_TX?
        gate_meta_index:GATE_TX-1];
    assign down_meta=down_meta_mem[down_meta_index<DOWN_TX?
        down_meta_index:DOWN_TX-1];

    function automatic [2047:0] transaction_weight(input integer index);
        transaction_weight=index<GATE_TX ? gate_weight_mem[index] :
            down_weight_mem[index-GATE_TX];
    endfunction

    function automatic [511:0] channel_beat(
        input integer channel,input integer beat_index);
        integer transaction,half;
        reg [2047:0] word;
        begin
            transaction=beat_index/2; half=beat_index%2;
            word=transaction_weight(transaction);
            channel_beat=channel==0 ? word[half*512+:512] :
                word[1024+half*512+:512];
        end
    endfunction

    function automatic [31:0] expected_addr(
        input integer channel,input integer burst_index);
        integer phase_burst;
        begin
            if(burst_index<GATE_TX/8)
                expected_addr=(channel?32'h2000_0000:32'h1000_0000)+
                    burst_index*1024;
            else begin
                phase_burst=burst_index-GATE_TX/8;
                expected_addr=(channel?32'h2100_0000:32'h1100_0000)+
                    phase_burst*1024;
            end
        end
    endfunction

    hap_mlp_full_command16_s45 #(
        .GATE_TILES(GATE_TILES),.HIDDEN_GROUPS(HIDDEN_GROUPS),
        .DOWN_GROUPS(DOWN_GROUPS),.DOWN_TILES(DOWN_TILES)
    ) dut (
        .core_clk(core_clk),.core_rst_n(core_rst_n),.core_clear(core_clear),
        .command_pause(1'b0),.weight_source_quiescent(),
        .input_valid(input_valid),.input_ready(input_ready),
        .input_bank(input_bank),.input_group(input_group),
        .input_s24x16x32(input_s24),.input_bank_ready(input_bank_ready),
        .command_valid(command_valid),.command_ready(command_ready),
        .command_bank(1'b0),.gate_ddr0_base_addr(32'h1000_0000),
        .gate_ddr1_base_addr(32'h2000_0000),
        .down_ddr0_base_addr(32'h1100_0000),
        .down_ddr1_base_addr(32'h2100_0000),
        .gate_meta_valid(gate_meta_valid),.gate_meta_ready(gate_meta_ready),
        .gate_meta_u224(gate_meta),.down_meta_valid(down_meta_valid),
        .down_meta_ready(down_meta_ready),.down_meta_u224(down_meta),
        .ddr0_clk(ddr0_clk),.ddr0_rst_n(ddr0_rst_n),
        .ddr0_axi_arvalid(d0_arvalid),.ddr0_axi_arready(d0_arready),
        .ddr0_axi_araddr(d0_araddr),.ddr0_axi_arlen(d0_arlen),
        .ddr0_axi_arsize(d0_arsize),.ddr0_axi_arburst(d0_arburst),
        .ddr0_axi_rvalid(d0_rvalid),.ddr0_axi_rready(d0_rready),
        .ddr0_axi_rdata(d0_rdata),.ddr0_axi_rresp(2'b00),
        .ddr0_axi_rlast(d0_rlast),.ddr1_clk(ddr1_clk),
        .ddr1_rst_n(ddr1_rst_n),.ddr1_axi_arvalid(d1_arvalid),
        .ddr1_axi_arready(d1_arready),.ddr1_axi_araddr(d1_araddr),
        .ddr1_axi_arlen(d1_arlen),.ddr1_axi_arsize(d1_arsize),
        .ddr1_axi_arburst(d1_arburst),.ddr1_axi_rvalid(d1_rvalid),
        .ddr1_axi_rready(d1_rready),.ddr1_axi_rdata(d1_rdata),
        .ddr1_axi_rresp(2'b00),.ddr1_axi_rlast(d1_rlast),
        .out_valid(out_valid),.out_ready(out_ready),
        .out_tile_index(out_tile_index),.projection_s24x16x16(projection_s24),
        .busy(busy),.done(done),.error(error),.phase(phase),
        .input_group_count(input_groups),
        .input_cache_read_count(input_reads),
        .input_cache_release_count(input_releases),
        .input_hadamard_saturation_count(input_saturation),
        .gate_ddr0_raw_beats(g_d0_raw),.gate_ddr1_raw_beats(g_d1_raw),
        .gate_ddr0_elapsed_cycles(g_d0_elapsed),
        .gate_ddr1_elapsed_cycles(g_d1_elapsed),
        .gate_physical_bytes(gate_physical),.gate_useful_bytes(gate_useful),
        .down_ddr0_raw_beats(d_d0_raw),.down_ddr1_raw_beats(d_d1_raw),
        .down_ddr0_elapsed_cycles(d_d0_elapsed),
        .down_ddr1_elapsed_cycles(d_d1_elapsed),
        .down_physical_bytes(down_physical),.down_useful_bytes(down_useful),
        .gate_cache_request_count(gate_cache_requests),
        .gate_weight_group_count(gate_weights),
        .gate_projection_tile_count(gate_tiles),
        .product_group_count(product_groups),
        .down_activation_write_count(act_writes),
        .down_activation_read_count(act_reads),
        .down_weight_tile_count(down_weights),
        .output_tile_count(output_tiles),.saturation_count(saturation_count)
    );

    initial begin
        $readmemh("data/mlp_input_frontend16_cache/input_s24x16x32.mem",input_mem);
        $readmemh("data/mlp_serial_ddr_command16_s45/gate_weights_s4x16x32.mem",gate_weight_mem);
        $readmemh("data/mlp_serial_ddr_command16_s45/gate_weight_meta_u224.mem",gate_meta_mem);
        $readmemh("data/mlp_serial_ddr_command16_s45/down_weights_s4x16x32.mem",down_weight_mem);
        $readmemh("data/mlp_serial_ddr_command16_s45/down_weight_meta_u224.mem",down_meta_mem);
        $readmemh("data/mlp_serial_ddr_command16_s45/expected_s24x16x16.mem",expected_mem);
        repeat(10)@(posedge core_clk);
        core_rst_n<=1;ddr0_rst_n<=1;ddr1_rst_n<=1;
    end

    always @(negedge core_clk) begin
        out_ready<=core_rst_n&&cycle%11!=4;
        if(!core_rst_n) begin
            input_valid<=0;command_valid<=0;
        end else begin
            if(!input_valid&&send_group<HIDDEN_GROUPS&&input_ready) begin
                input_valid<=1;input_bank<=0;input_group<=send_group[6:0];
                input_s24<=input_mem[send_group];
            end else if(input_valid&&input_ready) input_valid<=0;
            if(!command_valid&&command_count==0&&input_bank_ready[0])
                command_valid<=1;
            else if(command_valid&&command_ready)command_valid<=0;
        end
    end

    always @(negedge ddr0_clk) begin
        d0_arready<=ddr0_rst_n&&d0_cycle%11!=4;
        if(!(d0_rvalid&&!d0_rready)) begin
            if(ddr0_rst_n&&d0_out>0&&d0_cycle%17!=6&&d0_response<TOTAL_BEATS)begin
                d0_rvalid<=1;d0_rdata<=channel_beat(0,d0_response);
                d0_rlast<=d0_beat==15;
            end else begin d0_rvalid<=0;d0_rlast<=0;end
        end
    end
    always @(negedge ddr1_clk) begin
        d1_arready<=ddr1_rst_n&&d1_cycle%13!=5;
        if(!(d1_rvalid&&!d1_rready)) begin
            if(ddr1_rst_n&&d1_out>0&&d1_cycle%19!=7&&d1_response<TOTAL_BEATS)begin
                d1_rvalid<=1;d1_rdata<=channel_beat(1,d1_response);
                d1_rlast<=d1_beat==15;
            end else begin d1_rvalid<=0;d1_rlast<=0;end
        end
    end

    always @(posedge ddr0_clk)if(ddr0_rst_n)begin
        d0_cycle<=d0_cycle+1;
        if(d0_arvalid&&d0_arready)begin
            if(d0_araddr!==expected_addr(0,d0_ar_count)||d0_arlen!==15||
               d0_arsize!==6||d0_arburst!==1)$fatal(1,"FAIL d0 AR %0d",d0_ar_count);
            d0_ar_count<=d0_ar_count+1;
        end
        if(d0_rvalid&&d0_rready)begin
            d0_response<=d0_response+1;d0_beat<=d0_beat==15?0:d0_beat+1;
        end
        case({d0_arvalid&&d0_arready,d0_rvalid&&d0_rready&&d0_rlast})
          2'b10:d0_out<=d0_out+1;2'b01:d0_out<=d0_out-1;default:d0_out<=d0_out;
        endcase
    end
    always @(posedge ddr1_clk)if(ddr1_rst_n)begin
        d1_cycle<=d1_cycle+1;
        if(d1_arvalid&&d1_arready)begin
            if(d1_araddr!==expected_addr(1,d1_ar_count)||d1_arlen!==15||
               d1_arsize!==6||d1_arburst!==1)$fatal(1,"FAIL d1 AR %0d",d1_ar_count);
            d1_ar_count<=d1_ar_count+1;
        end
        if(d1_rvalid&&d1_rready)begin
            d1_response<=d1_response+1;d1_beat<=d1_beat==15?0:d1_beat+1;
        end
        case({d1_arvalid&&d1_arready,d1_rvalid&&d1_rready&&d1_rlast})
          2'b10:d1_out<=d1_out+1;2'b01:d1_out<=d1_out-1;default:d1_out<=d1_out;
        endcase
    end

    always @(posedge core_clk)if(core_rst_n)begin
        cycle<=cycle+1;
        if(input_valid&&input_ready)send_group<=send_group+1;
        if(command_valid&&command_ready)command_count<=command_count+1;
        if(gate_meta_valid&&gate_meta_ready)gate_meta_index<=gate_meta_index+1;
        if(down_meta_valid&&down_meta_ready)down_meta_index<=down_meta_index+1;
        if(out_valid&&out_ready)begin
            if(out_tile_index!==outputs||projection_s24!==expected_mem[outputs])
                $fatal(1,"FAIL projection tile=%0d got=%0d",outputs,out_tile_index);
            outputs<=outputs+1;
        end
        if(done)begin
            if(send_group!=HIDDEN_GROUPS||input_groups!=HIDDEN_GROUPS||
               input_reads!=GATE_TX||input_releases!=1||input_bank_ready!=0||
               command_count!=1||gate_meta_index!=GATE_TX||
               down_meta_index!=DOWN_TX||outputs!=DOWN_TILES||
               gate_cache_requests!=GATE_TX||gate_weights!=GATE_TX||
               gate_tiles!=GATE_TILES||product_groups!=DOWN_GROUPS||
               act_writes!=DOWN_GROUPS||act_reads!=DOWN_GROUPS||
               down_weights!=DOWN_TX||output_tiles!=DOWN_TILES||
               saturation_count!=0||input_saturation!=0||
               g_d0_raw!=GATE_TX*2||g_d1_raw!=GATE_TX*2||
               d_d0_raw!=DOWN_TX*2||d_d1_raw!=DOWN_TX*2||
               gate_physical!=GATE_TX*256||gate_useful!=GATE_TX*256||
               down_physical!=DOWN_TX*256||down_useful!=DOWN_TX*256||
               d0_ar_count!=TOTAL_TX/8||d1_ar_count!=TOTAL_TX/8)
                $fatal(1,"FAIL completion in=%0d/%0d/%0d bank=%b cmd=%0d gm=%0d dm=%0d o=%0d",
                    send_group,input_reads,input_releases,input_bank_ready,
                    command_count,gate_meta_index,down_meta_index,outputs);
            $display("PASS: hap_mlp_full_command16_s45 input_groups=%0d gate_tx=%0d down_tx=%0d outputs=%0d release=%0d cycles=%0d mismatches=0",
                input_groups,GATE_TX,DOWN_TX,16*16*DOWN_TILES,
                input_releases,cycle);
            $finish;
        end
        if(error)$fatal(1,"FAIL sticky error wrapper_state=%0d phase=%0d cycle=%0d",
            dut.state_r,phase,cycle);
        if(cycle>200000)$fatal(1,"FAIL timeout state=%0d phase=%0d sent=%0d bank=%b gm=%0d dm=%0d o=%0d",
            dut.state_r,phase,send_group,input_bank_ready,gate_meta_index,
            down_meta_index,outputs);
    end
endmodule
