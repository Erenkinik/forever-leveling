# Elle giriş: Wowhead'den bakılan Forever görevleri

pfQuest'te bulunmayan, yalnızca Forever'a özgü görevler `quests.yaml` içine elle girilir.
Dosya bir YAML listesidir; boşken `[]` kalır.

## Kural: metin kopyalanmaz, yalnız olgu

Wowhead'den yalnızca olgular alınır: görev kimliği, ad, seviye, NPC, koordinat.
Görev açıklaması, hedef ya da ödül metni kopyalanmaz. Her girişe baktığın sayfanın
adresi (`wowheadUrl`) ve baktığın tarih (`checkedOn`) yazılır.

## Alanlar

| Alan | Zorunlu | Açıklama |
|---|---|---|
| `id` | evet | Görev kimliği (tamsayı, dosyada tekrar edemez) |
| `name` | evet | Görev adı |
| `level` | evet | Görev seviyesi |
| `minLevel` | evet | Alınabilmesi için gereken en düşük seviye |
| `races` | hayır | Irk adları listesi |
| `prereqs` | hayır | Önkoşul görev kimlikleri listesi |
| `start` | hayır | Başlangıç noktası: `type`, `id`, `name`, `uiMapId`, `x`, `y` |
| `end` | hayır | Bitiş noktası, `start` ile aynı alanlar |
| `wowheadUrl` | evet | `https://www.wowhead.com/forever/quest=` ile başlamalı (`/classic/` kabul edilmez) |
| `checkedOn` | evet | Bakılan tarih, `YYYY-MM-DD` |

Yüklenen kayda `source: wowhead-manual` eklenir.

## Örnek

```yaml
- id: 90001
  name: Örnek Görev
  level: 5
  minLevel: 3
  races: [Human, Dwarf]
  prereqs: [90000]
  start:
    type: npc
    id: 1234
    name: Örnek NPC
    uiMapId: 1429
    x: 45.2
    y: 60.1
  end:
    type: npc
    id: 1235
    name: Örnek Teslim NPC
    uiMapId: 1429
    x: 40.0
    y: 62.5
  wowheadUrl: https://www.wowhead.com/forever/quest=90001/ornek-gorev
  checkedOn: 2026-10-22
```
