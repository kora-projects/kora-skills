# Исследование: Как создавать лучшие Claude Skills для технологий и фреймворков

**Дата:** 2026-05-18  
**Автор:** Anton Kurako  
**Статус:** Complete

---

## 📋 Содержание

1. [Executive Summary](#executive-summary)
2. [Официальные Best Practices (Anthropic)](#1-официальные-best-practices-anthropic)
3. [Community Experience](#2-community-experience)
4. [Programming/Framework Skills](#3-programmingframework-skills)
5. [Language Choice: English vs Russian](#4-language-choice-english-vs-russian)
6. [Skill Structure Specification](#5-skill-structure-specification)
7. [Checklist для эффективных Skills](#6-checklist-для-эффективных-skills)
8. [Применительно к KORA Skills](#7-применительно-к-kora-skills)

---

## Executive Summary

### Ключевые выводы

| Принцип | Что делать | Почему |
|---------|-----------|--------|
| **Concise is key** | SKILL.md <500 строк, только необходимое | Контекстное окно — общий ресурс |
| **Description = Trigger** | Конкретные триггеры в description | 80-84% activation vs 40-50% vague |
| **Progressive Disclosure** | 3 уровня загрузки (metadata → instructions → resources) | Unlimited content без penalty |
| **Reverse Prompting** | Просить Claude критиковать скилл | Находит амбигуозности до продакшена |
| **Iteration Cycles** | 2-3 цикла тестирования на реальных кейсах | Скилл с 1 попытки редко оптимален |
| **Examples > Instructions** | 2-3 примера идеального выхода | Распознаёт паттерн с 1 раза |
| **Гибридный язык** | Frontmatter/Headers English, пояснения Russian | 100% навигация + глубина понимания |

---

## 1. Официальные Best Practices (Anthropic)

### 1.1 Core Principles

#### Concise is key 🔑

**Контекстное окно — общий ресурс.** Skill делит его с:
- Системным промптом
- Историей conversation
- Metadata других скиллов
- Текущим запросом

**Важно:** Claude загружает SKILL.md только когда skill становится релевантным.

| ❌ Плохо (150 токенов) | ✅ Хорошо (50 токенов) |
|----------------------|---------------------|
| Объясняет что такое PDF, как работают библиотеки, почему выбран pdfplumber | `Use pdfplumber for text extraction` + код |

#### Degree of Freedom (Степень свободы)

| Уровень | Когда использовать | Пример |
|---------|-------------------|--------|
| **High** (текстовые инструкции) | Много валидных подходов, решение зависит от контекста | Code review process |
| **Medium** (псевдокод, скрипты с параметрами) | Есть предпочтительный паттерн, конфигурация влияет на поведение | Generate report template |
| **Low** (конкретные скрипты, мало параметров) | Операции хрупкие, консистентность критична | Database migration |

**Аналогия:** Узкий мост с обрывами → точные инструкции. Открытое поле → общее направление.

#### Test with all models

- **Haiku:** Нужно больше деталей в инструкциях
- **Sonnet:** Баланс ясности и эффективности
- **Opus:** Не переобъяснять (избыточные инструкции мешают)

### 1.2 YAML Frontmatter (Обязательно)

```yaml
---
name: kora-database                    # ≤64 chars, lowercase, hyphens
description: Database integration...   # ≤1024 chars, third person
---
```

| Поле | Требования | Цель |
|------|-----------|------|
| **name** | ≤64 chars, lowercase, hyphens, no "anthropic"/"claude" | Идентификация |
| **description** | ≤1024 chars, non-empty, **third person** | **Discovery** — Claude использует для выбора скилла |

**✅ Good:**
```yaml
description: Extract text and tables from PDF files, fill forms, merge documents. 
             Use when working with PDF files or when the user mentions PDFs, forms, or document extraction.
```

**❌ Bad:**
```yaml
description: Helps with documents  # Слишком общее
description: I can help you...     # Не third person
description: You can use this to... # Не third person
```

### 1.3 Progressive Disclosure (Прогрессивное раскрытие)

**3 уровня загрузки:**

| Уровень | Когда загружается | Токены | Содержание |
|---------|------------------|--------|------------|
| **Level 1: Metadata** | Всегда (startup) | ~100 / skill | name + description |
| **Level 2: Instructions** | Когда triggered | <5k токенов | SKILL.md body |
| **Level 3: Resources** | По необходимости | **Unlimited** | scripts/, references/, assets/ |

**Паттерн структуры:**
```
skill-name/
├── SKILL.md              # Main instructions (<500 lines)
├── FORMS.md              # Specialized guide (loaded on demand)
├── REFERENCE.md          # API reference (loaded on demand)
└── scripts/
    └── helper.py         # Executable (output only, not code)
```

### 1.4 Avoid Deeply Nested References

**❌ Плохо:**
```markdown
SKILL.md → advanced.md → details.md → actual info
```

**✅ Хорошо:**
```markdown
SKILL.md → advanced.md (инфо здесь)
       → reference.md (инфо здесь)
       → examples.md (инфо здесь)
```

Claude может использовать `head -100` для вложенных файлов → неполная информация.

**Правило:** Все reference файлы должны ссылаться **напрямую из SKILL.md** (one level deep).

### 1.5 Workflows для сложных задач

**Pattern: Checklist**
```markdown
## PDF form filling workflow

Copy this checklist and check off items:

```
Task Progress:
- [ ] Step 1: Analyze the form (run analyze_form.py)
- [ ] Step 2: Create field mapping (edit fields.json)
- [ ] Step 3: Validate mapping (run validate_fields.py)
- [ ] Step 4: Fill the form (run fill_form.py)
- [ ] Step 5: Verify output (run verify_output.py)
```
```

### 1.6 Feedback Loops (Validate → Fix → Repeat)

```markdown
## Document editing process

1. Make edits to `word/document.xml`
2. **Validate immediately:** `python ooxml/scripts/validate.py`
3. If validation fails:
   - Review error message
   - Fix XML
   - Run validation again
4. **Only proceed when validation passes**
```

### 1.7 Anti-Patterns

| ❌ Избегать | ✅ Делать |
|-----------|---------|
| Windows пути (`scripts\helper.py`) | Unix пути (`scripts/helper.py`) |
| Слишком много опций ("можно использовать pypdf или pdfplumber или PyMuPDF...") | Один дефолт + escape hatch для edge cases |
| "Voodoo constants" (`TIMEOUT=47`) | Self-documenting (`TIMEOUT=30 # HTTP requests typically complete within 30s`) |
| Понт в Claude ("figure it out") | Handle errors explicitly |
| Assumes tools installed | List dependencies: `pip install package` |
| MCP tools без префикса | Fully qualified: `BigQuery:bigquery_schema` |

---

## 2. Community Experience

### 2.1 Reverse Prompting 🔥 (Castaldo Solutions)

**Самая важная практика, которую почти никто не использует.**

После написания скилла попроси Claude:
1. Прочитать скилл
2. Найти амбигуозные/противоречивые инструкции
3. Указать что отсутствует
4. Предложить что удалить

**Почему работает:** Claude видит инконсистентности, которые автор не замечает.

### 2.2 Iteration Cycles

**Скилл с первой попытки редко работает оптимально.**

```
v1 → Test (3-5 реальных кейсов) → Note failures → Fix → v2
v2 → Test → Note failures → Fix → v3 ✅
```

**Сигнал готовности:** Выход консистентный на кейсах, которые не использовались при создании.

**Оптимальный размер:** 500-2000 токенов. Неотполированные >5000 токенов.

### 2.3 GitHub for Versioning

- **Versioning:** Отслеживаешь изменения, можно откатить
- **Remote access:** Модификация прямо из Claude Code
- **Collaboration:** Команда клонирует те же скиллы
- **Audit trail:** Каждый коммит с контекстом "почему"

### 2.4 Examples > Instructions

| Подход | Поведение Claude |
|--------|-----------------|
| Только инструкции | Инферирует цель, нужно больше итераций |
| Инструкции + примеры | Распознаёт паттерн, консистентный выход с 1 раза |

**Метод:**
1. Собрать 2-3 примера идеального выхода
2. Включить в скилл с пометкой "this is expected output"
3. Попросить Claude запомнить характеристики

---

## 3. Programming/Framework Skills

### 3.1 Структура для технических скиллов

#### Минимальная структура (BASIC Tier)
```
skill-name/
├── SKILL.md              # 100+ строк, YAML frontmatter
├── README.md             # Quick start
└── scripts/
    └── main.py           # 100-300 строк, argparse
```

#### Полная структура (POWERFUL Tier)
```
skill-name/
├── SKILL.md              # 300+ строк, comprehensive
├── README.md             # Detailed usage
├── scripts/              # Multiple sophisticated scripts
│   ├── main_processor.py
│   ├── data_analyzer.py
│   └── report_generator.py
├── assets/               # Sample data
│   ├── samples/
│   ├── examples/
│   └── data/
├── references/           # Technical docs
│   ├── api-reference.md
│   ├── specifications.md
│   └── best-practices.md
└── expected_outputs/     # Test outputs
    ├── json_outputs/
    └── text_reports/
```

### 3.2 YAML Frontmatter для технологий

#### Расширенные поля (engineering-team pattern)
```yaml
---
name: llm-wiki
description: Use when building or maintaining a persistent personal knowledge base...
context: fork                           # fork | current
version: 1.0.0
author: claude-code-skills
license: MIT
tags: [knowledge-management, obsidian, second-brain]
compatible_tools: [claude-code, codex-cli, cursor, antigravity]
---
```

### 3.3 Description = Trigger Mechanism

**Правило:** Description должен содержать слова, которые пользователи **действительно используют**.

| ❌ Плохо | ✅ Хорошо |
|---------|----------|
| "Helps with Kora" | "Build production-ready Java/Kotlin microservices on Kora framework" |
| "Database skill" | "Create JDBC repositories, write @Query methods, configure HikariCP" |
| Vague: "API helper" | Specific: "Generate OpenAPI clients, validate endpoints, handle auth" |

**Данные:** Specific descriptions с явными триггерами дают **80-84% activation rate** против 40-50% у vague.

### 3.4 Обязательные разделы для Framework Skills

```markdown
## Framework Version
Указать версию: **Kora 1.x**, совместимость с Java 25/Kotlin 17+

## Build System
Gradle 9+ recommended, Maven support

## Annotation Processors
```groovy
dependencies {
    annotationProcessor "ru.tinkoff.kora:kora-annotation-processor:$koraVersion"
    // Kotlin: ksp "ru.tinkoff.kora:kora-ksp:$koraVersion"
}
```

## Module System
Какие модули доступны:
- `kora-http-server` — REST API
- `kora-database` — JDBC/Cassandra
- `kora-kafka` — Producers/Consumers
- `kora-telemetry` — Metrics/Tracing

## Compile-time vs Runtime
Объяснить что генерируется при компиляции, что требует runtime

## Common Pitfalls
- Классы должны быть non-final/open
- @KoraSubmodule для каждого модуля
- Не смешивать sync/async сигнатуры
```

### 3.5 Scripts должны быть Dual-Output

```python
#!/usr/bin/env python3
"""Validate Kora entity classes."""

import argparse
import json
import sys

def main():
    parser = argparse.ArgumentParser(description='Validate Kora entities')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('path', help='Path to entity class')
    args = parser.parse_args()
    
    # Validation logic
    result = {"valid": True, "errors": []}
    
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("✓ Entity validation passed")
        for err in result["errors"]:
            print(f"✗ {err}")

if __name__ == "__main__":
    sys.exit(0 if result["valid"] else 1)
```

### 3.6 Examples Pattern для фреймворков

**Для каждого концепта — пример:**

```markdown
## @HttpController Example

```java
@HttpController
public class UserController {
    private final UserService service;
    
    @HttpController.Get("/users/{id}")
    public UserDto getUser(UUID id) {
        return service.findById(id);
    }
}
```

**Важно:** Контроллеры всегда sync, интерсепторы — CompletionStage.
```

---

## 4. Language Choice: English vs Russian

### 4.1 Multilingual Performance (Claude API Docs)

| Язык | Performance (относительно English) |
|------|----------------------------------|
| Spanish, Portuguese, Italian | 97-98% |
| French, German, Indonesian | 94-97% |
| Chinese, Japanese, Korean | 93-97% |
| Russian | ~95-97% (оценка, не бенчмарчен) |

### 4.2 Гибридный формат (оптимально для Kora)

```yaml
---
name: kora-database
description: Database integration in Kora applications using JDBC and Cassandra.
              Use when creating repositories, configuring databases, or writing 
              @Query methods in Kora services.
---

# Kora Database Skill

## Quick Start

### 1. Add Dependencies

```groovy
dependencies {
    implementation "ru.tinkoff.kora:database-jdbc:$koraVersion"
}
```

**Примечание:** Kora рекомендует JDBC + Virtual Threads вместо R2DBC.
```

| Элемент | Язык | Почему |
|---------|------|--------|
| YAML frontmatter | English | Discovery mechanism |
| Заголовки | English | Навигация, consistency с кодом |
| Код | English | Как в оригинале |
| Пояснения | Russian | Глубина понимания |
| Предупреждения | Russian | Контекст и нюансы |

### 4.3 Почему гибрид лучше для фреймворков

1. **Фреймворк документация** часто двуязычная (Kora: `/en/` + `/ru/`)
2. **Код всегда на English** — идентификаторы, аннотации
3. **Команда локальная** — Russian для нюансов
4. **Claude performance** ~97% для European languages

---

## 5. Skill Structure Specification

### 5.1 Directory Structure

```
skill-name/
├── SKILL.md              # Primary documentation (REQUIRED)
├── README.md             # Usage instructions (REQUIRED)
├── scripts/              # Python implementation (REQUIRED)
│   └── *.py              # At least one Python script
├── assets/               # Sample data (RECOMMENDED)
│   ├── samples/
│   ├── examples/
│   └── data/
├── references/           # Reference docs (RECOMMENDED)
│   ├── api-reference.md
│   ├── specifications.md
│   └── external-links.md
└── expected_outputs/     # Test outputs (RECOMMENDED)
    ├── sample_output.json
    └── test_cases/
```

### 5.2 SKILL.md Requirements

#### Mandatory YAML Frontmatter
```yaml
---
Name: skill-name
Tier: [BASIC|STANDARD|POWERFUL]
Category: [Category Name]
Dependencies: [None|List of dependencies]
Author: [Author Name]
Version: [Semantic Version]
Last Updated: [YYYY-MM-DD]
---
```

#### Required Sections
- **Description**: Comprehensive overview
- **Features**: Detailed list of key features
- **Usage**: Instructions for using the skill
- **Examples**: Practical usage examples

#### Content Requirements by Tier
- **BASIC**: Minimum 100 lines
- **STANDARD**: Minimum 200 lines
- **POWERFUL**: Minimum 300 lines

### 5.3 Scripts Requirements

#### Mandatory Requirements
- Shebang line: `#!/usr/bin/env python3`
- Module docstring: Comprehensive description
- Argparse implementation: CLI argument parsing
- Main guard: `if __name__ == "__main__":`
- Error handling: Exception handling + user feedback
- Dual output: JSON + human-readable formats

#### Script Size by Tier
- **BASIC**: 100-300 lines
- **STANDARD**: 300-500 lines
- **POWERFUL**: 500-800 lines

### 5.4 Naming Conventions

| Тип | Convention | Пример |
|-----|-----------|--------|
| **Директории** | lowercase, hyphens | `data-processor`, `api-client` |
| **Скрипты** | lowercase, hyphens | `data-processor.py` |
| **Классы** | PascalCase | `DataProcessor` |
| **Функции** | snake_case | `process_data()` |
| **Константы** | UPPER_CASE | `MAX_RETRIES` |

---

## 6. Checklist для эффективных Skills

### Core Quality
- [ ] Description специфичный + ключевые термины
- [ ] Description включает **что** делает и **когда** использовать
- [ ] SKILL.md body <500 строк
- [ ] Дополнительные детали в отдельных файлах
- [ ] Нет time-sensitive информации
- [ ] Консистентная терминология
- [ ] Примеры конкретные
- [ ] File references one level deep
- [ ] Workflows с чёткими шагами
- [ ] Указана **версия фреймворка** и совместимость
- [ ] **Build system** описан (Gradle/Maven)
- [ ] **Annotation processors** перечислены
- [ ] **Module system** объяснён
- [ ] **Quick Start** 5 шагов
- [ ] **Examples** для каждого концепта
- [ ] **Common Pitfalls** списком

### Code & Scripts
- [ ] Scripts решают проблемы, не понтуют в Claude
- [ ] Error handling явный
- [ ] Нет "magic numbers" (все значения обоснованы)
- [ ] Dependencies перечислены
- [ ] Нет Windows paths
- [ ] Validation для критичных операций
- [ ] Standard library only (no pip installs)
- [ ] Argparse implementation
- [ ] Main guard (`if __name__ == "__main__"`)
- [ ] JSON + human-readable output

### Testing
- [ ] ≥3 evaluations создано
- [ ] Тестировано на Haiku, Sonnet, Opus
- [ ] Тестировано на реальных сценариях
- [ ] Team feedback incorporated

---

## 7. Применительно к KORA Skills

### 7.1 Текущее состояние

| Элемент | Статус |
|---------|--------|
| YAML frontmatter | ✅ English |
| Заголовки | ✅ English |
| Пояснения | ✅ Russian |
| Код | ✅ English |
| Scripts | ✅ English, stdlib only |

### 7.2 Что улучшить

| Что | Как | Приоритет |
|-----|-----|-----------|
| **Examples** | Добавить больше concrete examples с UUID, конкретными типами | 🔴 High |
| **Common Pitfalls** | Расширить списком с конкретными ошибками (ID mismatch, @Query params) | 🔴 High |
| **Version Matrix** | Добавить version compatibility в каждый скилл | 🟡 Medium |
| **Scripts dual-output** | Проверить все скрипты на JSON + text output | 🟡 Medium |
| **Expected outputs** | Добавить expected_outputs/ для валидации | 🟢 Low |

### 7.3 Пример улучшения для kora-database

```markdown
## Common Pitfalls

**ID type mismatch:**
```java
// ❌ Wrong: Entity has UUID, repo uses String
@Entity
public class User { @Id private UUID id; }

public interface UserRepository extends JdbcRepository<User, String> {}

// ✅ Correct: ID types must match
public interface UserRepository extends JdbcRepository<User, UUID> {}
```

**Missing @Query named parameters:**
```java
// ❌ Wrong
@Query("SELECT * FROM users WHERE email = $1")
User findByEmail(String email);

// ✅ Correct: Use named parameters
@Query("SELECT * FROM users WHERE email = :email")
User findByEmail(@Param("email") String email);
```

**RETURNING clause for IDs:**
```java
// ❌ Wrong: No ID returned after insert
@Query("INSERT INTO users (email) VALUES (:email)")
void create(String email);

// ✅ Correct: RETURNING for generated ID
@Query("INSERT INTO users (email) VALUES (:email) RETURNING id")
UUID create(String email);
```
```

---

## 8. Источники

### Официальная документация
- [Anthropic — Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
- [Anthropic — Agent Skills overview](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)
- [Anthropic — Multilingual support](https://platform.claude.com/docs/en/build-with-claude/multilingual-support)

### Community Experience
- [Castaldo Solutions — Claude Code Skills 2026](https://www.castaldosolutions.it/articles/en/blog/skill-claude-code-guida-best-practices)
- [Firecrawl — Best Claude Code Skills 2026](https://www.firecrawl.dev/blog/best-claude-code-skills)
- [AI for Developers — Complete Guide to Claude Skills](https://aifordevelopers.substack.com/p/the-complete-guide-to-creating-and)
- [Composio — Top 10 Claude Skills](https://composio.dev/content/top-claude-skills)
- [Developers Digest — Best Skills 2026](https://www.developersdigest.tech/blog/best-claude-code-skills-2026)

### Internal References
- [Skill Structure Specification](engineering/skills/skill-tester/references/skill-structure-specification.md)
- [llm-wiki SKILL.md](engineering/llm-wiki/skills/llm-wiki/SKILL.md)
- [KORA Meta-Skill](KORA/SKILL.md)

---

## 9. Приложения

### A. Template для нового Programming Skill

```markdown
---
name: framework-name
description: Build production-ready applications with [Framework]. 
             Use when scaffolding new projects, creating controllers, 
             configuring databases, or writing [specific feature].
version: 1.0.0
author: your-name
tags: [framework, language, category]
---

# Framework Name Skill

## Framework Version
**Version:** X.x.x  
**Language:** Java XX / Kotlin XX+  
**Build:** Gradle XX+ / Maven

## Quick Start (5 steps)
1. [Step 1]
2. [Step 2]
3. [Step 3]
4. [Step 4]
5. [Step 5]

## Core Concepts
- [Concept 1: 1 paragraph]
- [Concept 2: 1 paragraph]

## Common Pitfalls
- [Pitfall 1 with example]
- [Pitfall 2 with example]

## Examples
### Example 1: [Use case]
[Code example]

### Example 2: [Use case]
[Code example]

## References
- [Reference 1](references/file.md)
- [Reference 2](references/file.md)
```

### B. Template для Scripts

```python
#!/usr/bin/env python3
"""
[Skill Name] — [Brief description]

Usage:
    python script_name.py [options] <path>

Examples:
    python script_name.py --json /path/to/file
    python script_name.py --verbose /path/to/file
"""

import argparse
import json
import sys
from typing import Any, Dict, List, Optional


def main():
    parser = argparse.ArgumentParser(
        description='[Description]',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s --json /path/to/file
  %(prog)s --verbose /path/to/file
'''
    )
    parser.add_argument('--json', action='store_true', 
                        help='Output as JSON')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Verbose output')
    parser.add_argument('path', help='Path to [resource]')
    
    args = parser.parse_args()
    
    try:
        # Main logic here
        result = process(args.path)
        
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print_human_readable(result, args.verbose)
            
    except FileNotFoundError as e:
        print(f"Error: File not found: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def process(path: str) -> Dict[str, Any]:
    """Process [resource] and return result."""
    # Implementation
    return {"status": "ok"}


def print_human_readable(result: Dict[str, Any], verbose: bool = False):
    """Print result in human-readable format."""
    print(f"✓ Status: {result['status']}")


if __name__ == "__main__":
    main()
```

---

**Документ будет обновляться по мере появления новых best practices и инсайтов.**

*Last Updated: 2026-05-18*
