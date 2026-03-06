#!/usr/bin/env python3
"""
搜神猎手 (SouShen Hunter) - Google 搜索引擎
使用 Playwright 底层 API + 高级反检测策略

注意：Google 有严格的反爬虫机制，本脚本仅供学习研究使用
"""

import asyncio
import json
import sys
import os
import shutil
import random
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from urllib.parse import urljoin, urlparse, quote

try:
    from playwright.async_api import async_playwright, Page, Browser, BrowserContext
except ImportError:
    print(json.dumps({"error": "playwright not installed. Run: pip install playwright"}, ensure_ascii=False))
    sys.exit(1)


def find_chrome_executable() -> Optional[str]:
    """自动查找 Chrome 可执行文件路径"""
    possible_paths = [
        os.environ.get('CHROME_PATH'),
        os.environ.get('CHROME_BIN'),
        '/root/ezisall/chrome-linux64/chrome',
        '/usr/bin/google-chrome',
        '/usr/bin/google-chrome-stable',
        '/usr/bin/chromium',
        '/usr/bin/chromium-browser',
        '/snap/bin/chromium',
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '/Applications/Chromium.app/Contents/MacOS/Chromium',
        r'C:\Program Files\Google\Chrome\Application\chrome.exe',
        r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
        os.path.expanduser('~/.local/bin/chrome-for-testing-dir/chrome'),
        os.path.expanduser('~/.local/bin/chrome-for-testing/chrome'),
        os.path.expanduser('~/chrome-linux64/chrome'),
    ]

    for path in possible_paths:
        if path and os.path.isfile(path) and os.access(path, os.X_OK):
            return path

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
    result_type: str = "organic"


@dataclass
class PageElements:
    """页面元素提取结果"""
    title: str
    url: str
    text_content: str
    headings: List[Dict]
    paragraphs: List[str]
    lists: List[Dict]
    tables: List[Dict]
    code_blocks: List[str]
    links: List[Dict[str, str]]
    forms: List[Dict[str, Any]]
    buttons: List[Dict[str, str]]
    scripts: List[str]
    meta: Dict[str, str]
    cookies: List[Dict]


class GoogleSearchAgent:
    """Google 搜索代理 - 高级反检测版本"""

    # 更真实的用户代理列表
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    ]

    # 常见的用户数据目录路径
    CHROME_PROFILES = [
        os.path.expanduser('~/.config/google-chrome'),
        os.path.expanduser('~/.config/chromium'),
        os.path.expanduser('~/Library/Application Support/Google/Chrome'),
        os.path.expanduser('~/.config/google-chrome-beta'),
        os.path.expanduser('~/.config/google-chrome-unstable'),
    ]

    def __init__(
        self,
        headless: bool = True,
        chrome_path: Optional[str] = None,
        use_profile: bool = True,
        lang: str = 'zh-CN'
    ):
        self.headless = headless
        self.chrome_path = chrome_path or find_chrome_executable()
        self.use_profile = use_profile
        self.lang = lang
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.context: Optional[BrowserContext] = None

    async def __aenter__(self):
        self.playwright = await async_playwright().start()

        # 选择随机用户代理
        user_agent = random.choice(self.USER_AGENTS)

        # 查找现有的 Chrome 用户数据目录
        user_data_dir = None
        if self.use_profile:
            for profile_path in self.CHROME_PROFILES:
                if os.path.exists(profile_path):
                    user_data_dir = profile_path
                    break

        # 如果没有现有配置，使用临时目录
        if not user_data_dir:
            user_data_dir = os.path.expanduser('~/.config/soushen-hunter-chrome-profile')
            os.makedirs(user_data_dir, exist_ok=True)

        # 浏览器启动参数 - 关键的反检测配置
        launch_args = [
            '--disable-blink-features=AutomationControlled',
            '--disable-features=IsolateOrigins,site-per-process',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu',
            '--disable-software-rasterizer',
            '--disable-extensions',
            '--disable-background-networking',
            '--disable-default-apps',
            '--disable-sync',
            '--disable-translate',
            '--metrics-recording-only',
            '--mute-audio',
            '--no-first-run',
            '--safebrowsing-disable-auto-update',
            '--disable-features=TranslateUI',
            '--disable-ipc-flooding-protection',
            '--disable-client-side-phishing-detection',
            '--disable-hang-monitor',
            '--disable-prompt-on-repost',
            '--force-color-profile=srgb',
            '--use-mock-keychain',
            '--disable-background-timer-throttling',
            '--disable-backgrounding-occluded-windows',
            '--disable-renderer-background',
            '--disable-logging',
            '--log-level=3',
            f'--lang={self.lang}',
        ]

        launch_options = {
            'headless': self.headless,
            'args': launch_args
        }

        if self.chrome_path:
            launch_options['executable_path'] = self.chrome_path

        # 使用 launch_persistent_context 来处理用户数据目录
        persistent_context_options = {
            'user_data_dir': user_data_dir,
            'user_agent': user_agent,
            'viewport': {'width': 1920, 'height': 1080},
            'locale': self.lang,
            'timezone_id': 'Asia/Shanghai',
            'permissions': ['geolocation'],
            'geolocation': {'latitude': 31.2304, 'longitude': 121.4737},  # 上海
            'color_scheme': 'light',
            'extra_http_headers': {
                'Accept-Language': f'{self.lang},{self.lang.split("-")[0]};q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            },
            'args': launch_args,
        }

        if self.chrome_path:
            persistent_context_options['executable_path'] = self.chrome_path

        # 使用持久化上下文启动浏览器
        self.context = await self.playwright.chromium.launch_persistent_context(
            **persistent_context_options
        )
        self.browser = self.context  # 持久化上下文既是浏览器也是上下文
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()

        # 注入 JavaScript 来隐藏自动化特征
        await self.page.add_init_script('''
            // 隐藏 webdriver 属性
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });

            // 隐藏 automation 属性
            Object.defineProperty(navigator, 'automation', {
                get: () => undefined
            });

            // 模拟真实的 plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });

            // 模拟真实的 languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['zh-CN', 'zh', 'en']
            });

            // 覆盖 permissions API
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        ''')

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self, 'context'):
            await self.context.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()

    async def _human_like_delay(self, min_ms: int = 1000, max_ms: int = 3000):
        """模拟真实用户的延迟"""
        delay = random.uniform(min_ms, max_ms) / 1000
        await asyncio.sleep(delay)

    async def _simulate_mouse_movement(self):
        """模拟鼠标移动"""
        try:
            # 随机移动几次鼠标
            for _ in range(random.randint(2, 5)):
                x = random.randint(100, 800)
                y = random.randint(100, 600)
                await self.page.mouse.move(x, y)
                await asyncio.sleep(random.uniform(0.1, 0.3))
        except:
            pass

    async def _check_captcha(self) -> bool:
        """检查是否遇到人机验证"""
        try:
            # 检测各种人机验证的特征
            captcha_indicators = [
                'div[g-recaptcha]',
                'iframe[src*="recaptcha"]',
                'div[class*="recaptcha"]',
                'title:has-text("机器人")',
                'title:has-text("CAPTCHA")',
                'title:has-text("unusual traffic")',
                'text="证明你不是机器人"',
                'text="Verify you are human"',
                'text="unusual traffic from your network"',
            ]

            for selector in captcha_indicators:
                try:
                    elem = await self.page.wait_for_selector(selector, timeout=2000)
                    if elem:
                        return True
                except:
                    continue

            # 检查 URL 是否包含验证相关参数
            current_url = self.page.url
            if 'captcha' in current_url.lower() or 'verify' in current_url.lower():
                return True

            return False
        except:
            return False

    async def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        """执行 Google 搜索并返回结构化结果"""
        results = []

        try:
            # 构造搜索 URL
            encoded_query = quote(query)
            search_url = f'https://www.google.com/search?q={encoded_query}&num={num_results}'

            # 直接访问搜索页面
            await self.page.goto(search_url, wait_until='domcontentloaded', timeout=60000)

            # 等待页面加载
            await asyncio.sleep(2)

            # 检查是否遇到人机验证
            is_captcha = await self._check_captcha()
            if is_captcha:
                print(json.dumps({
                    "warning": "检测到人机验证，可能需要手动处理",
                    "url": self.page.url,
                    "tip": "尝试使用有 Cookie 的 Chrome 用户数据目录，或降低搜索频率"
                }, ensure_ascii=False), file=sys.stderr)
                return results

            # 等待搜索结果加载
            try:
                await self.page.wait_for_selector('#search, #rso', timeout=5000)
            except:
                pass

            await self._human_like_delay(300, 800)

            # 提取搜索结果 - 使用多种选择器（适配 Google 新布局）
            result_selectors = [
                '#rso > div.MjjYud',  # 主要搜索结果容器（新布局）
                '#rso > div.ULSxyf',  # 另一种格式
                'div.g',  # 传统布局
            ]

            for selector in result_selectors:
                if len(results) >= num_results:
                    break
                elements = await self.page.query_selector_all(selector)
                for elem in elements:
                    try:
                        result = await self._extract_result(elem)
                        if result and result.url:
                            # 过滤掉 Google 内部链接
                            if 'google.com' not in result.url or '/search' not in result.url:
                                if result not in results:
                                    results.append(result)
                    except Exception:
                        continue

            # 如果结果不够，尝试其他选择器
            if len(results) < num_results:
                more_elements = await self.page.query_selector_all('#rso a[href^="http"], #search a[href^="http"]')
                
                # 提取链接
                seen_urls = set()
                for elem in more_elements[:50]:
                    try:
                        href = await elem.get_attribute('href')
                        if href and href not in seen_urls:
                            seen_urls.add(href)
                            # 过滤 Google 内部链接和非 http 链接
                            if ('google.com' not in href or '/search' not in href):
                                if href.startswith('http://') or href.startswith('https://'):
                                    result = await self._extract_result_v2(elem, href)
                                    if result and result.url:
                                        if result not in results:
                                            results.append(result)
                    except Exception:
                        continue

        except Exception:
            pass

        return results[:num_results]

    async def _extract_result(self, element) -> Optional[SearchResult]:
        """从单个元素提取搜索结果"""
        try:
            # 找标题链接 - 尝试多种选择器
            title_elem = None
            title_selectors = [
                'a[href^="http"]',  # 直接找外部链接
                'a[href]',  # 任何链接
                'h3 a',  # h3 标题下的链接
                '.vvjwJb a',  # 新布局标题
            ]
            for selector in title_selectors:
                title_elem = await element.query_selector(selector)
                if title_elem:
                    break

            if not title_elem:
                return None

            title = await title_elem.inner_text()
            url = await title_elem.get_attribute('href')

            # 清理 URL（Google 会包装链接）
            if url and url.startswith('/url?q='):
                url = url.split('/url?q=')[1].split('&')[0]
            elif url and url.startswith('http://www.google.com/url?q='):
                from urllib.parse import parse_qs
                parsed = urlparse(url)
                params = parse_qs(parsed.query)
                if 'q' in params:
                    url = params['q'][0]

            if not title or not title.strip():
                return None

            if not url or url.startswith('javascript:'):
                return None

            # 过滤 Google 内部链接
            if 'google.com' in url and '/search' in url:
                return None

            # 找摘要 - 尝试多种选择器
            snippet = ''
            snippet_selectors = [
                'div.VwiC3b',
                'div.lEBKkf',
                'span.aCOpRe',
                '.r025kc',
                '.ISHxd',
                '[data-sncf="1"]',
            ]
            for selector in snippet_selectors:
                snippet_elem = await element.query_selector(selector)
                if snippet_elem:
                    snippet = await snippet_elem.inner_text()
                    if snippet and len(snippet) > 20:
                        break

            # 找来源
            source = ''
            source_selectors = [
                'div.yT8vJ',
                'cite',
                '.fYyStc',
                '.dTeQhe',
                '.B6fQ8c',
            ]
            for selector in source_selectors:
                source_elem = await element.query_selector(selector)
                if source_elem:
                    source = await source_elem.inner_text()
                    if source:
                        break

            return SearchResult(
                title=title.strip(),
                url=url.strip(),
                snippet=snippet.strip()[:500] if snippet else '',
                source=source.strip()[:100] if source else urlparse(url).netloc,
                result_type='organic'
            )
        except Exception as e:
            return None

    async def _extract_result_v2(self, link_elem, href: str = None) -> Optional[SearchResult]:
        """从链接元素提取结果（备用方法）"""
        try:
            url = href or await link_elem.get_attribute('href')
            if not url:
                return None

            # 清理 URL
            if url.startswith('/url?q='):
                url = url.split('/url?q=')[1].split('&')[0]
            elif 'google.com/url?q=' in url:
                from urllib.parse import parse_qs, urlparse
                parsed = urlparse(url)
                params = parse_qs(parsed.query)
                if 'q' in params:
                    url = params['q'][0]

            # 过滤 Google 内部链接
            if 'google.com' in url and '/search' in url:
                return None

            # 获取标题文本
            title = await link_elem.inner_text()
            if not title or not title.strip():
                # 尝试从父元素或兄弟元素找标题
                parent = await link_elem.evaluate('el => el.parentElement')
                if parent:
                    # 尝试找 h3 标题
                    h3_elem = await link_elem.evaluate_handle('el => el.querySelector("h3") || el.parentElement.querySelector("h3")')
                    if h3_elem:
                        title = await link_elem.inner_text()

            if not title or not title.strip():
                title = url[:100]  # 使用 URL 作为备用标题

            return SearchResult(
                title=title.strip()[:200],
                url=url.strip(),
                snippet='',
                source=urlparse(url).netloc,
                result_type='organic'
            )
        except Exception as e:
            return None

    async def extract_page_elements(self, url: str) -> Optional[PageElements]:
        """深度提取页面所有关键元素"""
        try:
            await self.page.goto(url, wait_until='domcontentloaded', timeout=60000)
            await asyncio.sleep(1)

            title = await self.page.title()
            current_url = self.page.url
            cookies = await self.context.cookies()

            page_data = await self.page.evaluate('''() => {
                const cleanText = (el) => {
                    const clone = el.cloneNode(true);
                    clone.querySelectorAll('script, style, nav, header, footer, aside, .advertisement, .ads, [class*="ad-"], [class*="banner"]').forEach(e => e.remove());
                    return clone.innerText || '';
                };

                const headings = Array.from(document.querySelectorAll('h1, h2, h3, h4, h5, h6')).map(h => ({
                    level: parseInt(h.tagName[1]),
                    text: h.innerText.trim()
                })).filter(h => h.text.length > 0);

                const paragraphs = Array.from(document.querySelectorAll('p, article p, .content p, main p'))
                    .map(p => p.innerText.trim())
                    .filter(t => t.length > 20);

                const lists = Array.from(document.querySelectorAll('ul, ol')).map(list => ({
                    type: list.tagName.toLowerCase(),
                    items: Array.from(list.querySelectorAll('li')).map(li => li.innerText.trim()).filter(t => t.length > 0)
                })).filter(l => l.items.length > 0);

                const tables = Array.from(document.querySelectorAll('table')).map(table => {
                    const headers = Array.from(table.querySelectorAll('th')).map(th => th.innerText.trim());
                    const rows = Array.from(table.querySelectorAll('tr')).slice(1).map(tr =>
                        Array.from(tr.querySelectorAll('td')).map(td => td.innerText.trim())
                    ).filter(row => row.length > 0);
                    return { headers, rows };
                }).filter(t => t.rows.length > 0);

                const codeBlocks = Array.from(document.querySelectorAll('pre, code, .code, .highlight'))
                    .map(c => c.innerText.trim())
                    .filter(t => t.length > 10);

                const mainContent = document.querySelector('main, article, .content, .post, #content, [role="main"]');
                const bodyText = mainContent ? cleanText(mainContent) : cleanText(document.body);

                const links = Array.from(document.querySelectorAll('a[href]')).map(a => ({
                    text: a.textContent.trim(),
                    href: a.href,
                    type: a.getAttribute('data-type') || 'link'
                })).filter(l => l.href && !l.href.startsWith('javascript:') && l.text.length > 0);

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

                const buttons = Array.from(document.querySelectorAll('button, input[type="submit"], input[type="button"], .btn, [role="button"]')).map(b => ({
                    text: (b.textContent || b.value || '').trim(),
                    type: b.type || 'button',
                    id: b.id || '',
                    action: b.getAttribute('onclick') || b.getAttribute('data-action') || ''
                })).filter(b => b.text.length > 0);

                const scripts = Array.from(document.querySelectorAll('script[src]')).map(s => s.src);

                const meta = {};
                document.querySelectorAll('meta[name], meta[property]').forEach(m => {
                    const key = m.getAttribute('name') || m.getAttribute('property');
                    if (key) meta[key] = m.content;
                });

                return {
                    text_content: bodyText,
                    headings: headings,
                    paragraphs: paragraphs,
                    lists: lists,
                    tables: tables,
                    code_blocks: codeBlocks,
                    links: links,
                    forms: forms,
                    buttons: buttons,
                    scripts: scripts,
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
            return None


def format_output(results: List[SearchResult]) -> str:
    """格式化输出为 JSON"""
    return json.dumps({
        "tool": "soushen-hunter",
        "mode": "google_search",
        "total": len(results),
        "results": [asdict(r) for r in results]
    }, ensure_ascii=False, indent=2)


def format_page_elements(elements: PageElements, text_offset: int = 0, text_limit: int = 10000) -> str:
    """格式化页面元素输出为 JSON"""
    full_text = elements.text_content or ""
    text_total = len(full_text)
    text_slice = full_text[text_offset:text_offset + text_limit]
    has_more_text = (text_offset + text_limit) < text_total

    result = {
        "tool": "soushen-hunter",
        "mode": "deep",
        "page": {
            "title": elements.title,
            "url": elements.url
        },
        "text_content": {
            "content": text_slice,
            "offset": text_offset,
            "length": len(text_slice),
            "total_length": text_total,
            "has_more": has_more_text,
            "next_offset": text_offset + text_limit if has_more_text else None
        },
        "cookies": elements.cookies,
        "headings": elements.headings,
        "paragraphs": elements.paragraphs,
        "lists": elements.lists,
        "tables": elements.tables,
        "code_blocks": elements.code_blocks,
        "forms": elements.forms,
        "links": {
            "total": len(elements.links),
            "items": elements.links
        },
        "buttons": {
            "total": len(elements.buttons),
            "items": elements.buttons
        },
        "scripts": elements.scripts,
        "meta": elements.meta
    }

    return json.dumps(result, ensure_ascii=False, indent=2)


def parse_args():
    """解析命令行参数"""
    args = sys.argv[1:]
    result = {
        'mode': None,
        'query': None,
        'url': None,
        'text_offset': 0,
        'text_limit': 10000,
        'num_results': 10
    }

    if '--num' in args:
        idx = args.index('--num')
        if idx + 1 < len(args):
            try:
                result['num_results'] = int(args[idx + 1])
                args.pop(idx + 1)
                args.pop(idx)
            except ValueError:
                pass

    if '--text-offset' in args:
        idx = args.index('--text-offset')
        if idx + 1 < len(args):
            try:
                result['text_offset'] = int(args[idx + 1])
                args.pop(idx + 1)
                args.pop(idx)
            except ValueError:
                pass

    if '--text-limit' in args:
        idx = args.index('--text-limit')
        if idx + 1 < len(args):
            try:
                result['text_limit'] = int(args[idx + 1])
                args.pop(idx + 1)
                args.pop(idx)
            except ValueError:
                pass

    if '--deep' in args:
        deep_idx = args.index('--deep')
        if deep_idx + 1 >= len(args):
            print(json.dumps({"error": "--deep requires a URL argument"}, ensure_ascii=False))
            sys.exit(1)
        result['mode'] = 'deep'
        result['url'] = args[deep_idx + 1]
        return result

    if len(args) < 1:
        return None

    result['mode'] = 'google'
    result['query'] = args[0]
    return result


async def main():
    """主函数 - CLI 入口"""
    parsed = parse_args()

    if parsed is None:
        help_text = {
            "tool": "soushen-hunter-google",
            "usage": {
                "search": "python google_search.py <query>",
                "deep": "python google_search.py --deep <url> [--text-offset N] [--text-limit N]"
            },
            "options": {
                "--text-offset": "文本起始位置 (默认 0)",
                "--text-limit": "文本长度限制 (默认 10000)"
            },
            "examples": [
                "python google_search.py 'OpenClaw AI'",
                "python google_search.py --deep https://example.com",
                "python google_search.py --deep https://example.com --text-limit 50000",
                "python google_search.py --deep https://example.com --text-offset 10000 --text-limit 10000"
            ],
            "env": {
                "CHROME_PATH": "Chrome 可执行文件路径 (可选)",
                "CHROME_BIN": "Chrome 可执行文件路径 (可选)"
            },
            "tips": [
                "Google 有严格的反爬虫机制，如遇到人机验证:",
                "1. 使用真实的 Chrome 用户数据目录（自动检测）",
                "2. 降低搜索频率，添加延迟",
                "3. 使用有登录 Cookie 的浏览器配置",
                "4. 考虑使用 Bing 搜索作为替代"
            ]
        }
        print(json.dumps(help_text, ensure_ascii=False, indent=2))
        sys.exit(1)

    chrome_path = os.environ.get('CHROME_PATH') or os.environ.get('CHROME_BIN')

    async with GoogleSearchAgent(headless=True, chrome_path=chrome_path) as agent:
        if parsed['mode'] == 'deep':
            url = parsed['url']
            text_offset = parsed.get('text_offset', 0)
            text_limit = parsed.get('text_limit', 10000)
            elements = await agent.extract_page_elements(url)
            if elements:
                print(format_page_elements(elements, text_offset=text_offset, text_limit=text_limit))
            else:
                print(json.dumps({"error": "页面分析失败"}, ensure_ascii=False))
        else:
            results = await agent.search(parsed['query'], num_results=parsed['num_results'])
            print(format_output(results))


if __name__ == '__main__':
    asyncio.run(main())
