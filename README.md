# MusicMixCode — Ableton Auto-Mix MCP

> 🇬🇧 [Read this in English](README.en.md)

MCP-сервер для автосведения (auto-mixing) и авто-мастеринга в Ableton Live **под музыкальный стиль/жанр**.
ИИ-агент (opencode, Claude Code, Claude Desktop...) анализирует рендеры треков, сравнивает их с профилем
стиля и выдаёт/применяет корректировки: уровни, панорама, EQ-подсказки, компрессия — и дополнительно
рендерит превью-микс с полным мастерингом (сайдчейн, HPF, mud-cut, soft-clipper, true-peak лимитер).

## Возможности

- **10 MCP-инструментов**: анализ, авто-сведение под стиль, превью-рендер, проверка релиза.
- **11 профилей стилей** (JSON): techno, hip_hop, pop, lo_fi, ambient, balanced, trance, breaks, dubstep, drum_n_bass, trap.
- **Мастеринг-стадия**: sidechain (kick → bass, snare-band Dynamic EQ), HPF по ролям, mud-cut 200–500 Гц,
  tanh soft-clipper, LUFS-нормализация, true-peak lookahead-лимитер (4× oversampling), TPDF-дизеринг.
- **Стерео-имиджинг**: mid/side ширина по ролям (mono для кика/саба, wide/very_wide для хатов/падов) + панорама.
- **Спектральное распознавание ролей**: если имя файла не подсказывает роль, инструмент определяется по спектру.
- **Release Check**: LUFS/LRA/true-peak/RMS/sub-mid-gap против таргетов топ-лейблов — вердикт `ready` / `needs_work`.
- **Конфликт-анализ**: какие пары треков спорят за частотные полосы.
- **Offline-режим**: анализ и превью работают без Ableton Live (нужны только WAV-рендеры).

## Архитектура

```
You → MCP client → ableton-auto-mix-mcp (MCP server)
                         ├── styles/*.json     — профили стилей (целевые кривые)
                         ├── analyzer.py       — LUFS/LRA, спектр, стереоширина (librosa/pyloudnorm)
                         ├── mixer.py          — движок: анализ vs профиль → коррекции (ядро = kick, LUFS)
                         ├── preview.py        — рендер превью-микса + мастеринг-цепь
                         ├── qa.py             — конфликт-анализ + release check
                         └── ableton_client.py — AbletonOSC (python-osc) → Ableton Live
```

Принцип: **сам MCP не «сводит»** — он даёт инструменты и метрики, а решает модель.
Цикл: рендер → анализ → dry-run отчёт → превью-микс → release check → применение правок.

## Установка

```bash
pip install -r requirements.txt        # или: pip install -e .
```

Затем подключите MCP-сервер в своём клиенте (пример для Claude Code / opencode):

```json
{ "mcpServers": { "ableton-auto-mix": {
    "command": "python", "args": ["-m", "ableton_auto_mix"],
    "cwd": "C:/path/to/ableton-auto-mix-mcp"
}}}
```

> Анализ и превью-рендер не требуют Ableton Live — достаточно WAV-файлов (по одному на трек).

## Подготовка Ableton (опционально, для auto-apply)

1. Запустите Ableton Live.
2. Установите control surface **AbletonOSC** (https://github.com/ideoforms/AbletonOSC).
3. Preferences → Link, Tempo & MIDI → Control Surface → AbletonOSC.
4. Bounce каждого трека в `renders/` (по одному WAV на трек) для анализа.

## Инструменты MCP

| Инструмент | Что делает |
|---|---|
| `list_styles` | список стилей и их целей |
| `get_style(name)` | полный профиль стиля (кривая, баланс, компрессия, FX) |
| `get_ableton_status` | проверка связи с Live |
| `analyze_audio(path)` | метрики одного WAV |
| `analyze_render_dir(dir)` | метрики всех рендеров |
| `auto_mix(style, render_dir, dry_run)` | коррекции под стиль (dry-run или apply в Live) |
| `suggest_style(render_dir)` | какой стиль лучше подходит под материал |
| `preview_mix(style, render_dir, ...)` | рендер превью-микса с полным мастерингом в WAV |
| `analyze_conflicts(render_dir)` | пары треков, спорящих за частотные полосы |
| `release_check(style, render_dir)` | LUFS/TP/LRA vs таргеты лейблов, вердикт ready/needs_work |

## Пример сессии

```
"Сведи рендеры из renders/ в стиле techno, покажи что менять"
→ auto_mix("techno", "renders", dry_run=true)

"Ок, применяй"
→ auto_mix("techno", "renders", dry_run=false)

"Сделай превью-микс с мастерингом"
→ preview_mix("breaks", "renders", max_duration=30)

"Проверь, готово ли к релизу"
→ release_check("breaks", "renders")
```

## CLI (без MCP-клиента)

Вся функциональность доступна из командной строки. `python -m ableton_auto_mix <команда>`
(или `ableton-auto-mix-mcp <команда>` после установки):

```bash
ableton-auto-mix-mcp styles                                  # список стилей
ableton-auto-mix-mcp style breaks                            # профиль стиля
ableton-auto-mix-mcp analyze renders/                        # метрики всех рендеров
ableton-auto-mix-mcp suggest renders/                        # какой стиль подходит
ableton-auto-mix-mcp mix breaks renders/                     # dry-run: что менять
ableton-auto-mix-mcp preview breaks renders/ --max-duration 30   # превью-микс в WAV
ableton-auto-mix-mcp conflicts renders/                      # конфликты частот
ableton-auto-mix-mcp release breaks renders/                 # вердикт ready/needs_work
```

Вывод — JSON (удобно для скриптов). Пример: `preview breaks renders/ --manual-gain "bass=2.0,snt2=-4.0" --output out.wav`.

## Стили

Стили поставляются внутри пакета (`ableton_auto_mix/styles/`) — 11 профилей: techno, hip_hop, pop, lo_fi, ambient,
balanced, trance, breaks, dubstep, drum_n_bass, trap.
Каждый профиль задаёт: целевой LUFS/LRA, спектральную кривую (6 полос), относительные уровни инструментов
(kick/bass/vocals/lead/wobble/breaks/...), HPF по ролям, mud-cut, сайдчейн, мастеринг-настройки, компрессию и
FX-рекомендации. Можно добавлять свои: скопируйте JSON и поменяйте `name` и цели.

Чтобы использовать свои стили без правки пакета, укажите переменную окружения:

```bash
export ABLETON_AUTO_MIX_STYLES_DIR=/path/to/my-styles
```

## Тесты

```bash
python tests/test_smoke.py   # 5 smoke-тестов: рендер → микс → превью → release check
```

## Ограничения

- Анализ идёт по **рендерам** (оффлайн), т.к. Live не отдаёт семплы в реальном времени через OSC.
- Роль трека определяется по имени, при неизвестном имени — по спектру (kick, bass, vocals...). Называйте треки явно для точности.
- `auto_mix(dry_run=false)` требует запущенный Ableton Live с control surface AbletonOSC.
- Превью-мастеринг применяет стандартную цепь по профилю; финальный тюнинг делается вручную.

## Лицензия

[MIT](LICENSE) © 2026 MusicMixCode / HighVoltSound
