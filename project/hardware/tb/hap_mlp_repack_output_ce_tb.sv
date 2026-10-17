`timescale 1ns / 1ps

// Production parameters, two independent payload widths. No numeric rounding
// is performed by a repacker; the oracle queues accepted columns per matrix.
module m002_repack_ce_checker #(
    parameter integer DATA_W=32,
    parameter integer MATRICES=1
) (output reg done=0);
    localparam integer ROWS=16;
    localparam integer IW=ROWS*12*DATA_W;
    localparam integer OW=ROWS*16*DATA_W;
    reg clk=0;
    always #5 clk=~clk;
    reg rst_n=0, clear=0, in_valid=0, out_ready=0;
    reg [IW-1:0] in_data=0;
    reg [8:0] in_block=0;
    reg [1:0] in_pass=0;
    reg in_matrix=0;
    reg [11:0] in_mask=12'hfff;
    reg in_last=0;
    wire in_ready, out_valid, out_matrix, out_last, error;
    wire [OW-1:0] out_data;
    wire [8:0] out_block;
    wire [1:0] out_record;
    wire [15:0] out_mask;
    wire [31:0] input_count, output_count;
    wire ref_ready, ref_valid, ref_matrix, ref_last, ref_error;
    wire [OW-1:0] ref_data;
    wire [8:0] ref_block;
    wire [1:0] ref_record;
    wire [15:0] ref_mask;
    wire [31:0] ref_input_count,ref_output_count;

    generate
        if (DATA_W==32) begin : g_down
            hap_mlp_projection_repack12_to16_s32_history2 #(
                .ROWS(ROWS),.MATRICES(MATRICES),.TAG_W(9)) dut (
                .clk(clk),.rst_n(rst_n),.clear(clear),.in_valid(in_valid),
                .in_ready(in_ready),.in_projection_s32xrowsx12(in_data),
                .in_block_tag(in_block),.in_pass_index(in_pass),
                .in_matrix(in_matrix),.in_col_valid_u12(in_mask),.in_last_pass(in_last),
                .out_valid(out_valid),.out_ready(out_ready),
                .out_projection_s32xrowsx16(out_data),.out_block_tag(out_block),
                .out_record_index(out_record),.out_matrix(out_matrix),
                .out_col_valid_u16(out_mask),.out_last_record(out_last),
                .input_pass_count(input_count),.output_record_count(output_count),.error(error));
            hap_mlp_projection_repack12_to16_s32_history2_frozen #(
                .ROWS(ROWS),.MATRICES(MATRICES),.TAG_W(9)) original (
                .clk(clk),.rst_n(rst_n),.clear(clear),.in_valid(in_valid),
                .in_ready(ref_ready),.in_projection_s32xrowsx12(in_data),
                .in_block_tag(in_block),.in_pass_index(in_pass),
                .in_matrix(in_matrix),.in_col_valid_u12(in_mask),.in_last_pass(in_last),
                .out_valid(ref_valid),.out_ready(out_ready),
                .out_projection_s32xrowsx16(ref_data),.out_block_tag(ref_block),
                .out_record_index(ref_record),.out_matrix(ref_matrix),
                .out_col_valid_u16(ref_mask),.out_last_record(ref_last),
                .input_pass_count(ref_input_count),.output_record_count(ref_output_count),.error(ref_error));
        end else begin : g_gate
            hap_mlp_projection_repack12_to16_s24_history2 #(
                .ROWS(ROWS),.MATRICES(MATRICES),.TAG_W(9)) dut (
                .clk(clk),.rst_n(rst_n),.clear(clear),.in_valid(in_valid),
                .in_ready(in_ready),.in_projection_s24xrowsx12(in_data),
                .in_block_tag(in_block),.in_pass_index(in_pass),
                .in_matrix(in_matrix),.in_col_valid_u12(in_mask),.in_last_pass(in_last),
                .out_valid(out_valid),.out_ready(out_ready),
                .out_projection_s24xrowsx16(out_data),.out_block_tag(out_block),
                .out_record_index(out_record),.out_matrix(out_matrix),
                .out_col_valid_u16(out_mask),.out_last_record(out_last),
                .input_pass_count(input_count),.output_record_count(output_count),.error(error));
            hap_mlp_projection_repack12_to16_s24_history2_frozen #(
                .ROWS(ROWS),.MATRICES(MATRICES),.TAG_W(9)) original (
                .clk(clk),.rst_n(rst_n),.clear(clear),.in_valid(in_valid),
                .in_ready(ref_ready),.in_projection_s24xrowsx12(in_data),
                .in_block_tag(in_block),.in_pass_index(in_pass),
                .in_matrix(in_matrix),.in_col_valid_u12(in_mask),.in_last_pass(in_last),
                .out_valid(ref_valid),.out_ready(out_ready),
                .out_projection_s24xrowsx16(ref_data),.out_block_tag(ref_block),
                .out_record_index(ref_record),.out_matrix(ref_matrix),
                .out_col_valid_u16(ref_mask),.out_last_record(ref_last),
                .input_pass_count(ref_input_count),.output_record_count(ref_output_count),.error(ref_error));
        end
    endgenerate

    // This oracle is a column FIFO, not the DUT's previous-pass part-selects
    // or SRL history. Reset/clear invalidate FIFO state but preserve payload.
    reg [DATA_W-1:0] column_fifo [0:MATRICES-1][0:ROWS-1][0:47];
    integer fifo_columns [0:MATRICES-1];
    integer record_number [0:MATRICES-1];
    reg model_valid=0, model_error=0, model_active=0, model_has_payload=0;
    reg [OW-1:0] model_payload;
    reg [8:0] model_block, sequence_block=0;
    reg [1:0] model_record;
    reg model_matrix,model_last;
    reg [11:0] sequence_mask=0;
    reg sequence_last=0;
    integer next_token=0;
    integer model_inputs=0,model_outputs=0;
    integer cycles=0,diff_checks=0,oracle_outputs=0;
    integer simultaneous_replace=0,stall_cycles=0;
    integer reset_overlap=0,clear_overlap=0,error_cases=0;
    integer signed_high_lanes=0,tail4_cases=0,tail8_cases=0;
    integer saved_input_target;
    integer block_index,pass_index,matrix_index,terminal,abort_kind;
    integer mm,rr,cc,ncolumns,token,old_columns;
    reg mask_ok,order_ok,expect_ready,take_input,had_output;
    reg [31:0] rng=32'h762f914b ^ DATA_W;

    always @(posedge clk) begin
        cycles=cycles+1;
        ncolumns=0;
        for (cc=0;cc<12;cc=cc+1) ncolumns=ncolumns+in_mask[cc];
        mask_ok=(ncolumns!=0) && (in_mask==((1<<ncolumns)-1)) &&
            (in_last || ncolumns==12) && (in_pass!=3 || in_last);
        token=in_pass*MATRICES+in_matrix;
        order_ok=mask_ok && (in_matrix<MATRICES);
        if (model_active)
            order_ok=order_ok && token==next_token && in_block==sequence_block;
        else order_ok=order_ok && token==0;
        if (model_active && in_matrix!=0)
            order_ok=order_ok && in_mask==sequence_mask && in_last==sequence_last;
        expect_ready=(!model_valid || out_ready) && order_ok && !model_error;
        take_input=in_valid && expect_ready;
        had_output=model_valid;
        if (!rst_n || clear) begin
            if (take_input && ((fifo_columns[in_matrix]+ncolumns)>=16)) begin
                if (!rst_n) reset_overlap=reset_overlap+1;
                if (clear) clear_overlap=clear_overlap+1;
            end
            model_valid=0;model_error=0;model_active=0;
            model_inputs=0;model_outputs=0;next_token=0;
            sequence_mask=0;sequence_last=0;sequence_block=0;
            for (mm=0;mm<MATRICES;mm=mm+1) begin
                fifo_columns[mm]=0;record_number[mm]=0;
            end
        end else begin
            if (in_ready!==expect_ready)
                $fatal(1,"MLP%0d independent ready/order mismatch cycle=%0d",DATA_W,cycles);
            if (model_valid && !out_ready) stall_cycles=stall_cycles+1;
            if (model_valid && out_ready) model_valid=0;
            if (in_valid && (!had_output || out_ready) && !order_ok)
                model_error=1;
            if (take_input) begin
                model_inputs=model_inputs+1;
                if (!model_active) begin
                    sequence_block=in_block;
                    for (mm=0;mm<MATRICES;mm=mm+1) record_number[mm]=0;
                end
                old_columns=fifo_columns[in_matrix];
                for (rr=0;rr<ROWS;rr=rr+1)
                    for (cc=0;cc<ncolumns;cc=cc+1) begin
                        column_fifo[in_matrix][rr][old_columns+cc]=
                            in_data[(rr*12+cc)*DATA_W +: DATA_W];
                        if (in_data[(rr*12+cc)*DATA_W+DATA_W-1])
                            signed_high_lanes=signed_high_lanes+1;
                    end
                fifo_columns[in_matrix]=old_columns+ncolumns;
                if (fifo_columns[in_matrix]>=16) begin
                    for (rr=0;rr<ROWS;rr=rr+1) begin
                        for (cc=0;cc<16;cc=cc+1)
                            model_payload[(rr*16+cc)*DATA_W +:DATA_W]=column_fifo[in_matrix][rr][cc];
                        for (cc=16;cc<fifo_columns[in_matrix];cc=cc+1)
                            column_fifo[in_matrix][rr][cc-16]=column_fifo[in_matrix][rr][cc];
                    end
                    fifo_columns[in_matrix]=fifo_columns[in_matrix]-16;
                    model_valid=1;model_has_payload=1;
                    model_block=in_block;model_record=record_number[in_matrix];
                    model_matrix=in_matrix;model_last=in_last;
                    record_number[in_matrix]=record_number[in_matrix]+1;
                    model_outputs=model_outputs+1;oracle_outputs=oracle_outputs+1;
                    if (had_output && out_ready) simultaneous_replace=simultaneous_replace+1;
                end
                if (in_matrix==0) begin sequence_mask=in_mask;sequence_last=in_last;end
                if (in_matrix==MATRICES-1 && in_last) begin
                    model_active=0;next_token=0;
                    for (mm=0;mm<MATRICES;mm=mm+1)
                        if (fifo_columns[mm]!=0) model_error=1;
                end else begin model_active=1;next_token=token+1;end
            end
        end
        #1;
        if ({in_ready,out_valid,out_data,out_block,out_record,out_matrix,out_mask,
             out_last,input_count,output_count,error} !==
            {ref_ready,ref_valid,ref_data,ref_block,ref_record,ref_matrix,ref_mask,
             ref_last,ref_input_count,ref_output_count,ref_error})
            $fatal(1,"MLP%0d frozen-reference cycle mismatch cycle=%0d",DATA_W,cycles);
        if (out_valid!==model_valid || error!==model_error ||
            input_count!==model_inputs || output_count!==model_outputs || out_mask!==16'hffff)
            $fatal(1,"MLP%0d independent control/count/error mismatch cycle=%0d",DATA_W,cycles);
        if (model_has_payload && out_data!==model_payload)
            $fatal(1,"MLP%0d column FIFO oracle/hold mismatch cycle=%0d",DATA_W,cycles);
        if (model_valid && {out_block,out_record,out_matrix,out_last} !==
                           {model_block,model_record,model_matrix,model_last})
            $fatal(1,"MLP%0d independent metadata mismatch cycle=%0d",DATA_W,cycles);
        diff_checks=diff_checks+1;
    end

    task automatic tick;
        begin @(posedge clk);#2;end
    endtask
    task automatic clear_state;
        begin
            @(negedge clk);in_valid=0;clear=1;out_ready=0;
            tick();@(negedge clk);clear=0;tick();
        end
    endtask

    // Values distinguish every row/matrix/absolute source column and block.
    // Deliberately alternate sign bits; width truncation is the only cast.
    function automatic [DATA_W-1:0] lane(input integer b,input integer m,
                                        input integer row,input integer col);
        reg [31:0] value;
        begin
            value=32'hf18a3765 ^ b*32'h9e3779b1 ^ m*32'h7f4a7c15 ^
                row*32'h45d9f3b ^ col*32'h632be59b;
            lane=value[DATA_W-1:0];
        end
    endfunction

    task automatic drive_pass(input integer b,input integer p,input integer m,
                              input integer columns,input integer last_pass);
        integer row,col;
        begin
            in_block=b;in_pass=p;in_matrix=m;
            in_mask=(1<<columns)-1;in_last=last_pass;
            for (row=0;row<ROWS;row=row+1)
                for (col=0;col<12;col=col+1)
                    in_data[(row*12+col)*DATA_W +:DATA_W]=lane(b,m,row,p*12+col);
        end
    endtask

    task automatic send_pass(input integer b,input integer p,input integer m,
                             input integer columns,input integer last_pass,
                             input integer long_stall);
        integer t,wait_stall;
        reg [OW-1:0] held;
        reg [12:0] held_meta;
        reg held_valid;
        begin
            @(negedge clk);
            drive_pass(b,p,m,columns,last_pass);in_valid=1;
            rng=rng^(rng<<13);rng=rng^(rng>>17);rng=rng^(rng<<5);
            wait_stall=long_stall ? 211 : (rng & 7);
            out_ready=0;
            held=out_data;held_meta={out_block,out_record,out_matrix,out_last};
            held_valid=out_valid;
            repeat (wait_stall) begin
                tick();
                if (held_valid && (!out_valid || out_data!==held ||
                    {out_block,out_record,out_matrix,out_last}!==held_meta))
                    $fatal(1,"MLP payload/metadata changed under output stall");
                // The first offered pass may create an output in an empty
                // slot. Latch it once, then require valid/data/tag stability.
                if (!held_valid && out_valid) begin
                    held_valid=1;held=out_data;
                    held_meta={out_block,out_record,out_matrix,out_last};
                end
                // Stop offering immediately after its acceptance, preserving
                // ready/valid semantics while the output remains stalled.
                if (input_count!=model_inputs) $fatal(1,"MLP counter sampling error");
                if (in_valid && input_count==saved_input_target+1) begin
                    @(negedge clk);in_valid=0;
                end
            end
            @(negedge clk);out_ready=1;
            // With a zero-length stall it may already have fired at the
            // intervening posedge. Do not offer the same token twice.
            if (input_count==saved_input_target+1) in_valid=0;
            t=0;
            while (input_count!=saved_input_target+1) begin
                tick();t=t+1;
                if (t>10) $fatal(1,"MLP%0d legal input handshake timeout",DATA_W);
            end
            @(negedge clk);in_valid=0;
        end
    endtask

    task automatic offer(input integer b,input integer p,input integer m,
                         input integer columns,input integer last_pass,
                         input integer long_stall);
        begin
            saved_input_target=input_count;
            send_pass(b,p,m,columns,last_pass,long_stall);
        end
    endtask

    task automatic drain;
        begin
            @(negedge clk);in_valid=0;out_ready=1;
            repeat (3) tick();
            if (out_valid) $fatal(1,"MLP failed to drain output");
        end
    endtask

    task automatic malformed(input integer kind);
        begin
            clear_state();
            if (kind==3 || kind==4) offer(230+kind,0,0,12,0,0);
            if (kind==5 && MATRICES==2) offer(230+kind,0,0,12,0,0);
            @(negedge clk);out_ready=1;in_valid=1;
            drive_pass(230+kind,0,0,12,0);
            case (kind)
                0: in_pass=1;                         // first item out of order
                1: in_mask=12'h5;                     // non-contiguous mask
                2: in_mask=12'h0ff;                   // short non-terminal
                3: begin in_pass=1;in_block=9'd499;end // wrong block
                4: begin in_pass=1;in_matrix=1;end    // Down illegal matrix;
                                                      // Gate wrong pass order
                5: begin in_matrix=1;in_last=1;end    // Gate inconsistent pass
            endcase
            tick();
            if (!error || in_ready) $fatal(1,"MLP malformed case %0d not fail-closed",kind);
            @(negedge clk);in_valid=0;
            repeat (3) tick();
            if (!error) $fatal(1,"MLP error must be sticky until clear/reset");
            error_cases=error_cases+1;
        end
    endtask

    initial begin
        for (mm=0;mm<MATRICES;mm=mm+1) begin fifo_columns[mm]=0;record_number[mm]=0;end
        repeat (3) tick();@(negedge clk);rst_n=1;
        // 16, 32 and 48-column records exercise terminal4, terminal8 and
        // full terminal12, including all output record indices.
        for (block_index=0;block_index<18;block_index=block_index+1) begin
            terminal=1+block_index%3;
            for (pass_index=0;pass_index<=terminal;pass_index=pass_index+1)
                for (matrix_index=0;matrix_index<MATRICES;matrix_index=matrix_index+1) begin
                    offer(block_index,pass_index,matrix_index,
                          pass_index==terminal ? terminal*4 : 12,
                          pass_index==terminal,block_index%7==0);
                    if (pass_index==terminal && terminal==1) tail4_cases=tail4_cases+1;
                    if (pass_index==terminal && terminal==2) tail8_cases=tail8_cases+1;
                end
            drain();
            if (error) $fatal(1,"MLP normal transaction raised error");
        end
        // Force back-to-back output consume/refill at full throughput.
        clear_state();
        for (pass_index=0;pass_index<4;pass_index=pass_index+1)
            for (matrix_index=0;matrix_index<MATRICES;matrix_index=matrix_index+1) begin
                @(negedge clk);out_ready=1;in_valid=1;
                drive_pass(110,pass_index,matrix_index,12,pass_index==3);
                #1;if (!in_ready) $fatal(1,"MLP throughput input not ready");
                tick();
            end
        @(negedge clk);in_valid=0;drain();
        // Make a generating input ready on the exact reset/clear edge. Output
        // payload must hold even though the independently enabled SRL shifts.
        for (abort_kind=0;abort_kind<2;abort_kind=abort_kind+1) begin
            clear_state();
            for (matrix_index=0;matrix_index<MATRICES;matrix_index=matrix_index+1)
                offer(150+abort_kind,0,matrix_index,12,0,0);
            @(negedge clk);out_ready=1;in_valid=1;
            drive_pass(150+abort_kind,1,0,12,0);
            #1;if (!in_ready) $fatal(1,"MLP reset overlap did not have a qualified input");
            if (abort_kind==0) rst_n=0;else clear=1;
            tick();
            @(negedge clk);in_valid=0;rst_n=1;clear=0;
            tick();
            for (pass_index=0;pass_index<2;pass_index=pass_index+1)
                for (matrix_index=0;matrix_index<MATRICES;matrix_index=matrix_index+1)
                    offer(170+abort_kind,pass_index,matrix_index,
                          pass_index==1?4:12,pass_index==1,0);
            drain();
        end
        for (block_index=0;block_index<5;block_index=block_index+1) malformed(block_index);
        if (MATRICES==2) malformed(5);
        // Legal short terminal passes that leave residual columns are faults.
        for (block_index=1;block_index<=12;block_index=block_index+1) begin
            if (block_index!=4) begin
                clear_state();
                for (matrix_index=0;matrix_index<MATRICES;matrix_index=matrix_index+1)
                    offer(260+block_index,0,matrix_index,12,0,0);
                for (matrix_index=0;matrix_index<MATRICES;matrix_index=matrix_index+1)
                    offer(260+block_index,1,matrix_index,block_index,1,0);
                if (!error) $fatal(1,"MLP residual terminal columns must raise error");
                error_cases=error_cases+1;
            end
        end
        clear_state();
        if (oracle_outputs<30 || simultaneous_replace==0 || stall_cycles<211 ||
            reset_overlap==0 || clear_overlap==0 || tail4_cases==0 || tail8_cases==0 || signed_high_lanes==0)
            $fatal(1,"MLP%0d coverage incomplete",DATA_W);
        $display("MLP_CE_COVERAGE width=%0d matrices=%0d cycles=%0d diff=%0d oracle_outputs=%0d replace=%0d stalls=%0d reset_overlap=%0d clear_overlap=%0d errors=%0d tail4=%0d tail8=%0d signed_high_lanes=%0d",
                 DATA_W,MATRICES,cycles,diff_checks,oracle_outputs,simultaneous_replace,
                 stall_cycles,reset_overlap,clear_overlap,error_cases,tail4_cases,tail8_cases,signed_high_lanes);
        done=1;
    end

    initial begin
        repeat (100000) @(posedge clk);
        if (!done) $fatal(1,"MLP finite protocol/test-completion cycle budget exceeded");
    end
endmodule

module hap_mlp_repack_output_ce_tb;
    wire down_done,gate_done;
    m002_repack_ce_checker #(.DATA_W(32),.MATRICES(1)) down(.done(down_done));
    m002_repack_ce_checker #(.DATA_W(24),.MATRICES(2)) gate(.done(gate_done));
    initial begin
        wait (down_done && gate_done);
        $display("PASS: hap_mlp_repack_output_ce");
        $finish;
    end
endmodule
