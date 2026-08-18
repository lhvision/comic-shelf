# 04 — cacheAll 部分成功不再误报为 error toast

**What to build:** 详情页缓存全部时，如果远端只缓存了部分页（`progress.complete`
为 false），当前用 `toast(..., 'error')` 上抛。应改用 `info` 语义（如
「已缓存 X/Y 页，其余阅读时自动补齐」），只有真正的异常才用 error；同时避免
与 LibraryView 的 `store.error` watch 重复弹 toast。

**Blocked by:** None — 可以立即开始（只动详情页缓存流程与 toast 调用）。
**Status:** ready-for-agent

- [ ] 部分成功 → `info`；真实失败 → `error`
- [ ] 与 `store.error` watch 不重复弹出
- [ ] `vp check` 通过

## 相关评审上下文

critique 29/40 Minor：cacheAll 部分成功用 `toast(..., 'error')` —— 语义错位
（progress 而非 failure）；LibraryView watch `store.error` 可能与逐次调用重复弹。
