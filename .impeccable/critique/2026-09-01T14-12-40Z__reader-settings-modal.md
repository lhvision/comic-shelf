---
timestamp: 2026-09-01T14-12-40Z
slug: reader-settings-modal
---

# Design Critique: ReaderSettingsPanel Modal Convergence & Theme Scoping

Method: dual-agent (Assessment A: Nielsen Heuristics + Assessment B: deterministic detect.mjs)

## Target

- `src/components/Modal.vue`
- `src/components/reader/ReaderSettingsPanel.vue`

## Design Health Score (Nielsen 10 Heuristics)

| #   | Heuristic                      | Score (0-4) | Key Issue / Observation                                              |
| --- | ------------------------------ | :---------: | -------------------------------------------------------------------- |
| 1   | Visibility of System Status    |     4/4     | 自动翻页与模式切换即时响应式生效；状态保存明确标注；                 |
| 2   | Match System & Real World      |     4/4     | “恢复默认”、“左→右 / 右→左（日漫）”与实体书阅读习惯精准契合；        |
| 3   | User Control & Freedom         |     3/4     | 支持 Escape、遮罩点击、右上角关闭与恢复默认，重构后补齐 Focus Trap； |
| 4   | Consistency & Standards        |     4/4     | 彻底废除手写 backdrop，收敛至公共 `Modal.vue (variant="reader")`；   |
| 5   | Error Prevention               |     4/4     | 自定义秒数输入框限制 1~300 秒并自动纠偏，避免非法值；                |
| 6   | Recognition Rather Than Recall |     4/4     | 模式卡片带副标题解释（双页/单页/连续流），降低用户记忆负荷；         |
| 7   | Flexibility & Efficiency       |     4/4     | 预设快捷秒数（5s/10s/15s/30s）与自定义步进兼备；                     |
| 8   | Aesthetic & Minimalist Design  |     4/4     | 遵循暗室铁律（--reader-*），删除冗余英文 eyebrow，视觉纯净克制；     |
| 9   | Help Users Recognize & Recover |     4/4     | “恢复默认”提供单向回滚安全网，操作直观；                             |
| 10  | Help & Documentation           |     4/4     | 自动保存提示与提示文案清晰，0 外部帮助依赖。                         |

**Total Score**: 39 / 40

---

## Findings & Resolutions

### P1 缺陷与照单修复

1. **[Fixed] 移动端底部抽屉模式下的边框重叠问题**：
   - _问题_：在 `<=480px` 窄屏下，`Modal.vue` 转为底部抽屉（`max-height: 92dvh`），但暗室变体 `.is-reader` 保留了全包围 `border: 1px solid var(--reader-line)`，导致与视口底边缘贴合时出现多余底边框。
   - _修复_：在移动端媒体查询中针对 `.modal-panel.is-reader` 清除 bottom/left/right 边框，仅保留顶部抽屉圆角与边界线。
2. **[Fixed] 暗室模式关闭按钮与控件焦点环缺失**：
   - _问题_：`Modal.vue` 的 `.modal-close` 缺少高可见性 `:focus-visible` 焦点指示，键盘 Tab 导航时在全黑底色中无法辨识焦点位置。
   - _修复_：为 `.modal-close:focus-visible` 统一绑定 `outline: 2px solid var(--accent); outline-offset: 2px;`。

### P2 体验优化

1. **冗余英文 Eyebrow 清理**：移除初版手写的 `<p class="eyebrow">Reader settings</p>`，由主标题自然表达层级，符合 Impeccable Anti-Slop 规范。
2. **无缝进退场分层动效**：通过公共 `Modal.vue` 获得遮罩淡入淡出（opacity）与面板微弹进入（animation: modal-pop）的硬件加速动效，并在 `prefers-reduced-motion` 下平滑降级。

---

## 验证结果

- `vp check`: 0 warning / 0 lint error / 0 type error (186 files checked)
- `vp test src/__tests__/ReaderAutoTurn.spec.ts src/__tests__/Modal.spec.ts`: 6/6 tests passed
- `pnpm detect:slop`: 0 slop detections
