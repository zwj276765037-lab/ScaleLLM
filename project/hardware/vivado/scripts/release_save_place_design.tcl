# SPDX-License-Identifier: Apache-2.0
# Preserve this native physical stage before reports or callbacks.
set_param general.maxThreads $::env(HAP_JOBS)
write_checkpoint [file join $::env(HAP_REPORT_DIR) place_design.dcp]
