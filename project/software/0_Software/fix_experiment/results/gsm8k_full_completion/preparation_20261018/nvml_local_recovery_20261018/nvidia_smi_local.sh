#!/usr/bin/env bash
set -euo pipefail
tool_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if ! /usr/bin/grep -q 'Kernel Module  580.159.03' /proc/driver/nvidia/version; then
  echo 'The loaded NVIDIA kernel version no longer matches this local tool.' >&2
  exit 1
fi
exec env LD_LIBRARY_PATH="$tool_dir/nvml_lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" "$tool_dir/extracted/nvidia-smi" "$@"
