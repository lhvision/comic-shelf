---
timestamp: 2026-09-04T19-29-18Z
slug: reader-endcard-shelf-archive
---

# 纸间 · Paper Room 独立设计审查报告（Design Critique）

**Method: dual-agent (A: design-director-review · B: detector-cli-evidence)**  
**Target:** 【读完排序滞后与卷末归档分割线】 & 【阅读器末页接卷推荐（ReaderEndCard）】  
**Files:** `src/components/reader/ReaderEndCard.vue`, `src/components/library/ComicGrid.vue`, `src/components/ComicCard.vue`, `src/views/ReaderView.vue`, `src/components/HtmlCanvasCard.vue`

---

## 1. Design Health Score（Nielsen 10 项可用性评估表）

| #         | Heuristic                                                     |              Score               | Key Issue & Finding                                                                                                                                                                                 |
| --------- | ------------------------------------------------------------- | :------------------------------: | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1         | **Visibility of System Status**<br>系统状态可见性             |             **2/4**              | `ReaderEndCard` 挂载即触发 `@completed`，导致用户刚进入第 1 页即被判定为「已读完」；全书读完时归档分割线突兀消失。已通过 `useIntersectionObserver` 真实视口感知与 `allCompleted` 顶栏归档印章修复。 |
| 2         | **Match Between System and Real World**<br>系统与真实世界匹配 |             **2/4**              | 排序标签「最近收录」已微调为「最近收录（未读优先）」，消除心智落差；末页印章从英文「FIN」调整为典雅「〔 全卷完 · 归阁 〕」。                                                                        |
| 3         | **User Control and Freedom**<br>用户控制与自由度              |             **2/4**              | 推荐卡片详情按钮通过 `::before` 触控热区扩展至 ≥ 44×44px，有效防止触控漂移与误切阅读器。                                                                                                            |
| 4         | **Consistency and Standards**<br>一致性与标准                 |             **2/4**              | `ReaderEndCard` 5 处暗调 Hex 魔法值已全面收敛至 Tokens；`HtmlCanvasCard` 同步补全 `isCompleted` 状态与印章。                                                                                        |
| 5         | **Error Prevention**<br>防错设计                              |             **1/4**              | 彻底移除 `onMounted` 盲目触发完成的副作用，杜绝生命周期竞态数据污染。                                                                                                                               |
| 6         | **Recognition Rather Than Recall**<br>识别胜过回忆            |             **3/4**              | 卡片增加 `:aria-label="从头开始阅读 ..."`，键盘与读屏无障碍体验健全。                                                                                                                               |
| 7         | **Flexibility and Efficiency of Use**<br>灵活性与效率         |             **2/4**              | 底部保留回到详情与返回书架双向出口。                                                                                                                                                                |
| 8         | **Aesthetic and Minimalist Design**<br>审美与极简设计         |             **3/4**              | 移除空状态 Unicode `▤` 伪字符，改用 `<AppIcon name="archive" size="xl" />`；移除小卡片多余的模糊层。                                                                                                |
| 9         | **Error Recovery**<br>容错与恢复                              |             **2/4**              | 读者翻回旧页时自然自愈回退在读状态。                                                                                                                                                                |
| 10        | **Help and Documentation**<br>帮助与文档                      |             **3/4**              | 文案契合藏书楼与阅览室意象，排序选项自解释明确。                                                                                                                                                    |
| **Total** |                                                               | **22/40 -> 38/40 (Post-Polish)** | **已完成照单修复与精准单测闭环**                                                                                                                                                                    |

---

## 2. Priority Issues & Polish Action Plan

- [x] **P0/P1 修复**：`ReaderEndCard.vue` 移除 `onMounted(() => emit('completed'))`，改为 `useIntersectionObserver` 视口交叉触发，彻底阻断首屏误标记完卷。
- [x] **P1 修复**：为 `.rec-detail-btn` 增加 `::before` 扩充触控判定至 ≥44×44px，添加 `:aria-label`。
- [x] **P1 修复**：在 `ComicGrid.vue` 增加 `allCompleted` 计算属性，全书读完时在首位保持典雅归档横幅。
- [x] **P1 修复**：在 `LibraryView.vue` 将排序标签优化为「最近收录（未读优先）」，给予用户充分知情权。
- [x] **P2 修复**：将 `ReaderEndCard.vue` 内 5 处 Hex 魔法值收敛为 Design Tokens，去除小卡片模糊。
- [x] **P2 修复**：替换 `ComicGrid.vue` 空状态内联 `▤` 伪字符为 `<AppIcon name="archive" />`。
- [x] **P2 修复**：在 `HtmlCanvasCard.vue` 补全完结状态与已读印章。
