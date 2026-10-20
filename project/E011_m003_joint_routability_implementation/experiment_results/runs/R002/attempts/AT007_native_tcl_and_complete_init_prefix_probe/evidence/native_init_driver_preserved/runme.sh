#!/bin/bash

# 
# Vivado(TM)
# runme.sh: a Vivado-generated Runs Script for UNIX
# Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
# Copyright 2022-2025 Advanced Micro Devices, Inc. All Rights Reserved.
# 

if [ -z "$PATH" ]; then
  PATH=/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vitis/bin:/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/ids_lite/ISE/bin/lin64:/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin
else
  PATH=/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vitis/bin:/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/ids_lite/ISE/bin/lin64:/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin:$PATH
fi
export PATH

if [ -z "$LD_LIBRARY_PATH" ]; then
  LD_LIBRARY_PATH=
else
  LD_LIBRARY_PATH=:$LD_LIBRARY_PATH
fi
export LD_LIBRARY_PATH

HD_PWD='/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/hardware/vivado/reports/m003_E011_R002_AT007_native_tcl_and_complete_init_prefix_probe/native_project/type_probe.runs/impl_1'
cd "$HD_PWD"

HD_LOG=runme.log
/bin/touch $HD_LOG

ISEStep="./ISEWrap.sh"
EAStep()
{
     $ISEStep $HD_LOG "$@" >> $HD_LOG 2>&1
     if [ $? -ne 0 ]
     then
         exit
     fi
}

# pre-commands:
/bin/touch .init_design.begin.rst
EAStep vivado -log type_probe.vdi -applog -m64 -product Vivado -messageDb vivado.pb -mode batch -source type_probe.tcl -notrace


