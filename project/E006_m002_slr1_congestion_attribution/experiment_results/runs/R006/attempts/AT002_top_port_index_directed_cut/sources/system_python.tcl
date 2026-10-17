# Pure invocation helper. Applies only to isolated CPU evidence subprocesses.
# Vivado process environment and native design/constraints remain unchanged.
proc m002_system_python {args} {
    set command [list /usr/bin/env]
    foreach name {PYTHONHOME PYTHONPATH PYTHONPLATLIBDIR PYTHONUSERBASE LD_LIBRARY_PATH LD_PRELOAD TCL_LIBRARY TK_LIBRARY __PYVENV_LAUNCHER__} {
        lappend command -u $name
    }
    lappend command PYTHONNOUSERSITE=1 /usr/bin/python3
    return [exec {*}$command {*}$args]
}
