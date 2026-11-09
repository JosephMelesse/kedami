"""The passage split: every later stage refers to the reference through it. See architecture/pipeline.md."""

from kedami_server.generation.ingest import KEEP, TRANSCRIBE, RoutedPage
from kedami_server.generation.passages import split_passages


def page(markdown, number=1, route=KEEP, file="notes.pdf", role="reference"):
    return RoutedPage(file=file, role=role, page=number, route=route, reason="", markdown=markdown)


def texts(markdown, route=KEEP):
    return [p.text for p in split_passages([page(markdown, route=route)])]


def test_text_between_blank_lines_is_a_passage():
    assert texts("# Lenses\n\nFirst line\nsecond line.\n\n   \n\nNext.") == ["# Lenses", "First line\nsecond line.", "Next."]


def test_numbers_run_through_the_whole_reference_with_file_and_page():
    passages = split_passages([page("One.\n\nTwo.", 1), page("Three.", 2), page("Four.", 1, file="more.pdf")])
    assert [(p.number, p.kind, p.file, p.page, p.text) for p in passages] == [
        (1, "text", "notes.pdf", 1, "One."),
        (2, "text", "notes.pdf", 1, "Two."),
        (3, "text", "notes.pdf", 2, "Three."),
        (4, "text", "more.pdf", 1, "Four."),
    ]


def test_blank_pages_and_problem_set_pages_add_nothing():
    pages = [page("  \n\n "), page("Problem 1.", role="problem_set"), page("Kept.", 3)]
    assert [(p.number, p.page) for p in split_passages(pages)] == [(1, 3)]


def test_a_page_marker_is_not_a_passage():
    assert texts("Body.") == ["Body."]
    assert all("notes.pdf, page" not in p.text for p in split_passages([page("Body.")]))


def test_a_paragraph_across_a_page_break_becomes_two():
    passages = split_passages([page("It starts here and", 1), page("ends here.", 2)])
    assert [(p.page, p.text) for p in passages] == [(1, "It starts here and"), (2, "ends here.")]


def test_a_fenced_code_block_stays_whole():
    code = "```python\nx = 1\n\n\ny = 2\n```"
    assert texts(f"Before.\n\n{code}\n\nAfter.") == ["Before.", code, "After."]


def test_a_fence_opened_with_tildes_only_closes_with_tildes():
    code = "~~~\n```\n\nstill code\n~~~"
    assert texts(f"{code}\n\nAfter.") == [code, "After."]


def test_a_longer_fence_isnt_closed_by_a_shorter_one():
    code = "````\n```\n\nstill code\n````"
    assert texts(f"{code}\n\nAfter.") == [code, "After."]


def test_a_math_block_stays_whole():
    math = "$$\nx = 1\n\ny = 2\n$$"
    assert texts(f"Before.\n\n{math}\n\nAfter.") == ["Before.", math, "After."]


def test_math_on_one_line_doesnt_open_a_block():
    assert texts("$$ x = 1 $$\n\nAfter.") == ["$$ x = 1 $$", "After."]


def test_a_math_block_stays_with_the_text_touching_it():
    joined = "So:\n$$\nx = 1\n\ny = 2\n$$\nwhich gives y."
    assert texts(f"{joined}\n\nAfter.") == [joined, "After."]


def test_math_inside_code_isnt_math():
    code = "```\n$$\n```"
    assert texts(f"{code}\n\nAfter.") == [code, "After."]


def test_code_inside_math_isnt_code():
    math = "$$\n```\n$$"
    assert texts(f"{math}\n\nAfter.") == [math, "After."]


def test_a_block_left_open_runs_to_the_end_of_its_page_and_loses_nothing():
    passages = split_passages([page("```\nx = 1\n\ny = 2", 1), page("Next page.", 2)])
    assert [p.text for p in passages] == ["```\nx = 1\n\ny = 2", "Next page."]


def test_a_whole_list_stays_in_one_passage():
    items = "- One\n\n- Two\n  more of two\n\n    indented, still two\n\n- Three"
    assert texts(f"Before.\n\n{items}\n\nAfter.") == ["Before.", items, "After."]


def test_a_numbered_list_stays_in_one_passage():
    items = "1. One\n\n2) Two\n\n3. Three"
    assert texts(f"{items}\n\nAfter.") == [items, "After."]


def test_a_list_stays_with_the_line_that_introduces_it():
    items = "These:\n- One\n\n- Two"
    assert texts(f"{items}\n\nAfter.") == [items, "After."]


def test_emphasis_at_the_start_of_a_line_isnt_a_list():
    assert texts("*One* thing.\n\n*Two* things.") == ["*One* thing.", "*Two* things."]
    assert texts("**One**\n\n**Two**") == ["**One**", "**Two**"]


def test_a_paragraph_starting_with_a_number_only_joins_a_list():
    assert texts("Before.\n\n1. One") == ["Before.", "1. One"]
    assert texts("3.5 is the index.\n\n4.0 is not.") == ["3.5 is the index.", "4.0 is not."]


def test_an_indented_line_after_a_paragraph_isnt_a_list():
    assert texts("Before.\n\n    Indented.") == ["Before.", "    Indented."]


def test_a_table_stays_whole():
    table = "| a | b |\n|---|---|\n| 1 | 2 |\n\n| 3 | 4 |"
    assert texts(f"Before.\n\n{table}\n\nAfter.") == ["Before.", table, "After."]


def test_a_figure_line_on_a_transcribed_page_is_a_note():
    passages = split_passages([page("Before.\n[Figure: a thin lens]\nAfter.", route=TRANSCRIBE)])
    assert [(p.kind, p.text) for p in passages] == [
        ("text", "Before."),
        ("note", "[Figure: a thin lens]"),
        ("text", "After."),
    ]


def test_a_figure_line_ends_a_list_but_loses_nothing():
    passages = split_passages([page("- One\n\n[Figure: a lens]\n\n- Two", route=TRANSCRIBE)])
    assert [p.text for p in passages] == ["- One", "[Figure: a lens]", "- Two"]


def test_a_figure_line_on_a_kept_page_is_the_page_s_own_text():
    assert [p.kind for p in split_passages([page("[Figure: see the book]")])] == ["text"]


def test_a_figure_mentioned_inside_a_line_stays_text():
    passages = split_passages([page("As in [Figure: a lens], the rays meet.", route=TRANSCRIBE)])
    assert [p.kind for p in passages] == ["text"]


def test_a_figure_line_inside_code_stays_code():
    code = "```\n[Figure: a lens]\n```"
    passages = split_passages([page(code, route=TRANSCRIBE)])
    assert [(p.kind, p.text) for p in passages] == [("text", code)]


def test_windows_line_ends_split_the_same_way():
    assert texts("One.\r\n\r\nTwo.\r\nmore") == ["One.", "Two.\nmore"]


def test_no_line_is_lost_or_moved():
    markdown = (
        "# Title\n\nPara one\nwraps.\n\n- a\n\n- b\n\nPara two.\n[Figure: f]\nPara three.\n\n"
        "$$\nx\n\ny\n$$\n\n```\ncode\n\nmore\n```\n\n| t |\n\n| u |\n\nEnd."
    )
    lines = [line for line in markdown.split("\n") if line.strip()]
    passages = split_passages([page(markdown, route=TRANSCRIBE)])
    assert [line for p in passages for line in p.text.split("\n") if line.strip()] == lines
    assert [p.number for p in passages] == list(range(1, len(passages) + 1))


def test_the_same_pages_always_split_the_same_way():
    pages = [page("One.\n\n- a\n\n- b\n\nTwo.", 1), page("Three.", 2)]
    assert split_passages(pages) == split_passages(pages)
