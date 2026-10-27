"""Plain text from stored WordPress HTML: the imported short description and review snippets."""

from html.parser import HTMLParser

SNIPPET_WORDS = 22
# Tags that separate words even with no whitespace around them in the source.
_BLOCK_TAGS = frozenset(
    {"address", "article", "aside", "blockquote", "br", "dd", "div", "dl", "dt", "figcaption"}
    | {"figure", "footer", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr", "li", "main"}
    | {"nav", "ol", "p", "pre", "section", "table", "td", "th", "tr", "ul"}
)
_SKIPPED_TAGS = frozenset({"script", "style", "template"})


class _TextParser(HTMLParser):
    def __init__(self, *, first_paragraph: bool) -> None:
        super().__init__(convert_charrefs=True)  # decodes &amp; and friends in handle_data
        self.first_paragraph = first_paragraph
        self.parts: list[str] = []
        self.in_paragraph = False
        self.done = False
        self.skipping = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIPPED_TAGS:
            self.skipping += 1
        elif tag == "p" and not self.done:
            self.in_paragraph = True
        if tag in _BLOCK_TAGS:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIPPED_TAGS:
            self.skipping = max(0, self.skipping - 1)
        elif tag == "p" and self.in_paragraph:
            self.in_paragraph = False
            self.done = self.first_paragraph
        if tag in _BLOCK_TAGS:
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        if self.skipping or self.done:
            return
        if self.first_paragraph and not self.in_paragraph:
            return
        self.parts.append(data)

    def text(self) -> str:
        return " ".join("".join(self.parts).split())


def _parse(html: str, *, first_paragraph: bool) -> str:
    parser = _TextParser(first_paragraph=first_paragraph)
    parser.feed(html)
    parser.close()
    return parser.text()


def first_paragraph_text(html: str) -> str:
    """The first `<p>` as plain text: tags stripped, entities decoded, whitespace collapsed.

    `""` when there is no `<p>` (wp-source contract, Brands → short_description).
    """
    return _parse(html, first_paragraph=True)


def plain_text(html: str) -> str:
    return _parse(html, first_paragraph=False)


def snippet(html: str, words: int = SNIPPET_WORDS) -> str:
    """At most `words` words of plain text, ending in `…` if it was cut (brands-api TopReview)."""
    parts = plain_text(html).split(" ")
    if len(parts) <= words:
        return " ".join(parts)
    return " ".join(parts[:words]) + "…"
