from string import Formatter
from types import SimpleNamespace

import pytest

from pmca_wifi import i18n, settings


def test_both_catalogs_format_the_same_parameters():
    for key, translations in i18n.MESSAGES.items():
        fields = [{field for _, field, _, _ in Formatter().parse(value) if field}
                  for value in translations]
        assert fields[0] == fields[1], key
        for language in i18n.LANGUAGES:
            rendered = i18n.text(key, language, **{field: "example" for field in fields[0]})
            assert rendered and "{password}" not in rendered


@pytest.mark.parametrize("lang_id,expected", [(0x0409, "en"), (0x0804, "zh-CN"),
                                              (0x0404, "zh-CN"), (0x0411, "en")])
def test_windows_display_language_selection(monkeypatch, lang_id, expected):
    kernel = SimpleNamespace(GetUserDefaultUILanguage=lambda: lang_id)
    monkeypatch.setattr(i18n.ctypes, "windll", SimpleNamespace(kernel32=kernel), raising=False)
    assert i18n.system_language() == expected


def test_saved_preference_overrides_system_and_corrupt_settings_fall_back(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "state_dir", lambda: tmp_path)
    monkeypatch.setattr(settings, "system_language", lambda: "en")
    assert settings.load_language() == "en"
    settings.save_language("zh-CN")
    assert settings.load_language() == "zh-CN"
    for content in ('broken', '{"language": "unsupported"}', '{"language": []}', '[]'):
        (tmp_path / "preferences.json").write_text(content, encoding="utf-8")
        assert settings.load_language() == "en"
    with pytest.raises(ValueError):
        settings.save_language("unsupported")


def test_errors_keep_codes_and_nested_details_when_language_changes():
    inner = i18n.UserError("hotspot_read", code=87)
    error = i18n.UserError("cleanup_failed", errors=[inner, OSError("native detail")])
    for language, expected in (("en", "Windows error 87"), ("zh-CN", "Windows 错误 87")):
        rendered = i18n.error_text(error, language)
        assert expected in rendered and "native detail" in rendered
    assert isinstance(inner, RuntimeError)
    assert isinstance(i18n.PackageError("apk_size"), ValueError)
