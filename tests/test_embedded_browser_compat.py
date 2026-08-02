import http.server
import subprocess
import threading
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHROME_CANDIDATES = (
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
)


class EmbeddedBrowserCompatTests(unittest.TestCase):
    def render_home(self, *, block_linked_assets=False, before_app=""):
        browser = next((path for path in CHROME_CANDIDATES if path.exists()), None)
        if browser is None:
            self.skipTest("Chrome or Edge is required for the embedded-browser check")

        root = ROOT

        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(root), **kwargs)

            def log_message(self, _format, *_args):
                return

            def do_GET(self):
                destination = self.headers.get("Sec-Fetch-Dest", "")
                if block_linked_assets and destination in {"style", "script"}:
                    self.send_error(403)
                    return
                if self.path in {"/", "/index.html"}:
                    html = (root / "index.html").read_text(encoding="utf-8")
                    html = html.replace("<!-- compat-core-app:start -->", before_app + "<!-- compat-core-app:start -->")
                    probe = """
                    <script>
                      addEventListener("load", () => {
                        document.body.dataset.computedBackground =
                          getComputedStyle(document.body).backgroundColor;
                        document.body.dataset.analyticsReady =
                          String(Boolean(window.ARAM_ANALYTICS?.isEnabled()));
                      });
                    </script>
                    """
                    payload = html.replace("</body>", f"{probe}</body>").encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return
                super().do_GET()

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = subprocess.run(
                [
                    str(browser),
                    "--headless=new",
                    "--no-sandbox",
                    "--disable-gpu",
                    "--host-resolver-rules=MAP us-assets.i.posthog.com 0.0.0.0",
                    "--dump-dom",
                    "--virtual-time-budget=3000",
                    f"http://127.0.0.1:{server.server_port}/",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
                check=False,
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_embedded_core_assets_match_the_editable_sources(self):
        result = subprocess.run(
            ["python", str(ROOT / "tools" / "embed_core_assets.py"), "--check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_home_renders_when_linked_styles_and_scripts_are_blocked(self):
        html = self.render_home(block_linked_assets=True)

        self.assertIn('class="hero-card"', html)
        self.assertNotIn('class="loading-state"', html)
        self.assertIn('data-computed-background="rgb(9, 13, 13)"', html)
        self.assertIn('data-analytics-ready="true"', html)

    def test_home_renders_when_session_storage_is_restricted(self):
        html = self.render_home(before_app="""
          <script>
            Storage.prototype.getItem = () => { throw new DOMException("blocked", "SecurityError"); };
            Storage.prototype.setItem = () => { throw new DOMException("blocked", "SecurityError"); };
            Storage.prototype.removeItem = () => { throw new DOMException("blocked", "SecurityError"); };
          </script>
        """)

        self.assertIn('class="hero-card"', html)
        self.assertNotIn('class="loading-state"', html)


if __name__ == "__main__":
    unittest.main()
