# Üçüncü taraf notları

- **pfQuest** (https://github.com/shagu/pfQuest), MIT lisansı. Görev adı (`T`), NPC ve nesne konumları gibi olgular için kullanılır. Görev açıklama metinleri (`D`/`O`) alınmaz.
- **wago.tools DB2 verisi**: game data © Blizzard Entertainment, used as facts, not redistributed. Ham CSV dosyaları `raw/` altındadır ve git'e girmez.
- **Yazı tipleri** (site, `@fontsource/*` paketleriyle kendi sunucumuzdan): Cinzel, Source Serif 4 ve IBM Plex Mono. Üçü de SIL Open Font License 1.1.
- **World of Warcraft**, Blizzard Entertainment, Inc.'in ticari markasıdır. Bu proje Blizzard ile bağlantılı değildir; görev adları ve koordinatlar olgu olarak kullanılır.
- **Bölge haritaları** (`site/public/maps/*.webp`): oyunun kendi harita görselleri (UiMapArt parçaları, wago.tools üzerinden), © Blizzard Entertainment. Ücretsiz, ticari olmayan rehberde yalnızca konum göstermek için kullanılır; `python -m pipeline maps` ile üretilir. Blizzard kaldırılmasını isterse kaldırılır.
- **Irk armaları ve görev parşömeni** (`site/public/art/*.webp`): oyunun jenerik ekranı armaları (`interface/glues/credits/*crest*`, `*banner*`) ve görev penceresi parşömeni (`interface/questframe/questbg.blp`), © Blizzard Entertainment. Aynı koşullarla kullanılır; `python -m pipeline maps` ile üretilir.
- **Simgeler** (`site/public/art/icon-*.webp`, `site/public/art/items/*.webp`): oyunun minimap nesne simgeleri atlası (`interface/minimap/objecticons.blp`) ve eşya simgeleri (`Item.IconFileDataID`), © Blizzard Entertainment. `python -m pipeline maps` ile üretilir.
