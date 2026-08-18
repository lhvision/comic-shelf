# HTML-in-Canvas 实验（详细规则）

## 8. HTML-in-Canvas 状态

- Chrome 148–150 Origin Trial；本地可用 Canary 149+ 打开
  `chrome://flags/#canvas-draw-element` 测试。
- 真网站仍建议去 Chrome Origin Trials 控制台为域名申请 token，并在
  `index.html` 填入：
  `<meta http-equiv="origin-trial" content="TOKEN">`
- 实验开关位于 `localStorage['comic-shelf:experiments:v1']`：
  `{ htmlCanvasCards: true }`。
- `HtmlCanvasSurface.vue` 只在 `canvas.getContext('html')` 可用且实验开启时启用；
  否则 default slot 作为普通 DOM 渲染，不要删除 fallback。
- 它绘制的是**完整卡片 DOM 子树**（封面 + 标题 + 作者 + 标签 + 缓存进度），
  交互由透明 overlay slot 保留；这才是 HTML-in-Canvas 相对普通 image 的价值点。
