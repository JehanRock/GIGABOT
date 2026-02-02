"""
Browser automation tool for GigaBot.

Provides web browser control for:
- Page navigation
- Element interaction
- Screenshot capture
- Form submission
"""

import asyncio
import base64
from typing import Any

from nanobot.agent.tools.base import BaseTool

try:
    from playwright.async_api import async_playwright, Browser, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


class BrowserTool(BaseTool):
    """
    Browser automation tool using Playwright.
    
    Supports:
    - navigate: Go to a URL
    - click: Click an element
    - type: Type into an element
    - screenshot: Take a screenshot
    - evaluate: Execute JavaScript
    - get_content: Get page content
    """
    
    name = "browser"
    description = """Browser automation for web interaction.
    
Actions:
- navigate: Go to a URL
- click: Click an element by selector
- type: Type text into an element
- screenshot: Take a screenshot
- evaluate: Execute JavaScript
- get_content: Get page text content
- close: Close the browser

Examples:
- Navigate: {"action": "navigate", "url": "https://example.com"}
- Click: {"action": "click", "selector": "button.submit"}
- Type: {"action": "type", "selector": "input#search", "text": "hello"}
- Screenshot: {"action": "screenshot"}
"""
    
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["navigate", "click", "type", "screenshot", "evaluate", "get_content", "close"],
                "description": "The browser action to perform"
            },
            "url": {
                "type": "string",
                "description": "URL for navigate action"
            },
            "selector": {
                "type": "string",
                "description": "CSS selector for click/type actions"
            },
            "text": {
                "type": "string",
                "description": "Text for type action"
            },
            "script": {
                "type": "string",
                "description": "JavaScript for evaluate action"
            },
            "wait_ms": {
                "type": "integer",
                "description": "Time to wait after action (ms)",
                "default": 1000
            }
        },
        "required": ["action"]
    }
    
    def __init__(self, headless: bool = True, profile_dir: str = ""):
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError(
                "Playwright not installed. Install with: pip install playwright && playwright install"
            )
        
        self.headless = headless
        self.profile_dir = profile_dir
        self._playwright = None
        self._browser: Browser | None = None
        self._page: Page | None = None
    
    async def _ensure_browser(self) -> Page:
        """Ensure browser is running and return page."""
        if self._page and not self._page.is_closed():
            return self._page
        
        if not self._playwright:
            self._playwright = await async_playwright().start()
        
        if not self._browser:
            launch_args = {
                "headless": self.headless,
            }
            if self.profile_dir:
                launch_args["user_data_dir"] = self.profile_dir
            
            self._browser = await self._playwright.chromium.launch(**launch_args)
        
        self._page = await self._browser.new_page()
        return self._page
    
    async def execute(self, **kwargs: Any) -> str:
        """Execute browser action."""
        action = kwargs.get("action", "")
        
        if action == "close":
            return await self._close()
        
        page = await self._ensure_browser()
        wait_ms = kwargs.get("wait_ms", 1000)
        
        try:
            if action == "navigate":
                return await self._navigate(page, kwargs.get("url", ""), wait_ms)
            
            elif action == "click":
                return await self._click(page, kwargs.get("selector", ""), wait_ms)
            
            elif action == "type":
                return await self._type(
                    page, 
                    kwargs.get("selector", ""), 
                    kwargs.get("text", ""),
                    wait_ms
                )
            
            elif action == "screenshot":
                return await self._screenshot(page)
            
            elif action == "evaluate":
                return await self._evaluate(page, kwargs.get("script", ""))
            
            elif action == "get_content":
                return await self._get_content(page)
            
            else:
                return f"Unknown action: {action}"
                
        except Exception as e:
            return f"Browser error: {str(e)}"
    
    async def _navigate(self, page: Page, url: str, wait_ms: int) -> str:
        """Navigate to a URL."""
        if not url:
            return "Error: URL required for navigate action"
        
        await page.goto(url, wait_until="domcontentloaded")
        await asyncio.sleep(wait_ms / 1000)
        
        return f"Navigated to {url}. Title: {await page.title()}"
    
    async def _click(self, page: Page, selector: str, wait_ms: int) -> str:
        """Click an element."""
        if not selector:
            return "Error: Selector required for click action"
        
        await page.click(selector)
        await asyncio.sleep(wait_ms / 1000)
        
        return f"Clicked element: {selector}"
    
    async def _type(self, page: Page, selector: str, text: str, wait_ms: int) -> str:
        """Type into an element."""
        if not selector:
            return "Error: Selector required for type action"
        
        await page.fill(selector, text)
        await asyncio.sleep(wait_ms / 1000)
        
        return f"Typed into {selector}"
    
    async def _screenshot(self, page: Page) -> str:
        """Take a screenshot."""
        screenshot = await page.screenshot(full_page=False)
        b64 = base64.b64encode(screenshot).decode("utf-8")
        
        # Return truncated base64 with info
        return f"Screenshot taken ({len(screenshot)} bytes). Base64 preview: {b64[:100]}..."
    
    async def _evaluate(self, page: Page, script: str) -> str:
        """Execute JavaScript."""
        if not script:
            return "Error: Script required for evaluate action"
        
        result = await page.evaluate(script)
        return f"Result: {result}"
    
    async def _get_content(self, page: Page) -> str:
        """Get page text content."""
        content = await page.inner_text("body")
        
        # Truncate if too long
        if len(content) > 5000:
            content = content[:5000] + "...[truncated]"
        
        return content
    
    async def _close(self) -> str:
        """Close the browser."""
        if self._page:
            await self._page.close()
            self._page = None
        
        if self._browser:
            await self._browser.close()
            self._browser = None
        
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        
        return "Browser closed"
