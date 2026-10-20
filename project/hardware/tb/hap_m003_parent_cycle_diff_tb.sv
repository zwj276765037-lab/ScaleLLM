`timescale 1ns / 1ps
module hap_m003_parent_cycle_diff_tb;
    localparam integer TILE_W=9;
    reg clk = '0;
    reg rst_n = '0;
    reg clear = '0;
    reg in_valid = '0;
    wire old_in_ready;
    wire new_in_ready;
    reg in_down = '0;
    reg in_first = '0;
    reg in_last = '0;
    reg [TILE_W-1:0]             in_tile = '0;
    reg signed [16*32*9-1:0]     activation_s9x16x32 = '0;
    reg signed [12*32*4-1:0]     weights_s4x12x32 = '0;
    reg [16*8-1:0]               activation_code_u8x16 = '0;
    reg [16*6-1:0]               activation_shift_u6x16 = '0;
    reg [12*8-1:0]               weight_code_u8x12 = '0;
    reg [12*6-1:0]               weight_shift_u6x12 = '0;
    reg [11:0]                    column_valid_u12 = '0;
    wire old_gate_valid;
    wire new_gate_valid;
    reg gate_ready = '0;
    wire signed [16*12*24-1:0]    old_gate_s24x16x12;
    wire signed [16*12*24-1:0]    new_gate_s24x16x12;
    wire old_down_valid;
    wire new_down_valid;
    reg down_ready = '0;
    wire [TILE_W-1:0]             old_down_tile;
    wire [TILE_W-1:0]             new_down_tile;
    wire signed [16*12*32-1:0]    old_down_s32x16x12;
    wire signed [16*12*32-1:0]    new_down_s32x16x12;
    wire [31:0]                   old_gate_saturation;
    wire [31:0]                   new_gate_saturation;
    wire [31:0]                   old_down_saturation;
    wire [31:0]                   new_down_saturation;
    wire old_guard_overflow;
    wire new_guard_overflow;
    wire old_accumulator_overflow;
    wire new_accumulator_overflow;
    wire [31:0]                   old_total_shift_format_count;
    wire [31:0]                   new_total_shift_format_count;
    wire old_format_error;
    wire new_format_error;
    wire [31:0]                   old_input_transaction_count;
    wire [31:0]                   new_input_transaction_count;
    wire [31:0]                   old_gate_output_pass_count;
    wire [31:0]                   new_gate_output_pass_count;
    wire [31:0]                   old_down_output_pass_count;
    wire [31:0]                   new_down_output_pass_count;
    wire old_error;
    wire new_error;
    hap_m003_old_parent #(.TILE_W(9)) old_dut (
        .clk(clk),
        .rst_n(rst_n),
        .clear(clear),
        .in_valid(in_valid),
        .in_ready(old_in_ready),
        .in_down(in_down),
        .in_first(in_first),
        .in_last(in_last),
        .in_tile(in_tile),
        .activation_s9x16x32(activation_s9x16x32),
        .weights_s4x12x32(weights_s4x12x32),
        .activation_code_u8x16(activation_code_u8x16),
        .activation_shift_u6x16(activation_shift_u6x16),
        .weight_code_u8x12(weight_code_u8x12),
        .weight_shift_u6x12(weight_shift_u6x12),
        .column_valid_u12(column_valid_u12),
        .gate_valid(old_gate_valid),
        .gate_ready(gate_ready),
        .gate_s24x16x12(old_gate_s24x16x12),
        .down_valid(old_down_valid),
        .down_ready(down_ready),
        .down_tile(old_down_tile),
        .down_s32x16x12(old_down_s32x16x12),
        .gate_saturation(old_gate_saturation),
        .down_saturation(old_down_saturation),
        .guard_overflow(old_guard_overflow),
        .accumulator_overflow(old_accumulator_overflow),
        .total_shift_format_count(old_total_shift_format_count),
        .format_error(old_format_error),
        .input_transaction_count(old_input_transaction_count),
        .gate_output_pass_count(old_gate_output_pass_count),
        .down_output_pass_count(old_down_output_pass_count),
        .error(old_error)
    );
    hap_m003_new_parent #(.TILE_W(9)) new_dut (
        .clk(clk),
        .rst_n(rst_n),
        .clear(clear),
        .in_valid(in_valid),
        .in_ready(new_in_ready),
        .in_down(in_down),
        .in_first(in_first),
        .in_last(in_last),
        .in_tile(in_tile),
        .activation_s9x16x32(activation_s9x16x32),
        .weights_s4x12x32(weights_s4x12x32),
        .activation_code_u8x16(activation_code_u8x16),
        .activation_shift_u6x16(activation_shift_u6x16),
        .weight_code_u8x12(weight_code_u8x12),
        .weight_shift_u6x12(weight_shift_u6x12),
        .column_valid_u12(column_valid_u12),
        .gate_valid(new_gate_valid),
        .gate_ready(gate_ready),
        .gate_s24x16x12(new_gate_s24x16x12),
        .down_valid(new_down_valid),
        .down_ready(down_ready),
        .down_tile(new_down_tile),
        .down_s32x16x12(new_down_s32x16x12),
        .gate_saturation(new_gate_saturation),
        .down_saturation(new_down_saturation),
        .guard_overflow(new_guard_overflow),
        .accumulator_overflow(new_accumulator_overflow),
        .total_shift_format_count(new_total_shift_format_count),
        .format_error(new_format_error),
        .input_transaction_count(new_input_transaction_count),
        .gate_output_pass_count(new_gate_output_pass_count),
        .down_output_pass_count(new_down_output_pass_count),
        .error(new_error)
    );
    always #5 clk=~clk;
    reg r0=0,r1=0;
    reg [6559:0] stimulus=0;
    reg [6559:0] model_head,model_tail;
    integer model_count=0,checks=0,full_pop=0,both_events=0,unequal_ready=0,clear_seen=0;
    reg push,pop;
    reg [31:0] rng=32'h10a32026;
    task automatic next_stimulus;
        for(integer j=0;j<205;j=j+1) begin
            rng={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};
            stimulus[j*32+:32]=rng;
        end
    endtask
    always_comb begin
        {column_valid_u12,weight_shift_u6x12,weight_code_u8x12,
         activation_shift_u6x16,activation_code_u8x16,
         weights_s4x12x32,activation_s9x16x32,in_tile,in_last,in_first,in_down}=stimulus;
    end
    always_comb begin
        old_dut.u_branch0.test_ready=r0;new_dut.u_branch0.test_ready=r0;
        old_dut.u_branch1.test_ready=r1;new_dut.u_branch1.test_ready=r1;
    end
    always @(posedge clk) begin
        if(old_in_ready!==(rst_n&&!clear&&(model_count!=2)) || new_in_ready!==old_in_ready)
            $fatal(1,"upstream credit mismatch");
        push=in_valid&&old_in_ready;
        pop=rst_n&&!clear&&(model_count!=0)&&r0&&r1;
        if(model_count==2&&pop) begin
            full_pop=full_pop+1;
            if(push||new_in_ready) $fatal(1,"full plus pop created same-cycle credit");
        end
        if(push&&pop) both_events=both_events+1;
        if(r0!=r1) unequal_ready=unequal_ready+1;
        if((new_dut.u_branch0.in_valid&&new_dut.u_branch0.in_ready) !== pop)
            $fatal(1,"branch0 atomic acceptance mismatch");
        if((new_dut.u_branch1.in_valid&&new_dut.u_branch1.in_ready) !== pop)
            $fatal(1,"branch1 atomic acceptance mismatch");
        if(!rst_n||clear) begin model_count=0;clear_seen=clear_seen+1;end
        else case({push,pop})
            2'b10:begin
                if(model_count==0) model_head=stimulus;else model_tail=stimulus;
                model_count=model_count+1;
            end
            2'b01:begin if(model_count==2) model_head=model_tail;model_count=model_count-1;end
            2'b11:model_head=stimulus;
            default:begin end
        endcase
        #1;
        if(new_dut.parent_count_r!==model_count[1:0] || old_dut.parent_count_r!==model_count[1:0])
            $fatal(1,"occupancy mismatch");
        if(new_dut.parent_head_r!==model_head || old_dut.parent_head_r!==model_head ||
           new_dut.parent_tail_r!==model_tail || old_dut.parent_tail_r!==model_tail)
            $fatal(1,"whole payload/reset/hold/tail move mismatch cycle=%0d",checks);
        if(new_dut.g_m003_parent_ce.head_ce!=={42{new_dut.parent_head_write_ce}} ||
           new_dut.g_m003_parent_ce.tail_ce!=={39{new_dut.parent_tail_write_ce}})
            $fatal(1,"CE identity primitive mismatch");
        checks=checks+1;
    end
    initial begin
        repeat(3) @(negedge clk);rst_n=1;in_valid=1;next_stimulus();
        repeat(5) @(negedge clk);
        r0=1;r1=0;repeat(4) @(negedge clk);
        r0=0;r1=1;repeat(4) @(negedge clk);
        r0=1;r1=1;repeat(8) @(negedge clk);
        for(integer i=0;i<3000;i=i+1) begin
            @(negedge clk);next_stimulus();
            rst_n=(i%137!=0);clear=(i%97==0);
            in_valid=rng[0]|rng[1];r0=rng[2];r1=rng[3];
        end
        @(negedge clk);in_valid=0;clear=0;rst_n=1;r0=1;r1=1;
        repeat(5) @(negedge clk);
        if(full_pop==0||both_events==0||unequal_ready==0||clear_seen<2||checks<3000)
            $fatal(1,"FIFO boundary coverage incomplete");
        $display("M003_M2_PARENT_CYCLE_DIFF_PASS");$finish;
    end
endmodule
