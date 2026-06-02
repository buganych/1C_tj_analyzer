---
name: tdeadlock-analyzer
description: ONLY 1C TDEADLOCK (deadlock cycles). Use tj-analyzer skill for ALL lock problems. Use this for TDEADLOCK-only tasks.
---

# TDEADLOCK Analyzer (1C) — только TDEADLOCK

## Routing

| User intent | Tool |
|-------------|------|
| **All** lock problems | `tj-analyzer` skill |
| **Only TDEADLOCK** | **`python -m tdeadlock_analyzer`** (this skill) |

Rule: [.cursor/rules/lock-analyzers.mdc](../../rules/lock-analyzers.mdc)

## When to use this skill

- Явно **взаимоблокировки** / `TDEADLOCK` / `DeadlockConnectionIntersections` / графы
- **Не** использовать для общего «найди все проблемы блокировок»

## Workflow

1. `pip install -e .`

2. ClickHouse:

   ```bash
   python -m tdeadlock_analyzer --source click --log-id <LOG_ID> --output both
   ```

   С фильтром базы (ProcessName):

   ```bash
   python -m tdeadlock_analyzer --source click --log-id <LOG_ID> --database UVI_UTD --output both
   ```

3. С исходниками конфигурации:

   ```bash
   python -m tdeadlock_analyzer --source click --log-id <LOG_ID> --config-catalog <CFG_DIR> --output json
   ```

4. Интерпретация:
   - `status`: `ok`, `incomplete_tx`, `too_few_events`
   - `deadlock_type`: повышение уровня / разный порядок захвата
   - `graphs.graph_wait_block`, `graphs.graph_locks`

## Do not

- Использовать `tlock-analyzer` для полного разбора цикла TDEADLOCK
- Путать с TTIMEOUT (таймаут ожидания, не цикл)

## Reference

- [README.md](../../README.md)
- BSL: `bmp/CommonModules/АнализВзаимоблокировок1C/Ext/Module.bsl` (`СтартКлик`)
