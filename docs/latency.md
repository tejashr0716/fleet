# Measurement notes

No former prototype's benchmark number is treated as verified for this rebuild. Do not relabel a target as a result.

`benchmark/ingest_load.py` runs sequential synthetic HTTP batches and records client-observed response times. It is a smoke probe, not a saturation/concurrency study. The rate is for that single-client workload, not maximum capacity. A 202 includes a completed PostgreSQL transaction but not completed viewer delivery.

`benchmark/e2e_latency.py` opens an authenticated WebSocket and measures from the same client's monotonic timestamp immediately before the HTTP submission until it observes the matching position frame. This includes HTTP admission, the worker and WebSocket handoff, but not browser rendering. It avoids subtracting unsynchronized server/client wall clocks.

`benchmark/query_bench.py` measures client HTTP history-response time on the current synthetic dataset. It does not claim raw SQL execution latency, a large data volume or a month-long history workload.

Every report records the probe type, sample count, batch size/workload, error count, elapsed duration, UTC run time, platform and raw timings. Small samples and shared build hardware cannot establish production p95/p99 guarantees. Results from the remote build environment are not measurements of Tejas's laptop. Re-run on the intended demo machine.

For a capacity claim, separately design a multi-client stepped workload with warm-up, a fixed dataset, CPU/memory observation, dependency versions, backlog tracking, request/position counts, error rates and recovery checks. That study has not been claimed here.
