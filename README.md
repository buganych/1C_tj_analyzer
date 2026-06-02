# 1C Tech Journal Analyzers

Python tools for analyzing 1C tech journal lock events: TLOCK waits, TTIMEOUT, and TDEADLOCK cycles.

| Tool | Event | ClickHouse table | 
|------|-------|------------------|
| **`tj-analyzer`** | **all three** | all tables | 
| `tlock-analyzer` | TLOCK (wait) | `tj_tlock` | 
| `ttimeout-analyzer` | TTIMEOUT | `tj_ttimeout` | 
| `tdeadlock-analyzer` | TDEADLOCK | `tj_tdeadlock` | 

Shared code: `tj_common/` (lock comparison, sources, reports). TLOCK/TTIMEOUT share the victim→culprit pipeline; TDEADLOCK uses a separate cycle analyzer on `DeadlockConnectionIntersections`.

## Install

```bash
pip install -e ".[dev]"
```

Entry points: **`tj-analyzer`** (recommended), or `tlock-analyzer` / `ttimeout-analyzer` / `tdeadlock-analyzer`, or `python -m tj_analyzer`.

## Unified analyzer (one command)

Runs **TLOCK + TTIMEOUT + TDEADLOCK** with the same filters; one JSON/text report with summary counts.

```bash
python -m tj_analyzer --source click --log-id teletrade_tj_logs --output both

python -m tj_analyzer --source click --log-id teletrade_tj_logs --database UVI_UTD ^
  --from "2026-05-27 00:00:00" --to "2026-05-27 12:00:00"

python -m tj_analyzer --source plain --file tj.log --log-id my_stream --base-date "2026-05-27"

# Only specific analyzers
python -m tj_analyzer --source click --log-id X --only tlock,ttimeout

# TDEADLOCK options (optional)
python -m tj_analyzer --source click --log-id X --config-catalog D:/cfg_export
```

JSON root: `analyzer: "unified"`, sections `tlock`, `ttimeout`, `tdeadlock`, `summary`.

## TLOCK Analyzer

Primary filter: **`log_id`**. Optional: `--from`/`--to`, `--hosts`, `--database`.

```bash
python -m tlock_analyzer --source click --log-id teletrade_tj_logs --output both
```

```sql
SELECT DISTINCT log_id FROM onec_logs.tj_tlock WHERE wait_connections != '';
```

## TTIMEOUT Analyzer

Same CLI as TLOCK; victims from `tj_ttimeout`. Culprit TLOCK still from `tj_tlock`.

```bash
python -m ttimeout_analyzer --source click --log-id teletrade_tj_logs --output both
```

## TDEADLOCK Analyzer

Analyzes **deadlock cycles** (2–3 connections) from `DeadlockConnectionIntersections`, builds timeline, deadlock type, ASCII cross matrix, and JSON graphs (`graph_wait_block`, `graph_locks`).

**ClickHouse filters:** `--log-id` (required), optional `--database` (maps to `process_name`, AND).

```bash
python -m tdeadlock_analyzer --source click --log-id teletrade_tj_logs --output both

python -m tdeadlock_analyzer --source click --log-id teletrade_tj_logs --database UVI_UTD ^
  --from "2026-05-27 00:00:00" --to "2026-05-27 12:00:00"

# Single case (like ОбработатьЕдиничныйTDEADLOCKClick)
python -m tdeadlock_analyzer --source click --log-id teletrade_tj_logs ^
  --at "2026-05-27 10:54:35.123456" --connect-id 518868 --session-id 100 --host vTerm02

# Resolve context lines against exported configuration
python -m tdeadlock_analyzer --source click --log-id X --config-catalog D:/cfg_export --output json
```

```sql
SELECT count() FROM onec_logs.tj_tdeadlock WHERE log_id = 'teletrade_tj_logs';
SELECT DISTINCT log_id FROM onec_logs.tj_tdeadlock;
```

**Statuses:** `ok`, `incomplete_tx` (missing transaction bounds), `too_few_events` (timeline &lt; 8 events per BSL).

**Deadlock types:** «Повышение уровня блокировки в рамках одной транзакции», «Разный порядок захвата ресурсов».

## Tests

```bash
python -m pytest --ignore=tests/test_integration_ch.py --ignore=tests/test_integration_ch_ttimeout.py --ignore=tests/test_integration_ch_tdeadlock.py
python -m pytest -m integration
```

## Repository layout

```
tj_common/
  analysis/unified_pipeline.py
  report/unified.py
tj_analyzer/          # unified CLI
tlock_analyzer/
ttimeout_analyzer/
tdeadlock_analyzer/
tests/
```
