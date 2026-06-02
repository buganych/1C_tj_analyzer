---
name: ttimeout-analyzer
description: ONLY 1C TTIMEOUT (lock wait timeout). Use tj-analyzer skill for ALL lock problems. Use this for TTIMEOUT-only tasks.
---

# TTIMEOUT Analyzer (1C) — только TTIMEOUT

## Routing

| User intent | Tool |
|-------------|------|
| **All** lock problems | `tj-analyzer` skill |
| **Only TTIMEOUT** | **`python -m ttimeout_analyzer`** (this skill) |

Rule: [.cursor/rules/lock-analyzers.mdc](../../rules/lock-analyzers.mdc)

## When to use this skill

- Явно **только таймауты** / `TTIMEOUT`
- **Не** использовать для «всех проблем блокировок» или только TLOCK/TDEADLOCK

## Workflow

1. `pip install -e .` из корня репозитория.

2. ClickHouse:

   ```bash
   python -m ttimeout_analyzer --source click --log-id <LOG_ID> --output both
   ```

3. Файлы ТЖ:

   ```bash
   python -m ttimeout_analyzer --source plain --file tj.log --log-id <LOG_ID> --base-date "2026-05-27"
   ```

4. Типы конфликтов: **ПолноеСоответствие**, **Эскалация**, **РазныйНаборИзмерений**, **БольшаяТранзакция**.

## Tables (ClickHouse)

| Роль | Таблица |
|------|---------|
| Жертвы | `tj_ttimeout` |
| TLOCK виновника | `tj_tlock` |
| Транзакции | `tj_sdbl`, fallback `tj_raw` |

## Do not

- Использовать `tlock-analyzer` для анализа таймаутов как основного сценария
- Дублировать `tj_common` / BSL в одноразовых скриптах

## Reference

- [README.md](../../README.md)
- Общий пайплайн: `tj_common/analysis/pipeline.py`
- BSL (признак у TLOCK, не отдельный пайплайн): `ЗаполнитьПризнакТаймаута` в `АнализTLOCK`
