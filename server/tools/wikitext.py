"""Converting the SQL book's wikitext to Markdown, for the maintainer tool fetch_sql_book.py.

Covers the markup the book's pages use: code blocks, headings, bold and italics, links, lists, definition lists,
tables, the book's exercise boxes and solution templates. Code is set aside first and put back unchanged, so
nothing inside it is read as markup. Navigation, the table of contents, comments, and images are dropped.
See architecture/sql-lessons.md, The book.
"""

import html
import re

_CODE_BLOCK = re.compile(r"<(syntaxhighlight|source|pre)\b([^>]*)>(.*?)</\1>", re.S | re.I)
_INLINE_CODE = re.compile(r"<(code|tt)>(.*?)</\1>", re.S | re.I)
_LANG = re.compile(r"""lang\s*=\s*["']?(\w+)""", re.I)


def to_markdown(wikitext: str, title: str) -> str:
    """One page as Markdown, headed by its title."""
    codes: list[str] = []

    def keep(text: str) -> str:
        codes.append(text)
        return f"\x00{len(codes) - 1}\x00"

    def block(match: re.Match) -> str:
        lang = _LANG.search(match[2])
        body = match[3].strip("\n")
        return "\n\n" + keep(f"```{lang[1].lower() if lang else ''}\n{body}\n```") + "\n\n"

    text = _CODE_BLOCK.sub(block, wikitext)
    def inline(match: re.Match) -> str:
        code = _inline_code(html.unescape(match[2]))
        return f"\n\n{keep(code)}\n\n" if code.startswith("```") else keep(code)

    text = _INLINE_CODE.sub(inline, text)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"<noinclude>.*?</noinclude>", "", text, flags=re.S | re.I)
    text = text.replace("__TOC__", "").replace("__NOTOC__", "")
    text = _templates(text)
    text = _exercise_boxes(text)
    text = re.sub(r"\[\[(?:File|Image):[^\[\]]*(?:\[\[[^\]]*\]\][^\[\]]*)*\]\]", "", text, flags=re.I)
    text = _tables(text)
    text = re.sub(r"</?div[^>]*>", "", text, flags=re.I)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</?(u|small|span|center)\b[^>]*>", "", text, flags=re.I)
    text = _links(text)
    text = _lines(text)
    text = _emphasis(text)
    text = html.unescape(text).replace("\u00a0", " ")
    # Tidied before the code goes back, so code keeps every space it was written with.
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    text = re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m[1])], text)
    return f"# {title}\n\n{text}\n"


def _inline_code(code: str) -> str:
    """Inline code; the book sometimes uses <code> for a few lines, broken with <br />, which become a block."""
    code = re.sub(r"<br\s*/?>\n?", "\n", code, flags=re.I).strip("\n")
    if "\n" in code:
        return f"```\n{code}\n```"
    fence = "``" if "`" in code else "`"
    return f"{fence}{code}{fence}"


# Templates


def _templates(text: str) -> str:
    """Solutions become a labeled block; every other template (navigation, colors, column layouts) is dropped."""
    out, i = [], 0
    while (start := text.find("{{", i)) != -1:
        end = _matching(text, start)
        out.append(text[i:start])
        inner = text[start + 2 : end - 2]
        name, _, rest = inner.partition("|")
        if name.strip() == "ExerciseSolution":
            content = re.sub(r"^\s*width\s*=[^|]*\|", "", rest)
            content = re.sub(r"^\s*text\s*=", "", content)
            out.append(f"\n\n'''Solution:'''\n\n{_templates(content).strip()}\n\n")
        i = end
    out.append(text[i:])
    return "".join(out)


def _matching(text: str, start: int) -> int:
    """The index just past the `}}` that closes the template opening at `start`."""
    depth, i = 0, start
    while i < len(text) - 1:
        pair = text[i : i + 2]
        if pair == "{{":
            depth += 1
            i += 2
        elif pair == "}}":
            depth -= 1
            i += 2
            if depth == 0:
                return i
        else:
            i += 1
    return len(text)


def _exercise_boxes(text: str) -> str:
    """The book's exercises are gold boxes: each becomes a labeled paragraph. Labels are wiki bold, which the line
    rules leave alone and the emphasis rules turn to Markdown, since a line starting "**" would read as a list."""
    return re.sub(
        r"<div[^>]*background:\s*gold[^>]*>\s*(.*?)\s*</div>",
        lambda m: f"\n\n'''Exercise:''' {m[1].strip()}\n\n",
        text,
        flags=re.S | re.I,
    )


# Tables


def _tables(text: str) -> str:
    """Wiki tables as Markdown tables. A table that only lays other tables out in columns is unwrapped."""
    lines = text.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        if lines[i].lstrip().startswith("{|"):
            end = _table_end(lines, i)
            out.extend(_table(lines[i + 1 : end]))
            i = end + 1
        elif re.fullmatch(r"\|[-}]?\s*", lines[i]):
            # Left behind by a column-layout template, which opens its table itself and is closed by a bare |}.
            i += 1
        else:
            out.append(lines[i])
            i += 1
    return "\n".join(out)


def _table_end(lines: list[str], start: int) -> int:
    depth = 0
    for j in range(start, len(lines)):
        stripped = lines[j].lstrip()
        if stripped.startswith("{|"):
            depth += 1
        elif stripped.startswith("|}"):
            depth -= 1
            if depth == 0:
                return j
    # Never closed: the table runs to the end of the page.
    return len(lines)


def _table(body: list[str]) -> list[str]:
    # A layout table holds whole tables in its cells; keep their content, without the layout.
    if any(line.lstrip().startswith("{|") for line in body):
        return [""] + _tables("\n".join(_layout_content(body))).split("\n") + [""]
    rows: list[tuple[bool, list[str]]] = []
    current: list[str] = []
    header = False
    for raw in body:
        line = raw.strip()
        if line.startswith("|+"):
            continue
        if line.startswith("|-"):
            if current:
                rows.append((header, current))
            current, header = [], False
            continue
        if line.startswith("!"):
            header = True
            current += [_cell(c) for c in re.split(r"!!|\|\|", line[1:])]
        elif line.startswith("|"):
            current += [_cell(c) for c in line[1:].split("||")]
        elif current and line:
            current[-1] += " " + line
    if current:
        rows.append((header, current))
    if not rows:
        return []
    width = max(len(cells) for _, cells in rows)
    pad = lambda cells: cells + [""] * (width - len(cells))  # noqa: E731
    head, *rest = rows if rows[0][0] else [(True, [""] * width), *rows]
    lines = ["", "| " + " | ".join(pad(head[1])) + " |", "|" + " --- |" * width]
    lines += ["| " + " | ".join(pad(cells)) + " |" for _, cells in rest]
    return lines + [""]


def _layout_content(body: list[str]) -> list[str]:
    """A layout table's lines without its own row and cell markers, keeping those of the tables inside it."""
    content, depth = [], 0
    for line in body:
        stripped = line.strip()
        if stripped.startswith("{|"):
            depth += 1
        elif stripped.startswith("|}"):
            depth -= 1
        elif depth == 0 and re.fullmatch(r"\|-?", stripped):
            continue
        content.append(line)
    return content


def _cell(cell: str) -> str:
    # A cell's attributes, if any, come before its last single "|": style=...| value.
    parts = re.split(r"(?<!\|)\|(?!\|)", cell)
    value = parts[-1] if len(parts) > 1 and "=" in parts[0] else cell
    return value.strip().replace("|", "\\|") or " "


# Links, lines, and emphasis


def _links(text: str) -> str:
    text = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]", r"\1", text)
    text = re.sub(r"\[\[([^\]]*)\]\]", lambda m: m[1].rsplit("/", 1)[-1], text)
    return re.sub(r"\[(https?://[^\s\]]+)\s+([^\]]+)\]", r"\2", text)


def _lines(text: str) -> str:
    out = []
    for line in text.split("\n"):
        if m := re.match(r"^(={2,6})\s*(.*?)\s*\1\s*$", line):
            out.append(f"\n{'#' * len(m[1])} {m[2]}\n")
        elif m := re.match(r"^([*#]+)\s*(.*)$", line):
            marker = "-" if m[1][-1] == "*" else "1."
            out.append("  " * (len(m[1]) - 1) + f"{marker} {m[2]}")
        elif m := re.match(r"^;\s*([^:]*?)\s*(?::\s*(.*))?$", line):
            out.append(f"**{m[1]}**" + (f": {m[2]}" if m[2] else ""))
        elif m := re.match(r"^:+\s*(.*)$", line):
            out.append(m[1])
        else:
            out.append(line)
    return "\n".join(out)


def _emphasis(text: str) -> str:
    text = re.sub(r"'''''(.+?)'''''", r"***\1***", text)
    text = re.sub(r"'''(.+?)'''", r"**\1**", text)
    return re.sub(r"''(.+?)''", r"*\1*", text)
