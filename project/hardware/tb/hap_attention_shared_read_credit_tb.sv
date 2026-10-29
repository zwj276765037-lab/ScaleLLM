`timescale 1ns/1ps
// A legal shared DDR return schedule: accepted bursts retain their order,
// and a stalled response cannot be bypassed by a later KV read. The actual
// reader and CDC payload FIFO feed a consumer that pauses for that KV read.
// This is a bounded transport counterexample, not a model of MIG internals.
module hap_attention_shared_read_credit_tb;
    reg ddr_clk=0,core_clk=0,rst_n=0,cmd_valid=0;
    always #2.5 ddr_clk=~ddr_clk;
    always #6.25 core_clk=~core_clk;
    wire cmd_ready,beat_valid,beat_ready,beat_last,busy,done,error,fifo_error;
    wire [511:0] beat_data;
    wire arvalid,arready,rvalid,rready,rlast;
    wire [31:0] araddr;
    wire [7:0] arlen;
    wire [2:0] arsize;
    wire [1:0] arburst;
    wire [511:0] rdata;
    wire half_valid,half_ready;
    wire [2047:0] half_data;
    wire [31:0] issued,received,received_beats,groups,max_outstanding;
    integer consumed=0,cycles=0,kv_wait_cycles=0,shared_stall_cycles=0;
    reg kv_requested=0,kv_accepted=0,kv_done=0;
    reg [31:0] qaddr[0:63];
    reg qkv[0:63];
    integer qhead=0,qtail=0,qcount=0,qbeat=0;
    wire choose_kv=kv_requested&&!kv_accepted;
    wire weight_ar_fire=arvalid&&arready;
    wire kv_ar_fire=choose_kv&&(qcount<63);
    wire head_kv=qcount>0&&qkv[qhead];
    wire shared_valid=qcount>0;
    wire shared_ready=head_kv?1'b1:rready;
    wire shared_last=head_kv||(qbeat==15);
    wire shared_end=shared_valid&&shared_ready&&shared_last;
    wire push=weight_ar_fire||kv_ar_fire;
    assign arready=!choose_kv&&(qcount<63);
    assign rvalid=shared_valid&&!head_kv;
    assign rdata=payload(qaddr[qhead]+qbeat*64);
    assign rlast=qbeat==15;
    assign half_ready=(consumed<4)||kv_done;

    function automatic [511:0] payload(input [31:0] address);
        integer lane;
        begin
            for(lane=0;lane<16;lane=lane+1)
                payload[lane*32+:32]=(address+lane*4)^32'hc4918d27;
        end
    endfunction
    hap_axi512_weight_reader reader(
        .clk(ddr_clk),.rst_n(rst_n),.clear(1'b0),
        .cmd_valid(cmd_valid),.cmd_ready(cmd_ready),
        .cmd_base_addr(32'h11800000),.cmd_group_count(17'd64),
        .beat_valid(beat_valid),.beat_ready(beat_ready),.beat_data(beat_data),.beat_group_last(beat_last),
        .m_axi_arvalid(arvalid),.m_axi_arready(arready),.m_axi_araddr(araddr),
        .m_axi_arlen(arlen),.m_axi_arsize(arsize),.m_axi_arburst(arburst),
        .m_axi_rvalid(rvalid),.m_axi_rready(rready),.m_axi_rdata(rdata),
        .m_axi_rresp(2'b00),.m_axi_rlast(rlast),
        .busy(busy),.done(done),.error(error),.command_count(),
        .issued_burst_count(issued),.received_burst_count(received),
        .received_beat_count(received_beats),.emitted_group_count(groups),
        .protocol_error_count(),.max_outstanding_count(max_outstanding));
    hap_ddr512_halfgroup_async half_fifo(
        .ddr_clk(ddr_clk),.ddr_rst_n(rst_n),.ddr_clear(1'b0),
        .beat_valid(beat_valid),.beat_ready(beat_ready),.beat_data(beat_data),.beat_last(beat_last),
        .core_clk(core_clk),.core_rst_n(rst_n),.core_clear(1'b0),
        .half_valid(half_valid),.half_ready(half_ready),.half_data(half_data),
        .ddr_beat_count(),.ddr_half_count(),.core_half_count(),.error(fifo_error));

    reg stalled=0;
    reg [512:0] held_response;
    always @(posedge ddr_clk) if(rst_n) begin
        cycles<=cycles+1;
        if(error||fifo_error)$fatal(1,"reader/FIFO error");
        if(stalled&&(!rvalid||{rdata,rlast}!==held_response))
            $fatal(1,"shared memory response changed while stalled");
        stalled<=rvalid&&!rready;
        held_response<={rdata,rlast};
        if(weight_ar_fire)begin
            if(araddr!==32'h11800000+issued*1024||arlen!==15||arsize!==6||arburst!==1)
                $fatal(1,"independent weight address/shape oracle");
            qaddr[qtail]<=araddr;qkv[qtail]<=0;qtail<=(qtail+1)%64;
        end
        if(kv_ar_fire)begin
            qaddr[qtail]<=32'h63800000;qkv[qtail]<=1;qtail<=(qtail+1)%64;
            kv_accepted<=1;
        end
        if(shared_valid&&shared_ready)begin
            if(shared_last)begin
                qhead<=(qhead+1)%64;qbeat<=0;
                if(head_kv)begin kv_done<=1;$display("KV_PROGRESS cycles=%0d issued=%0d received=%0d",cycles,issued,received);end
            end else qbeat<=qbeat+1;
        end
        case({push,shared_end})
            2'b10:qcount<=qcount+1;
            2'b01:qcount<=qcount-1;
        endcase
        if(rvalid&&!rready)shared_stall_cycles<=shared_stall_cycles+1;
        if(kv_requested&&!kv_done)kv_wait_cycles<=kv_wait_cycles+1;
        if(kv_wait_cycles==512)
            $fatal(1,"SHARED_R_PROGRESS_TIMEOUT consumed=%0d issued=%0d received=%0d Rbeats=%0d queue=%0d head_kv=%0d stalls=%0d",consumed,issued,received,received_beats,qcount,head_kv,shared_stall_cycles);
        if(cycles>4000)$fatal(1,"transport completion ceiling");
    end
    integer b;
    always @(posedge core_clk) if(rst_n) begin
        if(half_valid&&half_ready)begin
            for(b=0;b<4;b=b+1)
                if(half_data[b*512+:512]!==payload(32'h11800000+(consumed*4+b)*64))
                    $fatal(1,"independent payload oracle group=%0d beat=%0d",consumed,b);
            consumed<=consumed+1;
            if(consumed==3)kv_requested<=1;
        end
        if(consumed==64)begin
            if(!kv_done||busy||issued!=16||received!=16||received_beats!=256||groups!=64)
                $fatal(1,"final command/count/KV mismatch");
            $display("COVERAGE shared_ordered_R groups=%0d bursts=%0d beats=%0d KV_wait_cycles=%0d R_stalls=%0d max_outstanding=%0d",consumed,issued,received_beats,kv_wait_cycles,shared_stall_cycles,max_outstanding);
            $display("HARDWARE_AGENT_SIM_PASS");$finish;
        end
    end
    initial begin
        repeat(10)@(negedge core_clk);rst_n=1;
        repeat(20)@(negedge core_clk);
        @(negedge ddr_clk);cmd_valid=1;
        @(posedge ddr_clk);if(!cmd_ready)$fatal(1,"command not ready");
        @(negedge ddr_clk);cmd_valid=0;
    end
endmodule
