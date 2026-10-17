`timescale 1ns / 1ps

// Resource-folded S24 Q8.16 normalized Hadamard32 for the MLP input path.
// Butterfly arithmetic is bit-identical to hap_hadamard32_norm_stream.  Only
// four of the 32 S29xU14 normalization multiplies are issued per cycle; each
// multiplier maps to two DSP48E2 on VU9P, reducing the bank from 64 to 8 DSP.
module hap_mlp_hadamard32_s24_fold4 (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  clear,
    input  wire                  in_valid,
    output wire                  in_ready,
    input  wire [32*24-1:0]      in_s24,
    output wire                  out_valid,
    input  wire                  out_ready,
    output wire [32*27-1:0]      out_s27,
    output reg  [31:0]           input_group_count,
    output reg  [31:0]           output_group_count,
    output reg  [31:0]           saturation_count,
    output reg                   error
);
    localparam [13:0] INV_SQRT32_Q16=14'd11585;
    reg valid_s1,valid_s2,valid_s3,valid_s4,valid_s5;
    reg signed [24:0] data_s1[0:31];
    reg signed [25:0] data_s2[0:31];
    reg signed [26:0] data_s3[0:31];
    reg signed [27:0] data_s4[0:31];
    reg signed [28:0] data_s5[0:31];
    (* use_dsp="yes" *)reg signed [42:0] norm_product[0:3];
    reg norm_active_r,norm_capture_valid_r,out_valid_r;
    reg [5:0] issue_base_r,capture_base_r;
    reg [32*27-1:0] out_s27_r;
    wire in_fire=in_valid&&in_ready;
    wire out_fire=out_valid&&out_ready;
    wire pipeline_busy=valid_s1||valid_s2||valid_s3||valid_s4||valid_s5;
    assign in_ready=rst_n&&!clear&&!pipeline_busy&&!norm_active_r&&
        !norm_capture_valid_r&&!out_valid_r;
    assign out_valid=rst_n&&!clear&&out_valid_r;
    assign out_s27=out_s27_r;

    function automatic signed [26:0] round_sat_s43_to_s27;
        input signed [42:0] value;
        reg [43:0] magnitude,rounded_magnitude;
        reg signed [43:0] rounded_value;
        begin
            if(value<0)begin
                magnitude=-$signed({value[42],value});
                rounded_magnitude=(magnitude+44'd32768)>>16;
                rounded_value=-$signed(rounded_magnitude);
            end else begin
                magnitude={1'b0,value};
                rounded_magnitude=(magnitude+44'd32768)>>16;
                rounded_value=$signed(rounded_magnitude);
            end
            if(rounded_value>44'sd67108863)
                round_sat_s43_to_s27=27'sh3ff_ffff;
            else if(rounded_value< -44'sd67108864)
                round_sat_s43_to_s27=-27'sd67108864;
            else round_sat_s43_to_s27=rounded_value[26:0];
        end
    endfunction
    function automatic norm_saturates;
        input signed [42:0] value;
        reg [43:0] magnitude,rounded_magnitude;
        reg signed [43:0] rounded_value;
        begin
            if(value<0)begin
                magnitude=-$signed({value[42],value});
                rounded_magnitude=(magnitude+44'd32768)>>16;
                rounded_value=-$signed(rounded_magnitude);
            end else begin
                magnitude={1'b0,value};
                rounded_magnitude=(magnitude+44'd32768)>>16;
                rounded_value=$signed(rounded_magnitude);
            end
            norm_saturates=(rounded_value>44'sd67108863)||
                (rounded_value< -44'sd67108864);
        end
    endfunction

    integer lane,block_idx,offset;
    always @(posedge clk)begin
        if(in_fire)for(lane=0;lane<16;lane=lane+1)begin
            data_s1[2*lane]<=$signed(in_s24[(2*lane)*24+:24])+
                $signed(in_s24[(2*lane+1)*24+:24]);
            data_s1[2*lane+1]<=$signed(in_s24[(2*lane)*24+:24])-
                $signed(in_s24[(2*lane+1)*24+:24]);
        end
        if(valid_s1)for(block_idx=0;block_idx<8;block_idx=block_idx+1)
          for(offset=0;offset<2;offset=offset+1)begin
            data_s2[4*block_idx+offset]<=data_s1[4*block_idx+offset]+
                data_s1[4*block_idx+offset+2];
            data_s2[4*block_idx+offset+2]<=data_s1[4*block_idx+offset]-
                data_s1[4*block_idx+offset+2];
          end
        if(valid_s2)for(block_idx=0;block_idx<4;block_idx=block_idx+1)
          for(offset=0;offset<4;offset=offset+1)begin
            data_s3[8*block_idx+offset]<=data_s2[8*block_idx+offset]+
                data_s2[8*block_idx+offset+4];
            data_s3[8*block_idx+offset+4]<=data_s2[8*block_idx+offset]-
                data_s2[8*block_idx+offset+4];
          end
        if(valid_s3)for(block_idx=0;block_idx<2;block_idx=block_idx+1)
          for(offset=0;offset<8;offset=offset+1)begin
            data_s4[16*block_idx+offset]<=data_s3[16*block_idx+offset]+
                data_s3[16*block_idx+offset+8];
            data_s4[16*block_idx+offset+8]<=data_s3[16*block_idx+offset]-
                data_s3[16*block_idx+offset+8];
          end
        if(valid_s4)for(offset=0;offset<16;offset=offset+1)begin
            data_s5[offset]<=data_s4[offset]+data_s4[offset+16];
            data_s5[offset+16]<=data_s4[offset]-data_s4[offset+16];
        end
        if(norm_active_r)for(lane=0;lane<4;lane=lane+1)
            norm_product[lane]<=data_s5[issue_base_r+lane]*
                $signed({1'b0,INV_SQRT32_Q16});
        if(norm_capture_valid_r)for(lane=0;lane<4;lane=lane+1)
            out_s27_r[(capture_base_r+lane)*27+:27]<=
                round_sat_s43_to_s27(norm_product[lane]);
    end

    integer saturation_increment;
    always @(posedge clk or negedge rst_n)begin
      if(!rst_n)begin
        valid_s1<=0;valid_s2<=0;valid_s3<=0;valid_s4<=0;valid_s5<=0;
        norm_active_r<=0;norm_capture_valid_r<=0;out_valid_r<=0;
        issue_base_r<=0;capture_base_r<=0;input_group_count<=0;
        output_group_count<=0;saturation_count<=0;error<=0;
      end else if(clear)begin
        valid_s1<=0;valid_s2<=0;valid_s3<=0;valid_s4<=0;valid_s5<=0;
        norm_active_r<=0;norm_capture_valid_r<=0;out_valid_r<=0;
        issue_base_r<=0;capture_base_r<=0;input_group_count<=0;
        output_group_count<=0;saturation_count<=0;error<=0;
      end else begin
        valid_s1<=in_fire;valid_s2<=valid_s1;valid_s3<=valid_s2;
        valid_s4<=valid_s3;valid_s5<=valid_s4;
        if(in_fire)input_group_count<=input_group_count+1;
        if(valid_s5)begin norm_active_r<=1;issue_base_r<=0;end
        norm_capture_valid_r<=norm_active_r;
        if(norm_active_r)begin
          capture_base_r<=issue_base_r;
          if(issue_base_r==28)begin norm_active_r<=0;issue_base_r<=0;end
          else issue_base_r<=issue_base_r+4;
        end
        if(norm_capture_valid_r)begin
          saturation_increment=0;
          for(lane=0;lane<4;lane=lane+1)
            if(norm_saturates(norm_product[lane]))
              saturation_increment=saturation_increment+1;
          saturation_count<=saturation_count+saturation_increment;
          if(capture_base_r==28)out_valid_r<=1;
        end
        if(out_fire)begin out_valid_r<=0;output_group_count<=output_group_count+1;end
        if((valid_s5&&norm_active_r)||(out_valid_r&&norm_active_r))error<=1;
      end
    end
endmodule
