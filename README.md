# Simple Boss Manage

一个面向求职者的 BOSS 直聘数据管理工具，帮助你在求职过程中更好地跟踪和管理与招聘者的沟通。

## 功能

### 数据同步
- 一键同步 BOSS 直聘联系人、岗位信息和聊天记录到本地 SQLite 数据库
- 支持按天数范围筛选（仅同步最近 N 天的消息）
- 自动增量更新，已有记录不会重复存储
- 同步日志记录，可追溯每次同步的时间、数量和异常

### 投递管理
- 查看所有沟通过的 BOSS 列表，支持按城市、职位、面试/简历/笔试状态筛选
- 自定义列显示，可自由选择展示哪些字段
- 一键切换面试、简历投递、笔试状态
- 支持按首次联系、最近联系时间排序

### 聊天记录浏览
- 左右对话气泡布局，清晰区分我方和 BOSS 的消息
- 支持显示文本、Emoji 表情、贴图表情
- 自动标记简历投递状态

### 消息提醒
- 自动识别"对方未回复"的 BOSS，方便跟进
- 展示连续未回复条数，按紧急程度排序
- 支持 AI 自动生成提醒消息（基于 DeepSeek）
- 批量发送提醒消息（Playwright 自动化操作浏览器）

### 统计分析
- 概览仪表盘：投递公司数、沟通次数、约面次数、覆盖城市
- 城市分布柱状图、岗位方向饼图
- 每日沟通次数趋势图，支持按月/周筛选

### 自动发消息
- 单人或批量自动发送消息给指定 BOSS
- 支持固定文本模板（`{name}` 和 `{boss_title}` 占位符）
- 支持 AI 生成消息内容
- Playwright 驱动真实浏览器，模拟人工操作

## 技术栈

| 层 | 技术 |
|------|------|
| 前端 | Vue 3 + Element Plus + ECharts |
| 后端 | Python FastAPI |
| 数据库 | SQLite |
| 浏览器自动化 | Playwright |
| AI 消息生成 | OpenAI SDK (DeepSeek) |

## 快速开始

### 1. 安装依赖

```bash
# 后端
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# 前端
cd frontend
npm install
```

### 2. 启动服务

```bash
# 终端 1 - 后端
cd Simple-Boss-Manage
source backend/venv/bin/activate
uvicorn backend.main:app --reload --port 8000

# 终端 2 - 前端
cd frontend
npm run dev
```

### 3. 使用

1. 打开 `http://localhost:5173`
2. 进入「设置」→「登录管理」→ 点击「打开登录页面」扫码登录 BOSS
3. 点击「同步聊天记录」
4. 在「投递列表」「消息提醒」「统计分析」各页面查看数据

## 致谢

- [boss-cli](https://github.com/joohw/boss-cli) — BOSS 自动发送消息机制参考
- [GeekGeekRun](https://github.com/nicepkg/geekgeekrun) — 反检测与 Cookie 管理方案参考
