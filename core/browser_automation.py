#!/usr/bin/env python3
"""Browser automation utilities for UI verification.

Supports Playwright (preferred) and Puppeteer for visual verification
of UI features during long-running agent workflows.

This module is opt-in and requires browser automation tools to be installed:
- Playwright: npm install @playwright/test && npx playwright install
- Puppeteer: npm install puppeteer
"""

import subprocess
import json
import os
from typing import Optional, Dict, Any
from pathlib import Path
from dataclasses import dataclass


@dataclass
class BrowserResult:
    """Result of a browser automation operation."""
    success: bool
    screenshot_path: Optional[str] = None
    error: Optional[str] = None
    output: Optional[str] = None
    element_found: bool = False
    element_text: Optional[str] = None


def detect_browser_tool(work_dir: str) -> Optional[str]:
    """
    Detect available browser automation tool.

    Returns: 'playwright', 'puppeteer', or None
    """
    path = Path(work_dir)

    # Check for Playwright (preferred)
    playwright_paths = [
        path / "node_modules" / "@playwright" / "test",
        path / "node_modules" / "playwright",
    ]
    for p in playwright_paths:
        if p.exists():
            return "playwright"

    # Check for Puppeteer
    if (path / "node_modules" / "puppeteer").exists():
        return "puppeteer"

    # Check global installations
    try:
        result = subprocess.run(
            ['npx', 'playwright', '--version'],
            capture_output=True,
            timeout=10,
            cwd=work_dir
        )
        if result.returncode == 0:
            return "playwright"
    except Exception:
        pass

    try:
        result = subprocess.run(
            ['npx', 'puppeteer', '--version'],
            capture_output=True,
            timeout=10,
            cwd=work_dir
        )
        if result.returncode == 0:
            return "puppeteer"
    except Exception:
        pass

    return None


def take_screenshot(
    url: str,
    output_path: str,
    work_dir: str,
    selector: str = None,
    wait_for: str = None,
    timeout: int = 30000,
    full_page: bool = True
) -> BrowserResult:
    """
    Take a screenshot of a web page.

    Args:
        url: URL to screenshot
        output_path: Where to save the screenshot
        work_dir: Working directory
        selector: Optional CSS selector to wait for before screenshot
        wait_for: Optional JS expression to wait for (must return truthy)
        timeout: Timeout in milliseconds
        full_page: Whether to capture the full scrollable page

    Returns:
        BrowserResult with success status and screenshot path
    """
    tool = detect_browser_tool(work_dir)

    if not tool:
        return BrowserResult(
            success=False,
            error="No browser automation tool found. Install Playwright: npm install @playwright/test && npx playwright install"
        )

    # Ensure output directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    if tool == "playwright":
        return _playwright_screenshot(url, output_path, work_dir, selector, wait_for, timeout, full_page)
    else:
        return _puppeteer_screenshot(url, output_path, work_dir, selector, wait_for, timeout, full_page)


def _playwright_screenshot(
    url: str,
    output_path: str,
    work_dir: str,
    selector: str,
    wait_for: str,
    timeout: int,
    full_page: bool
) -> BrowserResult:
    """Take screenshot using Playwright."""
    # Escape strings for JavaScript
    url_escaped = url.replace("'", "\\'")
    output_escaped = output_path.replace("'", "\\'")

    wait_selector_code = ""
    if selector:
        selector_escaped = selector.replace("'", "\\'")
        wait_selector_code = f"await page.waitForSelector('{selector_escaped}', {{ timeout: {timeout} }});"

    wait_function_code = ""
    if wait_for:
        wait_for_escaped = wait_for.replace("'", "\\'")
        wait_function_code = f"await page.waitForFunction(() => {wait_for_escaped}, {{ timeout: {timeout} }});"

    script = f"""
const {{ chromium }} = require('playwright');

(async () => {{
    const browser = await chromium.launch({{ headless: true }});
    const page = await browser.newPage();

    try {{
        await page.goto('{url_escaped}', {{ timeout: {timeout}, waitUntil: 'networkidle' }});
        {wait_selector_code}
        {wait_function_code}
        await page.screenshot({{ path: '{output_escaped}', fullPage: {'true' if full_page else 'false'} }});
        console.log(JSON.stringify({{ success: true, path: '{output_escaped}' }}));
    }} catch (e) {{
        console.log(JSON.stringify({{ success: false, error: e.message }}));
    }} finally {{
        await browser.close();
    }}
}})();
"""

    try:
        result = subprocess.run(
            ['node', '-e', script],
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=timeout // 1000 + 30
        )

        if result.stdout.strip():
            try:
                output = json.loads(result.stdout.strip().split('\n')[-1])
                return BrowserResult(
                    success=output.get('success', False),
                    screenshot_path=output.get('path'),
                    error=output.get('error'),
                    output=result.stdout
                )
            except json.JSONDecodeError:
                pass

        return BrowserResult(
            success=False,
            error=result.stderr or "Unknown error"
        )

    except subprocess.TimeoutExpired:
        return BrowserResult(success=False, error="Screenshot timed out")
    except Exception as e:
        return BrowserResult(success=False, error=str(e))


def _puppeteer_screenshot(
    url: str,
    output_path: str,
    work_dir: str,
    selector: str,
    wait_for: str,
    timeout: int,
    full_page: bool
) -> BrowserResult:
    """Take screenshot using Puppeteer."""
    url_escaped = url.replace("'", "\\'")
    output_escaped = output_path.replace("'", "\\'")

    wait_selector_code = ""
    if selector:
        selector_escaped = selector.replace("'", "\\'")
        wait_selector_code = f"await page.waitForSelector('{selector_escaped}', {{ timeout: {timeout} }});"

    wait_function_code = ""
    if wait_for:
        wait_for_escaped = wait_for.replace("'", "\\'")
        wait_function_code = f"await page.waitForFunction(() => {wait_for_escaped}, {{ timeout: {timeout} }});"

    script = f"""
const puppeteer = require('puppeteer');

(async () => {{
    const browser = await puppeteer.launch({{ headless: 'new' }});
    const page = await browser.newPage();

    try {{
        await page.goto('{url_escaped}', {{ timeout: {timeout}, waitUntil: 'networkidle0' }});
        {wait_selector_code}
        {wait_function_code}
        await page.screenshot({{ path: '{output_escaped}', fullPage: {'true' if full_page else 'false'} }});
        console.log(JSON.stringify({{ success: true, path: '{output_escaped}' }}));
    }} catch (e) {{
        console.log(JSON.stringify({{ success: false, error: e.message }}));
    }} finally {{
        await browser.close();
    }}
}})();
"""

    try:
        result = subprocess.run(
            ['node', '-e', script],
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=timeout // 1000 + 30
        )

        if result.stdout.strip():
            try:
                output = json.loads(result.stdout.strip().split('\n')[-1])
                return BrowserResult(
                    success=output.get('success', False),
                    screenshot_path=output.get('path'),
                    error=output.get('error'),
                    output=result.stdout
                )
            except json.JSONDecodeError:
                pass

        return BrowserResult(
            success=False,
            error=result.stderr or "Unknown error"
        )

    except subprocess.TimeoutExpired:
        return BrowserResult(success=False, error="Screenshot timed out")
    except Exception as e:
        return BrowserResult(success=False, error=str(e))


def verify_element(
    url: str,
    selector: str,
    work_dir: str,
    expected_text: str = None,
    timeout: int = 30000
) -> BrowserResult:
    """
    Verify a UI element exists and optionally contains expected text.

    Args:
        url: URL to check
        selector: CSS selector for the element
        work_dir: Working directory
        expected_text: Optional text the element should contain
        timeout: Timeout in milliseconds

    Returns:
        BrowserResult with element_found and element_text populated
    """
    tool = detect_browser_tool(work_dir)

    if not tool:
        return BrowserResult(
            success=False,
            error="No browser automation tool found"
        )

    url_escaped = url.replace("'", "\\'")
    selector_escaped = selector.replace("'", "\\'")

    text_check = ""
    if expected_text:
        expected_escaped = expected_text.replace("'", "\\'")
        text_check = f"""
            if (!text.includes('{expected_escaped}')) {{
                throw new Error('Text mismatch: expected "{expected_escaped}" but found: ' + text.substring(0, 100));
            }}
"""

    if tool == "playwright":
        script = f"""
const {{ chromium }} = require('playwright');

(async () => {{
    const browser = await chromium.launch({{ headless: true }});
    const page = await browser.newPage();

    try {{
        await page.goto('{url_escaped}', {{ timeout: {timeout}, waitUntil: 'networkidle' }});
        const element = await page.waitForSelector('{selector_escaped}', {{ timeout: {timeout} }});

        if (element) {{
            const text = await element.textContent() || '';
            {text_check}
            console.log(JSON.stringify({{ success: true, found: true, text: text.substring(0, 500) }}));
        }} else {{
            console.log(JSON.stringify({{ success: false, found: false, error: 'Element not found' }}));
        }}
    }} catch (e) {{
        console.log(JSON.stringify({{ success: false, found: false, error: e.message }}));
    }} finally {{
        await browser.close();
    }}
}})();
"""
    else:  # puppeteer
        script = f"""
const puppeteer = require('puppeteer');

(async () => {{
    const browser = await puppeteer.launch({{ headless: 'new' }});
    const page = await browser.newPage();

    try {{
        await page.goto('{url_escaped}', {{ timeout: {timeout}, waitUntil: 'networkidle0' }});
        await page.waitForSelector('{selector_escaped}', {{ timeout: {timeout} }});
        const element = await page.$('{selector_escaped}');

        if (element) {{
            const text = await page.evaluate(el => el.textContent || '', element);
            {text_check}
            console.log(JSON.stringify({{ success: true, found: true, text: text.substring(0, 500) }}));
        }} else {{
            console.log(JSON.stringify({{ success: false, found: false, error: 'Element not found' }}));
        }}
    }} catch (e) {{
        console.log(JSON.stringify({{ success: false, found: false, error: e.message }}));
    }} finally {{
        await browser.close();
    }}
}})();
"""

    try:
        result = subprocess.run(
            ['node', '-e', script],
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=timeout // 1000 + 30
        )

        if result.stdout.strip():
            try:
                output = json.loads(result.stdout.strip().split('\n')[-1])
                return BrowserResult(
                    success=output.get('success', False),
                    element_found=output.get('found', False),
                    element_text=output.get('text'),
                    error=output.get('error'),
                    output=result.stdout
                )
            except json.JSONDecodeError:
                pass

        return BrowserResult(
            success=False,
            error=result.stderr or "Unknown error"
        )

    except subprocess.TimeoutExpired:
        return BrowserResult(success=False, error="Verification timed out")
    except Exception as e:
        return BrowserResult(success=False, error=str(e))


def get_installation_instructions() -> str:
    """Get instructions for installing browser automation tools."""
    return """
Browser Automation Setup
========================

The harness plugin supports Playwright (recommended) or Puppeteer for UI verification.

Option 1: Playwright (Recommended)
----------------------------------
npm install @playwright/test
npx playwright install chromium

Option 2: Puppeteer
-------------------
npm install puppeteer

After installation, enable browser automation:
/harness:configure browser on

Usage in verification:
- Screenshots are saved to .claude/screenshots/
- Use verify_element() to check UI elements exist
- Use take_screenshot() for visual verification
"""
