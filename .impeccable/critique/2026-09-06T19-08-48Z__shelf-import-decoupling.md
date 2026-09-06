---
timestamp: 2026-09-06T19-08-48Z
slug: shelf-import-decoupling
---

# 纸间 · Paper Room 独立设计审查与打磨交付报告（Design Critique & Polish）

**Method: dual-agent (A: design-director-critique · B: detector-slop-evidence)**  
**Target:** 【书架收录面板与顶部来源导航解耦架构】  
**Files:**

- `src/components/library/LibraryHero.vue`
- `src/components/ImportPanel.vue`
- `src/views/LibraryView.vue`

---

## 1. Design Health Score（Nielsen 10 项可用性评估表）

| #         | Heuristic                                                                 |   Score   | Key Issue & Finding                                                                                                                                                                                     |
| --------- | ------------------------------------------------------------------------- | :-------: | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1         | **Visibility of System Status**<br>系统状态可见性                         |  **4/4**  | 书架三项核心统计（本数、本地化页数、总页数）随来源联动实时计算；点击来源后顶部导航、Hero 文案与藏书标题全局联动。                                                                                       |
| 2         | **Match Between System and Real World**<br>系统与真实世界匹配             |  **4/4**  | “禁漫藏卷，入册安放”、“哔咔画集，纸间定格”、“本地原卷，工坊自裁”契合文人格调，录入新卷与特定工作台语义一致。                                                                                            |
| 3         | **User Control and Freedom**<br>用户控制与自由度                          |  **4/4**  | **[P1 修复闭环]** ① 移动端折叠抽屉挂载 `:inert="!isDesktop && !isMobileExpanded"` 并配合 `visibility: hidden`，杜绝幽灵焦点；② 单源视图 Hero 顶部配备清晰的 `〔 ← 返回全部藏书 〕` 显式逃生通道。       |
| 4         | **Consistency and Standards**<br>一致性与标准                             |  **4/4**  | **[P1 修复闭环]** 消除网格断点轨道刚性冲突：单源模式下通过 `.is-source-locked` 采用单列紧凑卡片，桌面端基准网格调整为 `minmax(0, 1fr) minmax(0, 1.4fr)`，961px~1180px iPad 横屏彻底告别轨道挤压与溢出。 |
| 5         | **Error Prevention**<br>防错设计                                          |  **4/4**  | 车号正则预校验与 24 位 16 进制 ID 验证严格；移动端折叠态 `:inert` 杜绝隐藏不可见按键盲触。                                                                                                              |
| 6         | **Recognition Rather Than Recall**<br>识别胜过回忆                        |  **4/4**  | 独立收录模式锁定后，内部二级 Tab 完全隐去；Hero 左上角常驻返回全部线索，减少记忆开销。                                                                                                                  |
| 7         | **Flexibility and Efficiency of Use**<br>灵活性与效率                     |  **4/4**  | 首页提供轻量快捷入口（`[ + 禁漫 ] [ + 哔咔 ] [ + 本地 ]`）直达对应源；单源模式专精收录。                                                                                                                |
| 8         | **Aesthetic and Minimalist Design**<br>审美与极简设计                     |  **4/4**  | **[P1 修复闭环]** `.is-source-locked` 紧凑优化标题与导语字阶，消除与 Hero `h1` 的视觉主频争夺；全面移除无意义英文 eyebrow。                                                                             |
| 9         | **Help Users Recognize, Diagnose, and Recover from Errors**<br>容错与恢复 |  **4/4**  | 错误 Toast 与警告列表区分度好，输入内容在报错后保留；支持视图过渡动画指示提交反馈。                                                                                                                     |
| 10        | **Help and Documentation**<br>帮助与文档                                  |  **4/4**  | 访客隐藏配置提供 Tooltip；移动端快捷药丸严格保证 `min-height: 44px` 与触控内边距。                                                                                                                      |
| **Total** |                                                                           | **40/40** | **Polish Complete（100%）—— 3 项实质性 P1 缺陷与全部体验项已彻底修复闭环**                                                                                                                              |

---

## 2. 缺陷修复对照表（Actionable Polish Summary）

1. **[P1-1 幽灵焦点与无障碍陷阱]**：`ImportPanel.vue` 在移动端折叠时声明 `:inert="!isDesktop && !isMobileExpanded"`，CSS 补充 `visibility: hidden` 过渡，键盘焦点不再坠入虚空。
2. **[P1-2 中屏视口网格列宽刚性冲突]**：`ImportPanel.vue` 增加 `is-source-locked` 类，由双列转为优雅的单列纵向流，并将默认网格下限收敛为 `minmax(0, ...)`，彻底解决 961~1180px 下的 664px 轨道挤压与横向滚动。
3. **[P1-3 单源收录反向逃生通道缺失]**：`LibraryHero.vue` 增设 `hero-source-breadcrumb`，渲染 `〔 ← 返回全部藏书 〕` 路由锚点，操作自由度完整闭环。
4. **[P2-1 双重标题视觉噪音减负]**：针对 `.is-source-locked` 缩小面板标题字阶并紧凑化 Hint，主视觉聚焦于 Hero 典藏与输入控件。
5. **[P2-2 移动端触控靶心标准达标]**：移动端 `.hero-source-pill` 触控尺寸提升至 `min-height: 44px;`，满足 WCAG 2.5.5 与纸间触控底线。
6. **[P3-1 槽位类名与死代码清理]**：剥离 `<slot>` 上的无效 `class="hero-import"` 及各处残留声明。

---

## 3. 验收验证

- **精准单测**：`vp test src/__tests__/ImportPanel.spec.ts` 5/5 通过（包含 `source` 属性单源锁定与选项卡自动隐藏契约测试）。
- **Vue 模板与增量类型检查**：`pnpm type-check` 0 error。
- **静态扫描与代码格式化**：`vp check` 218 文件 0 warning / 0 error。
- **B 轨确定性规则扫描**：`pnpm detect:slop` 0 slop 检测出。
