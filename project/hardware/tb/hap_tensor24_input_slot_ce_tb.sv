`timescale 1ns / 1ps

// Frozen-original cycle equivalence plus an address-based independent oracle.
// Both physical waves retain production RAM/group/slot dimensions.
module hap_tensor24_input_slot_ce_tb;
    reg clk = 0;
    always #5 clk = ~clk;
    reg rst_n = 0, clear = 0, wr_valid = 0, load_start = 0;
    reg [12:0] wr_addr = 0;
    reg [255:0] wr_data = 0;
    reg activation_ready = 0;
    wire wr_ready, activation_valid, activation_wave, busy, error;
    wire [6:0] activation_group;
    wire [6143:0] activation_s24;
    wire ref_wr_ready, ref_valid, ref_wave, ref_busy, ref_error;
    wire [6:0] ref_group;
    wire [6143:0] ref_data;
    integer epoch = 0;
    integer cycles = 0, diff_checks = 0, slot_checks = 0;
    integer accepted = 0, expected_wave = 0, expected_group = 0;
    integer interruption_cases = 0, stall_checks = 0;
    integer last_slot_before = 0, last_slot_after = 0;
    integer valid_interrupts = 0, async_reset_cases = 0, boundary_interrupts = 0;
    integer test_wave, test_slot, test_reset, test_after;
    integer image_address, g, w;
    reg [31:0] random_state = 32'h83be219d;

    hap_tensor24_input_buffer16 dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .wr_valid(wr_valid), .wr_ready(wr_ready), .wr_addr(wr_addr),
        .wr_data(wr_data), .load_start(load_start),
        .activation_valid(activation_valid), .activation_ready(activation_ready),
        .activation_wave(activation_wave), .activation_group(activation_group),
        .activation_s24(activation_s24), .busy(busy), .error(error));
    hap_tensor24_input_buffer16_frozen ref_dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .wr_valid(wr_valid), .wr_ready(ref_wr_ready), .wr_addr(wr_addr),
        .wr_data(wr_data), .load_start(load_start),
        .activation_valid(ref_valid), .activation_ready(activation_ready),
        .activation_wave(ref_wave), .activation_group(ref_group),
        .activation_s24(ref_data), .busy(ref_busy), .error(ref_error));

    // Independent row-major DMA oracle: different words/address and epoch
    // complement exercise nonzero signed/high-bit payloads without DUT state.
    function automatic [255:0] beat_value(input integer ep, input integer addr);
        integer word_index;
        reg [31:0] v;
        begin
            for (word_index=0; word_index<8; word_index=word_index+1) begin
                v = 32'h6d92a357 ^ (addr * 32'h9e3779b1) ^
                    (word_index * 32'h7f4a7c15) ^ ((ep >> 1)*32'h45d9f3b);
                beat_value[word_index*32 +:32] = ep[0] ? ~v : v;
            end
        end
    endfunction

    task automatic check_group(input integer wave_index,
                               input integer group_index,
                               input [6143:0] data);
        integer slot_index, addr;
        begin
            for (slot_index=0; slot_index<24; slot_index=slot_index+1) begin
                // slot/3 is the source row, slot%3 the 256b row-group beat.
                addr = wave_index*3072 + (slot_index/3)*384 +
                    group_index*3 + slot_index%3;
                if (data[slot_index*256 +:256] !== beat_value(epoch,addr))
                    $fatal(1,"input oracle epoch=%0d wave=%0d group=%0d slot=%0d cycle=%0d",
                           epoch,wave_index,group_index,slot_index,cycles);
                slot_checks = slot_checks + 1;
            end
        end
    endtask

    // Sample accepted transactions before NBA; no TB/DUT drive race.
    always @(posedge clk) begin
        cycles = cycles + 1;
        if (!rst_n || clear) begin
            accepted = 0;
            expected_wave = 0;
            expected_group = 0;
        end else if (activation_valid && activation_ready) begin
            if (activation_wave !== expected_wave[0] ||
                activation_group !== expected_group[6:0])
                $fatal(1,"input accepted wave/group order mismatch");
            check_group(expected_wave,expected_group,activation_s24);
            accepted = accepted + 1;
            if (expected_group==127) begin
                expected_group = 0;
                expected_wave = 1-expected_wave;
            end else expected_group = expected_group+1;
        end
        #1;
        if ({wr_ready,activation_valid,activation_wave,activation_group,
             activation_s24,busy,error} !==
            {ref_wr_ready,ref_valid,ref_wave,ref_group,ref_data,ref_busy,ref_error})
            $fatal(1,"input frozen-reference external cycle mismatch cycle=%0d",cycles);
        // Check each bank even while wave1 is held behind all 128 wave0 groups.
        if ({dut.wave0_valid,dut.wave0_group,dut.wave0_s24,
             dut.wave1_valid,dut.wave1_group,dut.wave1_s24} !==
            {ref_dut.wave0_valid,ref_dut.wave0_group,ref_dut.wave0_s24,
             ref_dut.wave1_valid,ref_dut.wave1_group,ref_dut.wave1_s24})
            $fatal(1,"input frozen-reference private-wave mismatch cycle=%0d",cycles);
        diff_checks = diff_checks+1;
        if (rst_n && !clear) begin
            if (dut.wave0_valid) check_group(0,dut.wave0_group,dut.wave0_s24);
            if (dut.wave1_valid) check_group(1,dut.wave1_group,dut.wave1_s24);
        end
    end

    task automatic tick;
        begin @(posedge clk); #2; end
    endtask

    task automatic pulse_clear;
        begin
            @(negedge clk); clear=1; activation_ready=0;
            tick();
            @(negedge clk); clear=0;
            tick();
            if (busy || activation_valid || error)
                $fatal(1,"input clear did not revoke state");
        end
    endtask

    task automatic fill_image;
        integer a;
        begin
            for (a=0; a<6144; a=a+1) begin
                @(negedge clk);
                wr_addr=a; wr_data=beat_value(epoch,a); wr_valid=1;
                #1;
                if (!wr_ready) $fatal(1,"input write not ready addr=%0d",a);
                tick();
            end
            @(negedge clk); wr_valid=0;
        end
    endtask

    task automatic start_load;
        begin
            @(negedge clk); load_start=1;
            tick();
            @(negedge clk); load_start=0;
        end
    endtask

    task automatic await_both_first;
        integer t;
        begin
            t=0;
            while (!(dut.wave0_valid && dut.wave1_valid)) begin
                tick(); t=t+1;
                if (t>40) $fatal(1,"input first dual group timeout");
            end
            if (dut.wave0_group!=0 || dut.wave1_group!=0)
                $fatal(1,"input fresh epoch did not begin at group zero");
            check_group(0,0,dut.wave0_s24);
            check_group(1,0,dut.wave1_s24);
        end
    endtask

    task automatic drain_full_image;
        integer wave_index,group_index,t,stall;
        reg [6143:0] held;
        begin
            for (wave_index=0; wave_index<2; wave_index=wave_index+1)
                for (group_index=0; group_index<128; group_index=group_index+1) begin
                    t=0;
                    while (!activation_valid) begin
                        tick(); t=t+1;
                        if (t>40) $fatal(1,"input group timeout");
                    end
                    random_state = random_state ^ (random_state<<13);
                    random_state = random_state ^ (random_state>>17);
                    random_state = random_state ^ (random_state<<5);
                    stall = (group_index%31==0) ? 257 : (random_state & 7);
                    held=activation_s24;
                    repeat (stall) begin
                        tick();
                        if (!activation_valid || activation_wave!==wave_index[0] ||
                            activation_group!==group_index[6:0] || activation_s24!==held)
                            $fatal(1,"input changed during short/long stall");
                        stall_checks=stall_checks+1;
                    end
                    @(negedge clk); activation_ready=1;
                    tick();
                    @(negedge clk); activation_ready=0;
                end
            tick();
            if (busy || error || accepted!=256)
                $fatal(1,"input complete image did not retire 256 clean groups");
        end
    endtask

    task automatic interrupt_slot(input integer wave_index,
                                   input integer slot_index,
                                   input integer use_reset,
                                   input integer after_write);
        integer t;
        reg selected;
        reg [6143:0] held0,held1;
        begin
            t=0; selected=0;
            // At a negedge, the selected slot will be captured next posedge.
            while (!selected) begin
                @(negedge clk);
                if (wave_index==0)
                    selected=dut.u_wave0.active_r && !dut.wave0_valid &&
                        dut.u_wave0.read_stage_valid_r &&
                        dut.u_wave0.capture_index_r==slot_index;
                else
                    selected=dut.u_wave1.active_r && !dut.wave1_valid &&
                        dut.u_wave1.read_stage_valid_r &&
                        dut.u_wave1.capture_index_r==slot_index;
                t=t+1;
                if (t>40) $fatal(1,"input capture slot was not reached");
            end
            if (after_write) begin tick(); @(negedge clk); end
            held0=dut.wave0_s24; held1=dut.wave1_s24;
            if ((wave_index==0 && dut.wave0_valid) ||
                (wave_index==1 && dut.wave1_valid)) valid_interrupts=valid_interrupts+1;
            if (slot_index==23 && after_write) last_slot_after=last_slot_after+1;
            if (slot_index==23 && !after_write) last_slot_before=last_slot_before+1;
            if (use_reset) begin
                rst_n=0;
                async_reset_cases=async_reset_cases+1;
                #1;
                if (dut.wave0_s24!==6144'd0 || dut.wave1_s24!==6144'd0)
                    $fatal(1,"input async payload reset lost");
            end else clear=1;
            tick();
            if (!use_reset && (dut.wave0_s24!==held0 || dut.wave1_s24!==held1))
                $fatal(1,"input clear must hold every payload slot");
            @(negedge clk); rst_n=1; clear=0;
            tick();
            if (busy || activation_valid || error)
                $fatal(1,"input interrupt did not revoke old epoch");
            interruption_cases=interruption_cases+1;
        end
    endtask

    task automatic interrupt_wave_boundary(input integer use_reset);
        integer group_index,t;
        begin
            pulse_clear();start_load();
            for (group_index=0;group_index<127;group_index=group_index+1) begin
                t=0;
                while (!activation_valid) begin
                    tick();t=t+1;
                    if (t>40) $fatal(1,"input boundary preparation timeout");
                end
                @(negedge clk);activation_ready=1;
                tick();@(negedge clk);activation_ready=0;
            end
            t=0;
            while (!activation_valid) begin
                tick();t=t+1;
                if (t>40) $fatal(1,"input final-wave0 group timeout");
            end
            if (activation_wave || activation_group!=127)
                $fatal(1,"input boundary interrupt did not hit wave0/group127");
            repeat (301) tick();
            @(negedge clk);
            if (use_reset) begin rst_n=0;async_reset_cases=async_reset_cases+1;end
            else clear=1;
            tick();
            @(negedge clk);rst_n=1;clear=0;
            tick();
            if (busy || activation_valid || error)
                $fatal(1,"input wave-boundary interrupt retained old qualification");
            boundary_interrupts=boundary_interrupts+1;
            epoch=epoch+1;fill_image();start_load();drain_full_image();
        end
    endtask

    initial begin
        repeat (3) tick();
        @(negedge clk); rst_n=1;
        fill_image(); start_load(); drain_full_image();
        // Every slot of each wave, reset and clear, immediately before and
        // after capture. Each interruption is followed by a new full DMA image
        // with epoch-complemented data, then both first groups are validated.
        for (test_wave=0; test_wave<2; test_wave=test_wave+1)
            for (test_slot=0; test_slot<24; test_slot=test_slot+1)
                for (test_reset=0; test_reset<2; test_reset=test_reset+1)
                    for (test_after=0; test_after<2; test_after=test_after+1) begin
                        pulse_clear(); start_load();
                        interrupt_slot(test_wave,test_slot,test_reset,test_after);
                        epoch=epoch+1;
                        fill_image(); start_load(); await_both_first();
                        repeat (17) tick();
                    end
        // Interrupt an already valid long-stalled pair and replace its image.
        repeat (301) tick(); pulse_clear(); epoch=epoch+1;
        fill_image(); start_load(); drain_full_image();
        interrupt_wave_boundary(0);interrupt_wave_boundary(1);
        if (interruption_cases!=192 || last_slot_before!=4 || last_slot_after!=4 ||
            valid_interrupts!=4 || async_reset_cases!=97 || boundary_interrupts!=2 ||
            stall_checks<2570 || slot_checks==0)
            $fatal(1,"input coverage incomplete");
        $display("INPUT_CE_COVERAGE cycles=%0d diff=%0d slots=%0d interruptions=%0d stalls=%0d epochs=%0d full_images=4 last_slot_before=%0d last_slot_after=%0d valid_interrupts=%0d async_reset_cases=%0d boundary_interrupts=%0d",
                 cycles,diff_checks,slot_checks,interruption_cases,stall_checks,epoch+1,
                 last_slot_before,last_slot_after,valid_interrupts,async_reset_cases,boundary_interrupts);
        $display("PASS: hap_tensor24_input_slot_ce");
        $finish;
    end

    initial begin
        repeat (2000000) @(posedge clk);
        $fatal(1,"input finite protocol/test-completion cycle budget exceeded");
    end
endmodule
