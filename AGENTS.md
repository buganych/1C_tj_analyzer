# Agent instructions

Анализ проблем блокировок 1С. **Главное правило маршрутизации:** [.cursor/rules/lock-analyzers.mdc](.cursor/rules/lock-analyzers.mdc)

## Как сформулировать задачу агенту

### Все проблемы сразу (рекомендуется)

```
Найди все проблемы блокировок в ClickHouse, log_id teletrade_tj_logs, за последний час.
Запусти python -m tj_analyzer, output both.
```

```
Сводный анализ ТЖ: TLOCK, TTIMEOUT, TDEADLOCK для log_id …
```

### Только один тип

```
Только TLOCK / ожидания с WaitConnections для log_id …
→ python -m tlock_analyzer
```

```
Только таймауты TTIMEOUT для log_id …
→ python -m ttimeout_analyzer
```

```
Только взаимоблокировки TDEADLOCK для log_id …
→ python -m tdeadlock_analyzer
```

### Комбинация через сводную тулзу

```
tj_analyzer --only tlock,tdeadlock   # без TTIMEOUT
```

## Команды

| Задача | Команда |
|--------|---------|
| **Все: TLOCK + TTIMEOUT + TDEADLOCK** | `python -m tj_analyzer` |
| Только TLOCK | `python -m tlock_analyzer` |
| Только TTIMEOUT | `python -m ttimeout_analyzer` |
| Только TDEADLOCK | `python -m tdeadlock_analyzer` |

```bash
python -m tj_analyzer --source click --log-id <LOG_ID> --output both
```

## Skills и правила

| Режим | Rule | Skill |
|-------|------|-------|
| Маршрутизация | [lock-analyzers.mdc](.cursor/rules/lock-analyzers.mdc) | — |
| Все сразу | [tj-analyzer.mdc](.cursor/rules/tj-analyzer.mdc) | [tj-analyzer/SKILL.md](.cursor/skills/tj-analyzer/SKILL.md) |
| TLOCK | [tlock-analyzer.mdc](.cursor/rules/tlock-analyzer.mdc) | [tlock-analyzer/SKILL.md](.cursor/skills/tlock-analyzer/SKILL.md) |
| TTIMEOUT | [ttimeout-analyzer.mdc](.cursor/rules/ttimeout-analyzer.mdc) | [ttimeout-analyzer/SKILL.md](.cursor/skills/ttimeout-analyzer/SKILL.md) |
| TDEADLOCK | [tdeadlock-analyzer.mdc](.cursor/rules/tdeadlock-analyzer.mdc) | [tdeadlock-analyzer/SKILL.md](.cursor/skills/tdeadlock-analyzer/SKILL.md) |

[README.md](README.md)
