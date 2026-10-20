`timescale 1ns / 1ps

module hap_m003_shared_production_width_tb;
    localparam integer GG=128,DG=448,DT=4,TOTAL=GG*2+DG*DT;
    reg clk=0,rst_n=0,clear=0;
    always #5 clk=~clk;
    integer cycle=0,sent=0,gate_received=0,down_received=0,phase=0;
    integer first_accept=-1,last_accept=-1,max_ii=0,dispatch0=0,dispatch1=0;
    integer last_dispatch0=-1,last_dispatch1=-1,max_dispatch_ii0=0,max_dispatch_ii1=0;
    integer stable_checks=0,lane_checks=0,first_output=-1,guard_index=0;
    integer gate_stall_left=0,down_stall_left=0;
    reg running=0,stall_mode=0;
    wire in_valid=running && sent<TOTAL;
    wire in_ready;
    reg in_down,in_first,in_last;
    reg [8:0] tile;
    reg [4607:0] activation;
    reg [1535:0] weight;
    reg [127:0] acode;
    reg [95:0] ashift,wcode;
    reg [71:0] wshift;
    reg [11:0] mask;
    wire gate_valid,down_valid;
    wire gate_ready=!stall_mode || (gate_stall_left==0 && cycle%47>17);
    wire down_ready=!stall_mode || (down_stall_left==0 && cycle%53>23);
    wire [4607:0] gate_data;
    wire [6143:0] down_data;
    wire [8:0] down_tile;
    wire [31:0] gate_sat,down_sat,formats,input_count,gate_count,down_count;
    wire guard_overflow,accumulator_overflow,format_error,error;
    reg [4607:0] gate_expected[0:1];
    reg [6143:0] down_expected[0:DT-1];
    reg gate_held=0,down_held=0;
    reg [4607:0] held_gate;
    reg [6143:0] held_down;
    reg [8:0] held_tile;
    integer row,column,k,group_index,pass_index,t,source_group;
    longint signed dot,sum,rounded;

    function automatic integer av(input integer g,r,j);
        av=(g*17+r*23+j*11)%511-255;
    endfunction
    function automatic integer wv(input integer g,c,j);
        wv=(g*7+c*3+j*5)%16-8;
    endfunction
    function automatic longint signed finish_value(input longint signed q);
        finish_value=q<0 ? -((-q+128)/256) : (q+128)/256;
    endfunction
    function automatic longint signed group_guard(input integer g,r,c);
        longint signed d,a,w;
        begin
            d=0;
            for(integer j=0;j<32;j=j+1) begin
                a=av(g,r,j);
                w=wv(g,c,j);
                d=d+a*w;
            end
            group_guard=d*(3+r)*(2+c)*16;
        end
    endfunction

    always_comb begin
        in_down=sent>=GG && sent<GG+DG*DT;
        source_group=in_down ? (sent-GG)/DT : sent%GG;
        tile=in_down ? (sent-GG)%DT : 0;
        in_first=source_group==0;
        in_last=source_group==(in_down ? DG-1 : GG-1);
        mask=in_down ? (tile==1 ? 12'h0ff : tile==3 ? 12'h00f : 12'hfff) :
            (sent>=GG+DG*DT ? 12'h0ff : 12'hfff);
        activation='0;weight='0;acode='0;ashift='0;wcode='0;wshift='0;
        for(integer r=0;r<16;r=r+1) begin
            acode[r*8+:8]=3+r;
            ashift[r*6+:6]=in_down ? 6 : 10;
            for(integer j=0;j<32;j=j+1)
                activation[(r*32+j)*9+:9]=av(source_group,r,j);
        end
        for(integer c=0;c<12;c=c+1) begin
            wcode[c*8+:8]=2+c;
            wshift[c*6+:6]=in_down ? 6 : 10;
            for(integer j=0;j<32;j=j+1)
                weight[(c*32+j)*4+:4]=wv(source_group,c,j);
        end
    end

    hap_mlp_shared_dual_slice16x12_s44_s54 #(.DOWN_TILES(DT),.DOWN_GROUPS(DG),.TILE_W(9)) dut (
        .clk(clk),.rst_n(rst_n),.clear(clear),.in_valid(in_valid),.in_ready(in_ready),
        .in_down(in_down),.in_first(in_first),.in_last(in_last),.in_tile(tile),
        .activation_s9x16x32(activation),.weights_s4x12x32(weight),
        .activation_code_u8x16(acode),.activation_shift_u6x16(ashift),
        .weight_code_u8x12(wcode),.weight_shift_u6x12(wshift),.column_valid_u12(mask),
        .gate_valid(gate_valid),.gate_ready(gate_ready),.gate_s24x16x12(gate_data),
        .down_valid(down_valid),.down_ready(down_ready),.down_tile(down_tile),
        .down_s32x16x12(down_data),.gate_saturation(gate_sat),.down_saturation(down_sat),
        .guard_overflow(guard_overflow),.accumulator_overflow(accumulator_overflow),
        .total_shift_format_count(formats),.format_error(format_error),
        .input_transaction_count(input_count),.gate_output_pass_count(gate_count),
        .down_output_pass_count(down_count),.error(error)
    );

    always @(posedge clk) begin
        cycle<=cycle+1;
        if(cycle>20000) $fatal(1,"dispatch timeout");
        if(rst_n && !clear && running) begin
            if(stall_mode && gate_valid && gate_stall_left>0)
                gate_stall_left<=gate_stall_left-1;
            if(stall_mode && down_valid && down_stall_left>0)
                down_stall_left<=down_stall_left-1;
            if(in_valid && in_ready) begin
                if(first_accept<0) first_accept=cycle;
                if(last_accept>=0 && cycle-last_accept>max_ii) max_ii=cycle-last_accept;
                last_accept=cycle;
                sent<=sent+1;
            end
            if(dut.u_branch0.dispatch_fire) begin
                if(dispatch0<3) $display("DISPATCH_TRACE index=%0d first=%b last=%b",dispatch0,
                    dut.u_branch0.ingress_first[dut.u_branch0.ingress_rd_ptr_r],
                    dut.u_branch0.ingress_last[dut.u_branch0.ingress_rd_ptr_r]);
                if(last_dispatch0>=0 && cycle-last_dispatch0>max_dispatch_ii0)
                    max_dispatch_ii0=cycle-last_dispatch0;
                last_dispatch0=cycle;dispatch0=dispatch0+1;
            end
            if(dut.u_branch1.dispatch_fire) begin
                if(last_dispatch1>=0 && cycle-last_dispatch1>max_dispatch_ii1)
                    max_dispatch_ii1=cycle-last_dispatch1;
                last_dispatch1=cycle;dispatch1=dispatch1+1;
            end
            if(dut.u_branch0.kernel_fire) begin
                if(guard_index<3) $display("GUARD_TRACE index=%0d got=%0d expected=%0d first=%b group_index=%0d",
                    guard_index,$signed(dut.u_branch0.guard_s37[36:0]),group_guard(guard_index,0,0),
                    dut.u_branch0.tag_first[dut.u_branch0.tag_rd_ptr_r],dut.u_branch0.u_gate_accum.group_index_r);
                guard_index=guard_index+1;
            end
            if(gate_held) begin
                if(!gate_valid || gate_data!==held_gate) $fatal(1,"gate stall stability");
                stable_checks=stable_checks+1;
            end
            if(down_held) begin
                if(!down_valid || down_data!==held_down || down_tile!==held_tile)
                    $fatal(1,"down stall stability");
                stable_checks=stable_checks+1;
            end
            gate_held=gate_valid && !gate_ready;
            down_held=down_valid && !down_ready;
            if(gate_held) held_gate=gate_data;
            if(down_held) begin held_down=down_data;held_tile=down_tile;end
            if(gate_valid && gate_ready) begin
                if(gate_received>=2 || gate_data!==gate_expected[gate_received]) begin
                    for(integer lane=0;lane<192;lane=lane+1)
                        if(gate_data[lane*24+:24]!==gate_expected[gate_received][lane*24+:24])
                            $display("GATE_MISMATCH lane=%0d got=%0d expected=%0d",lane,
                                $signed(gate_data[lane*24+:24]),$signed(gate_expected[gate_received][lane*24+:24]));
                    $fatal(1,"independent Gate integer mismatch pass=%0d",gate_received);
                end
                gate_received=gate_received+1;lane_checks=lane_checks+192;
                if(first_output<0) first_output=cycle;
            end
            if(down_valid && down_ready) begin
                if(down_received>=DT || down_tile!==down_received[1:0] ||
                   down_data!==down_expected[down_received])
                    $fatal(1,"independent Down integer/tag mismatch tile=%0d",down_received);
                down_received=down_received+1;lane_checks=lane_checks+192;
            end
            if({error,guard_overflow,accumulator_overflow,format_error}!==4'b0000 || formats!==32'd0)
                $fatal(1,"dispatch status error sent=%0d error=%b guard=%b accum=%b format=%b formats=%0d branch=%b/%b kernel=%b/%b gate=%b/%b down=%b/%b",
                    sent,error,guard_overflow,accumulator_overflow,format_error,formats,
                    dut.error0,dut.error1,dut.u_branch0.kernel_error,dut.u_branch1.kernel_error,
                    dut.u_branch0.gate_error,dut.u_branch1.gate_error,
                    dut.u_branch0.down_error,dut.u_branch1.down_error);
        end
    end

    task automatic reset_scoreboard;
        begin
            sent=0;gate_received=0;down_received=0;dispatch0=0;dispatch1=0;
            first_accept=-1;last_accept=-1;max_ii=0;
            last_dispatch0=-1;last_dispatch1=-1;max_dispatch_ii0=0;max_dispatch_ii1=0;
            gate_held=0;down_held=0;first_output=-1;
            guard_index=0;
        end
    endtask

    initial begin
        // Integer dot/scale/accumulate reference is computed without DUT helpers.
        if(group_guard(0,0,0)!==64'sd172032 || group_guard(1,0,0)!==64'sd162816 ||
           group_guard(2,0,0)!==64'sd52224)
            $fatal(1,"independent reference arithmetic witness mismatch");
        for(row=0;row<16;row=row+1) for(column=0;column<12;column=column+1) begin
            sum=0;
            for(group_index=0;group_index<GG;group_index=group_index+1) begin
                dot=group_guard(group_index,row,column);
                sum=sum+dot;
            end
            rounded=finish_value(sum);
            if(rounded>8388607) rounded=8388607;
            if(rounded < -8388608) rounded=-8388608;
            gate_expected[0][(row*12+column)*24+:24]=rounded;
            gate_expected[1][(row*12+column)*24+:24]=column<8 ? rounded : 0;
            sum=0;
            for(group_index=0;group_index<DG;group_index=group_index+1) begin
                dot=group_guard(group_index,row,column);
                sum=sum+dot*256;
            end
            rounded=finish_value(sum);
            if(rounded>64'sd2147483647) rounded=64'sd2147483647;
            if(rounded < -64'sd2147483648) rounded=-64'sd2147483648;
            for(t=0;t<DT;t=t+1)
                down_expected[t][(row*12+column)*32+:32]=
                    ((t==1 && column>=8) || (t==3 && column>=4)) ? 0 : rounded;
        end
        // Hold reset beyond glbl's100ns startup interval before admitting work.
        repeat(20) @(negedge clk);
        rst_n=1;running=1;
        // Clear an in-flight, nonempty dispatch before the two complete streams.
        repeat(40) @(negedge clk);
        clear=1;running=0;
        @(negedge clk);
        clear=0;reset_scoreboard();running=1;
        for(phase=0;phase<2;phase=phase+1) begin
            wait(gate_received==2 && down_received==DT);
            repeat(5) @(negedge clk);
            if(input_count!=TOTAL || gate_count!=2 || down_count!=DT ||
               dispatch0!=TOTAL || dispatch1!=TOTAL)
                $fatal(1,"dispatch transaction conservation");
            if(!stall_mode && (max_ii!=1 || max_dispatch_ii0!=1 || max_dispatch_ii1!=1))
                $fatal(1,"production dispatch intrinsic II regression");
            $display("DISPATCH phase=%0d inputs=%0d branches=%0d/%0d issue_cycles=%0d first_output=%0d ii=%0d/%0d/%0d",
                phase,input_count,dispatch0,dispatch1,last_accept-first_accept+1,
                first_output-first_accept,max_ii,max_dispatch_ii0,max_dispatch_ii1);
            @(negedge clk);running=0;clear=1;
            @(negedge clk);clear=0;reset_scoreboard();stall_mode=1;
            gate_stall_left=9;down_stall_left=13;running=phase==0;
        end
        if(stable_checks==0 || lane_checks!=2304)
            $fatal(1,"dispatch coverage missing lane=%0d stable=%0d",lane_checks,stable_checks);
        $display("DISPATCH checks=%0d stable=%0d",lane_checks,stable_checks);
        $display("PASS hap_mlp_shared_dual_s44_s54_dispatch");
        $display("HARDWARE_AGENT_SIM_PASS");
        $finish;
    end
endmodule
