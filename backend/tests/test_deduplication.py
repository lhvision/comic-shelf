from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db import (
    batch_find_comic_mirrors,
    find_comic_mirrors,
    init_db,
    set_db_path,
    upsert_comic_index,
)
from app.formatting import normalize_title


class TestComicDeduplication(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "comic_shelf_test.db"
        set_db_path(self.db_path)
        init_db(self.db_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_normalize_title_rules(self) -> None:
        # 1. Strips scanlator, circle, event, format tags
        t1 = "[脸肿汉化组] (C101) [MIDDLY (みどりのちや)] カラフルコネクト 7th:Dive (プリンセスコネクト!Re:Dive) [中国翻訳] [DL版]"
        t2 = "[MIDDLY] カラフルコネクト 7th:Dive"
        self.assertEqual(normalize_title(t1), normalize_title(t2))
        self.assertEqual(normalize_title(t1), "カラフルコネクト 7th dive")

        # 2. Traditional to Simplified conversion
        t_trad = "[綿120パーセント ]梓喵買醬油合集 AZUS@TTACK 1-5 番外"
        t_simp = "梓喵买酱油合集 AZUS@TTACK 1-5 番外"
        self.assertEqual(normalize_title(t_trad), normalize_title(t_simp))
        self.assertEqual(normalize_title(t_trad), "梓喵买酱油合集 azus@ttack 1 5 番外")

        # 3. Volume distinction preservation (no false positives across volumes)
        vol1 = "间谍过家家 01"
        vol2 = "间谍过家家 02"
        self.assertNotEqual(normalize_title(vol1), normalize_title(vol2))
        self.assertNotEqual(normalize_title("间谍过家家 [01]"), normalize_title("间谍过家家 [02]"))
        self.assertNotEqual(normalize_title("间谍过家家 (1)"), normalize_title("间谍过家家 (2)"))
        self.assertNotEqual(normalize_title("间谍过家家 【第1话】"), normalize_title("间谍过家家 【第2话】"))
        self.assertNotEqual(normalize_title("海贼王 [1000话]"), normalize_title("海贼王 [1001话]"))
        self.assertNotEqual(normalize_title("[社团] 某某物语 【上】"), normalize_title("[社团] 某某物语 【下】"))
        self.assertNotEqual(normalize_title("葬送的芙莉莲 (Vol.1)"), normalize_title("葬送的芙莉莲 (Vol.2)"))

        # 4. Pure brackets and pure symbols fallback
        fallback = "[C100][DL版]"
        self.assertTrue(len(normalize_title(fallback)) > 0)
        self.assertEqual(normalize_title("???"), "???")
        self.assertEqual(normalize_title("......"), "......")

    def test_upsert_and_find_mirrors(self) -> None:
        # Insert a JM comic
        upsert_comic_index({
            "source": "jm",
            "source_id": "523607",
            "display_id": "JM523607",
            "title": "[綿120パーセント ]梓喵買醬油合集 AZUS@TTACK 1-5 番外",
            "page_count": 48,
            "cached_pages": 48,
            "cover_count": 4,
        })

        # Cross-source mirror match from PicACG
        mirrors = find_comic_mirrors(
            source="picacg",
            source_id="5ebe89bf63918511c2c362a7",
            title="梓喵买酱油合集 AZUS@TTACK 1-5 番外",
        )
        self.assertEqual(len(mirrors), 1)
        self.assertEqual(mirrors[0]["source"], "jm")
        self.assertEqual(mirrors[0]["source_id"], "523607")
        self.assertEqual(mirrors[0]["display_id"], "JM523607")

        # Same source and ID should NOT match itself as mirror
        self_mirrors = find_comic_mirrors(
            source="jm",
            source_id="523607",
            title="梓喵买酱油合集 AZUS@TTACK 1-5 番外",
        )
        self.assertEqual(len(self_mirrors), 0)

    def test_hidden_comic_security(self) -> None:
        upsert_comic_index({
            "source": "jm",
            "source_id": "secret123",
            "display_id": "JMsecret123",
            "title": "馆长私密收藏漫画",
            "page_count": 10,
            "hidden_from_guest": 1,
        })

        # Curator can see it in cross-source mirror search
        res_curator = find_comic_mirrors(
            source="picacg",
            source_id="pica888",
            title="馆长私密收藏漫画",
            is_curator=True,
        )
        self.assertEqual(len(res_curator), 1)

        # Guest cannot see it (preventing metadata leakage or brute force probing)
        res_guest = find_comic_mirrors(
            source="picacg",
            source_id="pica888",
            title="馆长私密收藏漫画",
            is_curator=False,
        )
        self.assertEqual(len(res_guest), 0)

        # Default is_curator=False must also refuse to leak
        res_default = find_comic_mirrors(
            source="picacg",
            source_id="pica888",
            title="馆长私密收藏漫画",
        )
        self.assertEqual(len(res_default), 0)

    def test_batch_find_comic_mirrors(self) -> None:
        upsert_comic_index({
            "source": "jm",
            "source_id": "111",
            "display_id": "JM111",
            "title": "间谍过家家 [01]",
        })
        upsert_comic_index({
            "source": "jm",
            "source_id": "222",
            "display_id": "JM222",
            "title": "间谍过家家 [02]",
        })

        candidates = [
            ("copymanga", "cp1", "间谍过家家 [01]"),
            ("copymanga", "cp2", "间谍过家家 [02]"),
            ("copymanga", "cp3", "完全不存在的漫画"),
        ]
        res = batch_find_comic_mirrors(candidates, is_curator=True)
        self.assertIsNotNone(res[("copymanga", "cp1")])
        self.assertEqual(res[("copymanga", "cp1")]["source_id"], "111")
        self.assertIsNotNone(res[("copymanga", "cp2")])
        self.assertEqual(res[("copymanga", "cp2")]["source_id"], "222")
        self.assertIsNone(res[("copymanga", "cp3")])


if __name__ == "__main__":
    unittest.main()
