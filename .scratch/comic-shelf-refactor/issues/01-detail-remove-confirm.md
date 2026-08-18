# 01 — 详情页「移除本地」换成产品内危险确认

**What to build:** 在详情页内，点「移除本地」不再弹出浏览器原生
`window.confirm`，而是显示一个纸面/朱砂风格的内联危险确认（说明将删除
《xxx》的全部本地页面、不可撤销），确认后才真正调用删除；取消即关。

**Blocked by:** None — 可以立即开始。

**Status:** ready-for-agent

- [ ] 移除 `window.confirm`，改为详情页内危险确认（键盘/朗读可读，可 Esc 关闭）
- [ ] 显示被删作品名与"本地缓存将丢失"的具体后果，而非泛泛"确定吗"
- [ ] 确认/取消按钮焦点管理正确，`vp check` 通过

## 相关评审上下文

critique `src-views-readerview-vue`（29/40）Priority P1：「移除本地」用原生
window.confirm，无产品内确认/无撤销/无后果强调。
