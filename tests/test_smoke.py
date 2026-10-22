from pipeline import config


def test_config_constants():
    assert config.DATA_BUILD == "1.60.1.70532"
    assert config.SOURCE_LINEAGE["pfquest"] == "vanilla-emu"
    assert config.SOURCE_LINEAGE["lodestar"] == "community"
    assert config.RACE_BITS["Gnome"] == 64
    assert config.RAW_DIR.name == "raw"
