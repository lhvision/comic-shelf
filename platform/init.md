在当前项目下里加一个 platform/ 目录，做一个最小的 UI 回归测试平台，
只用 Node 标准库、不引框架：

1. 服务端 server.mjs：
   - 读 e2e/user-admin.spec.ts 里所有 test 名 + cases.json 的分组/优先级，合成用例清单
   - POST /api/run 起 playwright 子进程（支持 -g 只跑某个分组），实时统计进度
   - 跑完解析 JSON 报告，给每条失败用例匹配 midscene_run/report/ 下的 HTML，存进 runs.json
2. 前端 public/：左边用例清单按分组展示，右边最新一轮结果 + 历史
   - UI 用 Vercel 风格：白底、克制的灰阶、状态色只给红绿

完成后自己跑起来，用浏览器截图确认能用。
