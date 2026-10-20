# Vivado sets PYTHONHOME/PYTHONPATH for its own bundled interpreter. A separate
# system Python process must not consume them. Preserve the native Vivado env.
proc m003_python {args} {
    return [exec /usr/bin/env -u PYTHONHOME -u PYTHONPATH /usr/bin/python3 {*}$args]
}
