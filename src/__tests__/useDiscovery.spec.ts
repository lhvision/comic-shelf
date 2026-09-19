import { describe, it, expect, vi, beforeEach } from 'vite-plus/test'
import { createPinia, setActivePinia } from 'pinia'
import { useDiscovery } from '@/composables/useDiscovery'
import { api } from '@/api/client'
import type { DiscoveryFeed, DiscoveryItem } from '@/types'

describe('useDiscovery', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('loads weekly ranking successfully', async () => {
    const mockFeed: DiscoveryFeed = {
      timeframe: 'week',
      updated_at: '2026-08-26 00:00:00',
      items: [
        {
          id: 'JM1001',
          source_id: '1001',
          source: 'jm',
          title: 'Top Weekly Manga',
          author: 'Artist A',
          category: 'Single',
          in_library: false,
        },
      ],
    }

    vi.spyOn(api, 'discoveryRanking').mockResolvedValueOnce(mockFeed)

    const { timeframe, feed, loading, loadRanking } = useDiscovery()
    expect(timeframe.value).toBe('week')
    expect(feed.value).toBeNull()

    await loadRanking('week', false)

    expect(loading.value).toBe(false)
    expect(feed.value?.items.length).toBe(1)
    expect(feed.value?.items[0]?.title).toBe('Top Weekly Manga')
  })

  it('ingests comic into library', async () => {
    const item: DiscoveryItem = {
      id: 'JM1002',
      source_id: '1002',
      source: 'jm',
      title: 'Monthly Gem',
      author: 'Artist B',
      category: 'Single',
      in_library: false,
    }

    vi.spyOn(api, 'importComic').mockResolvedValueOnce({
      meta: {
        source: 'jm',
        source_id: '1002',
        display_id: 'JM1002',
        title: 'Monthly Gem',
        authors: ['Artist B'],
        works: [],
        actors: [],
        tags: [],
        description: '',
        uploader: null,
        page_count: 20,
        published_at: '',
        updated_at: '',
        views: '',
        likes: '',
        comment_count: 0,
        favorite: false,
        cover_count: 4,
        source_url: '',
        pages: [],
        imported_at: '',
        last_checked_at: '',
        raw: {},
      },
      from_cache: false,
      prefetched: 0,
      warnings: [],
    })

    const { ingestComic } = useDiscovery()
    await ingestComic(item)

    expect(item.in_library).toBe(true)
  })

  it('switches between jm and picacg sources and clears stale feed', async () => {
    const jmFeed: DiscoveryFeed = {
      source: 'jm',
      timeframe: 'week',
      updated_at: '2026-08-26 00:00:00',
      items: [
        {
          id: 'jm_1001',
          source_id: '1001',
          source: 'jm',
          title: 'JM Manga',
          author: 'Artist A',
          category: 'Single',
          in_library: false,
        },
      ],
    }

    const picaFeed: DiscoveryFeed = {
      source: 'picacg',
      timeframe: 'day',
      updated_at: '2026-09-19 12:00:00',
      items: [
        {
          id: 'picacg_6aa41d',
          source_id: '6aa41d',
          source: 'picacg',
          title: 'PicAcg Daily Top',
          author: 'Artist P',
          category: 'Doujin',
          in_library: false,
        },
      ],
    }

    const spy = vi.spyOn(api, 'discoveryRanking').mockImplementation(async (src, _tf) => {
      if (src === 'picacg') return picaFeed
      return jmFeed
    })

    const { source, timeframe, feed, loadRanking } = useDiscovery()

    // 1. Load JM weekly
    await loadRanking('jm', 'week', false)
    expect(source.value).toBe('jm')
    expect(feed.value?.source).toBe('jm')
    expect(feed.value?.items[0]?.title).toBe('JM Manga')

    // 2. Switch to PicAcg daily
    await loadRanking('picacg', 'day', false)
    expect(source.value).toBe('picacg')
    expect(timeframe.value).toBe('day')
    expect(feed.value?.source).toBe('picacg')
    expect(feed.value?.items[0]?.title).toBe('PicAcg Daily Top')
    expect(spy).toHaveBeenCalledTimes(2)

    // 3. Call loadRanking with undefined timeframe and refresh=true
    await loadRanking(undefined, true)
    expect(spy).toHaveBeenLastCalledWith('picacg', 'day', true, expect.any(Object))
  })
})
