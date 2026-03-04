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
    links: List[Dict[str, str]]  # [{text, href, type}]
    forms: List[Dict[str, Any]]   # [{action, method, inputs}]
    buttons: List[Dict[str, str]] # [{text, type, action}]
    scripts: List[str]            # 外部 JS 文件 URL
    meta: Dict[str, str]          # 元数据


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
        """深度提取页面所有关键元素"""
        try:
            await self.page.goto(url, wait_until='domcontentloaded')
            await asyncio.sleep(0.5)  # 短暂等待动态内容
            
            # 提取基础信息
            title = await self.page.title()
            current_url = self.page.url
            
            # 提取所有链接
            links = await self.page.evaluate('''() => {
                return Array.from(document.querySelectorAll('a[href]')).map(a => ({
                    text: a.textContent.trim().substring(0, 100),
                    href: a.href,
                    type: a.getAttribute('data-type') || 'link'
                })).filter(l => l.href && !l.href.startsWith('javascript:'));
            }''')
            
            # 提取表单
            forms = await self.page.evaluate('''() => {
                return Array.from(document.querySelectorAll('form')).map(form => ({
                    action: form.action,
                    method: form.method || 'GET',
                    inputs: Array.from(form.querySelectorAll('input, select, textarea')).map(i => ({
                        name: i.name,
                        type: i.type || i.tagName.toLowerCase(),
                        required: i.required
                    }))
                }));
            }''')
            
            # 提取按钮
            buttons = await self.page.evaluate('''() => {
                return Array.from(document.querySelectorAll('button, input[type="submit"], input[type="button"], .btn, [role="button"]')).map(b => ({
                    text: (b.textContent || b.value || '').trim().substring(0, 50),
                    type: b.type || 'button',
                    action: b.getAttribute('onclick') || b.getAttribute('data-action') || ''
                }));
            }''')
            
            # 提取外部脚本
            scripts = await self.page.evaluate('''() => {
                return Array.from(document.querySelectorAll('script[src]')).map(s => s.src);
            }''')
            
            # 提取元数据
            meta = await self.page.evaluate('''() => {
                const meta = {};
                document.querySelectorAll('meta[name], meta[property]').forEach(m => {
                    const key = m.getAttribute('name') || m.getAttribute('property');
                    if (key) meta[key] = m.content;
                });
                return meta;
            }''')
            
            return PageElements(
                title=title,
                url=current_url,
                links=links[:50],  # 限制数量
                forms=forms,
                buttons=buttons[:30],
                scripts=scripts[:20],
                meta=meta
            )
            
        except Exception as e:
            print(f"Extraction error: {e}", file=sys.stderr)
            return None


def format_output(results: List[SearchResult]) -> str:
    """格式化输出为简洁文本"""
    lines = []
    lines.append(f"🔍 找到 {len(results)} 条结果\n")
    
    for i, r in enumerate(results, 1):
        lines.append(f"[{i}] {r.title}")
        lines.append(f"    📄 {r.snippet[:150]}..." if len(r.snippet) > 150 else f"    📄 {r.snippet}")
        lines.append(f"    🔗 {r.url}")
        lines.append(f"    🏢 {r.source}\n")
    
    return '\n'.join(lines)


def format_page_elements(elements: PageElements) -> str:
    """格式化页面元素输出"""
    lines = []
    lines.append(f"📄 页面: {elements.title}")
    lines.append(f"🔗 URL: {elements.url}\n")
    
    lines.append(f"⛓️  链接 ({len(elements.links)} 个):")
    for link in elements.links[:10]:
        lines.append(f"   • {link['text'][:40]} → {link['href'][:80]}")
    if len(elements.links) > 10:
        lines.append(f"   ... 还有 {len(elements.links) - 10} 个链接\n")
    
    if elements.forms:
        lines.append(f"\n📝 表单 ({len(elements.forms)} 个):")
        for form in elements.forms:
            lines.append(f"   • Action: {form['action']}, Method: {form['method']}")
            lines.append(f"     Inputs: {len(form['inputs'])} 个字段")
    
    if elements.buttons:
        lines.append(f"\n🔘 按钮 ({len(elements.buttons)} 个):")
        for btn in elements.buttons[:5]:
            lines.append(f"   • {btn['text']}")
    
    if elements.scripts:
        lines.append(f"\n📜 外部脚本 ({len(elements.scripts)} 个):")
        for script in elements.scripts[:5]:
            lines.append(f"   • {script}")
    
    return '\n'.join(lines)


async def main():
    """主函数 - CLI 入口"""
    if len(sys.argv) < 2:
        print("Usage: python bing_search.py <query> [--deep <url>]")
        print("\nEnvironment variables:")
        print("  CHROME_PATH    Path to Chrome executable (optional)")
        sys.exit(1)
    
    query = sys.argv[1]
    deep_mode = '--deep' in sys.argv
    deep_url = sys.argv[sys.argv.index('--deep') + 1] if deep_mode else None
    
    # 支持通过环境变量指定 Chrome 路径
    chrome_path = os.environ.get('CHROME_PATH') or os.environ.get('CHROME_BIN')
    
    async with BingSearchAgent(headless=True, chrome_path=chrome_path) as agent:
        if deep_url:
            # 深度分析模式
            elements = await agent.extract_page_elements(deep_url)
            if elements:
                print(format_page_elements(elements))
            else:
                print("Failed to extract page elements")
        else:
            # 搜索模式
            results = await agent.search(query, num_results=10)
            print(format_output(results))
            
            # 同时输出 JSON 格式供程序使用
            print("\n---JSON---")
            print(json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    asyncio.run(main())
