# KanjiDamage — Clean Structured Dataset

A cleaned, deduplicated, machine-readable extraction of the **Official KanjiDamage Anki deck**
(~1,757 notes), converted from HTML-stuffed Anki fields into structured JSON.

## Contents

| File | Description |
|---|---|
| `kanjidamage.json` | 1,757 entries (JSON array), ordered by `position` |
| `tags.json` | 68 tags: `id -> {name, description, count}` |
| `onyomi-keywords.json` | 169 onyomi readings -> English mnemonic keyword |
| `media/` | 2,028 media files (stroke-order diagrams, visual aids, radical images, font) |
| `extract_kanjidamage.py` | Extractor script (input: `Official_KanjiDamage_deck.apkg`) |

## Entry schema (`kanjidamage.json`)

Each entry:

| Field | Type | Meaning |
|---|---|---|
| `id` | int | Canonical KanjiDamage ID (URL-slug number) |
| `position` | int | Display order (deck "Number", 3 gaps) |
| `slug` | str | Decoded URL slug |
| `url` | str | Official page URL |
| `kanji` | str \| null | Character, or null for image-only radicals |
| `image` | str \| null | Radical image filename (key for image radicals) |
| `meaning` | str | English gloss |
| `usefulness` | int \| null | 0–5 star rating |
| `stroke_count` | int \| null | Stroke count |
| `frequency_ranking` | int | KanjiDamage frequency rank |
| `tags` | str[] | Canonical tag names |
| `description` | str \| null | "Why you should bother" text |
| `components` | obj[] | `{id, kanji, image, label}` |
| `onyomi` | obj[] | `{reading, mnemonic}` |
| `mnemonic` | str \| null | Kanji-meaning story |
| `kunyomi` | obj[] | `{reading, particles, meaning, usefulness, tags}` |
| `jukugo` | obj[] | `{word, reading, particles, meaning, usefulness, tags, components, notes}` |
| `lookalikes` | obj[] | `{kanji, id, meaning, hint, radical, radical_id, radical_image}` |
| `used_in` | obj[] | `{id, kanji, image}` |
| `media` | obj | `{stroke_order, visual_aids[]}` |

### Conventions

- **`id` vs `position`**: `id` is the real KanjiDamage ID used in URLs; `position` is display order.
- **Image radicals**: 121 entries have `kanji: null` and are keyed by `image` (e.g. `heel.jpg`).
- **Tags** are normalized to the official spelling (e.g. `SAME ON`, not `Same-ON`).
- **`null` vs `[]`**: absent scalar -> `null`; absent list -> `[]`.

## Notes / known gaps

- The source deck is missing 10 entries present on the website: **閥** and 9 katakana radicals
  (ク, メ, ラ, ホ, テ, オ, ノ, 丶, ユ).
- `visualaid-1graspinghand%20copy.jpg` and `visualaid-bundle%20head.jpg` are referenced by the
  deck but absent from its media archive.

## Attribution

Data derived from [KanjiDamage](https://www.kanjidamage.com/). All kanji mnemonics, tags and text
are the work of the KanjiDamage author(s); this repository contains a transformation of that
content. Please respect the original site's terms/copyright before redistributing. Media files
retain their original names.
