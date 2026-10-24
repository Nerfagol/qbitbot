from pathlib import Path

p = Path("/app/utils.py")
s = p.read_text()
old = "    options.add_argument('--ignore-certificate-errors')"
assert s.count(old) == 1, "Upstream certificate flag drift"
s = s.replace(old, "    options.set_capability('acceptInsecureCerts', False)")
p.write_text(s)
assert "--ignore-certificate-errors" not in s
p = Path("/app/flaresolverr_service.py")
s = p.read_text()
guard = """def _reject_browser_error_document(driver):
    # Chromium can display a TLS/network interstitial without raising from get().
    # Inspect its internal document URI rather than matching untrusted HTML.
    uri = driver.execute_script("return document.documentURI")
    if not isinstance(uri, str) or uri.startswith("chrome-error://"):
        raise Exception("Browser rejected the destination certificate or network response.")


"""
assert "def _reject_browser_error_document" not in s
s += "\n\n" + guard
for anchor in [
    "    # wait for the page\n",
    "    # Get cookies after all waits to capture cookies set during JavaScript execution\n",
]:
    assert s.count(anchor) == 1, "Upstream navigation anchor drift"
    s = s.replace(anchor, "    _reject_browser_error_document(driver)\n\n" + anchor)
p.write_text(s)
