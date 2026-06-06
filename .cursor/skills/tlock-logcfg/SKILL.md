---
name: tlock-logcfg
description: Generate 1C tech journal logcfg.xml from TLOCK waits with WaitConnections. Use lock analyzers (tlock/tj) for culprit analysis, not this skill.
---

# TLOCK Logcfg Generator — настройка ТЖ

## Routing

| User intent | Tool |
|-------------|------|
| **Analyze** lock problems, find culprits | `tlock-analyzer` / `tj-analyzer` skill |
| **Generate logcfg** for monitoring observed waits | **`python -m tlock_logcfg`** (this skill) |

Rule: [.cursor/rules/tlock-logcfg.mdc](../../rules/tlock-logcfg.mdc)

## When to use this skill

- Собрать **настройку ТЖ** (`logcfg.xml`) по наблюдаемым TLOCK с `WaitConnections`
- Уникальные **regions** из ClickHouse, plain или json
- **Не** использовать для поиска виновников или отчётов анализа

## Workflow

1. Убедиться, что пакет установлен:

   ```bash
   pip install -e .
   ```

2. Определить источник:
   - **click** — ClickHouse `tj_tlock`, нужен `--log-id`
   - **plain** / **json** — `--file`, опционально `--base-date`

3. Запустить генерацию (пример ClickHouse):

   ```bash
   python -m tlock_logcfg --source click --log-id <LOG_ID> \
     --location-path "D:\TJ\locks" --report-dir reports/<LOG_ID>
   ```

   При `tlock_analyzer` / `tj_analyzer` с `--report-dir` файл `logcfg.xml` создаётся автоматически **только если остались неразобранные блокировки**; иначе используй `python -m tlock_logcfg`.

4. Сообщить пользователю путь к `logcfg.xml` и краткую сводку (regions, количество, среднее/макс. ожидание).

## Параметры

| Параметр | По умолчанию | Назначение |
|----------|--------------|------------|
| `--min-duration` | **3** | Мин. ожидание, сек |
| `--platform-version` | **8.3.25** | <= 8.3.24 — без `format="json" compress="zip"` |
| `--location-path` | — | **Обязателен**, путь вместо `!!!ПУТЬ!!!` |
| `--report-dir` | — | Каталог отчёта → `logcfg.xml` (рекомендуется) |
| `-o` / `--output` | — | Выходной XML (если без `--report-dir`) |
| `--template` | bundled | Свой шаблон вместо `logcfg_шаблон.xml` |

Общие фильтры как у анализаторов: `--from`, `--to`, `--database`, `--hosts`, `--file-like`.

## Выход

Один XML-файл. Для каждого region:

```xml
<!-- Количество = 42, среднее ожидание = 5, максимальное ожидание = 20 -->
<event>
  <eq property="name" value="TLOCK"/>
  <eq property="regions" value="InfoRg10053.DIMS"/>
</event>
```

Плюс SCALL/SDBL из шаблона для транзакций.

## ClickHouse env

Из `.cursor/mcp.json` или переменных окружения. Не хардкодить пароли в команды.

## Do not

- Писать одноразовый скрипт генерации logcfg
- Использовать `tlock_analyzer`, если нужен только конфиг сбора (без анализа виновников)
- Забывать `--report-dir` или `-o` и `--location-path`

## Reference

- Шаблон: [logcfg_шаблон.xml](../../../logcfg_шаблон.xml)
- Пакет: `tlock_logcfg/`
- Тесты: `tests/test_logcfg.py`
