"""The dashboard reading page keeps the public paper and wires the real actions."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "paper.html"
PAGE = ROOT / "dashboard" / "paper.html"
SCRIPT = ROOT / "dashboard" / "paper.js"


def text(html: str) -> str:
    html = re.sub(r"<script[\s\S]*?</script>", " ", html)
    html = re.sub(r"<sup[\s\S]*?</sup>", "", html)
    html = re.sub(r"<[^>]+>", " ", html)
    html = html.replace("\xa0", " ")
    return re.sub(r"\s+", " ", html).strip()


def chunks(html: str, tags: str) -> list[str]:
    body = html[html.index("<body"):html.index("</body>")]
    found = re.findall(rf"<({tags})[^>]*>([\s\S]*?)</\1>", body)
    out = []
    for _tag, inner in found:
        inner = re.sub(r"<sup[\s\S]*?</sup>", "", inner)
        inner = re.sub(r"<[^>]+>", " ", inner)
        inner = re.sub(r"\s+", " ", inner).strip()
        if inner:
            out.append(inner)
    return out


class PaperPageTest(unittest.TestCase):
    def test_public_paragraphs_are_present(self) -> None:
        page = text(PAGE.read_text(encoding="utf-8"))
        for kind in ("p", "li", "td", "h3", "figcaption"):
            for chunk in chunks(DOCS.read_text(encoding="utf-8"), kind):
                # The reading page sets the word Abstract as its own label.
                if chunk.startswith("Abstract. "):
                    chunk = "Abstract " + chunk[len("Abstract. "):]
                self.assertIn(chunk, page, chunk[:120])
        for heading in chunks(DOCS.read_text(encoding="utf-8"), "h2"):
            title = re.sub(r"^\d+A?\.\s*", "", heading)
            self.assertIn(title, page, heading)

    def test_actions_and_real_learners(self) -> None:
        html = PAGE.read_text(encoding="utf-8")
        script = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("paper.pdf", html)
        self.assertFalse((ROOT / "dashboard" / "paper.pdf").exists())
        self.assertIn("https://testnet.nearblocks.io/address/lightswarm16771.testnet", html)
        self.assertNotIn("mainnet.nearblocks", html)
        self.assertIn('href="index.html?tab=playground"', html)
        self.assertIn('id="cite"', html)
        self.assertIn('id="theme"', html)
        self.assertIn("independent hackathon project · not an official NEAR page", html)
        self.assertNotIn("example run", html.lower())
        self.assertNotIn("501455504540", script)
        self.assertIn("decodeWeights", script)
        self.assertIn("predict", script)
        self.assertIn("UPBRINGING", script)
        self.assertIn("ABLATION", script)
        self.assertIn("light-agents-theme", html)


if __name__ == "__main__":
    unittest.main()
