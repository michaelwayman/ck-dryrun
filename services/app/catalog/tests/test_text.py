import json
from pathlib import Path

import pytest

from catalog.text import first_paragraph_text, snippet

WP_SOURCE = Path(__file__).resolve().parents[4] / "docs/contracts/wp-source"


def test_short_description_cases_from_the_contract() -> None:
    example = json.loads((WP_SOURCE / "examples/brand-row.json").read_text())

    for case in example["short_description_cases"]:
        assert first_paragraph_text(case["post_content"]) == case["short_description"]


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        ("<p>Alpha <strong>synthetic</strong> co.</p><p>Second.</p>", "Alpha synthetic co."),
        ('<div><p class="x">One<br>two</p></div>', "One two"),
        ("No paragraph here.", ""),
        ("<p>&lt;b&gt; &#8211; &nbsp;x</p>", "<b> – x"),
        ("<p></p><p>Later.</p>", ""),
    ],
)
def test_first_paragraph_text(html: str, expected: str) -> None:
    assert first_paragraph_text(html) == expected


def test_snippet_keeps_short_text_whole() -> None:
    assert snippet("<p>Short   and\n<em>sweet</em>.</p>") == "Short and sweet."


def test_snippet_cuts_at_22_words_and_adds_an_ellipsis() -> None:
    words = [f"w{i}" for i in range(30)]
    html = "<p>" + " ".join(words[:10]) + "</p><p>" + " ".join(words[10:]) + "</p>"

    assert snippet(html) == " ".join(words[:22]) + "…"


def test_snippet_of_exactly_22_words_has_no_ellipsis() -> None:
    words = " ".join(f"w{i}" for i in range(22))

    assert snippet(f"<p>{words}</p>") == words


def test_snippet_drops_scripts_and_separates_blocks() -> None:
    assert snippet("<p>One.</p><script>alert(1)</script><p>Two.</p>") == "One. Two."
