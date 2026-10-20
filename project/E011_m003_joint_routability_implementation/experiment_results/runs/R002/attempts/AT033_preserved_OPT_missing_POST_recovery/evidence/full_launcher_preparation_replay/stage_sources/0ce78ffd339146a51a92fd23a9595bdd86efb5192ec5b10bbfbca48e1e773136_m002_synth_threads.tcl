# SM005 managed runs use one child, four threads; supervisor + child <=8 CPUs.
set_param general.maxThreads 4
puts {M002_SYNTH_CHILD_MAX_THREADS 4}
