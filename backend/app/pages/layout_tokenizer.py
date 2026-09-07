"""Turn a finished HTML layout (copy baked in) into a block-model-v2 seed:
`{{TOKEN}}` template + `default_props` + `fields_schema`.

Used for the 71 layouts that lived in the Visual tab's Section Library
(`seeds/visual_editor_layouts.json`, extracted verbatim from
VisualEditor.tsx on 2026-09-07). Deterministic: the same HTML always
yields the same token names, so AI-filled props and saved pages stay
valid across re-seeds.

Rules
- Only text nodes whose parent is one of TEXT_TAGS become fields. Text
  with no letters/digits (icons ✓ ✕ ★ emoji) stays literal markup.
- `href` on <a> becomes a url field paired with the link text
  (LINK_n_TEXT / LINK_n_HREF); "#" hrefs are kept as the default.
- `src` on <img> becomes an image field (IMAGE_n_URL).
- Token names are role-based and numbered in document order:
  HEADLINE (first h1/h2), SUBHEADLINE (first p after it), TITLE_n (h3+),
  TEXT_n (p), LABEL_n (span), ITEM_n (li), BUTTON_n, LINK_n_TEXT/HREF.
- Text ≤ 80 chars → "text"; longer → "textarea".
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any

TEXT_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "a", "span", "li", "button", "label", "td", "th", "blockquote", "figcaption", "dt", "dd"}
VOID_TAGS = {"img", "br", "hr", "input", "meta", "link", "source", "wbr"}
_HAS_WORD = re.compile(r"[A-Za-z0-9À-ÿ]")
_PLACEHOLDER_INTERP = re.compile(r"\$\{PLACEHOLDER_IMGS\[(\d+)\]\}")

# Neutral SVG gradient placeholders (same idea as VisualEditor.PLACEHOLDER_IMGS)
# — replaced by Higgsfield imagery in S3.
PLACEHOLDER_IMAGE = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='600' height='450'%3E"
    "%3Cdefs%3E%3ClinearGradient id='g' x1='0' y1='0' x2='1' y2='1'%3E%3Cstop offset='0' stop-color='%236366f1'/%3E"
    "%3Cstop offset='1' stop-color='%23c7d2fe'/%3E%3C/linearGradient%3E%3C/defs%3E%3Crect width='600' height='450' fill='url(%23g)'/%3E%3C/svg%3E"
)


class _Tokenizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.out: list[str] = []
        self.props: dict[str, Any] = {}
        self.schema: list[dict] = []
        self.stack: list[str] = []
        self.counts: dict[str, int] = {}
        self.pending_link_key: str | None = None
        self.headline_done = False
        self.subheadline_done = False
        self._buffer: list[str] = []      # text accumulated for the current text parent
        self._buffer_tag: str | None = None

    # -- helpers -----------------------------------------------------------
    def _next(self, prefix: str) -> str:
        self.counts[prefix] = self.counts.get(prefix, 0) + 1
        return f"{prefix}_{self.counts[prefix]}"

    def _add_field(self, key: str, ftype: str, value: Any, **extra: Any) -> None:
        self.props[key] = value
        f: dict[str, Any] = {"key": key, "type": ftype, "label": key.replace("_", " ").title()}
        f.update(extra)
        self.schema.append(f)

    def _flush_text(self) -> None:
        if self._buffer_tag is None:
            return
        raw = "".join(self._buffer)
        self._buffer = []
        tag = self._buffer_tag
        self._buffer_tag = None
        text = raw.strip()
        if not text or not _HAS_WORD.search(text):
            self.out.append(raw)
            return
        text = " ".join(text.split())
        if tag in ("h1", "h2") and not self.headline_done:
            key = "HEADLINE"
            self.headline_done = True
        elif tag == "p" and self.headline_done and not self.subheadline_done:
            key = "SUBHEADLINE"
            self.subheadline_done = True
        elif tag == "a":
            key = (self.pending_link_key or self._next("LINK")) + "_TEXT"
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            key = self._next("TITLE")
        elif tag == "p":
            key = self._next("TEXT")
        elif tag == "li":
            key = self._next("ITEM")
        elif tag == "button":
            key = self._next("BUTTON")
        else:
            key = self._next("LABEL")
        ftype = "textarea" if len(text) > 80 else "text"
        self._add_field(key, ftype, text, max_len=160 if ftype == "text" else 600)
        lead = raw[: len(raw) - len(raw.lstrip())]
        trail = raw[len(raw.rstrip()):]
        self.out.append(f"{lead}{{{{{key}}}}}{trail}")

    # -- parser callbacks -------------------------------------------------
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._flush_text()
        attrs_out: list[str] = []
        link_key: str | None = None
        if tag == "a":
            link_key = self._next("LINK")
            self.pending_link_key = link_key
        for name, val in attrs:
            if tag == "a" and name == "href" and link_key:
                key = f"{link_key}_HREF"
                self._add_field(key, "url", val or "#")
                val = f"{{{{{key}}}}}"
            elif tag == "img" and name == "src":
                key = self._next("IMAGE") + "_URL"
                src = val or ""
                if _PLACEHOLDER_INTERP.search(src) or not src:
                    src = PLACEHOLDER_IMAGE
                self._add_field(key, "image", src)
                val = f"{{{{{key}}}}}"
            elif tag == "img" and name == "alt" and val and _HAS_WORD.search(val):
                key = self.counts.get("IMAGE", 0) and f"IMAGE_{self.counts['IMAGE']}_ALT" or self._next("ALT")
                self._add_field(key, "text", val, max_len=120)
                val = f"{{{{{key}}}}}"
            elif name == "placeholder" and val and _HAS_WORD.search(val):
                key = self._next("PLACEHOLDER")
                self._add_field(key, "text", val, max_len=80)
                val = f"{{{{{key}}}}}"
            if val is None:
                attrs_out.append(name)
            else:
                attrs_out.append(f'{name}="{val}"')
        self.out.append(f"<{tag}" + (" " + " ".join(attrs_out) if attrs_out else "") + ">")
        if tag not in VOID_TAGS:
            self.stack.append(tag)
        if tag == "a":
            # link text is captured by _flush_text using pending_link_key
            pass

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in VOID_TAGS:
            self.stack.pop()
            self.out[-1] = self.out[-1][:-1] + "/>"
        else:
            self.out[-1] = self.out[-1][:-1] + "/>"

    def handle_endtag(self, tag: str) -> None:
        self._flush_text()
        if tag == "a":
            self.pending_link_key = None
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
        self.out.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        parent = self.stack[-1] if self.stack else None
        if parent in TEXT_TAGS:
            if self._buffer_tag != parent:
                self._flush_text()
                self._buffer_tag = parent
            self._buffer.append(data)
        else:
            self._flush_text()
            self.out.append(data)

    def handle_entityref(self, name: str) -> None:
        self.handle_data(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.handle_data(f"&#{name};")

    def close(self) -> None:
        self._flush_text()
        super().close()


_GRADIENT_PLACEHOLDER = re.compile(
    r'<div class="([^"]*\baspect-\[[^"]*\bbg-gradient-to-[a-z]+[^"]*)"></div>'
)


def _promote_gradient_placeholders(html: str) -> str:
    """The visual layouts used empty gradient boxes where a photo belongs
    (`<div class="aspect-[4/3] … bg-gradient-to-br …"></div>`). Turn them
    into real <img> slots so they become image fields (and get library
    imagery in S3) while keeping the same size/rounding classes."""
    def _sub(m: re.Match[str]) -> str:
        classes = " ".join(c for c in m.group(1).split() if not c.startswith(("bg-gradient", "from-", "to-", "via-")))
        return f'<img src="" alt="" class="{classes} w-full object-cover"/>'
    return _GRADIENT_PLACEHOLDER.sub(_sub, html)


def tokenize_layout(html: str) -> tuple[str, dict[str, Any], list[dict]]:
    """Returns (jsx_template, default_props, fields_schema)."""
    p = _Tokenizer()
    p.feed(_promote_gradient_placeholders(html))
    p.close()
    template = "".join(p.out)
    # Entities inside captured copy: the engine escapes v2 values, so store
    # the *decoded* text (Jane &amp; Co → Jane & Co) to avoid double-escaping.
    import html as _html
    props = {k: (_html.unescape(v) if isinstance(v, str) and k.endswith(("_TEXT", "_ALT")) or k.startswith(("HEADLINE", "SUBHEADLINE", "TITLE", "TEXT", "LABEL", "ITEM", "BUTTON", "PLACEHOLDER")) else v)
             for k, v in p.props.items()}
    return template, props, p.schema


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return s or "layout"
