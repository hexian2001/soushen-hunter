# 搜神猎手 (SouShen Hunter)

> "搜索如狩猎，信息即猎物"

高性能 Bing/Google 搜索引擎 Skill for OpenClaw - 无需 API 费用，深度网页元素提取

## ✨ 特性

- 🔍 **Bing 搜索** - 使用 Playwright 底层 API，零 API 费用
- 🌐 **Google 搜索** - 高级反检测策略，绕过人机验证
- 🎯 **深度提取** - 自动提取页面链接、表单、按钮、脚本
- ⚡ **高性能** - 异步架构，快速响应
- 🛡️ **反检测** - 绕过反爬虫机制（用户数据目录、行为模拟、指纹伪装）
- 🤖 **OpenClaw 集成** - 开箱即用

## 📦 安装

```bash
# 克隆仓库
git clone https://github.com/hexian2001/soushen-hunter.git

# 复制到 OpenClaw skills 目录
cp -r soushen-hunter ~/.openclaw/skills/

# 重启 OpenClaw
```

## 🔧 依赖

```bash
pip install playwright
```

**Chrome 自动检测**

脚本会自动检测以下位置的 Chrome：
- 环境变量 `CHROME_PATH` 或 `CHROME_BIN`
- 系统 PATH 中的 `google-chrome`, `chromium` 等
- 常见安装路径（Linux/macOS/Windows）
- 项目自带 `/root/ezisall/chrome-linux64/chrome`

手动指定 Chrome 路径：
```bash
export CHROME_PATH=/usr/bin/google-chrome
./soushen "搜索关键词"
```

## 🚀 使用

### CLI 命令

**主入口（推荐）**
```bash
# 使用默认搜索引擎（默认 Bing）
./soushen "搜索关键词"

# 指定结果数量
./soushen "搜索关键词" --num 20

# 指定搜索引擎
./soushen "搜索关键词" --engine google

# 深度页面分析
./soushen --deep "https://目标网址"

# 设置默认搜索引擎
./soushen --set-default-engine google
./soushen --set-default-engine bing

# 查看配置
./soushen --config
```

**Bing 搜索**
```bash
# 基础搜索
python scripts/bing_search.py "搜索关键词"

# 指定结果数量
python scripts/bing_search.py "搜索关键词" --num 20

# 深度页面分析
python scripts/bing_search.py --deep "https://目标网址"
```

**Google 搜索**
```bash
# 基础搜索
python scripts/google_search.py "搜索关键词"

# 指定结果数量
python scripts/google_search.py "AI Agent" --num 20

# 深度页面分析
python scripts/google_search.py --deep "https://目标网址"
```

### Python API

**Bing 搜索**
```python
from scripts.bing_search import BingSearchAgent
import asyncio

async def main():
    async with BingSearchAgent() as agent:
        results = await agent.search("OpenClaw AI Agent")
        for r in results:
            print(f"{r.title}: {r.url}")

asyncio.run(main())
```

**Google 搜索**
```python
from scripts.google_search import GoogleSearchAgent
import asyncio

async def main():
    async with GoogleSearchAgent() as agent:
        results = await agent.search("OpenClaw AI Agent")
        for r in results:
            print(f"{r.title}: {r.url}")

asyncio.run(main())
```

**深度页面分析**
```python
# 使用 Bing 引擎
async with BingSearchAgent() as agent:
    elements = await agent.extract_page_elements("https://example.com")
    print(f"找到 {len(elements.links)} 个链接")

# 使用 Google 引擎
async with GoogleSearchAgent() as agent:
    elements = await agent.extract_page_elements("https://example.com")
    print(f"找到 {len(elements.links)} 个链接")
```

## 📁 结构

```
soushen-hunter/
├── SKILL.md              # Skill 定义文档
├── README.md             # 本文件
├── soushen               # 主入口脚本
├── .soushen_config.json  # 配置文件（自动生成）
└── scripts/
    ├── bing_search.py    # Bing 搜索脚本
    └── google_search.py  # Google 搜索脚本
```

## ⚙️ 配置文件

主入口脚本会在首次运行时自动生成 `.soushen_config.json` 配置文件：

```json
{
  "default_engine": "bing",
  "default_num_results": 10
}
```

- `default_engine`: 默认搜索引擎（`bing` 或 `google`）
- `default_num_results`: 默认返回结果数量

可通过命令修改：
```bash
./soushen --set-default-engine google
./soushen --config  # 查看当前配置
```

## 🔥 为什么叫"搜神猎手"

> 在古代神话中，猎手们追踪猎物于山林之间
> 在信息时代，我们追寻知识于网络之中

**搜神** - 搜寻信息的神奇能力
**猎手** - 精准、迅猛、一击必中

## 🛡️ Google 反检测策略说明

Google 拥有严格的反爬虫机制，本脚本采用以下策略来 bypass 人机检测：

### 核心策略

1. **用户数据目录复用** - 自动检测并使用现有的 Chrome 用户配置，保留 Cookie 和会话
2. **浏览器指纹伪装** - 隐藏 `navigator.webdriver` 等自动化特征
3. **行为模拟** - 随机延迟、鼠标移动模拟真实用户行为
4. **多用户代理轮换** - 随机选择真实的浏览器 User-Agent
5. **地理位置模拟** - 设置合理的时区和地理位置

### 如遇到人机验证

如果仍然遇到"证明你不是机器人"验证，可以尝试：

```bash
# 1. 使用你自己的 Chrome 配置目录
export CHROME_PROFILE_DIR=~/.config/google-chrome
python scripts/google_search.py "关键词"

# 2. 使用有登录状态的 Chrome（已登录 Google 账号）
# 脚本会自动检测并使用现有配置

# 3. 降低搜索频率，添加延迟
# 脚本已内置随机延迟，建议不要高频调用

# 4. 使用 Bing 搜索作为替代方案
python scripts/bing_search.py "关键词"
```

### 最佳实践

- ✅ 首次运行时使用**有头模式**手动通过一次验证，保存 Cookie
- ✅ 复用现有的 Chrome 用户配置（已登录 Google 的更好）
- ✅ 控制搜索频率，建议每分钟不超过 5-10 次
- ✅ 如遇持续验证，切换到 Bing 搜索

## 👤 作者

胤仙（何润培）- 小喵的主人

## 📄 许可

MIT License

---

*由 OpenClaw AI 助手「小喵」协助创建* 🐱
