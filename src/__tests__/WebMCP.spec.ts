import { describe, it, expect, vi, beforeEach } from 'vite-plus/test'
import {
  ref,
  computed,
  reactive,
  shallowRef,
  effectScope,
  nextTick,
  type Ref,
  type ComputedRef,
} from 'vue'
import { useReaderWebMCP } from '@/composables/useReaderWebMCP'
import { useShelfWebMCP } from '@/composables/useShelfWebMCP'
import { useComicDetailWebMCP } from '@/composables/useComicDetailWebMCP'
import { useDiscoveryWebMCP } from '@/composables/useDiscoveryWebMCP'
import { useShelfState } from '@/composables/useShelfState'
import { useLibraryStore, createPlaceholderDetail } from '@/stores/library'
import { createPinia, setActivePinia } from 'pinia'
import { api } from '@/api/client'
import type { ReaderSettings } from '@/composables/useReaderSettings'
import type { Chapter, ComicDetail } from '@/types'
import type { RouteLocationNormalizedLoaded, Router } from 'vue-router'

describe('WebMCP Composables', () => {
  describe('useReaderWebMCP', () => {
    let mockSettings: ReaderSettings
    let currentPage: Ref<number>
    let pageCount: ComputedRef<number>
    let goToPageMock: (page: number) => void
    let prevGroupMock: () => void
    let nextGroupMock: () => void
    let goNextChapterMock: () => void
    let goPrevChapterMock: () => void
    let toggleFavoriteMock: () => void

    beforeEach(() => {
      mockSettings = reactive<ReaderSettings>({
        mode: 'vertical-continuous',
        fit: 'height',
        pagesPerView: 1,
        direction: 'ltr',
        autoTurn: false,
        autoTurnInterval: 10,
        seamless: false,
      })
      currentPage = ref(1)
      pageCount = computed(() => 50)
      goToPageMock = vi.fn<(page: number) => void>((page: number) => {
        currentPage.value = page
      })
      prevGroupMock = vi.fn<() => void>(() => {
        currentPage.value = Math.max(1, currentPage.value - 1)
      })
      nextGroupMock = vi.fn<() => void>(() => {
        currentPage.value = Math.min(50, currentPage.value + 1)
      })
      goNextChapterMock = vi.fn<() => void>()
      goPrevChapterMock = vi.fn<() => void>()
      toggleFavoriteMock = vi.fn<() => void>()
    })

    it('initializes reader WebMCP tools without crashing', () => {
      const scope = effectScope()
      scope.run(() => {
        const mcp = useReaderWebMCP({
          currentPage,
          pageCount,
          settings: mockSettings,
          goToPage: goToPageMock,
          prevGroup: prevGroupMock,
          nextGroup: nextGroupMock,
          goNextChapter: goNextChapterMock,
          goPrevChapter: goPrevChapterMock,
          toggleFavorite: toggleFavoriteMock,
        })
        expect(mcp).toBeDefined()
        expect(mcp!.jumpTool).toBeDefined()
        expect(mcp!.turnTool).toBeDefined()
        expect(mcp!.modeTool).toBeDefined()
        expect(mcp!.fitTool).toBeDefined()
        expect(mcp!.autoTurnTool).toBeDefined()
        expect(mcp!.favTool).toBeDefined()
        expect(mcp!.locateBubbleTool).toBeDefined()
        expect(mcp!.jumpChapterTool).toBeDefined()
      })
      scope.stop()
    })

    it('handles simulated execution for all reader tools', async () => {
      const registeredTools: Record<string, (args: unknown) => Promise<unknown>> = {}
      const registerToolMock = vi.fn<
        (toolDef: { name: string; execute: (args: unknown) => Promise<unknown> }) => void
      >((toolDef) => {
        registeredTools[toolDef.name] = toolDef.execute
      })

      // @ts-expect-error mock window.document
      const originalModelContext = window.document.modelContext
      // @ts-expect-error mock window.document
      window.document.modelContext = {
        registerTool: registerToolMock,
      }

      const routerReplaceMock = vi.fn<() => Promise<void>>().mockResolvedValue(undefined)
      const mockRouter = {
        replace: routerReplaceMock,
      } as unknown as Router
      const mockRoute = {
        query: {},
      } as unknown as RouteLocationNormalizedLoaded

      try {
        const scope = effectScope()
        scope.run(() => {
          useReaderWebMCP({
            currentPage,
            pageCount,
            settings: mockSettings,
            goToPage: goToPageMock,
            prevGroup: prevGroupMock,
            nextGroup: nextGroupMock,
            goNextChapter: goNextChapterMock,
            goPrevChapter: goPrevChapterMock,
            toggleFavorite: toggleFavoriteMock,
            router: mockRouter,
            route: mockRoute,
          })
        })

        await nextTick()

        expect(registerToolMock).toHaveBeenCalled()
        const jumpExecute = registeredTools['reader_jump_to_page']
        expect(jumpExecute).toBeDefined()

        const res = await jumpExecute!({ page: 25 })
        expect(goToPageMock).toHaveBeenCalledWith(25)
        expect(res).toEqual(
          expect.objectContaining({
            content: expect.arrayContaining([
              expect.objectContaining({
                text: expect.stringContaining('25'),
              }),
            ]),
          }),
        )

        // Turn next & prev with step count
        const turnExecute = registeredTools['reader_turn_page']
        expect(turnExecute).toBeDefined()
        await turnExecute!({ direction: 'next', count: 3 })
        expect(nextGroupMock).toHaveBeenCalledTimes(3)
        await turnExecute!({ direction: 'prev', count: 2 })
        expect(prevGroupMock).toHaveBeenCalledTimes(2)

        // Switch mode, fit & seamless
        const modeExecute = registeredTools['reader_switch_mode']
        expect(modeExecute).toBeDefined()
        await modeExecute!({ mode: 'horizontal', seamless: true })
        expect(mockSettings.mode).toBe('horizontal')
        expect(mockSettings.seamless).toBe(true)

        const fitExecute = registeredTools['reader_switch_fit']
        expect(fitExecute).toBeDefined()
        await fitExecute!({ fit: 'width' })
        expect(mockSettings.fit).toBe('width')

        // Auto turn
        const autoTurnExecute = registeredTools['reader_toggle_auto_turn']
        expect(autoTurnExecute).toBeDefined()
        await autoTurnExecute!({ enable: true, interval: 15 })
        expect(mockSettings.autoTurn).toBe(true)
        expect(mockSettings.autoTurnInterval).toBe(15)

        // Locate bubble
        const locateExecute = registeredTools['reader_locate_bubble']
        expect(locateExecute).toBeDefined()
        await locateExecute!({
          page: 12,
          box: [0.1, 0.2, 0.3, 0.4],
          text: 'Hello World',
        })
        expect(goToPageMock).toHaveBeenCalledWith(12)
        expect(routerReplaceMock).toHaveBeenCalledWith({
          query: expect.objectContaining({
            page: '12',
            bubble_box: '0.1,0.2,0.3,0.4',
            bubble_text: 'Hello World',
            highlight_bubble: '1',
          }),
        })

        // Jump chapter
        const chapterExecute = registeredTools['reader_jump_chapter']
        expect(chapterExecute).toBeDefined()
        await chapterExecute!({ direction: 'next' })
        expect(goNextChapterMock).toHaveBeenCalled()
        await chapterExecute!({ direction: 'prev' })
        expect(goPrevChapterMock).toHaveBeenCalled()

        // Favorite
        const favExecute = registeredTools['reader_toggle_favorite']
        expect(favExecute).toBeDefined()
        await favExecute!({ favorite: true })
        expect(toggleFavoriteMock).toHaveBeenCalled()

        scope.stop()
      } finally {
        // @ts-expect-error restore
        window.document.modelContext = originalModelContext
      }
    })
  })

  describe('useShelfWebMCP', () => {
    it('handles shelf search, dialogue FTS5, random pick, import, and opening comics', async () => {
      const registeredTools: Record<string, (args: unknown) => Promise<unknown>> = {}
      const registerToolMock = vi.fn<
        (toolDef: { name: string; execute: (args: unknown) => Promise<unknown> }) => void
      >((toolDef) => {
        registeredTools[toolDef.name] = toolDef.execute
      })

      // @ts-expect-error mock window.document
      const originalModelContext = window.document.modelContext
      // @ts-expect-error mock window.document
      window.document.modelContext = {
        registerTool: registerToolMock,
      }

      const routerPushMock = vi.fn<() => Promise<void>>().mockResolvedValue(undefined)
      const mockRouter = {
        push: routerPushMock,
      } as unknown as Router

      vi.spyOn(api, 'searchDialogue').mockResolvedValue({
        total: 1,
        results: [
          {
            source: 'jm',
            source_id: '123456',
            title: 'Sample Comic',
            page_index: 5,
            text: 'Found dialogue',
            box: [0.1, 0.2, 0.3, 0.4],
          },
        ],
      })

      try {
        setActivePinia(createPinia())
        const scope = effectScope()
        scope.run(() => {
          const store = useLibraryStore()
          store.items = [
            {
              source: 'jm',
              source_id: '123456',
              display_id: '123456',
              title: 'Sample Comic',
              page_count: 30,
              authors: ['Author A'],
              works: [],
              actors: [],
              tags: ['Romance'],
              favorite: false,
              views: '100',
              likes: '50',
              uploaded_at: '',
              published_at: '',
              updated_at: '',
              imported_at: '',
              cover_paths: [],
              cached_pages: 30,
              cover_count: 1,
              chapter_titles: [],
              last_page: 0,
            },
          ]

          useShelfWebMCP({
            router: mockRouter,
          })
        })

        await nextTick()

        const filterExecute = registeredTools['shelf_search_comics']
        const dialogueExecute = registeredTools['shelf_search_dialogue']
        const randomExecute = registeredTools['shelf_pick_random']
        const openComicExecute = registeredTools['shelf_open_comic']

        expect(filterExecute).toBeDefined()
        expect(dialogueExecute).toBeDefined()
        expect(randomExecute).toBeDefined()
        expect(openComicExecute).toBeDefined()

        // 1. Test filtering with reset & multiple tags
        await filterExecute!({
          reset: true,
          keyword: 'test query',
          tags: ['Romance', 'Fantasy'],
          sortBy: 'pages',
          favoritesOnly: true,
          readingStatus: 'reading',
        })

        const shelfState = useShelfState()
        expect(shelfState.search.value).toBe('test query')
        expect(shelfState.activeTags.value).toEqual(['Romance', 'Fantasy'])
        expect(shelfState.sortBy.value).toBe('pages')
        expect(shelfState.favoritesOnly.value).toBe(true)
        expect(shelfState.readingStatus.value).toBe('reading')

        // 2. Test dialogue search
        const dialogueRes = await dialogueExecute!({ query: 'Found dialogue' })
        expect(api.searchDialogue).toHaveBeenCalledWith('Found dialogue', undefined, 10)
        expect(dialogueRes).toEqual(
          expect.objectContaining({
            content: expect.arrayContaining([
              expect.objectContaining({
                text: expect.stringContaining('Found dialogue'),
              }),
            ]),
          }),
        )

        // 3. Test pick random and enter reader
        await randomExecute!({ openReader: true })
        expect(routerPushMock).toHaveBeenCalledWith({
          path: '/comic/jm/123456/read/1',
        })

        // 4. Test open comic with chapter
        await openComicExecute!({ source: 'jm', source_id: '123456', chapter_id: 'c2' })
        expect(routerPushMock).toHaveBeenCalledWith('/comic/jm/123456/chapter/c2')

        // 5. Test read comic directly with bubble
        const readComicExecute = registeredTools['shelf_read_comic']
        expect(readComicExecute).toBeDefined()
        await readComicExecute!({
          source: 'jm',
          source_id: '123456',
          page: 5,
          bubble_box: [0.1, 0.2, 0.3, 0.4],
          bubble_text: 'Found dialogue',
        })
        expect(routerPushMock).toHaveBeenCalledWith({
          path: '/comic/jm/123456/read/5',
          query: {
            page: '5',
            bubble_box: '0.1000,0.2000,0.3000,0.4000',
            bubble_text: 'Found dialogue',
            highlight_bubble: '1',
          },
        })

        // 6. Test image search
        vi.spyOn(api, 'imageSearch').mockResolvedValue([
          {
            source: 'jm',
            source_id: '123456',
            page_index: 8,
            is_cover: false,
            score: 0.945,
          },
        ])
        const imageSearchExecute = registeredTools['shelf_search_image']
        expect(imageSearchExecute).toBeDefined()
        const imgRes = await imageSearchExecute!({
          image_base64: 'data:image/jpeg;base64,aGVsbG8=',
        })
        expect(api.imageSearch).toHaveBeenCalled()
        expect(imgRes).toEqual(
          expect.objectContaining({
            content: expect.arrayContaining([
              expect.objectContaining({
                text: expect.stringContaining('95%'),
              }),
            ]),
          }),
        )

        // 7. Test import comic with auto inference, tags, favorite & open_after
        vi.spyOn(api, 'importComic').mockResolvedValue({
          from_cache: false,
          background: true,
          prefetched: 0,
          warnings: [],
          meta: createPlaceholderDetail({
            source: 'jm',
            source_id: '999999',
            display_id: '999999',
            title: 'Imported Title',
            page_count: 20,
            authors: [],
            works: [],
            actors: [],
            tags: [],
            favorite: false,
            views: '0',
            likes: '0',
            uploaded_at: '',
            published_at: '',
            updated_at: '',
            imported_at: '',
            cover_paths: [],
            cached_pages: 0,
            cover_count: 1,
            chapter_titles: [],
            last_page: 0,
          }).meta,
        })
        const mockImportDetail = createPlaceholderDetail({
          source: 'jm',
          source_id: '999999',
          display_id: '999999',
          title: 'Imported Title',
          page_count: 20,
          authors: [],
          works: [],
          actors: [],
          tags: ['ExistingTag'],
          favorite: false,
          views: '0',
          likes: '0',
          uploaded_at: '',
          published_at: '',
          updated_at: '',
          imported_at: '',
          cover_paths: [],
          cached_pages: 0,
          cover_count: 1,
          chapter_titles: [],
          last_page: 0,
        })
        const setFavSpy = vi
          .spyOn(api, 'setFavorite')
          .mockResolvedValue({ ok: true, favorite: true })
        const updateMetaSpy = vi.spyOn(api, 'updateMetadata').mockResolvedValue(mockImportDetail)
        vi.spyOn(api, 'detail').mockResolvedValue(mockImportDetail)

        const importComicExecute = registeredTools['shelf_import_comic']
        expect(importComicExecute).toBeDefined()
        const importRes = await importComicExecute!({
          id: '999999',
          prefetch_all: true,
          favorite: true,
          tags: ['NewTag'],
          open_after: true,
        })
        expect(api.importComic).toHaveBeenCalledWith({
          id: '999999',
          source: 'jm',
          prefetch_covers: 4,
          prefetch_all: true,
        })
        expect(setFavSpy).toHaveBeenCalledWith('jm', '999999', true)
        expect(updateMetaSpy).toHaveBeenCalledWith('jm', '999999', {
          tags: ['ExistingTag', 'NewTag'],
        })
        expect(routerPushMock).toHaveBeenCalledWith({
          name: 'comic-detail',
          params: { source: 'jm', sourceId: '999999' },
        })
        expect(importRes).toEqual(
          expect.objectContaining({
            content: expect.arrayContaining([
              expect.objectContaining({
                text: expect.stringContaining('Imported Title'),
              }),
            ]),
          }),
        )

        scope.stop()
      } finally {
        // @ts-expect-error restore
        window.document.modelContext = originalModelContext
      }
    })
  })

  describe('useComicDetailWebMCP', () => {
    it('handles reading start, caching, chapter switching, metadata update and inspection', async () => {
      const registeredTools: Record<string, (args: unknown) => Promise<unknown>> = {}
      const registerToolMock = vi.fn<
        (toolDef: { name: string; execute: (args: unknown) => Promise<unknown> }) => void
      >((toolDef) => {
        registeredTools[toolDef.name] = toolDef.execute
      })

      // @ts-expect-error mock window.document
      const originalModelContext = window.document.modelContext
      // @ts-expect-error mock window.document
      window.document.modelContext = {
        registerTool: registerToolMock,
      }

      const routerPushMock = vi.fn<() => Promise<void>>().mockResolvedValue(undefined)
      const mockRouter = {
        push: routerPushMock,
      } as unknown as Router

      const mockDetail = createPlaceholderDetail({
        source: 'jm',
        source_id: '523607',
        display_id: '523607',
        title: 'Test Comic Title',
        authors: ['Test Artist'],
        works: [],
        actors: [],
        tags: ['Action', 'Fantasy'],
        favorite: true,
        page_count: 100,
        views: '1000',
        likes: '500',
        uploaded_at: '',
        published_at: '',
        updated_at: '',
        imported_at: '',
        cover_paths: [],
        cached_pages: 80,
        cover_count: 1,
        chapter_titles: ['Chapter 1', 'Chapter 2'],
        last_page: 0,
      })
      mockDetail.meta.chapters = [
        { id: 'c1', title: 'Chapter 1', page_count: 50, start: 1, index: 1 },
        { id: 'c2', title: 'Chapter 2', page_count: 50, start: 51, index: 2 },
      ]

      const detailRef = shallowRef<ComicDetail | null>(mockDetail)
      const chaptersRef = computed<Chapter[]>(() => mockDetail.meta.chapters || [])
      const lastReadRef = ref(15)
      const cacheAllMock = vi.fn<() => Promise<void>>().mockResolvedValue(undefined)
      const cacheChapterMock = vi.fn<(id: string) => Promise<void>>().mockResolvedValue(undefined)
      const toggleFavMock = vi.fn<() => Promise<void>>().mockResolvedValue(undefined)

      vi.spyOn(api, 'updateMetadata').mockResolvedValue({
        ...mockDetail,
        meta: {
          ...mockDetail.meta,
          title: 'Updated Title',
        },
      })
      vi.spyOn(api, 'createDirectPass').mockResolvedValue({
        token: 'mock-temp-token-xyz',
        source: 'jm',
        source_id: '523607',
        page_index: 15,
        expires_at: 1700007200,
        expires_in: 7200,
        direct_url: '/comic/jm/523607/read/15?temp_token=mock-temp-token-xyz',
      })

      try {
        const scope = effectScope()
        scope.run(() => {
          useComicDetailWebMCP({
            source: computed(() => 'jm'),
            sourceId: computed(() => '523607'),
            detail: detailRef,
            chapters: chaptersRef,
            lastRead: lastReadRef,
            router: mockRouter,
            cacheAll: cacheAllMock,
            cacheChapter: cacheChapterMock,
            toggleFavorite: toggleFavMock,
            activeChapterId: computed(() => 'c1'),
          })
        })

        await nextTick()

        const startReading = registeredTools['detail_start_reading']
        const cacheAll = registeredTools['detail_cache_all_pages']
        const cacheChapter = registeredTools['detail_cache_chapter']
        const openChapter = registeredTools['detail_open_chapter']
        const getInfo = registeredTools['detail_get_comic_info']
        const toggleFav = registeredTools['detail_toggle_favorite']
        const updateMeta = registeredTools['detail_update_metadata']
        const createDirectPass = registeredTools['detail_create_direct_pass']

        expect(startReading).toBeDefined()
        expect(cacheAll).toBeDefined()
        expect(cacheChapter).toBeDefined()
        expect(openChapter).toBeDefined()
        expect(getInfo).toBeDefined()
        expect(toggleFav).toBeDefined()
        expect(updateMeta).toBeDefined()
        expect(createDirectPass).toBeDefined()

        // 1. Start reading from last read
        await startReading!({})
        expect(routerPushMock).toHaveBeenCalledWith({
          path: '/comic/jm/523607/read/15',
          query: { page: '15', chapter: 'c1' },
        })

        // 2. Start reading from chapter_id c2
        await startReading!({ chapter_id: 'c2' })
        expect(routerPushMock).toHaveBeenCalledWith({
          path: '/comic/jm/523607/read/51',
          query: { page: '51', chapter: 'c2' },
        })

        // 3. Cache all
        await cacheAll!({})
        expect(cacheAllMock).toHaveBeenCalled()

        // 4. Cache chapter
        await cacheChapter!({ chapter_id: 'c2' })
        expect(cacheChapterMock).toHaveBeenCalledWith('c2')

        // 5. Open chapter
        await openChapter!({ chapter_id: 'c2' })
        expect(routerPushMock).toHaveBeenCalledWith('/comic/jm/523607/chapter/c2')

        // 6. Get comic info
        const infoRes = await getInfo!({})
        expect(infoRes).toEqual(
          expect.objectContaining({
            content: expect.arrayContaining([
              expect.objectContaining({
                text: expect.stringContaining('Test Comic Title'),
              }),
            ]),
          }),
        )

        // 7. Toggle favorite
        await toggleFav!({ favorite: false })
        expect(toggleFavMock).toHaveBeenCalled()

        // 8. Update metadata
        const updateRes = await updateMeta!({ title: 'Updated Title' })
        expect(api.updateMetadata).toHaveBeenCalledWith('jm', '523607', { title: 'Updated Title' })
        expect(updateRes).toEqual(
          expect.objectContaining({
            content: expect.arrayContaining([
              expect.objectContaining({
                text: expect.stringContaining('Updated Title'),
              }),
            ]),
          }),
        )

        // 9. Create direct pass
        const directPassRes = await createDirectPass!({ page: 15, ttl_seconds: 3600 })
        expect(api.createDirectPass).toHaveBeenCalledWith({
          source: 'jm',
          source_id: '523607',
          page_index: 15,
          ttl_seconds: 3600,
        })
        expect(directPassRes).toEqual(
          expect.objectContaining({
            content: expect.arrayContaining([
              expect.objectContaining({
                text: expect.stringContaining('mock-temp-token-xyz'),
              }),
            ]),
          }),
        )

        scope.stop()
      } finally {
        // @ts-expect-error restore
        window.document.modelContext = originalModelContext
      }
    })
  })

  describe('useDiscoveryWebMCP', () => {
    it('handles ranking queries, timeframe switching, ingestion and navigation', async () => {
      const registeredTools: Record<string, (args: unknown) => Promise<unknown>> = {}
      const registerToolMock = vi.fn<
        (toolDef: { name: string; execute: (args: unknown) => Promise<unknown> }) => void
      >((toolDef) => {
        registeredTools[toolDef.name] = toolDef.execute
      })

      // @ts-expect-error mock window.document
      const originalModelContext = window.document.modelContext
      // @ts-expect-error mock window.document
      window.document.modelContext = {
        registerTool: registerToolMock,
      }

      const routerPushMock = vi.fn<() => Promise<void>>().mockResolvedValue(undefined)
      const mockRouter = {
        push: routerPushMock,
      } as unknown as Router

      const timeframeRef = ref<'week' | 'month' | 'day'>('week')
      const mockFeed = {
        timeframe: 'week' as const,
        updated_at: '',
        items: [
          {
            id: '888888',
            source: 'jm',
            source_id: '888888',
            title: 'Top Discovery Comic',
            author: 'Great Artist',
            category: 'Comedy',
            in_library: false,
          },
        ],
      }
      const feedRef = shallowRef(mockFeed)
      const loadRankingMock = vi.fn<() => Promise<void>>().mockResolvedValue(undefined)
      const ingestComicMock = vi.fn<() => Promise<void>>().mockResolvedValue(undefined)

      try {
        const { useDiscoveryWebMCP } = await import('@/composables/useDiscoveryWebMCP')
        const scope = effectScope()
        scope.run(() => {
          useDiscoveryWebMCP({
            timeframe: timeframeRef,
            feed: feedRef,
            loadRanking: loadRankingMock,
            ingestComic: ingestComicMock,
            router: mockRouter,
          })
        })

        await nextTick()

        const getRanking = registeredTools['discovery_get_ranking']
        const switchTimeframe = registeredTools['discovery_switch_timeframe']
        const ingestComic = registeredTools['discovery_ingest_comic']
        const openDetail = registeredTools['discovery_open_detail']

        expect(getRanking).toBeDefined()
        expect(switchTimeframe).toBeDefined()
        expect(ingestComic).toBeDefined()
        expect(openDetail).toBeDefined()

        // 1. Get ranking with limit and category filter
        const res = await getRanking!({
          timeframe: 'month',
          refresh: true,
          limit: 5,
          category: 'Comedy',
        })
        expect(loadRankingMock).toHaveBeenCalledWith('jm', 'month', true)
        expect(res).toEqual(
          expect.objectContaining({
            content: expect.arrayContaining([
              expect.objectContaining({
                text: expect.stringContaining('Top Discovery Comic'),
              }),
            ]),
          }),
        )

        // 2. Switch timeframe
        await switchTimeframe!({ timeframe: 'day' })
        expect(loadRankingMock).toHaveBeenCalledWith('jm', 'day', false)

        // 3. Ingest comic and navigate
        await ingestComic!({ source_id: '888888', open_after: true })
        expect(ingestComicMock).toHaveBeenCalled()
        expect(routerPushMock).toHaveBeenCalledWith({
          name: 'comic-detail',
          params: { source: 'jm', sourceId: '888888' },
        })

        // 4. Open detail
        await openDetail!({ source: 'jm', source_id: '888888' })
        expect(routerPushMock).toHaveBeenCalledWith({
          name: 'comic-detail',
          params: { source: 'jm', sourceId: '888888' },
        })

        scope.stop()
      } finally {
        // @ts-expect-error restore
        window.document.modelContext = originalModelContext
      }
    })
  })

  describe('WebMCP Role Isolation (Guest vs Curator Gating)', () => {
    it('does not register curator-only tools on guest sessions while keeping read tools active', async () => {
      const registeredTools: Record<string, (args: unknown) => Promise<unknown>> = {}
      const registerToolMock = vi.fn<
        (toolDef: { name: string; execute: (args: unknown) => Promise<unknown> }) => void
      >((toolDef) => {
        registeredTools[toolDef.name] = toolDef.execute
      })

      // @ts-expect-error mock window.document
      const originalModelContext = window.document.modelContext
      // @ts-expect-error mock window.document
      window.document.modelContext = {
        registerTool: registerToolMock,
      }

      const mockRouter = {
        push: vi.fn<() => Promise<void>>().mockResolvedValue(undefined),
      } as unknown as Router

      const { useAuth } = await import('@/composables/useAuth')
      const auth = useAuth()
      const prevAuthRequired = auth.authRequired.value
      const prevRole = auth.role.value
      const prevAuth = auth.authenticated.value

      auth.authRequired.value = true
      auth.authenticated.value = true
      auth.role.value = 'guest'
      expect(auth.canWrite.value).toBe(false)

      try {
        const scope = effectScope()
        scope.run(() => {
          // 1. Shelf
          const shelfMcp = useShelfWebMCP({ router: mockRouter })
          expect(shelfMcp!.searchComicsTool).toBeDefined()
          expect(shelfMcp!.importComicTool).toBeUndefined()

          // 2. Detail
          const mockDetail = createPlaceholderDetail({
            source: 'jm',
            source_id: '123',
            display_id: '123',
            title: 'Guest View Comic',
            page_count: 10,
            authors: [],
            works: [],
            actors: [],
            tags: [],
            favorite: false,
            views: '0',
            likes: '0',
            uploaded_at: '',
            published_at: '',
            updated_at: '',
            imported_at: '',
            cover_paths: [],
            cached_pages: 0,
            cover_count: 1,
            chapter_titles: [],
            last_page: 0,
          })
          const detailMcp = useComicDetailWebMCP({
            source: computed(() => 'jm'),
            sourceId: computed(() => '123'),
            detail: shallowRef(mockDetail),
            chapters: computed(() => []),
            lastRead: ref(1),
            router: mockRouter,
          })
          expect(detailMcp!.startReadingTool).toBeDefined()
          expect(detailMcp!.cacheAllTool).toBeUndefined()
          expect(detailMcp!.cacheChapterTool).toBeUndefined()
          expect(detailMcp!.updateMetadataTool).toBeUndefined()
          expect(detailMcp!.createDirectPassTool).toBeUndefined()

          // 3. Discovery
          const discoveryMcp = useDiscoveryWebMCP({
            timeframe: ref('week'),
            feed: shallowRef(null),
            loadRanking: vi.fn<() => Promise<void>>().mockResolvedValue(undefined),
            ingestComic: vi.fn<() => Promise<void>>().mockResolvedValue(undefined),
            router: mockRouter,
          })
          expect(discoveryMcp!.getRankingTool).toBeDefined()
          expect(discoveryMcp!.ingestComicTool).toBeUndefined()
        })

        await nextTick()

        // Verify registered tool names in document.modelContext
        expect(registeredTools['shelf_search_comics']).toBeDefined()
        expect(registeredTools['shelf_import_comic']).toBeUndefined()
        expect(registeredTools['detail_start_reading']).toBeDefined()
        expect(registeredTools['detail_cache_all_pages']).toBeUndefined()
        expect(registeredTools['detail_update_metadata']).toBeUndefined()
        expect(registeredTools['detail_create_direct_pass']).toBeUndefined()
        expect(registeredTools['discovery_get_ranking']).toBeDefined()
        expect(registeredTools['discovery_ingest_comic']).toBeUndefined()

        scope.stop()
      } finally {
        auth.authRequired.value = prevAuthRequired
        auth.role.value = prevRole
        auth.authenticated.value = prevAuth
        // @ts-expect-error restore
        window.document.modelContext = originalModelContext
      }
    })

    it('completely shuts down all WebMCP registration for single-book sandbox temporary sessions (Zero MCP Attack Surface)', async () => {
      const registeredTools: Record<string, (args: unknown) => Promise<unknown>> = {}
      const registerToolMock = vi.fn<
        (toolDef: { name: string; execute: (args: unknown) => Promise<unknown> }) => void
      >((toolDef) => {
        registeredTools[toolDef.name] = toolDef.execute
      })

      // @ts-expect-error mock window.document
      const originalModelContext = window.document.modelContext
      // @ts-expect-error mock window.document
      window.document.modelContext = {
        registerTool: registerToolMock,
      }

      const { useAuth } = await import('@/composables/useAuth')
      const auth = useAuth()
      const prevAuthRequired = auth.authRequired.value
      const prevRole = auth.role.value
      const prevAuth = auth.authenticated.value
      const prevUserId = auth.userId.value

      auth.authRequired.value = true
      auth.role.value = 'guest'
      auth.authenticated.value = true
      auth.userId.value = 'direct:jm:523607'

      expect(auth.isDirectPass.value).toBe(true)

      const routerPushMock = vi.fn<() => Promise<void>>().mockResolvedValue(undefined)
      const mockRouter = { push: routerPushMock } as unknown as Router

      try {
        const scope = effectScope()
        scope.run(() => {
          // 1. Shelf
          const shelfMcp = useShelfWebMCP({ router: mockRouter })
          expect(shelfMcp).toBeUndefined()

          // 2. Detail
          const mockDetail = createPlaceholderDetail({
            source: 'jm',
            source_id: '523607',
            display_id: '523607',
            title: 'Direct Pass Comic',
            page_count: 10,
            authors: [],
            works: [],
            actors: [],
            tags: [],
            favorite: false,
            views: '0',
            likes: '0',
            uploaded_at: '',
            published_at: '',
            updated_at: '',
            imported_at: '',
            cover_paths: [],
            cached_pages: 0,
            cover_count: 1,
            chapter_titles: [],
            last_page: 0,
          })
          const detailMcp = useComicDetailWebMCP({
            source: computed(() => 'jm'),
            sourceId: computed(() => '523607'),
            detail: shallowRef(mockDetail),
            chapters: computed(() => []),
            lastRead: ref(1),
            router: mockRouter,
          })
          expect(detailMcp).toBeUndefined()

          // 3. Reader
          const readerMcp = useReaderWebMCP({
            currentPage: ref(1),
            pageCount: computed(() => 10),
            settings: {
              mode: 'vertical',
              direction: 'ltr',
              fit: 'width',
              pagesPerView: 1,
              seamless: true,
              theme: 'dark',
              autoTurn: false,
              autoTurnInterval: 5,
              brightness: 100,
            } as unknown as ReaderSettings,
            goToPage: vi.fn<(page: number) => void>(),
            prevGroup: vi.fn<() => void>(),
            nextGroup: vi.fn<() => void>(),
          })
          expect(readerMcp).toBeUndefined()

          // 4. Discovery
          const discoveryMcp = useDiscoveryWebMCP({
            timeframe: ref('week'),
            feed: shallowRef(null),
            loadRanking: vi.fn<() => Promise<void>>().mockResolvedValue(undefined),
            ingestComic: vi.fn<() => Promise<void>>().mockResolvedValue(undefined),
            router: mockRouter,
          })
          expect(discoveryMcp).toBeUndefined()
        })

        await nextTick()

        // Absolutely zero tools registered on document.modelContext!
        expect(registerToolMock).not.toHaveBeenCalled()
        expect(Object.keys(registeredTools).length).toBe(0)

        scope.stop()
      } finally {
        auth.authRequired.value = prevAuthRequired
        auth.role.value = prevRole
        auth.authenticated.value = prevAuth
        auth.userId.value = prevUserId
        // @ts-expect-error restore
        window.document.modelContext = originalModelContext
      }
    })
  })
})
