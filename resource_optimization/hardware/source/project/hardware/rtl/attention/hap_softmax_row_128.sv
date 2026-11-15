`timescale 1ns / 1ps

module hap_softmax_row_128 (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  clear,
    input  wire                  in_valid,
    output wire                  in_ready,
    input  wire                  in_first_key,
    input  wire                  in_last_key,
    input  wire                  in_mask,
    input  wire signed [19:0]    in_score_q14_s20,
    output wire                  out_valid,
    input  wire                  out_ready,
    output wire [15:0]           out_prob_u16,
    output wire [6:0]            out_key_index,
    output wire                  out_last_key,
    output wire                  busy,
    output reg  [31:0]           input_score_count,
    output reg  [31:0]           output_prob_count,
    output reg  [31:0]           row_count,
    output reg                    error
);

    localparam [2:0] ST_LOAD       = 3'd0;
    localparam [2:0] ST_EXP        = 3'd1;
    localparam [2:0] ST_RECIP_REQ  = 3'd2;
    localparam [2:0] ST_RECIP_WAIT = 3'd3;
    localparam [2:0] ST_PROB       = 3'd4;
    localparam [2:0] ST_ERROR      = 3'd5;

    reg [2:0] state_r;
    (* ram_style = "distributed" *) reg signed [19:0] score_mem [0:127];
    (* ram_style = "distributed" *) reg mask_mem [0:127];
    (* ram_style = "distributed" *) reg [16:0] exp_mem [0:127];
    reg [6:0] load_index_r;
    reg [6:0] exp_issue_index_r;
    reg [7:0] exp_issue_count_r;
    reg [6:0] exp_receive_index_r;
    reg [7:0] exp_receive_count_r;
    reg [6:0] prob_issue_index_r;
    reg [7:0] prob_issue_count_r;
    reg [6:0] prob_output_index_r;
    reg [7:0] row_key_count_r;
    reg signed [19:0] row_max_s20_r;
    reg unmasked_seen_r;
    reg [23:0] row_sum_u24_r;
    reg [16:0] reciprocal_u17_r;

    wire in_fire = in_valid && in_ready;
    wire out_fire = out_valid && out_ready;

    wire exp_in_valid = (state_r == ST_EXP) &&
        (exp_issue_count_r < row_key_count_r);
    wire exp_in_ready;
    wire exp_out_valid;
    wire [16:0] exp_out_u17;
    wire [31:0] exp_input_count_unused;
    wire [31:0] exp_output_count_unused;
    wire exp_error;
    wire exp_in_fire = exp_in_valid && exp_in_ready;
    wire exp_out_fire = exp_out_valid;
    wire signed [20:0] exp_score_ext_s21 =
        {{1{score_mem[exp_issue_index_r][19]}}, score_mem[exp_issue_index_r]};
    wire signed [20:0] max_ext_s21 =
        {{1{row_max_s20_r[19]}}, row_max_s20_r};
    wire signed [20:0] exp_delta_s21 = exp_score_ext_s21 - max_ext_s21;
    reg signed [18:0] exp_delta_clipped_s19;

    wire recip_in_valid = (state_r == ST_RECIP_REQ);
    wire recip_in_ready;
    wire recip_out_valid;
    wire [16:0] recip_out_u17;
    wire [31:0] recip_input_count_unused;
    wire [31:0] recip_output_count_unused;
    wire recip_error;

    wire prob_in_valid = (state_r == ST_PROB) &&
        (prob_issue_count_r < row_key_count_r);
    wire prob_in_ready;
    wire prob_out_valid;
    wire [15:0] prob_out_u16;
    wire [31:0] prob_clamp_count_unused;
    wire prob_error;
    wire prob_in_fire = prob_in_valid && prob_in_ready;

    wire final_load_unmasked = unmasked_seen_r || !in_mask;
    wire [16:0] exp_effective_u17 = mask_mem[exp_receive_index_r] ?
        17'd0 : exp_out_u17;
    wire [23:0] row_sum_next_u24 = row_sum_u24_r +
        {7'd0, exp_effective_u17};

    assign in_ready = rst_n && !clear && (state_r == ST_LOAD);
    assign out_valid = rst_n && !clear && (state_r == ST_PROB) &&
        prob_out_valid;
    assign out_prob_u16 = prob_out_u16;
    assign out_key_index = prob_output_index_r;
    assign out_last_key =
        ({1'b0, prob_output_index_r} + 8'd1 == row_key_count_r);
    assign busy = state_r != ST_LOAD;

    always @* begin
        if (mask_mem[exp_issue_index_r])
            exp_delta_clipped_s19 = 19'sd0;
        else if (exp_delta_s21 > 0)
            exp_delta_clipped_s19 = 19'sd0;
        else if (exp_delta_s21 < -21'sd262144)
            exp_delta_clipped_s19 = -19'sd262144;
        else
            exp_delta_clipped_s19 = exp_delta_s21[18:0];
    end

    hap_softmax_exp_u17 u_exp (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(exp_in_valid), .in_ready(exp_in_ready),
        .in_delta_q14_s19(exp_delta_clipped_s19),
        .out_valid(exp_out_valid), .out_ready(1'b1),
        .out_exp_u17(exp_out_u17),
        .input_count(exp_input_count_unused),
        .output_count(exp_output_count_unused), .error(exp_error)
    );

    hap_softmax_recip_u17 u_recip (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(recip_in_valid), .in_ready(recip_in_ready),
        .in_row_sum_u24(row_sum_u24_r),
        .out_valid(recip_out_valid), .out_ready(1'b1),
        .out_recip_u17(recip_out_u17),
        .input_count(recip_input_count_unused),
        .output_count(recip_output_count_unused), .error(recip_error)
    );

    hap_softmax_prob_u16 u_prob (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(prob_in_valid), .in_ready(prob_in_ready),
        .in_exp_u17(exp_mem[prob_issue_index_r]),
        .in_recip_u17(reciprocal_u17_r),
        .out_valid(prob_out_valid),
        .out_ready((state_r == ST_PROB) && out_ready),
        .out_prob_u16(prob_out_u16),
        .clamp_count(prob_clamp_count_unused), .error(prob_error)
    );

    // Row memories do not require reset contents: the FSM writes every
    // addressed score/mask entry before ST_EXP reads it, and writes every
    // addressed exponential entry before ST_PROB reads it.  Keeping the RAM
    // writes in a resetless process allows Vivado to honor ram_style instead
    // of expanding all 4,864 payload bits into reset-controlled flip-flops.
    always @(posedge clk) begin
        if (in_fire) begin
            score_mem[load_index_r] <= in_score_q14_s20;
            mask_mem[load_index_r] <= in_mask;
        end
        if (exp_out_fire)
            exp_mem[exp_receive_index_r] <= exp_effective_u17;
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state_r <= ST_LOAD;
            load_index_r <= 7'd0;
            exp_issue_index_r <= 7'd0;
            exp_issue_count_r <= 8'd0;
            exp_receive_index_r <= 7'd0;
            exp_receive_count_r <= 8'd0;
            prob_issue_index_r <= 7'd0;
            prob_issue_count_r <= 8'd0;
            prob_output_index_r <= 7'd0;
            row_key_count_r <= 8'd128;
            row_max_s20_r <= -20'sd524288;
            unmasked_seen_r <= 1'b0;
            row_sum_u24_r <= 24'd0;
            reciprocal_u17_r <= 17'd0;
            input_score_count <= 32'd0;
            output_prob_count <= 32'd0;
            row_count <= 32'd0;
            error <= 1'b0;
        end else if (clear) begin
            state_r <= ST_LOAD;
            load_index_r <= 7'd0;
            exp_issue_index_r <= 7'd0;
            exp_issue_count_r <= 8'd0;
            exp_receive_index_r <= 7'd0;
            exp_receive_count_r <= 8'd0;
            prob_issue_index_r <= 7'd0;
            prob_issue_count_r <= 8'd0;
            prob_output_index_r <= 7'd0;
            row_key_count_r <= 8'd128;
            row_max_s20_r <= -20'sd524288;
            unmasked_seen_r <= 1'b0;
            row_sum_u24_r <= 24'd0;
            reciprocal_u17_r <= 17'd0;
            input_score_count <= 32'd0;
            output_prob_count <= 32'd0;
            row_count <= 32'd0;
            error <= 1'b0;
        end else begin
            if (exp_error || recip_error || prob_error) begin
                error <= 1'b1;
                state_r <= ST_ERROR;
            end
            case (state_r)
                ST_LOAD: begin
                    if (in_fire) begin
                        input_score_count <= input_score_count + 32'd1;
                        if (in_first_key != (load_index_r == 0))
                            error <= 1'b1;
                        if (load_index_r == 0) begin
                            unmasked_seen_r <= !in_mask;
                            row_max_s20_r <= in_mask ? -20'sd524288 :
                                in_score_q14_s20;
                        end else if (!in_mask) begin
                            unmasked_seen_r <= 1'b1;
                            if (!unmasked_seen_r ||
                                (in_score_q14_s20 > row_max_s20_r))
                                row_max_s20_r <= in_score_q14_s20;
                        end
                        if (in_last_key) begin
                            row_key_count_r <= {1'b0, load_index_r} + 8'd1;
                            load_index_r <= 7'd0;
                            if (!final_load_unmasked) begin
                                error <= 1'b1;
                                state_r <= ST_ERROR;
                            end else begin
                                exp_issue_index_r <= 7'd0;
                                exp_issue_count_r <= 8'd0;
                                exp_receive_index_r <= 7'd0;
                                exp_receive_count_r <= 8'd0;
                                row_sum_u24_r <= 24'd0;
                                state_r <= ST_EXP;
                            end
                        end else begin
                            load_index_r <= load_index_r + 1'b1;
                        end
                    end
                end
                ST_EXP: begin
                    if (exp_in_fire) begin
                        exp_issue_count_r <= exp_issue_count_r + 1'b1;
                        exp_issue_index_r <= exp_issue_index_r + 1'b1;
                        if (!mask_mem[exp_issue_index_r] &&
                            (exp_delta_s21 > 0))
                            error <= 1'b1;
                    end
                    if (exp_out_fire) begin
                        row_sum_u24_r <= row_sum_next_u24;
                        exp_receive_count_r <= exp_receive_count_r + 1'b1;
                        exp_receive_index_r <= exp_receive_index_r + 1'b1;
                        if (exp_receive_count_r + 8'd1 == row_key_count_r) begin
                            if (row_sum_next_u24 < 24'd65536) begin
                                error <= 1'b1;
                                state_r <= ST_ERROR;
                            end else begin
                                state_r <= ST_RECIP_REQ;
                            end
                        end
                    end
                end
                ST_RECIP_REQ: begin
                    if (recip_in_ready)
                        state_r <= ST_RECIP_WAIT;
                end
                ST_RECIP_WAIT: begin
                    if (recip_out_valid) begin
                        reciprocal_u17_r <= recip_out_u17;
                        prob_issue_index_r <= 7'd0;
                        prob_issue_count_r <= 8'd0;
                        prob_output_index_r <= 7'd0;
                        state_r <= ST_PROB;
                    end
                end
                ST_PROB: begin
                    if (prob_in_fire) begin
                        prob_issue_count_r <= prob_issue_count_r + 1'b1;
                        prob_issue_index_r <= prob_issue_index_r + 1'b1;
                    end
                    if (out_fire) begin
                        output_prob_count <= output_prob_count + 32'd1;
                        if (out_last_key) begin
                            row_count <= row_count + 32'd1;
                            prob_output_index_r <= 7'd0;
                            row_max_s20_r <= -20'sd524288;
                            unmasked_seen_r <= 1'b0;
                            state_r <= ST_LOAD;
                        end else begin
                            prob_output_index_r <= prob_output_index_r + 1'b1;
                        end
                    end
                end
                default: state_r <= ST_ERROR;
            endcase
        end
    end

endmodule
