"""Converting the SQL book's wikitext to Markdown. See architecture/sql-lessons.md, The book."""

import re
from pathlib import Path

import pytest

from kedami_server.sql_chapters import BOOK_DIR, book_file
from tools.wikitext import _CODE_BLOCK, to_markdown

FIXTURES = Path(__file__).parent / "fixtures" / "sql_book"
PAGES = {
    "SELECT: Join Operation": "SELECT_Join_Operation.wiki",
    "SELECT: Predefined Functions": "SELECT_Predefined_Functions.wiki",
    "with clause": "with_clause.wiki",
}


def body(wikitext: str) -> str:
    return to_markdown(wikitext, "Page").removeprefix("# Page\n\n").rstrip("\n")


def page(title: str) -> tuple[str, str]:
    wikitext = (FIXTURES / PAGES[title]).read_text(encoding="utf-8")
    return wikitext, to_markdown(wikitext, title)


def outside_code(markdown: str) -> str:
    return re.sub(r"```.*?```|`[^`\n]*`", "", markdown, flags=re.S)


class TestCode:
    def test_a_block_is_fenced_with_its_language(self):
        assert body('<syntaxhighlight lang="sql">\nSELECT 1;\n</syntaxhighlight>') == "```sql\nSELECT 1;\n```"

    def test_a_block_keeps_its_spaces_and_markup_like_lines(self):
        code = "SELECT a,   \n       b\n; -- '''not bold''' [[not a link]]\n* not a list\n== not a heading =="
        assert body(f"<source lang=sql>\n{code}\n</source>") == f"```sql\n{code}\n```"

    def test_a_pre_block_has_no_language(self):
        assert body("<pre>\nx\n</pre>") == "```\nx\n```"

    def test_inline_code(self):
        assert body("Use <code>WHERE x = 1</code> and <tt>LIKE</tt>.") == "Use `WHERE x = 1` and `LIKE`."

    def test_inline_code_with_a_backtick(self):
        assert body("<code>`name`</code>") == "```name```"

    def test_inline_code_over_lines_becomes_a_block(self):
        assert body("See\n<code>\nf(a)<br />\nf(b)\n</code>\nthen") == "See\n\n```\nf(a)\nf(b)\n```\n\nthen"

    def test_entities_in_inline_code_are_decoded(self):
        assert body("<code>a &lt;&gt; b</code>") == "`a <> b`"


class TestText:
    def test_headings(self):
        assert body("== Syntax ==\ntext\n=== Detail ===") == "## Syntax\n\ntext\n\n### Detail"

    def test_emphasis(self):
        assert body("'''bold''' ''italic'' '''''both'''''") == "**bold** *italic* ***both***"

    def test_lists(self):
        assert body("* one\n** nested\n# first") == "- one\n  - nested\n1. first"

    def test_definitions_and_indents(self):
        assert body("; Term : meaning\n; Alone\n: indented") == "**Term**: meaning\n**Alone**\nindented"

    def test_links(self):
        text = "[[Structured Query Language/Like Predicate|LIKE]], [[Structured Query Language/Recursions]], " \
            "[https://example.org the site]"
        assert body(text) == "LIKE, Recursions, the site"

    def test_navigation_comments_and_images_are_dropped(self):
        text = "<noinclude>{{Nav}}</noinclude>\n__TOC__\n<!-- note -->[[File:a.png|thumb|A [[link]]]]Text{{Color|x}}"
        assert body(text) == "Text"

    def test_exercise_and_solution(self):
        text = "<div style=background:gold;{{Text default color}};>\nCount rows.\n</div>\n" \
            "{{ExerciseSolution|width=100%|text=\n<syntaxhighlight lang=\"sql\">\nSELECT COUNT(*) FROM t;\n" \
            "</syntaxhighlight>\n}}"
        assert body(text) == "**Exercise:** Count rows.\n\n**Solution:**\n\n```sql\nSELECT COUNT(*) FROM t;\n```"

    def test_a_table(self):
        text = '{| class="wikitable"\n|+ caption\n|-\n! A !! B\n|-\n| style=color:red | 1 || a|b\n|-\n| 2\n|}'
        assert body(text) == "| A | B |\n| --- | --- |\n| 1 | a\\|b |\n| 2 |  |"

    def test_a_table_without_a_header_gets_an_empty_one(self):
        assert body("{|\n|-\n| 1 || 2\n|}") == "|  |  |\n| --- | --- |\n| 1 | 2 |"

    def test_a_layout_table_is_unwrapped(self):
        text = "{|\n|-\n|\nLeft\n{|\n! A\n|-\n| 1\n|}\n|\nRight\n|}"
        assert body(text) == "Left\n\n| A |\n| --- |\n| 1 |\n\nRight"

    def test_unclosed_markup_does_not_hang_or_raise(self):
        assert body("{{Nav|\ntext") == ""
        assert body("{|\n! A\n|-\n| 1") == "| A |\n| --- |\n| 1 |"
        assert "x" in body("<syntaxhighlight>\nx")

    def test_no_runs_of_blank_lines(self):
        assert body("a\n\n\n\n<div>\n\n\n</div>\n\nb  \n") == "a\n\nb"


class TestRealPages:
    @pytest.mark.parametrize("title", PAGES)
    def test_every_code_block_is_kept_verbatim(self, title):
        wikitext, markdown = page(title)
        blocks = [m[3].strip("\n") for m in _CODE_BLOCK.finditer(wikitext)]
        assert blocks
        for code in blocks:
            assert f"\n{code}\n```" in markdown

    @pytest.mark.parametrize("title", PAGES)
    def test_no_markup_is_left_outside_code(self, title):
        text = outside_code(page(title)[1])
        for leftover in ("{{", "}}", "{|", "|}", "<div", "<br", "<code", "<syntaxhighlight", "'''", "[[", "__TOC__"):
            assert leftover not in text, leftover

    @pytest.mark.parametrize("title", PAGES)
    def test_the_bundled_page_matches_the_converter(self, title):
        # Fails when the converter changes without the book being fetched again, or the other way round.
        assert (BOOK_DIR / book_file(title)).read_text(encoding="utf-8") == page(title)[1]

    def test_join_operation(self):
        markdown = page("SELECT: Join Operation")[1]
        assert markdown.startswith("# SELECT: Join Operation\n\n")
        assert "| ID | LASTNAME | FIRSTNAME | ... |\n| --- | --- | --- | --- |\n| 1 | Goldstein | Larry | ... |" \
            in markdown
        assert markdown.count("**Exercise:**") == 5
        assert markdown.count("**Solution:**") == 5
        assert "**Exercise:** Show first- and lastname plus icq number for persons having an icq number\n\n" \
            "**Solution:**\n\n```sql\nSELECT p.id, p.firstname, p.lastname, c.contact_value\n" in markdown

    def test_predefined_functions(self):
        markdown = page("SELECT: Predefined Functions")[1]
        assert "```\nfunction_name ([ALL|DISTINCT]<column name>)\nCOUNT (DISTINCT weight) -- as an example\n```" \
            in markdown
        assert "\nA Word of Caution\n" in markdown

    def test_with_clause_keeps_a_semicolon_line_in_its_code(self):
        markdown = page("with clause")[1]
        assert "SELECT ... FROM cte_1\n; -- consider the semicolon:" in markdown
        assert "**-- consider" not in markdown
