#!/usr/bin/env python3
"""
Bing Search Agent - 高性能搜索引擎
使用 Playwright 底层 API，最大化过滤有效信息
"""

import asyncio
import json
import sys
import os
import shutil
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from urllib.parse import urljoin, urlparse

try:
    from playwright.async_api import async_playwright, Page, Browser
except ImportError:
    print("ERROR: playwright not installed. Run: pip install playwright")
    sys.exit(1)


def find_chrome_executable() -> Optional[str]:
    """自动查找 Chrome 可执行文件路径"""
    
    # 可能的 Chrome 路径列表
    possible_paths = [
        # 环境变量
        os.environ.get('CHROME_PATH'),
        os.environ.get('CHROME_BIN'),
        # Linux 常见路径
        '/usr/bin/google-chrome',
        '/usr/bin/google-chrome-stable',
        '/usr/bin/chromium',
        '/usr/bin/chromium-browser',
        '/snap/bin/chromium',
        # macOS
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '/Applications/Chromium.app/Contents/MacOS/Chromium',
        # Windows
        r'C:\Program Files\Google\Chrome\Application\chrome.exe',
        r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
        # 用户本地安装
        os.path.expanduser('~/.local/bin/chrome-for-testing-dir/chrome'),
        os.path.expanduser('~/.local/bin/chrome-for-testing/chrome'),
        os.path.expanduser('~/chrome-linux64/chrome'),
    ]
    
    for path in possible_paths:
        if path and os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    
    # 尝试在 PATH 中查找
    chrome_names = ['google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'chrome']
    for name in chrome_names:
        path = shutil.which(name)
        if path:
            return path
    
    return None


@dataclass
class SearchResult:
    """搜索结果数据结构"""
    title: str
    url: str
    snippet: str
    source: str
    result_type: str = "organic"  # organic, ad, news, video, etc.


@dataclass
class PageElements:
    """页面元素提取结果"""
    title: str
    url: str
    text_content: str           # 主要文本内容（清洗后）
    headings: List[Dict]        # 标题结构 h1-h6
    paragraphs: List[str]       # 段落文本
    lists: List[Dict]           # 列表内容
    tables: List[Dict]          # 表格数据
    code_blocks: List[str]      # 代码块
    links: List[Dict[str, str]] # [{text, href, type}]
    forms: List[Dict[str, Any]] # [{action, method, inputs}]
    buttons: List[Dict[str, str]]
    scripts: List[str]
    meta: Dict[str, str]
    cookies: List[Dict]         # Cookie信息


class BingSearchAgent:
    """Bing 搜索代理 - 高性能版本"""
    
    def __init__(self, headless: bool = True, chrome_path: Optional[str] = None):
        self.headless = headless
        self.chrome_path = chrome_path or find_chrome_executable()
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        
    async def __aenter__(self):
        self.playwright = await async_playwright().start()
        
        # 配置启动参数
        launch_options = {
            'headless': self.headless,
            'args': [
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
                '--no-sandbox',
                '--disable-setuid-sandbox',
            ]
        }
        
        # 如果找到 Chrome 路径，使用它
        if self.chrome_path:
            print(f"Using Chrome: {self.chrome_path}")
            launch_options['executable_path'] = self.chrome_path
        else:
            print("Chrome not found, using Playwright bundled Chromium...")
            print("Tip: Install Chrome or set CHROME_PATH environment variable")
        
        self.browser = await self.playwright.chromium.launch(**launch_options)
        context = await self.browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
        )
        self.page = await context.new_page()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()
    
    async def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        """执行 Bing 搜索并返回结构化结果"""
        results = []
        
        try:
            # 访问 Bing
            await self.page.goto('https://www.bing.com', wait_until='domcontentloaded')
            
            # 输入搜索词
            search_box = await self.page.wait_for_selector('[name="q"]')
            await search_box.fill(query)
            await search_box.press('Enter')
            
            # 等待结果加载
            await self.page.wait_for_load_state('networkidle')
            
            # 提取搜索结果 - 使用高性能选择器
            result_selectors = [
                'li.b_algo',  # 主要搜索结果
                '.b_ad li',   # 广告结果
                '.news-card', # 新闻结果
            ]
            
            for selector in result_selectors:
                elements = await self.page.query_selector_all(selector)
                for elem in elements[:num_results]:
                    try:
                        result = await self._extract_result(elem)
                        if result and result.url:
                            results.append(result)
                    except Exception as e:
                        continue
                        
        except Exception as e:
            print(f"Search error: {e}", file=sys.stderr)
            
        return results[:num_results]
    
    async def _extract_result(self, element) -> Optional[SearchResult]:
        """从单个元素提取搜索结果"""
        try:
            # 提取标题
            title_elem = await element.query_selector('h2 a, .b_title a, a')
            if not title_elem:
                return None
                
            title = await title_elem.inner_text()
            url = await title_elem.get_attribute('href')
            
            # 提取摘要
            snippet_elem = await element.query_selector('.b_caption p, .b_snippet, p')
            snippet = await snippet_elem.inner_text() if snippet_elem else ''
            
            # 提取来源
            source_elem = await element.query_selector('.b_attribution cite, cite')
            source = await source_elem.inner_text() if source_elem else urlparse(url).netloc
            
            return SearchResult(
                title=title.strip(),
                url=url,
                snippet=snippet.strip(),
                source=source.strip(),
                result_type='organic'
            )
        except:
            return None
    
    async def extract_page_elements(self, url: str) -> Optional[PageElements]:
        """深度提取页面所有关键元素 - 增强版"""
        try:
            # 增加超时到60秒，网络慢也能加载
            await self.page.goto(url, wait_until='domcontentloaded', timeout=60000)
            await asyncio.sleep(1)  # 等待动态内容渲染
            
            # 提取基础信息
            title = await self.page.title()
            current_url = self.page.url
            
            # 获取 cookies
            cookies = await self.page.context.cookies()
            
            # 智能提取主要文本内容（去除导航、广告等噪音）
            page_data = await self.page.evaluate('''() => {
                // 清理函数：移除隐藏元素和脚本样式
                const cleanText = (el) => {
                    const clone = el.cloneNode(true);
                    // 移除脚本、样式、导航、广告等噪音
                    clone.querySelectorAll('script, style, nav, header, footer, aside, .advertisement, .ads, [class*="ad-"], [class*="banner"]').forEach(e => e.remove());
                    return clone.innerText || '';
                };
                
                // 提取标题结构
                const headings = Array.from(document.querySelectorAll('h1, h2, h3, h4, h5, h6')).map(h => ({
                    level: parseInt(h.tagName[1]),
                    text: h.innerText.trim().substring(0, 200)
                })).filter(h => h.text.length > 0);
                
                // 提取段落（过滤短文本）
                const paragraphs = Array.from(document.querySelectorAll('p, article p, .content p, main p'))
                    .map(p => p.innerText.trim())
                    .filter(t => t.length > 20 && t.length < 500);
                
                // 提取列表
                const lists = Array.from(document.querySelectorAll('ul, ol')).map(list => ({
                    type: list.tagName.toLowerCase(),
                    items: Array.from(list.querySelectorAll('li')).map(li => li.innerText.trim()).filter(t => t.length > 0)
                })).filter(l => l.items.length > 0);
                
                // 提取表格
                const tables = Array.from(document.querySelectorAll('table')).map(table => {
                    const headers = Array.from(table.querySelectorAll('th')).map(th => th.innerText.trim());
                    const rows = Array.from(table.querySelectorAll('tr')).slice(1).map(tr => 
                        Array.from(tr.querySelectorAll('td')).map(td => td.innerText.trim())
                    ).filter(row => row.length > 0);
                    return { headers, rows };
                }).filter(t => t.rows.length > 0);
                
                // 提取代码块
                const codeBlocks = Array.from(document.querySelectorAll('pre, code, .code, .highlight'))
                    .map(c => c.innerText.trim())
                    .filter(t => t.length > 10);
                
                // 提取主要内容区域文本
                const mainContent = document.querySelector('main, article, .content, .post, #content, [role="main"]');
                const bodyText = mainContent ? cleanText(mainContent) : cleanText(document.body);
                
                // 提取所有链接
                const links = Array.from(document.querySelectorAll('a[href]')).map(a => ({
                    text: a.textContent.trim().substring(0, 100),
                    href: a.href,
                    type: a.getAttribute('data-type') || 'link'
                })).filter(l => l.href && !l.href.startsWith('javascript:') && l.text.length > 0);
                
                // 提取表单（增强版）
                const forms = Array.from(document.querySelectorAll('form')).map(form => {
                    const inputs = Array.from(form.querySelectorAll('input, select, textarea')).map(i => ({
                        name: i.name,
                        type: i.type || i.tagName.toLowerCase(),
                        placeholder: i.placeholder || '',
                        required: i.required,
                        value: i.value || ''
                    }));
                    return {
                        action: form.action,
                        method: form.method || 'GET',
                        name: form.name || form.id || '',
                        inputs: inputs
                    };
                });
                
                // 提取按钮
                const buttons = Array.from(document.querySelectorAll('button, input[type="submit"], input[type="button"], .btn, [role="button"]')).map(b => ({
                    text: (b.textContent || b.value || '').trim().substring(0, 50),
                    type: b.type || 'button',
                    id: b.id || '',
                    action: b.getAttribute('onclick') || b.getAttribute('data-action') || ''
                })).filter(b => b.text.length > 0);
                
                // 提取外部脚本
                const scripts = Array.from(document.querySelectorAll('script[src]')).map(s => s.src);
                
                // 提取元数据
                const meta = {};
                document.querySelectorAll('meta[name], meta[property]').forEach(m => {
                    const key = m.getAttribute('name') || m.getAttribute('property');
                    if (key) meta[key] = m.content;
                });
                
                return {
                    text_content: bodyText.substring(0, 5000), // 限制长度
                    headings: headings.slice(0, 20),
                    paragraphs: paragraphs.slice(0, 30),
                    lists: lists.slice(0, 10),
                    tables: tables.slice(0, 5),
                    code_blocks: codeBlocks.slice(0, 10),
                    links: links.slice(0, 50),
                    forms: forms,
                    buttons: buttons.slice(0, 30),
                    scripts: scripts.slice(0, 20),
                    meta: meta
                };
            }''')
            
            return PageElements(
                title=title,
                url=current_url,
                text_content=page_data.get('text_content', ''),
                headings=page_data.get('headings', []),
                paragraphs=page_data.get('paragraphs', []),
                lists=page_data.get('lists', []),
                tables=page_data.get('tables', []),
                code_blocks=page_data.get('code_blocks', []),
                links=page_data.get('links', []),
                forms=page_data.get('forms', []),
                buttons=page_data.get('buttons', []),
                scripts=page_data.get('scripts', []),
                meta=page_data.get('meta', {}),
                cookies=cookies
            )
            
        except Exception as e:
            print(f"Extraction error: {e}", file=sys.stderr)
            return None


def format_output(results: List[SearchResult]) -> str:
    """格式化输出为简洁文本"""
    lines = []
    lines.append("╔══════════════════════════════════════╗")
    lines.append("║     🔍 搜神猎手 (SouShen Hunter)      ║")
    lines.append("╚══════════════════════════════════════╝")
    lines.append(f"\n🎯 找到 {len(results)} 条结果\n")
    
    for i, r in enumerate(results, 1):
        lines.append(f"[{i}] {r.title}")
        lines.append(f"    📄 {r.snippet[:150]}..." if len(r.snippet) > 150 else f"    📄 {r.snippet}")
        lines.append(f"    🔗 {r.url}")
        lines.append(f"    🏢 {r.source}\n")
    
    return '\n'.join(lines)


def format_page_elements(elements: PageElements) -> str:
    """格式化页面元素输出 - 增强版"""
    lines = []
    lines.append("╔══════════════════════════════════════╗")
    lines.append("║     🔍 搜神猎手 (SouShen Hunter)      ║")
    lines.append("║      深度页面分析报告                ║")
    lines.append("╚══════════════════════════════════════╝")
    lines.append(f"\n📄 页面: {elements.title}")
    lines.append(f"🔗 URL: {elements.url}\n")
    
    # Cookie信息
    if elements.cookies:
        lines.append(f"🍪 Cookies ({len(elements.cookies)} 个):")
        for c in elements.cookies[:5]:
            lines.append(f"   • {c.get('name', '')}: {c.get('value', '')[:50]}...")
        if len(elements.cookies) > 5:
            lines.append(f"   ... 还有 {len(elements.cookies) - 5} 个")
        lines.append("")
    
    # 主要内容文本
    if elements.text_content:
        lines.append("📝 主要内容:")
        text = elements.text_content[:800].replace('\n', ' ')
        lines.append(f"   {text}...")
        lines.append("")
    
    # 标题结构
    if elements.headings:
        lines.append(f"📌 标题结构 ({len(elements.headings)} 个):")
        for h in elements.headings[:10]:
            indent = "  " * (h['level'] - 1)
            lines.append(f"   {indent}{'#' * h['level']} {h['text'][:60]}")
        lines.append("")
    
    # 段落
    if elements.paragraphs:
        lines.append(f"📃 关键段落 ({len(elements.paragraphs)} 个):")
        for p in elements.paragraphs[:3]:
            lines.append(f"   • {p[:100]}...")
        lines.append("")
    
    # 列表
    if elements.lists:
        lines.append(f"📋 列表 ({len(elements.lists)} 个):")
        for lst in elements.lists[:2]:
            lines.append(f"   {lst['type'].upper()} ({lst['items']} 项)")
        lines.append("")
    
    # 代码块
    if elements.code_blocks:
        lines.append(f"💻 代码块 ({len(elements.code_blocks)} 个):")
        for code in elements.code_blocks[:2]:
            preview = code[:80].replace('\n', ' ')
            lines.append(f"   ```{preview}...```")
        lines.append("")
    
    # 表单（Pentest重点）
    if elements.forms:
        lines.append(f"🎯 表单 ({len(elements.forms)} 个) - Pentest重点:")
        for form in elements.forms:
            lines.append(f"   • Form: {form.get('name', 'unnamed')}")
            lines.append(f"     Action: {form['action']}")
            lines.append(f"     Method: {form['method']}")
            lines.append(f"     字段:")
            for inp in form['inputs']:
                req = " [必填]" if inp.get('required') else ""
                ph = f" placeholder='{inp.get('placeholder', '')}'" if inp.get('placeholder') else ""
                lines.append(f"       - {inp['name']} ({inp['type']}){req}{ph}")
        lines.append("")
    
    # API端点/链接
    if elements.links:
        api_links = [l for l in elements.links if '/api/' in l['href'] or 'graphql' in l['href']]
        lines.append(f"⛓️  链接 ({len(elements.links)} 个):")
        if api_links:
            lines.append(f"   🔥 API端点发现 ({len(api_links)} 个):")
            for link in api_links[:5]:
                lines.append(f"      • {link['text'][:30]} → {link['href'][:60]}")
        for link in elements.links[:5]:
            if link not in api_links:
                lines.append(f"   • {link['text'][:30]} → {link['href'][:60]}")
        lines.append("")
    
    # 按钮
    if elements.buttons:
        lines.append(f"🔘 交互按钮 ({len(elements.buttons)} 个):")
        for btn in elements.buttons[:5]:
            action = f" [{btn.get('action', '')[:30]}]" if btn.get('action') else ""
            lines.append(f"   • {btn['text']}{action}")
        lines.append("")
    
    # 元数据
    if elements.meta:
        important = ['description', 'keywords', 'author', 'csrf-token', 'csrf_token']
        found = {k: v for k, v in elements.meta.items() if any(i in k.lower() for i in important)}
        if found:
            lines.append("🏷️  关键Meta:")
            for k, v in list(found.items())[:5]:
                lines.append(f"   • {k}: {v[:80]}")
            lines.append("")
    
    return '\n'.join(lines)


def parse_args():
    """解析命令行参数"""
    args = sys.argv[1:]
    
    # 检查是否是深度分析模式
    if '--deep' in args:
        deep_idx = args.index('--deep')
        if deep_idx + 1 >= len(args):
            print("Error: --deep requires a URL argument")
            print("Usage: python bing_search.py --deep <url>")
            sys.exit(1)
        return {
            'mode': 'deep',
            'url': args[deep_idx + 1],
            'query': None
        }
    
    # 普通搜索模式
    if len(args) < 1:
        return None
    
    return {
        'mode': 'search',
        'query': args[0],
        'url': None
    }


async def main():
    """主函数 - CLI 入口"""
    parsed = parse_args()
    
    if parsed is None:
        print("Usage:")
        print("  python bing_search.py <query>           # Bing 搜索")
        print("  python bing_search.py --deep <url>      # 深度页面分析")
        print("\nExamples:")
        print('  python bing_search.py "OpenClaw AI"')
        print('  python bing_search.py --deep https://example.com')
        print("\nEnvironment variables:")
        print("  CHROME_PATH    Path to Chrome executable (optional)")
        sys.exit(1)
    
    # 支持通过环境变量指定 Chrome 路径
    chrome_path = os.environ.get('CHROME_PATH') or os.environ.get('CHROME_BIN')
    
    async with BingSearchAgent(headless=True, chrome_path=chrome_path) as agent:
        if parsed['mode'] == 'deep':
            # 深度分析模式 - 全面自动化提取
            url = parsed['url']
            print("╔══════════════════════════════════════╗")
            print("║     🔍 搜神猎手 (SouShen Hunter)      ║")
            print("║      正在执行深度页面分析...          ║")
            print("╚══════════════════════════════════════╝")
            print(f"\n🎯 目标: {url}\n")
            elements = await agent.extract_page_elements(url)
            if elements:
                print(format_page_elements(elements))
            else:
                print("❌ 页面分析失败")
        else:
            # 搜索模式
            results = await agent.search(parsed['query'], num_results=10)
            print(format_output(results))
            
            # 同时输出 JSON 格式供程序使用
            print("\n---JSON---")
            print(json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    asyncio.run(main())
