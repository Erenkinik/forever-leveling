# Keşif notu: wago.tools (22 Ekim 2026)

Kaynak: `https://wago.tools/api/builds` ve CSV dışa aktarımları (`https://wago.tools/db2/{table}/csv?build={build}`). Denetleyici tarafından 2026-10-22'de doğrulandı.

## Build'ler

- Ürün `wowf` (WoW Forever): iki build var, `70532` ve `70245`.
- Veri sabiti: `1.60.1.70532` (`pipeline/config.py` içinde `DATA_BUILD`).

## Tablolar

| Tablo | Bulgu |
|---|---|
| `QuestV2` | 6616 görev ID'si. Yalnız `ID,UniqueBitFlag,UiQuestDetailsThemeID` sütunları var; ad, seviye, NPC yok. |
| `UiMap` | Elwynn Forest 1429, Westfall 1436, Zephras Isle 2521. |
| `QuestPOIBlob` | Yalnız 57 satır; kullanışsız. |

## Sonuç

wago yalnızca iki iş için kullanılır:

1. "Bu görev Forever'da var mı?" sorusu (`QuestV2` ID kümesi).
2. Harita tabloları (`UiMap` vb.).

Görev adı, seviye ve NPC bilgisi pfQuest'ten ve elle girişten gelir.
