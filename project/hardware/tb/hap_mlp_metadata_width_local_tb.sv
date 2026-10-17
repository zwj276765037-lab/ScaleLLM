`timescale 1ns/1ps

module hap_mlp_metadata_width_local_tb;
    localparam integer G=229376,D=114688;
    reg clk=0,rst_n=0,clear=0;
    always #5 clk=~clk;
    reg load_begin_valid=0,load_begin_bank=0;
    wire load_begin_ready;
    reg gate_wr_valid=0,down_wr_valid=0,gate_wr_bank=0,down_wr_bank=0;
    reg [17:0] gate_wr_addr=0;
    reg [16:0] down_wr_addr=0;
    reg [223:0] gate_wr_data=0,down_wr_data=0;
    wire gate_wr_ready,down_wr_ready;
    reg commit_valid=0,commit_bank=0,consumer_quiescent=1;
    reg [31:0] commit_generation=0;
    wire commit_ready,active_bank;
    wire [31:0] active_generation;
    wire [1:0] bank_valid,bank_loading;
    reg gate_rd_valid=0,down_rd_valid=0;
    reg [17:0] gate_rd_addr=0;
    reg [16:0] down_rd_addr=0;
    wire gate_rd_ready,down_rd_ready,gate_rsp_valid,down_rsp_valid;
    reg gate_rsp_ready=0,down_rsp_ready=0;
    wire [223:0] gate_rsp_data,down_rsp_data;
    wire [31:0] gw0,gw1,dw0,dw1,gr,dr;
    wire error;
    integer cycles=0,qhead=0,qtail=0,peak=0,last_issue=-1,last_response=-1;
    integer first_latency=-1,ii_pairs=0,last_write_cycle=0;
    integer expected_addr[0:G-1],request_cycle[0:G-1];
    reg [31:0] expected_generation=0;
    reg check_ii=0,stream_down=0;
    reg [223:0] stalled_data;
    reg stalled_valid=0;

    hap_mlp_weight_meta_resident_ab dut (
        .clk(clk),.rst_n(rst_n),.clear(clear),
        .load_begin_valid(load_begin_valid),.load_begin_ready(load_begin_ready),
        .load_begin_bank(load_begin_bank),
        .gate_wr_valid(gate_wr_valid),.gate_wr_ready(gate_wr_ready),
        .gate_wr_bank(gate_wr_bank),.gate_wr_addr(gate_wr_addr),
        .gate_wr_meta_u224(gate_wr_data),
        .down_wr_valid(down_wr_valid),.down_wr_ready(down_wr_ready),
        .down_wr_bank(down_wr_bank),.down_wr_addr(down_wr_addr),
        .down_wr_meta_u224(down_wr_data),
        .commit_valid(commit_valid),.commit_ready(commit_ready),
        .commit_bank(commit_bank),.commit_generation(commit_generation),
        .consumer_quiescent(consumer_quiescent),.active_bank(active_bank),
        .active_generation(active_generation),.bank_valid(bank_valid),
        .bank_loading(bank_loading),
        .gate_rd_valid(gate_rd_valid),.gate_rd_ready(gate_rd_ready),
        .gate_rd_addr(gate_rd_addr),.gate_rsp_valid(gate_rsp_valid),
        .gate_rsp_ready(gate_rsp_ready),.gate_rsp_meta_u224(gate_rsp_data),
        .down_rd_valid(down_rd_valid),.down_rd_ready(down_rd_ready),
        .down_rd_addr(down_rd_addr),.down_rsp_valid(down_rsp_valid),
        .down_rsp_ready(down_rsp_ready),.down_rsp_meta_u224(down_rsp_data),
        .gate_write_count_bank0(gw0),.gate_write_count_bank1(gw1),
        .down_write_count_bank0(dw0),.down_write_count_bank1(dw1),
        .gate_read_count(gr),.down_read_count(dr),.error(error)
    );

    function automatic [223:0] payload(input integer addr,input bit down,
                                       input [31:0] generation);
        integer k;
        begin
            for(k=0;k<7;k=k+1)
                payload[k*32+:32]=(32'h9e3779b9*(k+1)) ^
                    (32'h85ebca6b*addr) ^ generation ^ (down?32'hd00d1234:32'h671234ab);
        end
    endfunction
    function automatic integer address(input integer index,input bit down,input bit boundary);
        begin
            if(!boundary) address=index;
            else case(index%4)
                0: address=0;
                1: address=16383;
                2: address=16384;
                3: address=down?D-1:G-1;
            endcase
        end
    endfunction
    task automatic require(input bit condition,input string message);
        if(condition!==1'b1) $fatal(1,"%s cycle=%0d",message,cycles);
    endtask
    task tick; begin @(posedge clk);#1;end endtask
    task automatic begin_load(input bit bank);
        begin
            @(negedge clk);load_begin_bank=bank;load_begin_valid=1;
            #1;require(load_begin_ready,"load begin blocked");tick();
            @(negedge clk);load_begin_valid=0;
        end
    endtask
    task automatic fill_bank(input bit bank,input [31:0] generation);
        integer i;
        begin
            begin_load(bank);
            for(i=0;i<G;i=i+1) begin
                @(negedge clk);
                gate_wr_bank=bank;gate_wr_valid=1;gate_wr_addr=i;
                gate_wr_data=payload(i,0,generation);
                down_wr_bank=bank;down_wr_valid=i<D;down_wr_addr=i;
                down_wr_data=payload(i,1,generation);
                #1;require(gate_wr_ready,"gate write II1 lost");
                if(i<D) require(down_wr_ready,"down write II1 lost");
                tick();
                require((bank?gw1:gw0)==i+1,"gate accepted count changed");
                require((bank?dw1:dw0)==(i<D?i+1:D),"down accepted count changed");
            end
            last_write_cycle=cycles;
        end
    endtask
    task automatic commit_image(input bit bank,input [31:0] generation);
        bit fire;
        integer delay;
        begin
            @(negedge clk);gate_wr_valid=0;down_wr_valid=0;
            commit_bank=bank;commit_generation=generation;commit_valid=1;
            fire=0;
            while(!fire) begin
                @(posedge clk);fire=commit_ready;#1;
                require(cycles-last_write_cycle<=3,"commit drain exceeded budget");
            end
            delay=cycles-last_write_cycle;
            require(delay>=1&&delay<=2,"commit landing latency outside baseline/candidate budget");
            require(active_bank==bank&&active_generation==generation,"commit identity mismatch");
            $display("META_COMMIT bank=%0d final_write_to_commit=%0d",bank,delay);
            expected_generation=generation;
            @(negedge clk);commit_valid=0;
        end
    endtask
    task automatic run_stream(input bit down,input integer n,input bit boundary,input bit stall);
        integer i,elapsed,frozen;
        bit fire;
        begin
            qhead=0;qtail=0;peak=0;last_issue=-1;last_response=-1;
            first_latency=-1;ii_pairs=0;check_ii=!stall;stream_down=down;
            stalled_valid=0;i=0;elapsed=0;frozen=-1;
            while(i<n) begin
                @(negedge clk);
                gate_rd_valid=!down;down_rd_valid=down;
                gate_rd_addr=address(i,down,boundary);down_rd_addr=address(i,down,boundary);
                gate_rsp_ready=!down&&(!stall||elapsed>=24);
                down_rsp_ready=down&&(!stall||elapsed>=24);
                @(posedge clk);fire=down?down_rd_ready:gate_rd_ready;#1;
                if(fire)i=i+1;
                if(stall&&elapsed==16) frozen=qtail;
                if(stall&&elapsed==23) begin
                    require(qtail==frozen,"read issued after credits exhausted");
                    require(qtail>=3&&qtail<=4,"long-stall credit capacity outside budget");
                end
                elapsed=elapsed+1;
            end
            @(negedge clk);gate_rd_valid=0;down_rd_valid=0;
            gate_rsp_ready=!down;down_rsp_ready=down;
            while(qhead<n) tick();
            require(qhead==n&&qtail==n,"response count mismatch");
            if(!stall) begin
                require(ii_pairs==n-1,"continuous read II1 mismatch");
                require(first_latency>=2&&first_latency<=3,"first read latency outside one-stage budget");
            end
            $display("META_STREAM down=%0d bank=%0d n=%0d stall=%0d latency=%0d ii_pairs=%0d peak_credits=%0d cycles=%0d",
                down,active_bank,n,stall,first_latency,ii_pairs,peak,elapsed);
            @(negedge clk);gate_rsp_ready=0;down_rsp_ready=0;check_ii=0;stalled_valid=0;
        end
    endtask

    always @(posedge clk) begin : scoreboard
        bit req,rsp,valid,ready;
        reg [223:0] data;
        cycles=cycles+1;
        if(cycles>3000000) $fatal(1,"metadata test timeout");
        if(rst_n&&!clear) begin
            req=stream_down?(down_rd_valid&&down_rd_ready):(gate_rd_valid&&gate_rd_ready);
            valid=stream_down?down_rsp_valid:gate_rsp_valid;
            ready=stream_down?down_rsp_ready:gate_rsp_ready;
            data=stream_down?down_rsp_data:gate_rsp_data;
            rsp=valid&&ready;
            if(stalled_valid) require(valid&&data===stalled_data,"stalled response changed");
            stalled_valid=valid&&!ready;stalled_data=data;
            if(req) begin
                expected_addr[qtail]=stream_down?down_rd_addr:gate_rd_addr;
                request_cycle[qtail]=cycles;qtail=qtail+1;
                if(check_ii&&last_issue>=0) begin
                    require(cycles-last_issue==1,"continuous issue gap");ii_pairs=ii_pairs+1;
                end
                last_issue=cycles;
            end
            if(rsp) begin
                require(qhead<qtail,"unreserved response");
                require(data===payload(expected_addr[qhead],stream_down,expected_generation),
                    "full224-bit payload/order/generation mismatch");
                if(qhead==0)first_latency=cycles-request_cycle[qhead];
                if(check_ii&&last_response>=0) require(cycles-last_response==1,"continuous return gap");
                last_response=cycles;qhead=qhead+1;
            end
            if(qtail-qhead>peak)peak=qtail-qhead;
            require(qtail-qhead<=4,"response credits exceeded budget");
        end else begin
            qhead=0;qtail=0;stalled_valid=0;
        end
    end

    initial begin
        repeat(4)tick();@(negedge clk);rst_n=1;tick();
        fill_bank(1,32'h11335577);commit_image(1,32'h11335577);
        run_stream(0,G,0,0);run_stream(1,D,0,0);
        run_stream(0,64,1,1);run_stream(1,64,1,1);
        require(!error,"unexpected first image error");
        fill_bank(0,32'hf1e2d3c4);commit_image(0,32'hf1e2d3c4);
        run_stream(0,G,0,0);run_stream(1,D,0,0);
        require(gr==2*G+64&&dr==2*D+64,"full-depth delivery counters mismatch");
        require(!error,"unexpected second image error");

        // Cancel both a forward request and a held response without resetting payload.
        stream_down=0;qhead=0;qtail=0;
        @(negedge clk);gate_rd_valid=1;gate_rd_addr=16384;
        tick();@(negedge clk);gate_rd_addr=G-1;tick();
        @(negedge clk);gate_rd_valid=0;clear=1;#1;
        require(!gate_rsp_valid&&!down_rsp_valid,"clear exposes old valid");tick();
        @(negedge clk);clear=0;
        repeat(6)begin tick();require(!gate_rsp_valid&&!down_rsp_valid&&!gate_rd_ready,
            "old response leaked after clear");end
        require(bank_valid==0&&gr==0&&dr==0,"clear counters/validity mismatch");

        begin_load(1);
        @(negedge clk);gate_wr_bank=1;gate_wr_addr=0;gate_wr_valid=1;
        gate_wr_data=payload(0,0,32'habcdef01);tick();
        @(negedge clk);gate_wr_valid=0;clear=1;tick();
        @(negedge clk);clear=0;repeat(4)tick();
        require(bank_valid==0&&bank_loading==0&&gw1==0&&!commit_ready,
            "clear did not cancel pending write publication");
        require(!error,"clear did not reset error");
        $display("PASS hap_mlp_metadata_width_local");
        $finish;
    end
endmodule
