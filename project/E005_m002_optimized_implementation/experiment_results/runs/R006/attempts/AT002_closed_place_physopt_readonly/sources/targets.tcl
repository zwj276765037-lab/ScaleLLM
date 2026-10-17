set targets [list \
    [list {input} {scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute/u_attention/u_input_buffer} {scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute/u_attention/u_input_buffer/*u_capture_decode} {LUT6} {48} {256}] \
    [list {gate} {scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute/u_mlp/u_serial_command/u_gate_scheduler/u_projection_repack} {scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute/u_mlp/u_serial_command/u_gate_scheduler/u_projection_repack/*u_output_payload_ce} {LUT1} {16} {384}] \
    [list {down} {scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute/u_mlp/u_serial_command/u_down_scheduler/u_projection_repack} {scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute/u_mlp/u_serial_command/u_down_scheduler/u_projection_repack/*u_output_payload_ce} {LUT1} {16} {512}] \
]
set windows [list \
    [list {North} {Global} {3} {CLEL_R_X60Y239} {DSP_X64Y245}] \
    [list {North} {Global} {4} {CLEL_R_X60Y240} {BRAM_X68Y255}] \
    [list {North} {Global} {5} {CLEL_R_X48Y215} {CLEL_R_X63Y246}] \
    [list {North} {Global} {6} {CLEL_R_X27Y183} {CLEM_X57Y246}] \
    [list {South} {Global} {3} {CLEL_R_X65Y204} {CLEL_R_X68Y211}] \
    [list {South} {Global} {4} {CLEL_R_X57Y201} {CLEM_X65Y216}] \
    [list {South} {Global} {5} {CLEL_R_X47Y204} {CLEL_R_X62Y235}] \
    [list {South} {Global} {6} {CLEL_R_X27Y199} {CLEM_X57Y262}] \
    [list {East} {Global} {3} {CLEL_R_X63Y234} {LAG_LAG_X66Y241}] \
    [list {East} {Global} {4} {CLEL_R_X57Y228} {CLEM_X65Y243}] \
    [list {East} {Global} {5} {CLEL_R_X54Y234} {DSP_X69Y265}] \
    [list {East} {Global} {6} {CLEL_R_X30Y226} {DSP_X59Y285}] \
    [list {West} {Global} {3} {CLEL_R_X65Y269} {CLEL_R_X68Y276}] \
    [list {West} {Global} {4} {CLEL_R_X60Y262} {BRAM_X68Y275}] \
    [list {West} {Global} {5} {CLEL_R_X47Y245} {CLEL_R_X62Y276}] \
    [list {West} {Global} {6} {CLEL_R_X29Y219} {CLEL_R_X58Y282}] \
    [list {North} {Long} {3} {CLEM_X69Y200} {XIPHY_BYTE_L_X72Y195}] \
    [list {North} {Long} {4} {CLEL_R_X60Y193} {BRAM_X68Y205}] \
    [list {North} {Long} {5} {CLEL_R_X50Y184} {CLEM_X66Y215}] \
    [list {North} {Long} {6} {CLEL_R_X26Y180} {CLEM_X56Y243}] \
    [list {South} {Long} {3} {CLEL_R_X65Y206} {CLEL_R_X68Y213}] \
    [list {South} {Long} {4} {CLEL_R_X60Y201} {BRAM_X68Y215}] \
    [list {South} {Long} {5} {CLEL_R_X48Y200} {CLEL_R_X63Y231}] \
    [list {South} {Long} {6} {CLEL_R_X19Y770} {CLEL_R_X49Y833}] \
    [list {East} {Long} {3} {CLEL_R_X55Y236} {CLEL_R_X58Y243}] \
    [list {East} {Long} {4} {CLEM_X56Y228} {CLEL_R_X63Y243}] \
    [list {East} {Long} {5} {CLEL_R_X54Y234} {DSP_X69Y265}] \
    [list {East} {Long} {6} {CLEL_R_X24Y214} {CLEL_R_X54Y277}] \
    [list {West} {Long} {3} {CLEL_R_X68Y264} {HPIO_L_X71Y270}] \
    [list {West} {Long} {4} {CLEM_X59Y256} {LAG_LAG_X66Y271}] \
    [list {West} {Long} {5} {CLEL_R_X48Y241} {CLEL_R_X63Y272}] \
    [list {West} {Long} {6} {CLEL_R_X26Y219} {CLEM_X56Y282}] \
    [list {North} {Short} {3} {CLEL_R_X49Y131} {CLEL_R_X52Y138}] \
    [list {North} {Short} {4} {CLEL_R_X45Y169} {CLEL_R_X52Y184}] \
    [list {North} {Short} {5} {CLEL_R_X45Y256} {CLEM_X60Y287}] \
    [list {North} {Short} {6} {CLEL_R_X30Y228} {DSP_X59Y290}] \
    [list {South} {Short} {3} {CLEM_X64Y252} {LAG_LAG_X66Y259}] \
    [list {South} {Short} {4} {CLEM_X59Y254} {LAG_LAG_X66Y269}] \
    [list {South} {Short} {5} {CLEL_R_X44Y231} {CLEM_X59Y262}] \
    [list {South} {Short} {6} {CLEL_R_X31Y224} {CLEM_X61Y287}] \
    [list {East} {Short} {3} {CLEL_R_X63Y269} {LAG_LAG_X66Y276}] \
    [list {East} {Short} {4} {CLEM_X59Y268} {LAG_LAG_X66Y283}] \
    [list {East} {Short} {5} {CLEL_R_X44Y262} {CLEM_X59Y293}] \
    [list {East} {Short} {6} {CLEM_X33Y229} {CLEM_X63Y292}] \
    [list {West} {Short} {3} {CLEL_R_X44Y221} {CLEM_X48Y228}] \
    [list {West} {Short} {4} {CLEL_R_X62Y263} {DSP_X69Y275}] \
    [list {West} {Short} {5} {CLEL_R_X46Y247} {CLEM_X61Y278}] \
    [list {West} {Short} {6} {CLEM_X33Y219} {CLEM_X63Y282}] \
]
set reference_part {xcvu9p-flga2104-2L-e}
set placed_driver_sites [list {SLICE_X107Y376} {SLICE_X110Y419} {SLICE_X116Y257} {SLICE_X116Y265} {SLICE_X117Y136} {SLICE_X117Y143} {SLICE_X120Y131} {SLICE_X122Y133} {SLICE_X147Y710} {SLICE_X147Y726} {SLICE_X148Y705} {SLICE_X148Y706} {SLICE_X148Y717} {SLICE_X149Y706} {SLICE_X149Y719} {SLICE_X149Y724} {SLICE_X150Y718} {SLICE_X150Y724} {SLICE_X150Y725} {SLICE_X151Y718} {SLICE_X152Y732} {SLICE_X153Y703} {SLICE_X155Y702} {SLICE_X155Y703} {SLICE_X156Y745} {SLICE_X156Y746} {SLICE_X158Y745} {SLICE_X158Y747} {SLICE_X159Y745} {SLICE_X159Y747} {SLICE_X161Y735} {SLICE_X161Y745} {SLICE_X161Y746} {SLICE_X162Y745} {SLICE_X162Y747} {SLICE_X36Y457} {SLICE_X42Y455} {SLICE_X49Y439} {SLICE_X50Y216} {SLICE_X51Y444} {SLICE_X51Y448} {SLICE_X53Y430} {SLICE_X62Y214} {SLICE_X66Y430} {SLICE_X69Y427} {SLICE_X72Y427} {SLICE_X74Y201} {SLICE_X76Y239} {SLICE_X86Y426} {SLICE_X93Y376} {SLICE_X93Y459} {SLICE_X94Y361} {SLICE_X94Y493} {SLICE_X95Y360} {SLICE_X95Y366} {SLICE_X96Y357}]
