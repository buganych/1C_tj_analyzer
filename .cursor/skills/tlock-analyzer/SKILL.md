---
name: tlock-analyzer
description: ONLY 1C TLOCK waits (WaitConnections). Use tj-analyzer skill if user wants ALL lock problems. Use this for TLOCK-only tasks.
---

# TLOCK Analyzer (1C) — только TLOCK

## Routing

| User intent | Tool |
|-------------|------|
| **All** lock problems | `tj-analyzer` skill → `python -m tj_analyzer` |
| **Only TLOCK** | **`python -m tlock_analyzer`** (this skill) |

Rule: [.cursor/rules/lock-analyzers.mdc](../../rules/lock-analyzers.mdc)

## When to use this skill

- Явно **только TLOCK**: ожидания, `WaitConnections`, виновник ожидания
- **Не** использовать, если пользователь просит также таймауты/дедлоки или «все проблемы»

## Workflow

1. Убедиться, что пакет установлен:

   ```bash
   pip install -e .
   ```

2. Определить источник:
   - **click** — ClickHouse, нужен `--log-id`
   - **plain** / **json** — `--file`, опционально `--log-id`, `--from`, `--to`

3. Запустить анализ (пример ClickHouse):

   ```bash
   python -m tlock_analyzer --source click --log-id <LOG_ID> --output both
   ```

4. Интерпретировать вывод:
   - **ПолноеСоответствие**, **Эскалация**, **РазныйНаборИзмерений**, **БольшаяТранзакция**
   - ошибка «Ошибка поиска начала транзакции» — нет BeginTransaction для connect_id в `tj_sdbl`/`tj_raw`

## ClickHouse env

Из `.cursor/mcp.json` или переменных окружения пользователя. Не хардкодить пароли в команды.

## Do not

- Писать новый анализатор с нуля
- Обходить тулзу прямыми SQL/MCP, кроме справочного `SELECT DISTINCT log_id`
- Смешивать legacy-поля (`Timestamp`, `tconnectID`) — в CH используется `ts`, `connect_id`, `wait_connections`

## Reference

- [README.md](../../README.md)
- BSL-эталон: `bmp/CommonModules/АнализTLOCK/Ext/Module.bsl` (`СтартClick`)
