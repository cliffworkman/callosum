"""Rendered Settings component with simulated Tauri IPC, not packaged-browser acceptance."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

if not os.environ.get("CALLOSUM_RUN_E2E"):
    pytest.skip("set CALLOSUM_RUN_E2E=1 for rendered preview controls", allow_module_level=True)

from playwright.sync_api import expect, sync_playwright  # noqa: E402

from app.backend.api.frontend import _transpile_jsx  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def document(mock=True):
    react = (ROOT / "node_modules/react/umd/react.development.js").read_text(encoding="utf-8")
    dom = (ROOT / "node_modules/react-dom/umd/react-dom.development.js").read_text(encoding="utf-8")
    component = (ROOT / "app/frontend/js/35h_browser_capture.jsx").read_text(encoding="utf-8")
    script = _transpile_jsx(
        "const {useState,useEffect}=React;"
        + component
        + '\nReactDOM.createRoot(document.getElementById("root")).render(<BrowserCaptureSettings/>);'
    )
    mock_ipc = (
        """
    window.calls=[];window.preview={enabled:false,prepared:false,connection:'not_checked',version:'0.1.1',folder:'/managed/extension',extension_id:'test-identity'};
    window.__TAURI__={core:{invoke:async(command,{action})=>{
      window.calls.push({command,action});
      if(window.fail)throw new Error(window.fail);
      if(action==='enable')window.preview.enabled=true;
      if(action==='prepare')window.preview.prepared=true;
      if(action==='verify')window.preview.connection='waiting';
      if(action==='disable')window.preview={...window.preview,enabled:false,prepared:false,connection:'not_checked'};
      return {...window.preview};
    }}};
    """
        if mock
        else ""
    )
    return f'<div id="root"></div><script>{react}</script><script>{dom}</script><script>{mock_ipc}</script><script>{script}</script>'


def test_explicit_setup_truthful_connection_errors_and_opt_out():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.set_content(document())
        page.get_by_role("button", name="Enable early access", exact=True).click()
        expect(page.get_by_role("button", name="Verify connection", exact=True)).to_be_disabled()
        page.get_by_role("button", name="Prepare extension", exact=True).click()
        page.get_by_role("button", name="Open extension folder", exact=True).click()
        expect(
            page.get_by_text("Browser installation and connection have not been verified.", exact=False)
        ).to_be_visible()
        expect(page.get_by_text("Connection verified at", exact=False)).to_have_count(0)
        page.get_by_role("combobox").select_option("Edge")
        expect(page.get_by_text("edge://extensions", exact=True)).to_be_visible()
        page.get_by_role("button", name="Verify connection", exact=True).click()
        expect(page.get_by_text("Waiting for the browser.", exact=False)).to_be_visible()
        page.evaluate("window.preview.connection='verified';window.preview.verified_at=Date.now()/1000")
        expect(page.get_by_text("Connection verified at", exact=False)).to_be_visible()
        page.evaluate("window.fail='Native registration failed'")
        page.get_by_role("button", name="Prepare extension", exact=True).click()
        expect(page.get_by_role("alert")).to_contain_text("Native registration failed")
        page.evaluate("window.fail=null")
        page.get_by_role("button", name="Turn off early access", exact=True).click()
        expect(page.get_by_role("button", name="Enable early access", exact=True)).to_be_visible()
        assert all(call["command"] == "browser_preview" for call in page.evaluate("window.calls"))
        assert not errors
        page.close()
        page = browser.new_page()
        page.set_content(document(mock=False))
        expect(page.get_by_text("Remote access cannot install", exact=False)).to_be_visible()
        expect(page.get_by_role("button")).to_have_count(0)
        browser.close()
