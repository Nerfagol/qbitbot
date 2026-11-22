"""Encode proxy inputs as JavaScript literals for GHSA-c52x-qhrp-8qqp."""

from pathlib import Path

path = Path("/app/utils.py")
source = path.read_text()
assert "import json\n" in source, "Upstream JSON import drift"

old_values = '''    """ % (
        scheme,
        host,
        port,
        username,
        password
    )'''
new_values = '''    """ % (
        json.dumps(str(scheme)),
        json.dumps(str(host)),
        port,
        json.dumps(str(username)),
        json.dumps(str(password))
    )'''
assert source.count(old_values) == 1, "Upstream proxy argument drift"
source = source.replace(old_values, new_values)

# JSON supplies the quotes and the escaping for each JavaScript string literal.
for field in ("scheme", "host", "username", "password"):
    old_literal = f'{field}: "%s"'
    assert source.count(old_literal) == 1, f"Upstream proxy field drift: {field}"
    source = source.replace(old_literal, f"{field}: %s")

path.write_text(source)
