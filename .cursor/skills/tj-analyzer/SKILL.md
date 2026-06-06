---
name: tj-analyzer
description: Unified 1C lock analysis — use when user wants ALL lock problems (TLOCK+TTIMEOUT+TDEADLOCK) or does not specify type. Use separate skills for single-type tasks.
---

# TJ Analyzer (unified)

## Routing (read first)

| User intent | Tool |
|-------------|------|
| All lock problems / no type specified | **`python -m tj_analyzer`** |
| Only TLOCK | `tlock-analyzer` skill |
| Only TTIMEOUT | `ttimeout-analyzer` skill |
| Only TDEADLOCK | `tdeadlock-analyzer` skill |

Rule: [.cursor/rules/lock-analyzers.mdc](../../rules/lock-analyzers.mdc)

## When to use this skill

Russian triggers: «все проблемы блокировок», «сводный анализ», «ожидания и таймауты и дедлоки», «полный разбор ТЖ по блокировкам».

## Workflow

1. `pip install -e .`

2. Default run:

   ```bash
   python -m tj_analyzer --source click --log-id <LOG_ID> --report-dir reports
   ```

3. Subset:

   ```bash
   python -m tj_analyzer --source click --log-id <LOG_ID> --only tlock,ttimeout
   ```

4. Read `summary` in JSON: `tlock_victims`, `ttimeout_victims`, `tdeadlock_cases`.

## Do not

- Use this when user explicitly asks for only one event type (use dedicated skill).
- Write custom SQL/scripts instead of CLI.

## Reference

- [README.md](../../README.md)
