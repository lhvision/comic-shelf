import os
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure backend package is importable
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.models import ComicMeta, FetchedComic, RemotePage, PageRecord
from app.storage import ComicStore
from app.main import _prefetch_worker


def create_test_comic(page_count: int = 15) -> FetchedComic:
    pages = [
        PageRecord(index=i, file=f"{i:05d}.webp", ext=".webp", cached=False, chapter="")
        for i in range(1, page_count + 1)
    ]
    remote_pages = [
        RemotePage(index=i, url=f"http://img/{i}.webp", file=f"{i:05d}.webp", ext=".webp", chapter="")
        for i in range(1, page_count + 1)
    ]
    meta = ComicMeta(
        source="jm",
        source_id="888888",
        display_id="JM888888",
        title="超长测试漫画",
        authors=["测试作者"],
        works=[],
        actors=[],
        tags=["测试"],
        description="",
        page_count=page_count,
        published_at="2026-01-01",
        updated_at="2026-01-01",
        pages=pages,
        chapters=[],
    )
    return FetchedComic(meta=meta, remote_pages=remote_pages)


def test_batch_prefetch_flow():
    print("Running batch prefetch unit tests...")
    tmp_dir = Path(tempfile.mkdtemp(prefix="paper_room_test_batch_"))
    try:
        store = ComicStore(root=tmp_dir / "library")
        fetched = create_test_comic(page_count=15)
        meta = fetched.meta
        store.save_fetched(fetched)

        # Mock ensure_page, ensure_webp_cover, ensure_page_thumb to avoid actual network/decryption
        def mock_ensure_page(f, idx):
            meta.pages[idx - 1].cached = True
            # Write a dummy file so reconcile_cached_pages sees it
            p = store.page_path(meta, idx)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"dummy_image_data")
            return p

        with patch.object(store, "ensure_page", side_effect=mock_ensure_page), \
             patch.object(store, "ensure_webp_cover"), \
             patch.object(store, "ensure_page_thumb"), \
             patch("app.storage.prefetch.MAX_PREFETCH", 6):

            # --- Batch 1: Should fetch pages 1..6 ---
            done1, warnings1 = store.prefetch(fetched, cover_count=4, prefetch_all=True)
            assert done1 == 6, f"Batch 1 expected 6, got {done1}"
            cached_count1 = sum(1 for p in meta.pages if p.cached)
            assert cached_count1 == 6, f"Expected 6 pages cached, got {cached_count1}"
            assert any("已达单批次预缓存上限（6 页）" in w for w in warnings1), "Missing batch limit warning in batch 1"
            assert any("尚余 9 页待缓存" in w for w in warnings1), "Remaining count incorrect in batch 1"
            print("  ✓ Batch 1 successfully prefetched 6 pages (1..6) with warning")

            # --- Batch 2: Should advance and fetch pages 7..12 ---
            done2, warnings2 = store.prefetch(fetched, cover_count=4, prefetch_all=True)
            assert done2 == 6, f"Batch 2 expected 6, got {done2}"
            cached_count2 = sum(1 for p in meta.pages if p.cached)
            assert cached_count2 == 12, f"Expected 12 pages cached, got {cached_count2}"
            assert any("尚余 3 页待缓存" in w for w in warnings2), "Remaining count incorrect in batch 2"
            print("  ✓ Batch 2 successfully advanced to prefetch next 6 pages (7..12)")

            # --- Gap Simulation: reader manually read and cached page 15 ---
            meta.pages[14].cached = True
            p15 = store.page_path(meta, 15)
            p15.write_bytes(b"dummy")

            # --- Batch 3: Only pages 13 and 14 are uncached, should fetch exactly 2 pages ---
            done3, warnings3 = store.prefetch(fetched, cover_count=4, prefetch_all=True)
            assert done3 == 2, f"Batch 3 expected 2, got {done3}"
            cached_count3 = sum(1 for p in meta.pages if p.cached)
            assert cached_count3 == 15, f"Expected all 15 pages cached, got {cached_count3}"
            assert len(warnings3) == 0, f"Expected 0 warnings when complete, got {warnings3}"
            print("  ✓ Batch 3 healed gap (pages 13, 14) and finished all 15 pages")

            # --- Idempotent check: Running again when 100% complete ---
            done4, warnings4 = store.prefetch(fetched, cover_count=4, prefetch_all=True)
            assert done4 == 0, f"Expected 0 on fully cached comic, got {done4}"
            assert len(warnings4) == 0
            print("  ✓ Batch 4 idempotent no-op on already completed comic")

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_prefetch_worker_macro_progress():
    print("Testing _prefetch_worker macro progress and broadcast event...")
    tmp_dir = Path(tempfile.mkdtemp(prefix="paper_room_test_worker_"))
    try:
        from app.routers import common as common_router
        store = ComicStore(root=tmp_dir / "library")
        fetched = create_test_comic(page_count=10)
        meta = fetched.meta
        store.save_fetched(fetched)

        def mock_ensure(f, idx):
            meta.pages[idx - 1].cached = True
            p = store.page_path(meta, idx)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"data")
            return p

        broadcast_events = []
        def mock_broadcast(event_name, payload):
            broadcast_events.append((event_name, payload))

        with patch.object(common_router.store, "prefetch") as mock_prefetch, \
             patch("app.routers.common.broadcast_event", side_effect=mock_broadcast), \
             patch.object(common_router.store, "reconcile_cached_pages"), \
             patch.object(common_router.store, "cached_page_count", side_effect=[0, 6]):

            mock_prefetch.return_value = (6, ["batch warning"])

            job = {"running": True, "done": False, "prefetched": 0, "total": 0}
            common_router._prefetch_worker(job, fetched, cover_count=4, prefetch_all=True)

            assert job["total"] == 10, f"Expected macro total 10, got {job['total']}"
            assert job["prefetched"] == 6, f"Expected macro prefetched 6, got {job['prefetched']}"
            assert len(broadcast_events) == 1
            assert broadcast_events[0][1]["action"] == "cache_partial"
            print("  ✓ Worker correctly reported macro progress (6/10) and emitted cache_partial")

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_prefetch_worker_exception_safety():
    print("Testing _prefetch_worker exception safety and finally broadcast...")
    tmp_dir = Path(tempfile.mkdtemp(prefix="paper_room_test_safety_"))
    try:
        from app.routers import common as common_router
        fetched = create_test_comic(page_count=10)
        broadcast_events = []
        def mock_broadcast(event_name, payload):
            broadcast_events.append((event_name, payload))

        with patch.object(common_router.store, "prefetch", side_effect=RuntimeError("simulated network failure")), \
             patch("app.routers.common.broadcast_event", side_effect=mock_broadcast), \
             patch.object(common_router.store, "reconcile_cached_pages"), \
             patch.object(common_router.store, "cached_page_count", side_effect=[0, 2]):

            job = {"running": True, "done": False, "prefetched": 0, "total": 0}
            try:
                common_router._prefetch_worker(job, fetched, cover_count=4, prefetch_all=True)
                assert False, "Expected RuntimeError from prefetch"
            except RuntimeError:
                pass

            assert job["prefetched"] == 2
            assert len(broadcast_events) == 1
            assert broadcast_events[0][1]["action"] == "cache_partial"
            print("  ✓ Worker successfully emitted broadcast event despite prefetch exception")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    test_batch_prefetch_flow()
    test_prefetch_worker_macro_progress()
    test_prefetch_worker_exception_safety()
    print("All batch prefetch tests passed successfully!")
