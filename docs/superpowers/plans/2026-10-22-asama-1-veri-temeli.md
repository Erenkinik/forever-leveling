# Aşama 1 — Veri Temeli: Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Forever görevlerinin kaynaklı ve güven düzeyli kanonik veritabanını (`data/canonical/quests.json`) wago DB2 + pfQuest + elle girişten üreten, test edilmiş bir Python veri hattı kurmak; ayrıca rota dosyaları için şema ve anlamsal doğrulayıcıyı hazırlamak.

**Architecture:** `pipeline/` altında saf Python modülleri: `ingest/` her kaynağı indirip ayrıştırır (ağ yalnızca `fetch_*` fonksiyonlarında), `normalize/` kaynakları birleştirip `sources`/`lineages`/`conflicts`/`confidence` hesaplar, `crosscheck/` rapor yazar, `validate/` şema ve rota kurallarını uygular. Testler yalnızca `tests/fixtures/` altındaki küçük kesitlerle çalışır, ağa çıkmaz.

**Tech Stack:** Python 3.14, pytest, jsonschema, PyYAML (proje `.venv`'i); GitHub Actions.

**Spec:** `docs/plan.md` (onaylandı 2026-10-22) — özellikle §5 Veri stratejisi, §6.3 şema, §7 test, §8.1–8.2 kararlar, Ek A Aşama 1 ve 2.1.

## Global Constraints

- Proje kökü: `C:\Users\eren\Projects\forever-leveling`. Kod, tanımlayıcı ve commit mesajları İngilizce; belgeler Türkçe.
- Python: `.venv\Scripts\python` (3.14). Bağımlılıklar yalnızca `pytest`, `jsonschema`, `PyYAML`. Lua kütüphanesi yok: pfQuest Lua tabloları kendi küçük ayrıştırıcımızla okunur.
- Windows: dosyalar UTF-8 (BOM'suz) yazılır, `open(..., encoding="utf-8")` her yerde açıkça verilir; Unicode basan komutlar `PYTHONIOENCODING=utf-8` ile çalışır.
- Forever DB2 build sabiti: `DATA_BUILD = "1.60.1.70532"` (`pipeline/config.py`). wago CSV URL kalıbı: `https://wago.tools/db2/{table}/csv?build={build}`.
- pfQuest kaynağı: `https://raw.githubusercontent.com/shagu/pfQuest/master/db/` dosyaları `quests.lua`, `units.lua`, `objects.lua`, `enUS/quests.lua`, `enUS/units.lua` (MIT).
- `raw/` git'e girmez (wago ham CSV'leri © Blizzard, dağıtılmaz). `data/canonical/` commit edilir (yalnızca olgular).
- QuestieDB, RestedXP ücretli içerik, Zygor, Guidelime/TomTom kodu hiçbir dosyada yer almaz (lisans kapısı testi bunu zorlar). pfQuest'in `D`/`O` (görev açıklama metni) alanları alınmaz; yalnızca `T` (ad).
- Kaynak kimlikleri ve soyları (lineage) — **sabit**:
  | source | lineage |
  |---|---|
  | `wago-db2` | `blizzard-client` |
  | `pfquest` | `vanilla-emu` |
  | `cmangos` | `vanilla-emu` |
  | `wowhead-manual` | `wowhead` |
  | `recorder` | `ingame` |
  | `lodestar`, `mittenquest`, `evergreen`, `polestar`, `rxp-free`, `tugs` | `community` |
- Güven kuralı (§5.2 + §5.1 notu): `verified-ingame` ⇐ `ingame` soyu var; aksi hâlde `cross-checked` ⇐ en az 2 farklı soy VE `conflicts` boş VE soylardan biri `blizzard-client`/`vanilla-emu`/`ingame`; aksi hâlde `unverified`. `community` soyu tek başına sayılmaz.
- Irk bit maskesi (vanilla): Human 1, Orc 2, Dwarf 4, Night Elf 8, Undead 16, Tauren 32, Gnome 64, Troll 128. Skyborne biti bilinmiyor → `RACE_BITS` içinde yok; bilinmeyen bitler `races` listesine `"unknown-bit-<n>"` olarak düşer (sessizce atılmaz).
- Commit'ler: Eren'in onayıyla, yalnızca yerel; push yok.

## Review Focus

1. **Eşya ya da nesneyle başlayan görev** (pfQuest `start.I` / `start.O`): `start.type` `"item"`/`"object"` olur, koordinat `null`; normalize çökmez. → Task 6 testi `test_quest_started_by_item`.
2. **NPC'nin koordinatı yok ya da birden çok bölgede**: görevin başlangıç bölgesine ait ilk koordinat seçilir; hiç yoksa `x/y/uiMapId = null` ve `conflicts` içine `"start.coords"` eklenir. → Task 6 `test_npc_without_coords_marks_conflict`.
3. **Forever'da olan ama pfQuest'te olmayan görev** (yeni Forever görevi): sessizce düşmez; elle giriş yoksa crosscheck raporunda `needsManual` listesinde çıkar. → Task 7 `test_new_forever_quest_listed_as_needs_manual`.
4. **pfQuest'te olan ama Forever QuestV2'de olmayan görev**: kanonik veride `inForever: false` ile kalır, rota üretimine girmez, raporda sayılır. → Task 6 `test_quest_missing_from_forever_flagged`.
5. **Lua dizgesinde kaçışlar ve CRLF** (`\'`, `\"`, `\\`, `$B`, Windows satır sonu): ayrıştırıcı birebir çözer. → Task 3 `test_parses_escapes_and_crlf`.

---

### Task 1: Depo iskeleti, keşif notu, CI

**Files:**
- Create: `.gitignore`, `pyproject.toml`, `pipeline/__init__.py`, `pipeline/config.py`, `tests/test_smoke.py`, `.github/workflows/ci.yml`, `docs/spike-wago.md`, `THIRD_PARTY.md`

**Interfaces:**
- Produces: `pipeline.config` → `DATA_BUILD: str`, `ROOT: Path` (proje kökü), `RAW_DIR = ROOT/"raw"`, `DATA_DIR = ROOT/"data"`, `SOURCE_LINEAGE: dict[str, str]` (Global Constraints tablosu), `RACE_BITS: dict[str, int]`.

- [ ] **Step 1:** `git init` (kök dizinde), `python -m venv .venv`, `.venv\Scripts\python -m pip install pytest jsonschema PyYAML` (Eren'in kurulum onayı alınmış olmalı).
- [ ] **Step 2: Failing test** `tests/test_smoke.py`:
  ```python
  from pipeline import config
  def test_config_constants():
      assert config.DATA_BUILD == "1.60.1.70532"
      assert config.SOURCE_LINEAGE["pfquest"] == "vanilla-emu"
      assert config.SOURCE_LINEAGE["lodestar"] == "community"
      assert config.RACE_BITS["Gnome"] == 64
      assert config.RAW_DIR.name == "raw"
  ```
- [ ] **Step 3:** Run `.venv\Scripts\python -m pytest -q` → FAIL (`ModuleNotFoundError`).
- [ ] **Step 4:** `pipeline/config.py`'yi yaz. `pyproject.toml`: `[project] name="foreverxp-pipeline" requires-python=">=3.14"`, `[tool.pytest.ini_options] testpaths=["tests"]`. `.gitignore`: `.venv/`, `raw/`, `__pycache__/`, `.superpowers/`. CI: `windows-latest`, Python 3.14, `pip install pytest jsonschema PyYAML`, `python -m pytest -q`.
- [ ] **Step 5:** `docs/spike-wago.md`'ye 22 Ekim keşfini yaz: `wowf` build'leri 70532/70245; tablolar ve satır sayıları (QuestV2 6616 ID, yalnız `ID,UniqueBitFlag,UiQuestDetailsThemeID`; UiMap'te Elwynn 1429, Westfall 1436, Zephras Isle 2521; QuestPOIBlob 57 satır — kullanışsız); sonuç: wago yalnız "görev Forever'da var mı" + harita tabloları için kullanılır, ad/seviye/NPC pfQuest ve elle girişten gelir. `THIRD_PARTY.md`: pfQuest MIT atfı, wago DB2 "game data © Blizzard, used as facts, not redistributed".
- [ ] **Step 6:** Test → PASS. Commit: `chore: scaffold pipeline, config, CI and wago spike notes`.

### Task 2: JSON şemaları ve doğrulama yardımcısı

**Files:**
- Create: `schema/quest.schema.json`, `schema/route.schema.json`, `pipeline/schema.py`, `tests/test_schema.py`, `tests/fixtures/route_valid.json`, `tests/fixtures/route_invalid_steptype.json`

**Interfaces:**
- Produces: `pipeline.schema.validate(kind: Literal["quest","route"], obj: dict) -> list[str]` (boş liste = geçerli; hata mesajları JSON-pointer yolu içerir).
- Quest nesnesi alanları: `id:int`, `name:str|null`, `level:int|null`, `minLevel:int|null`, `races:list[str]|null` (null = tüm ırklar), `prereqs:list[int]`, `start`/`end`: `{type: "npc"|"item"|"object"|null, id:int|null, name:str|null, uiMapId:int|null, x:number|null, y:number|null}`, `objectives: {units:list[int], items:list[int], objects:list[int]}`, `inForever:bool`, `sources:list[str]` (enum = SOURCE_LINEAGE anahtarları), `lineages:list[str]`, `conflicts:list[str]`, `confidence: "unverified"|"cross-checked"|"verified-ingame"`, `verifiedBuild:str|null`.
- Route nesnesi (plan §6.3): `id, race, faction ("Alliance"|"Horde"), levelRange [int,int], generatedAt (ISO 8601 UTC), dataBuild, reviewed:bool, releaseTier: "beta"|"full", steps[]`. Step ortak: `id` (`^[a-z0-9-]+$`), `type` ∈ `accept|turnin|complete|travel|sethearth|train|grind|gap`, `mapId:int`, `x,y` ∈ [0,100], `note?`, `classOnly?: list[str]`, `confidence`. Türe özel zorunlu alanlar `oneOf` ile: accept/turnin → `questId,npcId`; complete → `questId`; travel → `mode` ∈ `walk|flight|boat|zeppelin|hearth`, `radius`; sethearth/train → `npcId`; grind → `untilLevel`; gap → `reason:str` (§8.1).

- [ ] **Step 1: Failing tests** `tests/test_schema.py`:
  ```python
  def test_valid_route_passes(): assert validate("route", load("route_valid.json")) == []
  def test_unknown_step_type_rejected():
      errs = validate("route", load("route_invalid_steptype.json")); assert any("/steps/0" in e for e in errs)
  def test_gap_step_requires_reason():
      r = load("route_valid.json"); r["steps"].append({"id":"g1","type":"gap","mapId":1429,"x":1,"y":1,"confidence":"unverified"})
      assert validate("route", r) != []
  def test_coords_out_of_range_rejected(): ...  # x=101 → hata
  def test_quest_unknown_source_rejected(): ...  # sources=["questie"] → hata
  ```
  `route_valid.json`: Human, Alliance, `[1,12]`, `releaseTier:"beta"`, 3 adım (accept 783 npc 823 @48.2,41.7 / complete 33 / turnin 33 npc 196), `mapId:1429`.
- [ ] **Step 2:** Run `.venv\Scripts\python -m pytest tests/test_schema.py -q` → FAIL.
- [ ] **Step 3:** Şemaları (draft 2020-12) ve `validate`'i yaz (`jsonschema.Draft202012Validator`, şemalar modül yüklenirken bir kez okunur).
- [ ] **Step 4:** → PASS. Commit: `feat(schema): quest and route JSON schemas with validator`.

### Task 3: Lua tablo ayrıştırıcısı + pfQuest ingest

**Files:**
- Create: `pipeline/ingest/__init__.py`, `pipeline/ingest/luatable.py`, `pipeline/ingest/pfquest.py`, `tests/test_luatable.py`, `tests/test_pfquest.py`, `tests/fixtures/pfquest/{quests.lua,units.lua,objects.lua,enUS/quests.lua,enUS/units.lua}`

**Interfaces:**
- Produces: `parse_lua_table(text: str) -> dict | list` — metindeki ilk `=` sonrası ilk tablo literalini ayrıştırır. Anahtarları yalnızca `1..n` ardışık tamsayı olan tablolar `list` olur; diğerleri `dict` (int ya da str anahtar). Desteklenen: `{}`, `[n] =`, `["k"] =`, çift/tek tırnaklı dizgeler (`\'`,`\"`,`\\`,`\n` kaçışları), tamsayı/ondalık/negatif sayı, `true/false/nil`, `--` yorumları, sondaki virgül, CRLF.
- Produces: `fetch_pfquest(raw_dir: Path) -> None` (5 dosyayı `raw/pfquest/` altına indirir; önce `.part` dosyasına yazar, bitince yeniden adlandırır — yarım dosya kalmaz; HTTP hatasında `RuntimeError` dosya adıyla).
- Produces: `load_pfquest(src_dir: Path) -> PfData`; `PfData` = `@dataclass(frozen=True)` alanları `quests: dict[int, dict]` (ham `lvl,min,race,pre,start,end,obj` + `name` = enUS `T`), `units: dict[int, dict]` (`name`, `coords: list[tuple[float,float,int]]` = x,y,zoneAreaId; respawn atılır, `fac`), `objects: dict[int, dict]` (aynı biçim).

- [ ] **Step 1: Failing tests:** `test_parses_nested_quest_table` (fixture'daki `[33]` → `lvl==2`, `pre==[5261]`, `end=={"U":[196]}`), `test_sequential_int_keys_become_list` (`{ [1] = {48.9, 41.6, 12, 285} }` → `[[48.9, 41.6, 12, 285]]`), `test_parses_escapes_and_crlf` (`"you\'ll\r\n"` içeren fixture → `"you'll"`), `test_negative_and_float_numbers`, `test_load_pfquest_joins_enus_name` (`quests[33]["name"] == "Wolves Across the Border"`), `test_load_pfquest_drops_description_text` (`"D" not in quests[33]` ve `"O" not in quests[33]`), `test_unit_coords_tuple` (`units[197]["coords"][0] == (48.9, 41.6, 12)`).
  Fixture'lar gerçek pfQuest dosyalarından kesit: görevler 7, 33, 783, 5261 + item-başlangıçlı 1; birimler 196, 197, 823; enUS adları.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** `luatable.py`: elle yazılmış özyinelemeli iniş ayrıştırıcı (tokenizer + `parse_value`); `pfquest.py`.
- [ ] **Step 4:** → PASS. Ek doğrulama (ağ, CI'da değil): `PYTHONIOENCODING=utf-8 .venv\Scripts\python -c "from pipeline.ingest.pfquest import *; from pipeline.config import RAW_DIR; fetch_pfquest(RAW_DIR); d=load_pfquest(RAW_DIR/'pfquest'); print(len(d.quests), d.quests[33]['name'])"` → 4000+ görev ve `Wolves Across the Border`.
- [ ] **Step 5:** Commit: `feat(ingest): Lua table parser and pfQuest loader`.

### Task 4: wago DB2 ingest

**Files:**
- Create: `pipeline/ingest/wago.py`, `tests/test_wago.py`, `tests/fixtures/wago/{QuestV2.csv,UiMap.csv,UiMapAssignment.csv,AreaTable.csv}`

**Interfaces:**
- Produces: `WAGO_TABLES = ("QuestV2","UiMap","UiMapAssignment","AreaTable","QuestXP")`; `fetch_tables(build: str, raw_dir: Path, opener=urllib.request.urlopen) -> None` (`raw/wago/<build>/<Table>.csv`, `.part` + yeniden adlandırma, HTTP≠200 → `RuntimeError`).
- Produces: `load_quest_ids(dir: Path) -> frozenset[int]`; `load_uimaps(dir) -> dict[int, str]` (UiMapID → ad); `load_zone_to_uimap(dir) -> dict[int, int]` (AreaTable zone ID → UiMapID; UiMapAssignment'ta `AreaID` eşleşen, `OrderIndex` en küçük satır).

- [ ] **Step 1: Failing tests:** `test_load_quest_ids` (fixture'da 33 ve 783 var, 99999 yok), `test_load_uimaps_has_zephras` (`2521 → "Zephras Isle"`), `test_zone_to_uimap_elwynn` (`12 → 1429`), `test_fetch_refuses_partial_file` (sahte `opener` 500 döndürür → `RuntimeError`, hedef dizinde `.csv` yok). Fixture'lar 22 Ekim'de indirilen gerçek CSV'lerden ilgili satırlar (başlık satırı korunur).
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Uygula (`csv.DictReader`, `urllib.request`).
- [ ] **Step 4:** → PASS. Ağ doğrulaması: `fetch_tables(DATA_BUILD, RAW_DIR)` sonrası `len(load_quest_ids(...)) == 6616` ve `load_zone_to_uimap(...)[12] == 1429`. Eşleşme 1429 değilse dur ve Eren'e bildir (koordinat çerçevesi varsayımı yanlış).
- [ ] **Step 5:** Commit: `feat(ingest): wago DB2 loader for Forever build`.

### Task 5: Elle giriş formatı (Wowhead'den bakılan Forever görevleri)

**Files:**
- Create: `data/manual/README.md`, `data/manual/quests.yaml` (boş liste `[]`), `pipeline/ingest/manual.py`, `tests/test_manual.py`, `tests/fixtures/manual/quests.yaml`

**Interfaces:**
- Produces: `load_manual(path: Path) -> dict[int, dict]`. YAML öğesi: `id`, `name`, `level`, `minLevel`, `races?`, `prereqs?`, `start?{type,id,name,uiMapId,x,y}`, `end?`, `wowheadUrl` (zorunlu, `https://www.wowhead.com/forever/quest=` ile başlar), `checkedOn` (YYYY-MM-DD, zorunlu). Dönen kayıt `source="wowhead-manual"` taşır.

- [ ] **Step 1: Failing tests:** `test_manual_entry_loads`, `test_manual_requires_wowhead_url` (eksik → `ValueError` görev id'siyle), `test_manual_rejects_non_forever_url` (`/classic/quest=` → `ValueError`), `test_manual_duplicate_id_rejected`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Uygula (`yaml.safe_load`). README: alanlar, örnek, "metin kopyalanmaz, yalnız olgu" kuralı.
- [ ] **Step 4:** → PASS. Commit: `feat(ingest): manual Wowhead fact entries`.

### Task 6: Normalize — kanonik görev veritabanı

**Files:**
- Create: `pipeline/normalize/__init__.py`, `pipeline/normalize/quests.py`, `pipeline/__main__.py`, `tests/test_normalize.py`
- Output: `data/canonical/quests.json`

**Interfaces:**
- Consumes: `PfData` (Task 3), `load_quest_ids`, `load_zone_to_uimap` (Task 4), `load_manual` (Task 5), `config.SOURCE_LINEAGE`, `config.RACE_BITS`, `schema.validate` (Task 2).
- Produces: `races_from_mask(mask: int | None) -> list[str] | None` (None/0/255 → None).
- Produces: `confidence_for(lineages: set[str], conflicts: list[str]) -> str` (Global Constraints'teki kural, birebir).
- Produces: `build_canonical(pf: PfData, forever_ids: frozenset[int], zone_to_uimap: dict[int,int], manual: dict[int,dict]) -> list[dict]` — id'ye göre sıralı, her kayıt `validate("quest", …) == []`. Kurallar: id kümesi = pfQuest ∪ manual ∪ forever_ids; `inForever = id in forever_ids`; `wago-db2` kaynağı yalnız varlık için eklenir; pfQuest ile manual aynı alanda farklıysa alan adı `conflicts`'e (manual değeri kazanır, çünkü Forever'a özgü); NPC koordinatı: diğer uç NPC'nin bölgesiyle aynı bölgedeki ilk koordinat, yoksa ilk koordinat; `zone_to_uimap`'te karşılığı olmayan bölge → `uiMapId=null` ve `"start.coords"`/`"end.coords"` conflict.
- CLI: `python -m pipeline normalize` → raw'dan okur, `data/canonical/quests.json` yazar (UTF-8, `indent=1`, `ensure_ascii=False`, sonda `\n`), yazmadan önce tüm kayıtları doğrular; tek hata bile varsa dosya yazılmaz ve çıkış kodu 1.

- [ ] **Step 1: Failing tests:**
  ```python
  def test_confidence_rules():
      assert confidence_for({"blizzard-client","vanilla-emu"}, []) == "cross-checked"
      assert confidence_for({"vanilla-emu"}, []) == "unverified"
      assert confidence_for({"community","wowhead"}, []) == "unverified"
      assert confidence_for({"blizzard-client","vanilla-emu"}, ["level"]) == "unverified"
      assert confidence_for({"vanilla-emu","ingame"}, []) == "verified-ingame"
  def test_races_from_mask():
      assert races_from_mask(77) == ["Human","Dwarf","Night Elf","Gnome"]; assert races_from_mask(255) is None
  def test_unknown_race_bit_kept(): assert "unknown-bit-256" in races_from_mask(1 | 256)
  def test_wolves_across_the_border_canonical():
      q = by_id(33); assert q["start"]["type"] == "npc" and q["start"]["id"] == 196 and q["start"]["uiMapId"] == 1429
      assert q["confidence"] == "cross-checked"; assert q["prereqs"] == [5261]
  ```
  ve Review Focus testleri: `test_quest_started_by_item`, `test_npc_without_coords_marks_conflict`, `test_quest_missing_from_forever_flagged`; ayrıca `test_manual_overrides_pfquest_and_records_conflict`, `test_canonical_records_pass_schema`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Uygula. **Step 4:** → PASS.
- [ ] **Step 5:** Gerçek veriyle: `PYTHONIOENCODING=utf-8 .venv\Scripts\python -m pipeline normalize` → çıkış 0; ardından Human'a açık (`races` None ya da Human içerir), `start.uiMapId == 1429`, `minLevel <= 12`, `inForever` görev sayısını yazdır; 0'dan büyük olmalı (Ek A 1.8 çıkış ölçütü).
- [ ] **Step 6:** Commit: `feat(normalize): canonical quest database with sources and confidence` (`data/canonical/quests.json` dahil).

### Task 7: Çapraz kontrol raporu + elle giriş sayımı

**Files:**
- Create: `pipeline/crosscheck/__init__.py`, `pipeline/crosscheck/report.py`, `tests/test_crosscheck.py`
- Output: `data/reports/crosscheck-<DATA_BUILD>.md`; `python -m pipeline crosscheck`

**Interfaces:**
- Consumes: `data/canonical/quests.json` biçimi (Task 6).
- Produces: `summarize(quests: list[dict], level_max: int = 30) -> Summary`; `Summary` = dataclass: `total:int`, `by_confidence: dict[str,int]`, `not_in_forever:int`, `needs_manual: list[int]` (inForever, kaynağı yalnız `wago-db2`), `conflicts: dict[str,int]` (alan → sayı), `in_scope:int` (inForever ve `minLevel<=level_max` ya da minLevel None). `render_markdown(s: Summary, build: str) -> str`.

- [ ] **Step 1: Failing tests:** `test_counts_by_confidence`, `test_new_forever_quest_listed_as_needs_manual` (yalnız `wago-db2` kaynaklı kayıt → `needs_manual`'da), `test_render_markdown_has_build_and_table` (çıktı `1.60.1.70532` ve `| cross-checked |` içerir).
- [ ] **Step 2:** FAIL → **Step 3:** uygula → **Step 4:** PASS.
- [ ] **Step 5:** `python -m pipeline crosscheck` gerçek veriyle; rapordaki `needs_manual` sayısını Eren'e bildir (§8.2: elle giriş yükü ölçüldü; takvim buna göre güncellenecek).
- [ ] **Step 6:** Commit: `feat(crosscheck): confidence report and manual-entry backlog`.

### Task 8: Rota anlamsal doğrulayıcısı ve yayın eşiği

**Files:**
- Create: `pipeline/validate/__init__.py`, `pipeline/validate/semantic.py`, `tests/test_semantic.py`, `tests/fixtures/routes/*.json` (her kural için bir kırık rota)

**Interfaces:**
- Consumes: `schema.validate` (Task 2), kanonik görev biçimi (Task 6), `load_uimaps` (Task 4).
- Produces: `check_route(route: dict, quests: dict[int, dict], known_maps: frozenset[int], xp_reaches_target: Callable[[dict], bool] | None = None) -> list[Issue]`; `Issue` = dataclass `rule:str, stepId:str|None, message:str`. Kural adları (sabit): `schema`, `turnin-before-accept`, `complete-before-accept`, `prereq-not-done`, `accepted-never-closed`, `unknown-map` (`mapId ∉ known_maps`), `duplicate-step-id`, `over-level` (adımın görevinin `minLevel` > o noktadaki tahmini seviye + 3; tahmini seviye = son `grind.untilLevel`, yoksa `levelRange[0]`), `xp-target` (yalnız `xp_reaches_target` verilirse; Aşama 2 doldurur), `tier-full-requires-cross-checked` (`releaseTier=="full"` iken `unverified` adım ya da `gap` adımı varsa).
- CLI: `python -m pipeline validate [--all | <route.json>]` → issue varsa listeler, çıkış kodu 1.

- [ ] **Step 1: Failing tests:** her kural için bir test (`test_rule_<kural>`), artı `test_beta_tier_allows_gap_and_unverified`, `test_valid_fixture_has_no_issues`.
- [ ] **Step 2:** FAIL → **Step 3:** uygula → **Step 4:** PASS.
- [ ] **Step 5:** Commit: `feat(validate): semantic route rules and release-tier gate`.

### Task 9: Lisans kapısı + CI'da veri doğrulaması

**Files:**
- Create: `tests/test_license_guard.py`, `tests/test_canonical_data.py`

**Interfaces:**
- Consumes: `schema.validate`, `data/canonical/quests.json`.

- [ ] **Step 1: Tests:**
  - `test_no_forbidden_sources`: `git ls-files` ile izlenen tüm dosyalar (`tests/test_license_guard.py`, `docs/`, `THIRD_PARTY.md` hariç) şu dizgeleri içermez (büyük/küçük harf duyarsız): `QuestieDB`, `questie`, `RXPGuides`, `zygor`, `Guidelime_`, `TomTom`.
  - `test_no_raw_dir_tracked`: `git ls-files raw/` boş.
  - `test_canonical_data_valid`: `quests.json` her kaydı şemayı geçer; `sources` yalnız izinli kimlikler; hiçbir kayıtta `D`/`O` anahtarı yok. **Atlama yok:** dosya yoksa test FAIL olur (§5.2-6).
- [ ] **Step 2:** Run → hepsi PASS olmalı (Task 6 verisi var). Biri FAIL ise nedeni düzelt, testi gevşetme.
- [ ] **Step 3:** Commit: `test: license guard and canonical data validation in CI`.

---

## Bu planın kapsamı dışında (sonraki planlar)

- **CMaNGOS ingest (Ek A 1.5) ertelendi:** pfQuest zaten CMaNGOS/VMaNGOS türevi; aynı soy (`vanilla-emu`) olduğu için güvene katkısı yok. Aşama 2'de önkoşul zinciri eksikliği ölçülünce yeniden değerlendirilir.
- **Görev XP'si:** client `QuestV2`'de XP zorluk indeksi yok; Aşama 2 planı XP kaynağını belirleyecek.
- **Topluluk rotaları (Lodestar vb.) ingest'i:** Aşama 2 (rota sırası karşılaştırması).
