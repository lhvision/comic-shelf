from __future__ import annotations

import sys
import time
from pathlib import Path

# Ensure backend package is importable
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.zh_conv import to_simplified, to_traditional, expand_search_variants, _load_tables


def test_zh_conv_basic_conversions():
    # 1. Simplified to Traditional
    assert to_traditional("战斗") == "戰鬥"
    assert to_traditional("漫画") == "漫畫"
    assert to_traditional("台词") == "臺詞"
    assert to_traditional("动漫") == "動漫"
    assert to_traditional("身体健康") == "身體健康"
    assert to_traditional("发财") == "發財"

    # 2. Traditional to Simplified
    assert to_simplified("戰鬥") == "战斗"
    assert to_simplified("漫畫") == "漫画"
    assert to_simplified("臺詞") == "台词"
    assert to_simplified("動漫") == "动漫"
    assert to_simplified("頭髮") == "头发"
    assert to_simplified("身體健康") == "身体健康"

    # 3. Empty & Whitespace edge cases
    assert to_traditional("") == ""
    assert to_simplified("") == ""
    assert to_traditional(None) == ""  # type: ignore
    assert to_simplified(None) == ""  # type: ignore

    # 4. Non-Chinese & mixed characters
    assert to_traditional("Hello 123! @#$") == "Hello 123! @#$"
    assert to_simplified("Hello 123! @#$") == "Hello 123! @#$"
    assert to_traditional("JOJO的奇妙冒险 Part 3") == "JOJO的奇妙冒險 Part 3"
    assert to_simplified("JOJO的奇妙冒險 Part 3") == "JOJO的奇妙冒险 Part 3"
    print("  ✓ Basic conversions & edge cases passed")


def test_expand_search_variants():
    # 1. Simplified input -> [simp, trad]
    v1 = expand_search_variants("战斗")
    assert v1 == ["战斗", "戰鬥"]

    # 2. Traditional input -> [trad, simp]
    v2 = expand_search_variants("戰鬥")
    assert v2 == ["戰鬥", "战斗"]

    # 3. English / No change input -> [original]
    v3 = expand_search_variants("Naruto")
    assert v3 == ["Naruto"]

    # 4. Empty / Whitespace input -> []
    assert expand_search_variants("") == []
    assert expand_search_variants("   ") == []
    assert expand_search_variants("\n\t") == []

    # 5. Trimmed variants
    v4 = expand_search_variants("  JOJO的奇妙冒险  ")
    assert v4[0] == "JOJO的奇妙冒险"
    assert "JOJO的奇妙冒險" in v4
    print("  ✓ Search variant expansion passed")


def test_lazy_loading_and_performance():
    s2t, t2s = _load_tables()
    assert len(s2t) > 3000
    assert len(t2s) > 3000

    # Ensure caching works (same object identity)
    s2t_2, t2s_2 = _load_tables()
    assert s2t is s2t_2
    assert t2s is t2s_2

    # Benchmark conversion speed
    sample = "这就是最后的波纹吗，JOJO！人类的赞歌就是勇气的赞歌！" * 50
    t0 = time.perf_counter()
    trad = to_traditional(sample)
    t1 = time.perf_counter()
    simp = to_simplified(trad)
    t2 = time.perf_counter()

    assert "最後的波紋" in trad
    assert "最后的波纹" in simp
    dur_trad_ms = (t1 - t0) * 1000
    dur_simp_ms = (t2 - t1) * 1000
    print(f"  ✓ Conversion benchmark (2500 chars): trad={dur_trad_ms:.3f}ms, simp={dur_simp_ms:.3f}ms")


def test_astral_plane_and_concurrency():
    import concurrent.futures
    import app.zh_conv as zh_mod

    # 1. Test SMP Astral plane characters (4-byte UTF-8)
    assert to_simplified("𠗣") == "㓆"
    assert to_traditional("㓆") == "𠗣"
    assert "𠗣" in expand_search_variants("㓆")

    # 2. Test concurrent multithreaded access
    zh_mod._S2T_TABLE = None
    zh_mod._T2S_TABLE = None

    def worker(text: str) -> tuple[str, str]:
        return to_traditional(text), to_simplified(text)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [
            executor.submit(worker, f"测试文本_{i}_最后波纹")
            for i in range(50)
        ]
        results = [f.result() for f in futures]

    assert len(results) == 50
    for trad, simp in results:
        assert "測試文本" in trad
        assert "最后波纹" in simp
    print("  ✓ Astral plane characters & concurrent multithreading passed")


if __name__ == "__main__":
    print("Running zh_conv unit tests...")
    test_zh_conv_basic_conversions()
    test_expand_search_variants()
    test_lazy_loading_and_performance()
    test_astral_plane_and_concurrency()
    print("All zh_conv unit tests passed successfully!")
