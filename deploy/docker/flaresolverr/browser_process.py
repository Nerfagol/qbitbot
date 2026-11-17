"""Give detached Chromium streams a lifetime independent of its launch helper."""

from pathlib import Path

path = Path("/app/undetected_chromedriver/dprocess.py")
source = path.read_text()
old_import = "from subprocess import PIPE"
old_launch = "p = Popen([executable, *args], stdin=PIPE, stdout=PIPE, stderr=PIPE, **kwargs)"
assert source.count(old_import) == 1, "Upstream detached browser import drift"
assert source.count(old_launch) == 1, "Upstream detached browser launch drift"
# The helper exits immediately. Pipes have no remaining reader; output can kill
# the browser with SIGPIPE. DEVNULL also avoids blocking on undrained output or
# exposing visited URLs through browser diagnostics in production logs.
source = source.replace(old_import, "from subprocess import DEVNULL")
source = source.replace(old_launch, old_launch.replace("PIPE", "DEVNULL"))
path.write_text(source)
