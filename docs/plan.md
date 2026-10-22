# ForeverXP — WoW Forever Ücretsiz Hızlı Leveling Rehberi

**Plan belgesi · Sürüm 1 · 22 Ekim 2026**

Durum: Eren'in onayını bekliyor. Onay gelmeden kod yazılmaz.

> "ForeverXP" çalışma adıdır (benim seçimim). Değiştirilebilir.

---

## 1. Amaç ve neden

WoW Forever 4 Kasım 2026'da çıkıyor. RestedXP'nin Forever rehberi ücretli (fraksiyon başına 30 $, ikisi 45 $). Eren'in istediği, aynı işi ücretsiz yapan bir ürün: oyuncu ırkını seçiyor, 1'den 30'a en hızlı görev rotasını adım adım izliyor.

Ürün iki parçadan oluşuyor ve ikisi de aynı veritabanını kullanıyor:

1. **Web sitesi.** Irk seçilir, rota liste ve harita olarak okunur, adımlar işaretlenir.
2. **Oyun içi addon.** RestedXP'deki gibi oyunun içinde çalışır: sıradaki adımı gösterir, ok ile yönü verir, tamamlanan adımı kendisi işaretler. **Ürünün nihai hedefi budur.**

Başarı ölçütü: bir oyuncu siteyi ya da addon'u kullanarak, rehberden kopmadan 1–30 arasını kendi ırkının rotasıyla bitirebiliyor. Rotadaki her adımın görev kimliği, NPC'si ve koordinatı doğru.

## 2. Hedefler, kapsam dışı, başarısızlık sayılanlar

**Hedefler (v1)**
- Seviye 1–30.
- Her ırk için ayrı rota (bkz. §4).
- Sağlam veritabanı: her kayıt en az iki kaynakla karşılaştırılır, kaynağı yazılıdır, oyunda doğrulanma durumu görünür.
- Rota adımları elle yazılmaz, otomatik üretilir. İnsan yalnızca bölge sırasını belirler, sonra rotayı gözden geçirip düzeltir (§8.2).
- Site ve addon tamamen ücretsiz. Hesap ve reklam yok.

**Kapsam dışı (v1)**
- Seviye 30'un üstü.
- Sınıfa özel rotalar. Sınıf görevleri rotanın içinde not ya da dal olarak geçer.
- Kullanıcı hesabı ve sunucu tarafı veritabanı.
- Zindan rehberleri.

**Sonra (v1'den sonra)**
- AskMrRobot tarzı sınıfa göre BiS (best in slot) ve "çantada taşınacak en iyi eşya" önerileri. Veri modeli bunu sonradan eklemeye uygun tasarlanır.

**Başarısızlık sayılanlar (teknik olarak çalışsa bile)**
- Rotada yanlış NPC, yanlış koordinat ya da önkoşulu atlanmış görev yüzünden oyuncunun takılması.
- Başka bir rehberin (RestedXP, Zygor, Polestar, Wowhead) metnini kopyalamak.
- Wowhead'i toplu taramak (kullanım koşulları yasaklıyor).
- Addon'un ücretli ya da kilitli bir sürümünü yapmak (Blizzard addon politikası).

## 3. Onaylanan tasarım kararları (tarayıcıda seçildi)

| Konu | Seçim |
|---|---|
| Rehber sayfa düzeni | **A: liste + harita.** Solda adım listesi, sağda bölge haritası ve pinler. Tamamlanan adımlar sönük ve üstü çizili, aktif adım belirgin. |
| Görsel stil | **A: oyunun kendisi gibi.** Koyu sıcak zemin, altın başlıklar, serif yazı. |
| Addon penceresi | **A: küçük köşe penceresi + ok.** Sağ üstte şu anki adım ve sıradaki adım, ilerleme çubuğu. Ekranın ortasında yön oku ve mesafe. |
| Son birleşik taslak | `.superpowers/brainstorm/.../content/son-taslak.html`. Görsel referans budur. **Ayrıca açık onay alınmadı**; inşaatın ilk adımında yeniden gösterilecek. |

Taslak dosyaları: `C:\Users\eren\Projects\forever-leveling\.superpowers\brainstorm\1061-1792635874\content\`

### 3.1 Tasarım sistemi (ecc:a11y-architect, WCAG 2.2 AA)

Renk tokenları (oranlar elle hesaplandı, yayından önce bir kontrast aracıyla yeniden ölçülecek):

| Token | Hex | Kullanım |
|---|---|---|
| bg | #0f0c08 | sayfa |
| surface | #1c1710 | kart, adım |
| raised | #2a2216 | aktif adım |
| border | #7a6a4a | çerçeveler (3:1) |
| text | #e8dcc4 | gövde (13.1:1) |
| muted | #a89c84 | koordinat, tamamlanan adım (6.6:1) |
| gold | #f0c060 | başlık, vurgu |
| quest | #ffd100 | görev adı (kalın) |
| npc | #7fd0ff | NPC adı |
| alliance / horde | #6aa6ff / #ff6b5e | fraksiyon (her zaman ikon + yazıyla) |
| success | #6fcf7f | tamamlandı işareti |

Kurallar:
- Yazıya `opacity` uygulanmaz. Soluk yazı da 4.5:1 kontrastı geçmek zorunda.
- Kalın yan şerit ve renkli parlama gölgesi kullanılmaz. Aktif adım `raised` zemin, ince altın çerçeve, altın numara rozeti ve "Now" etiketiyle gösterilir.
- Gövde metni 16px, hiçbir metin 14px'in altına inmez. Yazı tipleri: Cinzel (yalnızca 22px üstü başlıklar), Source Serif 4 (gövde), sayılar için tabular bir yazı tipi. Inter yerine daha karakterli bir seçenek (ör. IBM Plex Mono) değerlendirilir.
- 900px altında liste ve harita alt alta dizilir. Telefonda dokunma hedefleri en az 44px.
- Klavye: "aktif adıma atla" bağlantısı, Space ile adımı tamamla, isteğe bağlı kısayollar kapatılabilir. Değişiklikler bir live region ile duyurulur.
- Harita yalnızca destekleyici: her pinin yazılı bir karşılığı (koordinat listesi) var. Pinler `<button>`, haritada +/− düğmeleri var.
- `prefers-reduced-motion` desteklenir. Ayrıca "yüksek kontrast" anahtarı bulunur.
- Fraksiyon ve adım durumu yalnızca renkle anlatılmaz.

## 4. Oyun gerçekleri (araştırma, 22 Ekim 2026)

- **Irklar (9):** Human, Dwarf, Night Elf, Gnome, Orc, Undead, Tauren, Troll ve yeni **Skyborne**. Skyborne iki fraksiyonda da seçilebiliyor ve **Zephras Isle**'da (1–12) başlıyor.
- **Rota sayısı (benim kararım):** Irk seçici 9 ırkı gösterir. Skyborne seçilince bir de fraksiyon sorulur, yani toplam **10 rota** var. Aynı başlangıç bölgesini paylaşan ırklar (Dwarf/Gnome, Orc/Troll) ilk bölümde aynı adımları kullanabilir. Rotalar ırka özel görevler ve ayrılan yollar kadar farklılaşır, ama her ırkın 1–30 boyunca kendi rota dosyası olur.
- **Seviye sınırı:** 60. 1–30 arasında klasik bölgeler ve Zephras Isle var. Vanilla görevleri duruyor, üstüne "1000+" yeni ya da değişmiş görev eklendi (bir kısmı Elwynn ve Westfall'da).
- **Addon API:** `## Interface: 16001`, oyun tipi `forever` (`WOW_PROJECT_CAMELOT = 18`). API ailesi Mainline 12.1.5. Kullanılacak olaylar ve fonksiyonlar: `QUEST_ACCEPTED`, `QUEST_TURNED_IN`, `QUEST_LOG_UPDATE`, `C_QuestLog`, `C_Map`, `C_SuperTrack`. Bunların Forever'da çalıştığı **varsayım**; çıkışta Blizzard'ın Forever UI kaynağıyla doğrulanacak. "Secret values" kısıtlamaları aktif ve bazı fonksiyonlar (ör. `GetItemInfo`) kaldırılmış.
- **Yerel kurulum:** `E:\World of Warcraft\_forever_` (ürün `wowf`, sürüm 1.60.1.70245). Oyun henüz hiç başlatılmadı. Oyunda doğrulama 4 Kasım'dan önce mümkün değil.

## 5. Veri stratejisi: sağlam veritabanı

### 5.1 Kaynaklar ve güven sırası

| Kaynak | Ne için | Lisans / koşul | Rol |
|---|---|---|---|
| wago.tools DB2 (Forever build 1.60.1.x) | görev, harita, alan, XP tabloları | oyun verisi © Blizzard, olgu olarak kullanılır, ham dosya dağıtılmaz | **Ana kaynak** |
| pfQuest DB | vanilla görev, NPC ve koordinatlar | MIT | **Ana kaynak** |
| CMaNGOS classic-db | spawn ve önkoşul zincirleri | GPL-3.0, yalnızca olgu çıkarılır | Destek |
| Kendi kayıt addon'umuz (Recorder) | canlıda NPC yeri, gerçek önkoşul, görev ID | bizim | **Kesin doğrulama** |
| Wowhead Forever | görev serisi bilgisi, elle kontrol | toplu tarama yasak, yalnızca elle bakılır ve kaynak gösterilir | Karşılaştırma |
| Polestar (GPL-3.0) | rota yapısı, bilinen veri hataları, hata geçmişi | metni kopyalanmaz | Karşılaştırma / tuzak listesi |
| Lodestar (`danielcosta42/lodestar`, MIT) | Forever 1–60 rotaları, Skyborne dahil | MIT, atıf verilir. Verisi QuestieDB kökenli olduğu için yalnızca olgu alınır | Karşılaştırma |
| MittenQuest (`rneuwi/MittenQuest`, GPL-3.0) | Forever 1–60 rotaları (Skyborne yok) | yalnızca olgu, metin kopyalanmaz | Karşılaştırma |
| Evergreen (`Dj2Swagittarius/evergreen-wow-forever`, GPL-2.0) | ırk başına 1–60 rotaları | yalnızca olgu. Forever kısımları kendi içinde de "doğrula" işaretli | Karşılaştırma |
| RestedXP ücretsiz rotaları (`RestedXP/RXPGuides`, CC BY-NC-SA 4.0) | Forever ~1–20 + Skyborne | yalnızca olgu. Doğrudan kopya, veritabanını NC-SA lisansına bağlar | Karşılaştırma |
| Guidelime TUGs | Forever 1–30 | All Rights Reserved, yalnızca olgu | Karşılaştırma |
| QuestieDB | — | lisanssız ("tüm hakları saklı" sayılmalı) | **Kullanılmaz** |
| RestedXP ücretli rotaları, Zygor | — | kapalı / ücretli, sızdırılmış kopyalar dahil | **Kullanılmaz** |
| Guidelime motoru, TomTom | rota verisi yok (motor / ok) | All Rights Reserved | **Kullanılmaz** (kod) |

**Karşılaştırma kaynaklarının kullanımı:** Bu kaynaklardan yalnızca olgular alınır: görev ID'si, seviye, bölge ve hub sırası. Adım metni ve rota sırası bizim tarafımızdan yazılır, her adımda kaynağı kaydedilir. Topluluk rotalarının çoğu QuestieDB'den beslendiği için, iki topluluk rotası birbiriyle uyuşsa bile bu "iki bağımsız kaynak" sayılmaz. `cross-checked` için kaynaklardan en az biri wago DB2, pfQuest ya da Recorder olmalıdır. Rotaların hiçbiri canlı sunucuda doğrulanmamıştır (araştırma, 22 Ekim 2026).

### 5.2 Güvenilirlik kuralları

1. Her kayıt (görev, NPC, koordinat, önkoşul) `sources[]` alanında hangi kaynaktan geldiğini taşır.
2. Bir değer en az **iki bağımsız kaynakta** uyuşmuyorsa ya da tek kaynaktan geliyorsa `confidence: unverified` olur.
3. Durum seviyeleri: `unverified` → `cross-checked` (2+ kaynak uyuşuyor) → `verified-ingame` (Recorder ile build X'te doğrulandı). Site ve addon bu durumu gösterir.
4. **4 Kasım çıkış farkı:** canlı build'in DB2 tabloları betayla karşılaştırılır. Değişen görevler otomatik olarak `unverified`'a düşer.
5. Önkoşul zincirleri açıkça saklanır. Eksik zincir rota üretimini durdurur, sessizce atlanmaz.
6. Ham veri, normalize edilmiş veri ve kaynak sürümleri depoda tutulur (yalnızca dağıtılması serbest olanlar). Herkes veriyi yeniden üretip denetleyebilir. Veri kontrolleri CI'da her seferinde çalışır, "veri yok, atla" yolu olmaz.
7. Lisansı temiz girdiler ile sorunlu girdiler ayrı tutulur. QuestieDB kodda hiç yer almaz.

### 5.3 Canlıda doğrulama

- Ayrı, küçük bir **Recorder** addon'u yazılır. Oyuncu görevi aldığında, bitirdiğinde ve teslim ettiğinde görev ID, NPC ID, harita ID, koordinat ve build numarasını SavedVariables'a kaydeder.
- Kayıtlar bir betikle veritabanına aktarılır, uyuşan adımlar `verified-ingame` olur.
- İlk hedef: Eren'in kendi oynayışıyla en az bir rota (Human) 1–30 uçtan uca doğrulanır.

## 6. Mimari (ecc:architect önerisi)

### 6.1 Teknoloji

| Katman | Seçim | Gerekçe |
|---|---|---|
| Veri hattı | Python 3.14, komut satırı betikleri | Eren Python kullanıyor, veri işleme kolay |
| Veri sözleşmesi | JSON Schema (`schema/route.schema.json`) | Python da site de aynı şemayla doğrular |
| Web sitesi | Astro (statik) + tek React adası (liste + harita) | Çoğu sayfa düz HTML, React/TS yüzeyi küçük (Eren TS/React'te yeni) |
| Harita | Leaflet `CRS.Simple` | Oyunun 0–100 koordinatlarını doğrudan kullanır |
| Addon | Saf Lua + XML, v1'de kütüphane yok | Az bağımlılık, ok kendi yazılır |
| Barındırma | Cloudflare Pages (yedek: GitHub Pages) | Ücretsiz, Git'ten derlenir |
| Addon dağıtımı | CurseForge + Wago Addons | Ücretsiz |

Hesap ve sunucu yok. İlerleme `localStorage`'da `fxp:v1:<race>` anahtarıyla tutulur. Aylık maliyet yaklaşık 0 $ (alan adı isteğe bağlı).

### 6.2 Veri akışı (tek doğruluk kaynağı)

```
kaynaklar (wago DB2, pfQuest, CMaNGOS, Recorder kayıtları)
  -> pipeline/ingest      raw/        (önbellek; dağıtılamayanlar gitignore)
  -> pipeline/normalize   data/canonical/*.json  (commit edilir, sources[] + confidence)
  -> pipeline/crosscheck  uyuşmazlık raporu
  -> pipeline/generate    data/routes/<route>.generated.json
  -> overrides            data/overrides/<route>.yaml  (insan düzeltmeleri)
  -> validate             data/routes/<route>.json     (şemaya uygun, commit edilir)
  -> export
       |- site/src/data/*.json          -> Astro -> Cloudflare Pages
       |- addon/ForeverXP/Data/*.lua    (otomatik üretilir, "ELLE DÜZENLEME")
```

Üretilen dosyalar elle düzenlenmez. İnsan düzeltmeleri `overrides/` içinde yama olarak durur (`insertAfter`, `remove`, `move`, `setCoords`). Böylece rota yeniden üretildiğinde düzeltmeler kaybolmaz.

### 6.3 Veri şeması (özet)

**Quest:** `id` (Blizzard questID), `name`, `level`, `minLevel`, `faction`, `races[]`, `classes[]`, `prereqs[]`, `startNpc {id,name,mapId,x,y}`, `endNpc`, `objectives[] {type,targetIds[],count,areas[]}`, `xp`, `sources[]`, `confidence`, `seenInBuild`

**Route:** `id`, `race`, `faction`, `levelRange [1,30]`, `generatedAt`, `dataBuild`, `reviewed`, `steps[]`

**Step** (ortak alanlar: `id` (kalıcı, asla yeniden kullanılmaz), `type`, `mapId`, `x`, `y`, `note?`, `classOnly?`, `confidence`):

| type | ek alanlar | addon'da otomatik ilerleme |
|---|---|---|
| accept | questId, npcId | `QUEST_ACCEPTED` |
| turnin | questId, npcId | `QUEST_TURNED_IN` |
| complete | questId, objectiveIdx? | `QUEST_LOG_UPDATE` + `C_QuestLog.IsComplete` |
| travel | mode (walk/flight/boat/zeppelin/hearth), radius | oyuncu hedef yarıçapa girince |
| sethearth | npcId | `HEARTHSTONE_BOUND` |
| train | npcId | elle / `TRAINER_CLOSED` |
| grind | untilLevel, untilXpPct? | `PLAYER_LEVEL_UP` / `PLAYER_XP_UPDATE` |

Adımlarda yalnızca kimlikler tutulur, adlar dışa aktarımda eklenir. BiS özelliği ileride `items.json` ve `classSpecs` olarak eklenir, rota hattı değişmez.

### 6.4 Rota üretimi (kural tabanlı, basit)

1. Irkın fraksiyonu ve ırkı için görevler filtrelenir (`minLevel ≤ 30`).
2. Önkoşullardan bir bağımlılık grafiği kurulur: accept → complete → turnin.
3. Yakın NPC'ler "hub" olarak kümelenir.
4. Hub'lar ortalama görev seviyesine ve mesafeye göre sıralanır.
5. Hub içinde önce tüm görevler alınır, hedefler en yakın komşu sırasıyla bitirilir, sonra teslim edilir.
6. XP simülasyonu: oyuncu bir hub'da görev seviyesinin 2 altına düşerse grind adımı eklenir ya da sonraki hub'ın görevleri öne çekilir. Görev günlüğü sınırı Forever'ın gerçek değeriyle modellenir (araştırmaya göre 40, doğrulanacak).
7. Bölgeler arası sıra elle yazılan `data/zone-order/<route>.yaml` dosyasından okunur (§8.2). Topluluk rehberlerinden yalnızca bu sıra için fikir alınır, metin alınmaz.
8. Çıktı kalitesi yetersizse daha sonra hub sırası üzerinde 2-opt iyileştirmesi eklenir. Gerek kanıtlanmadan eklenmez.

### 6.5 Depo düzeni

```
forever-leveling/
  schema/          route.schema.json
  pipeline/        ingest/ normalize/ crosscheck/ generate/ validate/ export/  (Python)
  data/            canonical/ routes/ overrides/ recordings/
  site/            Astro (src/pages/[route].astro, src/islands/RouteView.tsx)
  addon/ForeverXP/ ForeverXP.toc, Core.lua, Arrow.lua, UI.lua, Compat.lua, Data/ (üretilir)
  addon/ForeverXP_Recorder/
  docs/            plan.md, tasarım taslakları
  .github/workflows/ ci.yml, release.yml
```

## 7. Doğrulama ve test

- **Şema:** her rota dosyası JSON Schema'ya karşı doğrulanır, hata varsa CI düşer.
- **Anlamsal kontroller (pytest):**
  - turnin ve complete her zaman accept'ten sonra gelir.
  - Önkoşul, kabulden önce teslim edilmiştir.
  - Kabul edilen her görev kapanır.
  - Koordinatlar 0–100 aralığında ve `mapId` mevcut.
  - Tekrarlanan adım kimliği yok.
  - XP simülasyonu 30'a ulaşıyor.
  - Hiçbir adım oyuncunun seviyesinin 3 üstünde değil.
- **Çapraz kontrol raporu:** her build için kaç kaydın `unverified`, `cross-checked` ve `verified-ingame` olduğu yazılır.
- **Snapshot:** üretici çıktısındaki fark PR'da görünür.
- **Lua dışa aktarım testi:** üretilen Lua okunur ve JSON ile karşılaştırılır.
- **Site:** Playwright testi. Bir ırk açılır, adım işaretlenir, sayfa yenilenir, işaret durmalıdır. Bunlara erişilebilirlik taraması (axe) ve 320px görünüm kontrolü eklenir.
- **Oyunda:** rota başına oynama kontrol listesi ve Recorder kayıtları.

## 8. Aşamalar ve yol haritası

| Aşama | İçerik | Bitti sayılması için |
|---|---|---|
| **0 · Tasarım onayı** (şimdi) | Bu plan + tarayıcı taslakları | Eren planı ve son taslağı onaylar |
| **1 · Veri temeli** (4 Kasım öncesi) | şema, ingest (wago DB2 beta + pfQuest), normalize, crosscheck. İlk rota: Human 1–12 | CI yeşil, çapraz kontrol raporu çıkıyor |
| **2 · Rota üretici** | generate + overrides + validate, 10 rota | 10 rotanın tümü şemayı ve anlamsal kontrolleri geçiyor |
| **3 · Web sitesi** | ırk seçici, rota sayfası (liste + harita), ilerleme, Cloudflare Pages | Playwright + axe yeşil, taslakla görsel olarak uyumlu |
| **4 · Çıkış günü (4 Kasım+)** | canlı DB2 farkı, Recorder addon'u, Eren'in Human playtest'i | Human 1–30 `verified-ingame` |
| **5 · Oyun içi addon** | pencere + ok + otomatik ilerleme + geri/atla + karakter başına kayıt | Human rotası addon'la baştan sona oynanabiliyor. CurseForge/Wago'da yayında |
| **Sonra** | BiS / çantada en iyi eşya, 30+ seviyeler | ayrı plan |

Ayrıntılı iş listesi: **Ek A**.

Not: Aşama 1–3 çıkıştan önce beta verisiyle yapılır ve site "beta verisi" etiketiyle açılabilir. Asıl güven Aşama 4'te gelir.

### 8.1 Eren'in kararları (22 Ekim 2026)

- **4 Kasım için zorunlu teslim yok.** Önce 10 rotalık sağlam altyapı kurulur. Site hazır olduğunda açılır. Takvim baskısı yüzünden veri kalitesinden ödün verilmez.
- **Yayın eşiği aşamalıdır.**
  - **"Beta" etiketli bir rota** `unverified` adımlar içerebilir. Bu adımlar sitede ve addon'da açıkça işaretlenir.
  - **"Tam sürüm" etiketi** için rotadaki her adımın en az `cross-checked` olması gerekir. Önkoşul zincirlerinde boşluk olmamalıdır.
  - Bu eşik CI'da rota başına kontrol edilir.
  - Eksik önkoşul zinciri beta rotasında üretimi durdurmaz. Bunun yerine `gap` türünde, işaretli bir adım üretilir. Tam sürüm rotasında ise üretimi durdurur.

### 8.2 Builder check sonrası kararlarım

- **Bölge sırası elle, adımlar otomatik.** Her rotanın kıtalar ve bölgeler arası sırası (ör. Elwynn → Westfall → Loch Modan …) bir insan tarafından `data/zone-order/<route>.yaml` dosyasına yazılır. Bölge içindeki hub, görev ve adım sırasını üretici otomatik çıkarır. Bölge sırası yazılırken topluluk rehberlerinden yalnızca fikir alınır.
- **Harita v1'de sade.** Pinler, bölge adı ve 0–100 koordinat ızgarası üzerinde gösterilir, yanında koordinat listesi durur. Blizzard harita dokusu barındırılmaz. Gerçek bölge çizimleri v1 sonrasına kalır.
- **Yeni ve değişmiş Forever görevlerinin verisi.** pfQuest ve CMaNGOS yalnızca vanilla görevleri kapsıyor. wago DB2 görev kimliği, ad, seviye ve XP verir, ama NPC yeri ve önkoşul vermeyebilir. Bu nedenle:
  - Çıkıştan önce Forever'a özgü görevler (Zephras Isle, Skyborne, Elwynn/Westfall'daki yenilikler) Wowhead Forever sayfalarından **elle** girilir. Bu kayıtlar `source: wowhead-manual` ile işaretlenir ve `unverified` sayılır.
  - Asıl doğrulama çıkıştan sonra Recorder ile yapılır. Elle girilecek kayıt sayısı Aşama 1 sonunda ölçülür ve takvim buna göre güncellenir.
- **wago.tools'ta Forever beta verisinin varlığı doğrulanmadı.** Aşama 1'in ilk işi bunu denemektir. Zephras/Skyborne verisi yoksa Skyborne rotaları çıkış sonrasına kayar ve Aşama 2 hedefi geçici olarak 8 rotaya iner.

## 9. Riskler

| Risk | Önlem |
|---|---|
| Canlı veri betadan farklı | Çıkış günü DB2 farkı, değişen kayıtlar otomatik `unverified` |
| Kaynak lisansı / kullanım koşulları | §5.1 tablosu. QuestieDB, Wowhead taraması ve ücretli rehber içeriği yok. Her kayıtta kaynak |
| Rota kalitesi (otomatik üretim kötü sıralayabilir) | XP simülasyonu kapısı, override katmanı, Polestar hata geçmişi tuzak listesi, oyunda doğrulama, sitede "bu adımı bildir" bağlantısı |
| Addon API farkları / secret values | API çağrıları tek bir `Compat.lua` dosyasında. Konum alınamayınca ok gizlenir. Çıkışta Forever UI kaynağıyla kontrol edilir |
| Harita görselleri (Blizzard varlıkları) | v1'de sade koordinat ızgarası (§8.2). Ham oyun dokusu barındırılmaz |
| Forever'a özgü görevlerde temiz kaynak eksik | Çıkış öncesi Wowhead'den elle giriş (`unverified`), çıkış sonrası Recorder doğrulaması (§8.2) |
| Tek kişilik geliştirme, kapsamın büyümesi | Önce bir rota uçtan uca bitirilir, sonra çoğaltılır. Tek React bileşeni, backend yok |

## 10. Kullanılan ECC ajanları

| Ajan | İş |
|---|---|
| superpowers:brainstorming + görsel companion | soru-cevap, tarayıcıda 4 taslak ekranı |
| general-purpose (araştırma) | Forever gerçekleri, kaynaklar, lisanslar |
| general-purpose (Polestar denetimi) | Polestar veri güvenilirliği |
| ecc:architect | mimari, şema, aşamalar |
| ecc:a11y-architect | WCAG 2.2 AA tasarım sistemi |
| ecc:planner | uygulama adımlarının sırası ve riskleri (bkz. Ek A) |
| bağımsız okuyucu (builder check) | planda eksik kalan soruların denetimi |

İnşaat sırasında kullanılacak ajanlar: ecc:tdd-guide, ecc:python-reviewer, ecc:typescript-reviewer, ecc:react-reviewer, ecc:e2e-runner, ecc:security-reviewer, ecc:seo-specialist, impeccable (tasarım cilası ve denetimi).

## 11. Kurucuya bırakılanlar

- Astro bileşen yapısı, CSS düzeni, Python modül ayrımı.
- Hub kümeleme eşiği gibi algoritma parametreleri (testlerle ayarlanır).
- Addon penceresinin tam piksel boyutları (taslak referans alınır).
- Alan adı (isteğe bağlı, Eren karar verir).

## 12. Benim verdiğim kararlar (Eren'in kontrol etmesi için)

1. Ürün adı "ForeverXP" (geçici).
2. Skyborne için fraksiyona göre 2 rota, toplam 10 rota.
3. Site arayüzü İngilizce (oyun terimleri İngilizce olduğu için).
4. Sınıfa özel rota yok, sınıf adımları rota içinde dal olarak geçer.
5. Önce site, sonra addon. Ama addon'un veri dosyası Aşama 2'den itibaren otomatik üretilir.
6. Hesap yok, ilerleme tarayıcıda tutulur.
7. Polestar'dan kod ve metin alınmaz, yalnızca karşılaştırma kaynağıdır. Bu sayede addon'un lisansını Eren seçer.
8. Bölge sırası elle, bölge içi adımlar otomatik (§8.2).
9. v1 haritası sade koordinat ızgarası (§8.2).
10. Forever'a özgü görevler çıkıştan önce Wowhead'den elle girilir ve `unverified` sayılır (§8.2).
11. Lua birim testleri için bir Lua yorumlayıcısı (ör. busted) kurulacak. Bu bir yazılım kurulumu olduğu için zamanı gelince ayrıca onay istenecek.

---

## Ek A — Uygulama adımları (ecc:planner, kararlara göre güncellendi)

**Ön koşul:** Aşama 0 onayı (plan + `son-taslak.html`). Onay yoksa hiçbir iş başlamaz.
**İşaretler:** **Ö** = 4 Kasım öncesi yapılabilir · **Ç** = çıkışı bekler · **∥** = paralel yürüyebilir · Bağ. = bağımlılık. Her iş tek oturumluk (~1–4 saat). Her işte önce test yazılır, sonra kod. 4 Kasım için zorunlu teslim olmadığından (§8.1) sıralama takvime göre değil, bağımlılığa göre yapıldı.

### İlk 5 iş

1. **1.0** wago.tools Forever beta verisi var mı, keşif (yarım gün)
2. **1.1** Depo iskeleti + CI
3. **1.2** JSON Schema (adım türlerine `gap` dahil)
4. **1.3** wago DB2 ingest ∥ **1.4** pfQuest ingest
5. **2.1** Anlamsal kontroller (yalnız 1.2'ye bağlı, ingest işleriyle ∥)

### Aşama 1 · Veri temeli (tümü Ö)

| # | İş | Dosyalar | Önce yazılan test | Çıkış | Bağ. | Ajan |
|---|---|---|---|---|---|---|
| 1.0 | wago.tools'ta Forever beta tabloları: QuestV2, QuestXP, UiMap, AreaTable var mı? Zephras/Skyborne içeriği var mı? | `docs/spike-wago.md` | — (keşif) | Sonuç yazılı. Yoksa Skyborne çıkış sonrasına alınır (§8.2) | — | general-purpose |
| 1.1 | İskelet, CI, `raw/` gitignore | `pyproject.toml`, `pipeline/`, `.github/workflows/ci.yml` | `tests/test_smoke.py` | `python -m pytest` yeşil, CI yeşil | — | ecc:tdd-guide |
| 1.2 | Route + Quest şeması (`gap` adımı, `confidence`, `sources[]`) | `schema/route.schema.json` | `tests/test_schema.py` (geçerli ve geçersiz fixture) | Geçersiz fixture reddediliyor | 1.1 | ecc:python-reviewer |
| 1.3 | wago DB2 beta ingest | `pipeline/ingest/wago.py` | Örnek CSV ile ayrıştırma testi | `raw/wago/` doluyor | 1.0, 1.1 ∥ | ecc:python-reviewer |
| 1.4 | pfQuest ingest | `pipeline/ingest/pfquest.py` | Örnek Lua tablosu testi | NPC ve koordinat çıkıyor | 1.1 ∥ | ecc:python-reviewer |
| 1.5 | CMaNGOS önkoşul ve spawn | `pipeline/ingest/cmangos.py` | Zincir çıkarım testi | Önkoşullar okunuyor | 1.1 ∥ | ecc:python-reviewer |
| 1.6 | Lisans kapısı | `tests/test_license_guard.py` | QuestieDB ve yasaklı kaynak izi testi | CI'da çalışıyor | 1.1 ∥ | ecc:security-reviewer |
| 1.7 | Elle giriş formatı (Wowhead'den bakılan Forever görevleri) | `data/manual/*.yaml`, `pipeline/ingest/manual.py` | `source: wowhead-manual` → `unverified` testi | Zephras ve Elwynn yenilikleri girilebiliyor | 1.2 ∥ | ecc:python-reviewer |
| 1.8 | Normalize: `sources[]`, `confidence` | `pipeline/normalize/`, `data/canonical/*.json` | Tek kaynak → `unverified`, iki kaynak → `cross-checked` | Human 1–12 görevleri canonical'da | 1.2–1.7 | ecc:tdd-guide |
| 1.9 | Crosscheck raporu + elle giriş sayımı | `pipeline/crosscheck/` | Uyuşmazlık fixture testi | Sayılar yazılıyor, elle girilecek kayıt sayısı ölçüldü (§8.2) | 1.8 | ecc:python-reviewer |

### Aşama 2 · Rota üretici (tümü Ö)

| # | İş | Dosyalar | Önce yazılan test | Çıkış | Bağ. | Ajan |
|---|---|---|---|---|---|---|
| 2.1 | §7'deki anlamsal kurallar + beta/tam sürüm eşiği (§8.1) | `pipeline/validate/semantic.py` | `tests/test_semantic.py` (her kural için kırık rota) | Kurallar kırmızıdan yeşile döndü | 1.2 ∥ | ecc:tdd-guide |
| 2.2 | Bölge sırası dosyaları | `data/zone-order/*.yaml` | Şema testi, bilinmeyen bölge hatası | Human sırası yazılı | 1.2 ∥ | — |
| 2.3 | Filtre + bağımlılık grafiği | `pipeline/generate/graph.py` | Eksik zincir: beta'da `gap`, tam sürümde hata | Sessiz atlama yok | 1.8 | ecc:tdd-guide |
| 2.4 | Bölge içi hub kümeleme ve sıralama | `pipeline/generate/hubs.py` | Sentetik harita testi | Sıra deterministik | 2.2, 2.3 | ecc:python-reviewer |
| 2.5 | XP simülasyonu, grind, görev günlüğü sınırı | `pipeline/generate/xpsim.py` | 30'a ulaşma ve +3 seviye kuralı | Human 1–12 üretiliyor | 2.4 | ecc:python-reviewer |
| 2.6 | Overrides yamaları | `data/overrides/*.yaml`, `pipeline/generate/overrides.py` | Yeniden üretimde yama korunuyor | Dört yama türü çalışıyor | 2.3 ∥ | ecc:python-reviewer |
| 2.7 | JSON + Lua dışa aktarımı | `pipeline/export/`, `site/src/data/`, `addon/ForeverXP/Data/` | Lua→JSON eşitlik testi, snapshot | "ELLE DÜZENLEME" başlığı var | 2.5 | ecc:python-reviewer |
| 2.8 | Human 1–30 uçtan uca | `data/routes/human.json` | Snapshot | validate yeşil (beta eşiği) | 2.5–2.7 | ecc:tdd-guide |
| 2.9 | Kalan 9 rota (Skyborne ×2, 1.0 sonucuna bağlı) | `data/routes/*.json` | Rota başına snapshot | `python -m pipeline.validate --all` yeşil | 2.8 | ecc:python-reviewer |

### Aşama 3 · Web sitesi (tümü Ö; 3.1 hemen, kalanı 2.7'den sonra 2.8–2.9 ile ∥)

| # | İş | Dosyalar | Önce yazılan test | Çıkış | Bağ. | Ajan |
|---|---|---|---|---|---|---|
| 3.1 | Astro iskeleti, §3.1 tokenları, son taslağı Eren'e yeniden göster | `site/`, `site/src/styles/tokens.css` | Token kontrast testi (≥4.5:1) | Eren taslağı onayladı | Aşama 0 | impeccable |
| 3.2 | Irk seçici + Skyborne fraksiyon sorusu | `site/src/pages/index.astro` | Playwright: her rotaya ulaşılıyor | Test yeşil | 3.1 | ecc:e2e-runner |
| 3.3 | RouteView listesi + `fxp:v1:<race>` | `site/src/islands/RouteView.tsx` | Playwright: işaretle, yenile, işaret duruyor | Test yeşil | 3.2, 2.7 | ecc:typescript-reviewer, ecc:react-reviewer |
| 3.4 | Sade koordinat ızgarası haritası (Leaflet `CRS.Simple`), `<button>` pinler, +/−, koordinat listesi | `RouteView.tsx` | Pine klavyeyle erişim testi | Blizzard dokusu yok | 3.3 | ecc:react-reviewer |
| 3.5 | Skip link, Space, live region, reduced motion, yüksek kontrast, 900/320px | `site/src/` | axe + 320px Playwright | axe 0 ihlal | 3.4 | impeccable |
| 3.6 | "Beta" / "tam sürüm" etiketi, `unverified` ve `gap` adım işaretleri, "bu adımı bildir", meta etiketleri | `site/src/layouts/` | Playwright etiket kontrolü | Lighthouse SEO ≥ 90 | 3.3 ∥ | ecc:seo-specialist |
| 3.7 | Cloudflare Pages dağıtımı, CSP (hesap kurulumu Eren'in onayıyla) | `.github/workflows/`, `site/public/_headers` | Başlık testi | Canlı URL açılıyor | 3.5 | ecc:security-reviewer |

### Aşama 4 · Çıkış günü

| # | İş | Dosyalar | Önce yazılan test | Çıkış | Ö/Ç | Ajan |
|---|---|---|---|---|---|---|
| 4.1 | Recorder addon'u | `addon/ForeverXP_Recorder/` | — (oyunda denenecek) | Kod hazır | Ö | ecc:security-reviewer |
| 4.2 | Kayıtları aktarma betiği | `pipeline/ingest/recordings.py`, `data/recordings/` | Örnek SavedVariables → `verified-ingame` | pytest yeşil | Ö ∥ | ecc:tdd-guide |
| 4.3 | Build farkı betiği | `pipeline/crosscheck/builddiff.py` | Değişen görev `unverified`'a düşüyor | pytest yeşil | Ö ∥ | ecc:python-reviewer |
| 4.4 | Canlı DB2 ingest, fark, rotaları yeniden üret | `data/` | Mevcut testler | validate yeşil | Ç (4.3) | ecc:python-reviewer |
| 4.5 | API ve görev günlüğü sınırını Forever UI kaynağıyla doğrula | `docs/`, `Compat.lua` notları | — | Varsayım listesi kapandı | Ç | — |
| 4.6 | Eren'in Human 1–30 playtest'i (1–12, 12–20, 20–30) + override düzeltmeleri | `data/recordings/`, `data/overrides/human.yaml` | — | Human 1–30 "tam sürüm" eşiğini geçiyor | Ç (4.1–4.4) | — |

### Aşama 5 · Oyun içi addon

| # | İş | Dosyalar | Önce yazılan test | Çıkış | Ö/Ç | Ajan |
|---|---|---|---|---|---|---|
| 5.1 | TOC (`Interface: 16001`) + `Compat.lua` | `addon/ForeverXP/` | Sahte API ile Lua birim testi | Addon listede görünüyor | Ö yazılır, Ç doğrulanır | ecc:tdd-guide |
| 5.2 | Core durum makinesi: olay → adım, geri/atla, karakter başına kayıt | `Core.lua` | Sahte olay dizisi testi | Test yeşil | Ö (5.1) | ecc:tdd-guide |
| 5.3 | Köşe penceresi + ilerleme çubuğu, `unverified` işareti | `UI.lua` | — | Taslakla uyumlu | Ö ∥ 5.4 | impeccable |
| 5.4 | Ok + mesafe, konum yoksa gizle | `Arrow.lua` | Açı ve mesafe hesap testi | Test yeşil | Ö ∥ 5.3 | ecc:tdd-guide |
| 5.5 | Human rotasını addon'la oyna | — | — | 1–30 kopmadan tamamlandı | Ç (4.6, 5.1–5.4) | — |
| 5.6 | `release.yml`, CurseForge ve Wago (yayın Eren'in onayıyla) | `.github/workflows/release.yml` | Paket içeriği testi | İki sitede yayında | Ç | ecc:security-reviewer |

### Takvimi en çok tehdit eden 3 risk

1. **Beta DB2 verisi:** wago.tools'ta Forever tabloları eksikse 1.3 ve ondan sonraki işler tıkanır. Önlem: 1.0 ilk gün yapılır, pfQuest ile Elwynn yedek olarak hazır tutulur.
2. **Elle giriş yükü:** Forever'a özgü görevlerin sayısı büyükse 1.7 ile 1.9 arasındaki işler uzar. Önlem: 1.9'da sayı ölçülür, plan o sayıya göre güncellenir.
3. **Çıkış haftasında tek kişi:** API farkları ve secret values 5.x işlerini, playtest süresi de 4.6'yı uzatabilir. Önlem: Recorder (4.1) ve fark betiği (4.3) çıkıştan önce biter, oyun API'si yalnız `Compat.lua` üzerinden çağrılır.
