# Beast / FalkorDB — AMP-128 closure

Snapshot of the FalkorDB infrastructure on Beast (Hetzner M5, 135.181.161.131)
after AMP-128 closure (2026-05-05). The canonical files **on Beast** are the
authoritative copies — the files in this directory are a versioned snapshot for
review, audit, and reproducibility.

## Files

| File | Beast path | Purpose |
|------|------------|---------|
| `docker-compose.beast.snapshot.yml` | `/opt/amplified/docker-compose.yml` | Full Beast compose at AMP-128 closure point. The `falkordb` service block is the part that AMP-128 changed. |
| `99-falkordb.conf` | `/etc/sysctl.d/99-falkordb.conf` | Host sysctl: `vm.overcommit_memory=1`. Required for reliable BGSAVE fork(2) under memory pressure. |

The new APDS labeller pairs with this fix and lives in `../apds-labeller/`.

## What AMP-128 changed (vs pre-AMP-128 state)

### `falkordb` service in compose

| Knob | Pre-AMP-128 | AMP-128 | Why |
|------|-------------|---------|-----|
| `image` | `falkordb/falkordb:latest` | `falkordb/falkordb:v4.18.3` | Lock against silent upgrade by watchtower or manual pulls. |
| `--appendonly` | (default: `no`) | `yes` | Closes the AMP-110 silent-loss window. Without AOF, up to ~60s of writes live only in RAM. |
| `--appendfsync` | (n/a) | `everysec` | Caps write loss at <1s on any FalkorDB recycle. |
| `--auto-aof-rewrite-percentage` | (n/a) | `100` | Compact AOF when it doubles. |
| `--auto-aof-rewrite-min-size` | (n/a) | `64mb` | Minimum size before triggering rewrite. |
| `--save` | `3600 1`, `300 100`, `60 10000` | `900 1`, `300 10`, `60 1000` | Tighter RDB checkpointing. AOF is the primary durability layer; RDB is a fast-load fallback. |
| `--maxmemory` | `8gb` | `16gb` | Two-thirds of the 24G hard limit, leaves 8G COW headroom for BGSAVE. |
| `--maxmemory-policy` | `noeviction` | `noeviction` | Same. **Do not** set `allkeys-lru` on a graph DB — silent eviction breaks graph consistency. |
| `THREAD_COUNT` | `8` | `16` | Beast has 96 cores; raise FalkorDB's worker pool. |
| `CACHE_SIZE` | `64` | `50` | Slightly reduced (per-graph query plan cache). |
| `TIMEOUT_MAX` | (default) | `60000` | 60s max query time. |
| `TIMEOUT_DEFAULT` | (default `30000`) | `30000` | Same — explicit. |
| `QUERY_MEM_CAPACITY` | (default unlimited) | `1073741824` (1 GiB) | Cap per-query memory; surface OOM as an error rather than killing the module. |
| `DELTA_MAX_PENDING_CHANGES` | `10000` (default) | `1000` | Flushes the GraphBLAS delta matrix more often under streaming MERGE. The default is tuned for bulk loads. |
| `NODE_CREATION_BUFFER` | (default) | `16384` | Larger creation buffer reduces small-allocation churn. |
| `MAX_QUEUED_QUERIES` | `100` | `4096` | Real back-pressure: clients exceeding the queue get errors instead of FalkorDB hanging. Pairs with `store_with_retry`. |
| `healthcheck` | (none) | `redis-cli ping` 30s/10s/5/30s | Compose-level health for orchestrators. |
| `deploy.resources.limits.memory` | `16G` | `24G` | COW headroom for BGSAVE while maxmemory is 16G. |

### Host sysctl

`/etc/sysctl.d/99-falkordb.conf`:

```
vm.overcommit_memory=1
```

This is a Redis prerequisite for reliable `fork(2)` during BGSAVE on busy
hosts. Without it, BGSAVE can fail on a memory-pressured host and emit the
`WARNING Memory overcommit must be enabled!` line in `docker logs falkordb`.
Applied via:

```
sudo cp 99-falkordb.conf /etc/sysctl.d/99-falkordb.conf
sudo sysctl -p /etc/sysctl.d/99-falkordb.conf
```

## Recovery procedure if AOF retrofit goes wrong

A real production issue we hit during AMP-128 application: **Redis 8.x with
`--appendonly yes` and no existing AOF files ignores the existing `dump.rdb`
and starts with empty memory.** This is documented Redis behaviour but easy to
miss. The recovery requires a one-shot start with `--appendonly no`.

The procedure (with the volume's `dump.rdb` containing your data):

1. Snapshot current state aside (in case anything goes wrong).
2. Stop falkordb cleanly: `docker compose stop falkordb`.
3. (If `appendonlydir/` already exists and is empty, rename it aside.)
4. Restore the desired `dump.rdb` to the volume root if needed.
5. Edit compose to set `--appendonly no` (one knob).
6. `docker compose up -d falkordb` — recreates with new env. RDB loads.
7. Verify: `redis-cli GRAPH.QUERY business_knowledge 'MATCH (d:Document) RETURN count(d)'` returns expected count.
8. Runtime-enable AOF: `docker exec falkordb redis-cli CONFIG SET appendonly yes`.
   This triggers an immediate `BGREWRITEAOF`, which captures current memory
   into a fresh `appendonly.aof.1.base.rdb`. Wait for `aof_rewrite_in_progress=0`.
9. Edit compose back to `--appendonly yes`.
10. `docker compose up -d falkordb` — recreates with new env. This time Redis
    loads from AOF (because the manifest exists and points to a populated base).
    Boot log will show: `Reading RDB base file on AOF loading… RDB is base AOF`.

The retrofit is fully reversible — keep snapshots of `dump.rdb` and
`appendonlydir/` before each step.

## Acceptance criteria (AMP-128)

1. `docker logs falkordb 2>&1 | grep -c "WARNING Memory overcommit"` returns 0
   after sysctl applied.
2. Zero fresh-boot events in `docker logs falkordb` over a 30-min sustained
   MERGE run.
3. Verify-pass count: 100% of written docs present after the batch completes.
   `store_with_retry` allowed to fire ≤1% of the time as a safety net.
4. AOF file `/var/lib/falkordb/data/appendonlydir/appendonly.aof.*` exists and
   grows during the run.
5. `redis-cli INFO persistence` reports `aof_enabled:1` and `aof_last_status:ok`.

## What this does NOT fix

- The eleven 4.18.1 MERGE correctness bugs filed by a fuzzer 2026-04-29 (#1955,
  #1956, #1949, …). No upstream fix yet. Risk that v4.18.3 has them too —
  closure issue #1967 didn't list a changelog. Mitigation: `store_with_retry`'s
  read-back-after-write catches silent row-drops.
- The single-writer-per-graph bottleneck is architectural. Throughput ceiling
  stays in place; AMP-128 reduces *risk of loss*, not *throughput*.
- The strategic question of whether FalkorDB stays the canonical vault store
  long-term. Separate decision (alternatives research is in flight).

## Follow-up (not blocking AMP-128)

- Add `com.centurylinklabs.watchtower.enable=false` label to the falkordb
  service. Today the image is pinned, but the label adds a second line of
  defence so watchtower never pulls or recycles falkordb even by accident.
- Consider extracting the APDS labeller out of `/opt/amplified/apds/label/` on
  Beast and into a real repo (or under `02_build/apds/`). Right now Beast is
  the only home for that code.

---

*Devon-85d1 | 2026-05-05 | session devin-85d1c5d9cee24844adaa4187084c0e64 | AMP-128 closure*
