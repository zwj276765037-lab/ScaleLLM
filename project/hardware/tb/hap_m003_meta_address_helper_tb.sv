`timescale 1ns / 1ps
module hap_m003_meta_address_helper_tb;
    reg clk=0, rst_n=0, system_clear=0, launch=0, rsp_fire=0;
    always #5 clk=~clk;
    wire [16:0] addr;
    reg [16:0] reference_addr=0;
    integer checks=0;
    hap_weight_meta_read_addr_copy dut (
        .clk(clk),.rst_n(rst_n),.system_clear(system_clear),
        .launch(launch),.rsp_fire(rsp_fire),.addr(addr)
    );
    // Independent transcription of original core NBA order, rather than new CE/D.
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) reference_addr<=0;
        else if (system_clear) reference_addr<=0;
        else begin
            if (launch) reference_addr<=0;
            if (rsp_fire) reference_addr<=reference_addr+1'b1;
        end
    end
    always @(posedge clk) begin
        #1;
        if (addr!==reference_addr) $fatal(1,"address NBA mismatch got=%0d expected=%0d",addr,reference_addr);
        if (dut.local_ce !== (system_clear||launch||rsp_fire)) $fatal(1,"CE primitive INIT mismatch");
        if (dut.local_increment !== (rsp_fire&&!system_clear)) $fatal(1,"increment primitive INIT mismatch");
        checks=checks+1;
    end
    task automatic tick(input bit s,l,r);
        @(negedge clk);system_clear=s;launch=l;rsp_fire=r;
        @(posedge clk);#2;
    endtask
    initial begin
        repeat(3) @(negedge clk);
        rst_n=1;
        // Exercise every 17-bit carry/wrap transition with real RTL and UNISIM LUTs.
        for(integer i=0;i<131072;i=i+1) tick(0,0,1);
        if(addr!==17'd0) $fatal(1,"17-bit wrap mismatch");
        for(integer s=0;s<2;s=s+1)
            for(integer l=0;l<2;l=l+1)
                for(integer r=0;r<2;r=r+1) begin
                    tick(0,1,0);
                    repeat(19) tick(0,0,1);
                    tick(s,l,r);
                    repeat(3) tick(0,0,0);
                end
        // Async reset must be visible before another core sampling edge.
        tick(0,0,1);
        @(negedge clk);#1;rst_n=0;#1;
        if(addr!==0) $fatal(1,"asynchronous reset mismatch");
        @(negedge clk);rst_n=1;system_clear=0;launch=0;rsp_fire=0;
        repeat(4) tick(0,0,0);
        if(checks<131072) $fatal(1,"address coverage incomplete");
        $display("M003_A3_HELPER_PASS");
        $finish;
    end
endmodule
