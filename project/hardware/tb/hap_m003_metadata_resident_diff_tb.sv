`timescale 1ns / 1ps
module hap_m003_metadata_resident_diff_tb;
    reg clk=0,rst_n=0,system_clear=0,launch=0,abort_clear=0;
    always #5 clk=~clk;
    wire clear=system_clear||abort_clear;
    reg wr_valid=0,rsp_ready=0;
    reg [16:0] wr_addr=0;
    reg [255:0] wr_data=0;
    reg read_enable=0,illegal_read=0,max_invalid_read=0;
    reg [16:0] core_addr=0;
    reg core_pending=0;
    wire [16:0] request_addr=max_invalid_read ? 17'h1ffff : core_addr;
    wire rd_valid=illegal_read || (read_enable && core_addr<81920 && !core_pending);
    wire old_wr_ready,old_rd_ready,old_rsp_valid,old_error;
    wire new_wr_ready,new_rd_ready,new_rsp_valid,new_error;
    wire legacy_wr_ready,legacy_rd_ready,legacy_rsp_valid,legacy_error;
    wire [255:0] old_data,new_data,legacy_data;
    wire [31:0] old_writes,old_reads,old_formats;
    wire [31:0] new_writes,new_reads,new_formats;
    wire [31:0] legacy_writes,legacy_reads,legacy_formats;
    wire q=rd_valid&&old_rd_ready;
    wire r=old_rsp_valid&&rsp_ready;
    hap_m003_weight_meta_reference old_dut (
        .clk(clk),.rst_n(rst_n),.clear(clear),.wr_valid(wr_valid),.wr_ready(old_wr_ready),
        .wr_addr(wr_addr),.wr_meta16(wr_data),.rd_valid(rd_valid),.rd_ready(old_rd_ready),
        .rd_addr(request_addr),.rsp_valid(old_rsp_valid),.rsp_ready(rsp_ready),.rsp_meta16(old_data),
        .write_count(old_writes),.read_count(old_reads),.format_error_count(old_formats),.error(old_error)
    );
    hap_weight_meta_resident #(.LOCAL_ADDR_COPIES(1)) new_dut (
        .clk(clk),.rst_n(rst_n),.clear(clear),.addr_system_clear(system_clear),.addr_launch(launch),
        .wr_valid(wr_valid),.wr_ready(new_wr_ready),.wr_addr(wr_addr),.wr_meta16(wr_data),
        .rd_valid(rd_valid),.rd_ready(new_rd_ready),.rd_addr(request_addr),
        .rsp_valid(new_rsp_valid),.rsp_ready(rsp_ready),.rsp_meta16(new_data),
        .write_count(new_writes),.read_count(new_reads),.format_error_count(new_formats),.error(new_error)
    );
    // Ignored sidebands deliberately unknown in legacy/default mode.
    hap_weight_meta_resident legacy_dut (
        .clk(clk),.rst_n(rst_n),.clear(clear),.addr_system_clear(1'bx),.addr_launch(1'bx),
        .wr_valid(wr_valid),.wr_ready(legacy_wr_ready),.wr_addr(wr_addr),.wr_meta16(wr_data),
        .rd_valid(rd_valid),.rd_ready(legacy_rd_ready),.rd_addr(request_addr),
        .rsp_valid(legacy_rsp_valid),.rsp_ready(rsp_ready),.rsp_meta16(legacy_data),
        .write_count(legacy_writes),.read_count(legacy_reads),
        .format_error_count(legacy_formats),.error(legacy_error)
    );
    // Exact independent old core event order; no local-copy CE/D expression here.
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin core_addr<=0;core_pending<=0;end
        else if(system_clear) begin core_addr<=0;core_pending<=0;end
        else begin
            if(launch) begin core_addr<=0;core_pending<=0;end
            if(q) core_pending<=1;
            if(r) begin core_pending<=0;core_addr<=core_addr+1'b1;end
        end
    end
    reg [255:0] expected_memory[0:81919];
    reg [255:0] expected_rsp;
    reg model_token=1,model_valid=0,model_error=0;
    reg [31:0] model_writes=0,model_reads=0,model_formats=0;
    integer cycles=0,collision_checks=0,stalls=0,read_samples=0,aborts=0;
    reg wf,rf,sf;
    function automatic [255:0] word_at(input integer address);
        reg [255:0] value;
        begin
            value=0;
            for(integer c=0;c<16;c=c+1) begin
                value[c*16+:8]=(address*13+c*7)%255+1;
                value[c*16+8+:6]=(address+c)%64;
            end
            word_at=value;
        end
    endfunction
    function automatic bit invalid_format(input [255:0] value);
        bit bad;
        begin
            bad=0;
            for(integer c=0;c<16;c=c+1)
                if(value[c*16+14+:2]!=0 || (value[c*16+:8]==0 && value[c*16+8+:6]!=0)) bad=1;
            invalid_format=bad;
        end
    endfunction
    always @(posedge clk) begin
        cycles=cycles+1;
        if(cycles>800000) $fatal(1,"metadata functional cycle bound exceeded");
        if(old_wr_ready!==(rst_n&&!clear&&wr_addr<81920) ||
           old_rd_ready!==(rst_n&&!clear&&model_token&&request_addr<81920))
            $fatal(1,"independent metadata ready mismatch");
        if({new_wr_ready,new_rd_ready,new_rsp_valid,new_error}!==
           {old_wr_ready,old_rd_ready,old_rsp_valid,old_error} ||
           {legacy_wr_ready,legacy_rd_ready,legacy_rsp_valid,legacy_error}!==
           {old_wr_ready,old_rd_ready,old_rsp_valid,old_error})
            $fatal(1,"metadata handshake/status cycle mismatch");
        wf=wr_valid&&old_wr_ready;rf=q;sf=r;
        // Sample before write: same-address read/write must observe old data.
        if(rf) begin expected_rsp=expected_memory[core_addr];read_samples=read_samples+1;end
        if(wf) expected_memory[wr_addr]=wr_data;
        if(wf&&rf&&wr_addr==core_addr) collision_checks=collision_checks+1;
        if(old_rsp_valid&&!rsp_ready) stalls=stalls+1;
        if(!rst_n||clear) begin
            model_token=1;model_valid=0;model_writes=0;model_reads=0;model_formats=0;model_error=0;
            if(abort_clear) aborts=aborts+1;
        end else begin
            if(rf) model_token=0;else if(sf) model_token=1;
            if(sf) model_valid=0;
            if(rf) model_valid=1;
            if(wf) begin
                model_writes=model_writes+1;
                if(invalid_format(wr_data)) begin model_formats=model_formats+1;model_error=1;end
            end
            if(sf) model_reads=model_reads+1;
            if((wr_valid&&wr_addr>=81920)||(rd_valid&&request_addr>=81920)) model_error=1;
        end
        #1;
        if(new_dut.g_m003_width_slices.g_slice[0].u_addr.address_r!==core_addr ||
           new_dut.g_m003_width_slices.g_slice[1].u_addr.address_r!==core_addr)
            $fatal(1,"same-edge local address/tag invariant mismatch");
        if(new_rsp_valid!==(rst_n&&!clear&&model_valid)||old_rsp_valid!==new_rsp_valid||legacy_rsp_valid!==new_rsp_valid)
            $fatal(1,"response latency/token mismatch");
        if(model_valid && (old_data!==expected_rsp||new_data!==expected_rsp||legacy_data!==expected_rsp))
            $fatal(1,"old data/slice concatenation/stall mismatch addr=%0d",core_addr);
        if({old_writes,old_reads,old_formats,old_error}!=={model_writes,model_reads,model_formats,model_error}||
           {new_writes,new_reads,new_formats,new_error}!=={model_writes,model_reads,model_formats,model_error}||
           {legacy_writes,legacy_reads,legacy_formats,legacy_error}!=={model_writes,model_reads,model_formats,model_error})
            $fatal(1,"single metadata counter/format/error mismatch");
    end
    task automatic edge_wait;
        @(posedge clk);#2;
    endtask
    initial begin
        repeat(4) @(negedge clk);rst_n=1;
        // Write every physical production address using the actual external write port.
        for(integer a=0;a<81920;a=a+1) begin
            @(negedge clk);wr_valid=1;wr_addr=a;wr_data=word_at(a);edge_wait();
        end
        @(negedge clk);wr_valid=0;launch=1;edge_wait();
        @(negedge clk);launch=0;read_enable=1;
        for(integer step=0;core_addr<81920;step=step+1) begin
            @(negedge clk);rsp_ready=(step%7!=0 && step%11!=0);
            wr_valid=(core_addr%257==0)&&rd_valid&&old_rd_ready;
            wr_addr=core_addr;wr_data=word_at(core_addr+81920);edge_wait();
        end
        @(negedge clk);read_enable=0;wr_valid=0;illegal_read=1;rsp_ready=1;edge_wait();
        if(core_addr!==81920||!old_error) $fatal(1,"terminal/invalid address coverage missing");
        // Abort clears resident state, but must leave core/local address unchanged.
        @(negedge clk);illegal_read=0;abort_clear=1;edge_wait();
        if(core_addr!==81920) $fatal(1,"abort incorrectly reset address");
        @(negedge clk);abort_clear=0;launch=1;edge_wait();
        @(negedge clk);launch=0;read_enable=1;rsp_ready=1;
        while(core_addr<9) begin @(negedge clk);edge_wait();end
        // Keep a real response pending, then apply launch and consume on one edge.
        @(negedge clk);rsp_ready=0;
        while(!old_rsp_valid) begin @(negedge clk);edge_wait();end
        @(negedge clk);launch=1;rsp_ready=1;edge_wait();
        if(core_addr==0) $fatal(1,"launch won over trailing response increment");
        @(negedge clk);launch=0;rsp_ready=0;
        while(!old_rsp_valid) begin @(negedge clk);edge_wait();end
        @(negedge clk);abort_clear=1;edge_wait();
        @(negedge clk);abort_clear=0;launch=1;edge_wait();
        @(negedge clk);launch=0;system_clear=1;edge_wait();
        if(core_addr!==0) $fatal(1,"system clear address mismatch");
        @(negedge clk);system_clear=0;read_enable=0;wr_valid=1;wr_addr=81919;wr_data=256'h4000;edge_wait();
        @(negedge clk);wr_addr=81920;wr_data=0;edge_wait();
        // Maximum 17-bit illegal request is driven at the public resident input;
        // no core/helper state is forced. Both ports must reject without alias.
        @(negedge clk);wr_addr=17'h1ffff;max_invalid_read=1;illegal_read=1;edge_wait();
        if(new_wr_ready||new_rd_ready||new_writes!==1||new_reads!==0)
            $fatal(1,"maximum illegal address was accepted or changed counters");
        if(new_dut.g_m003_width_slices.g_slice[0].meta_mem[49151]!==expected_memory[49151][127:0]||
           new_dut.g_m003_width_slices.g_slice[1].meta_mem[49151]!==expected_memory[49151][255:128])
            $fatal(1,"maximum illegal write aliased production storage");
        @(negedge clk);wr_valid=0;illegal_read=0;max_invalid_read=0;repeat(3) edge_wait();
        if(collision_checks<100||stalls==0||read_samples<81920||aborts<2||new_formats!==1||!new_error)
            $fatal(1,"metadata production coverage incomplete");
        $display("M003_A3_RESIDENT_DIFF_PASS");$finish;
    end
endmodule
