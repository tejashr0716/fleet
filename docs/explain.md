# Inspect an actual history query plan

Do not copy a plausible-looking `EXPLAIN` output into a performance claim. Inspect the actual current dataset:

```sql
SELECT count(*) FROM fleet_v2.positions;
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM fleet_v2.positions
WHERE vehicle_id = 1
  AND recorded_at >= now() - interval '1 hour'
ORDER BY recorded_at DESC
LIMIT 200;
```

The unique `(vehicle_id, recorded_at)` constraint supplies a useful B-tree. A small seeded table can legitimately use a sequential scan; the planner is not wrong merely because an index exists. Report table size, query, hardware, cache state and actual timing before claiming an improvement. There are no Timescale hypertables, compression or continuous aggregates in this rebuild.
