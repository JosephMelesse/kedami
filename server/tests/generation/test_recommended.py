"""Reading a SQL chapter lesson's recommended problems. See architecture/sql-lessons.md, In a lesson."""

import pytest

from kedami_server.generation.leetcode import ConceptMapError, ProblemListError
from kedami_server.generation.recommended import bank_databases, build_extraction, parse_recommended
from kedami_server.generation.schemas import ConceptMap
from kedami_server.lesson import ExternalAnswer, QueryAnswer
from kedami_server.practice import Exercise

BANK = [
    Exercise("music-1", "music", "List every singer's name.", "SELECT name FROM singer", frozenset({"selecting"})),
    Exercise("music-2", "music", "Singers by age?", "SELECT name FROM singer ORDER BY age",
             frozenset({"selecting", "sorting"})),
    Exercise("zoo-1", "zoo", "Which animals have 4 legs?", "SELECT name FROM animal WHERE legs = 4",
             frozenset({"selecting", "filtering"})),
]


def concept_map(*numbers):
    return ConceptMap.model_validate({
        "concepts": [{"id": "where", "name": "WHERE", "summary": "Filtering rows."}],
        "problems": [{"number": n, "concepts": ["where"]} for n in numbers],
    })


class TestParse:
    def test_spider_and_pgexercises_problems(self):
        problems = parse_recommended("1. spider:music-2 Singers by age?\n2. pgexercises:joins/self2.html Members\n", BANK)
        assert [p.number for p in problems] == [1, 2]
        assert [p.source_ref for p in problems] == ["Problem 1", "Problem 2"]
        assert problems[0].answer == QueryAnswer(
            kind="query", database="bank/music", reference="SELECT name FROM singer ORDER BY age", ordered=True,
            exercise="music-2",
        )
        assert problems[1].answer == ExternalAnswer(
            kind="external", platform="pgexercises", path="joins/self2.html",
            title="Produce a list of all members, along with their recommender",
        )

    def test_the_text_comes_from_the_bank_and_the_page_not_the_line(self):
        problems = parse_recommended("1. spider:music-1 something else\n2. pgexercises:joins/self.html\n", BANK)
        assert problems[0].text == "List every singer's name."
        assert problems[1].text == 'Solve "Produce a list of all members who have recommended another member" on pgexercises.'

    def test_blank_lines_headings_and_page_markers_are_ignored(self):
        text = "# Recommended problems\n\n[problems.md, page 1]\n1. spider:music-1 a\n\n2. spider:zoo-1 b\n"
        assert [p.number for p in parse_recommended(text, BANK)] == [1, 2]

    @pytest.mark.parametrize(
        "text, message",
        [
            ("1. spider:music-1 a\n3. spider:zoo-1 b", "line 2 is problem 3, but the next problem is 2"),
            ("2. spider:music-1 a", "line 1 is problem 2, but the next problem is 1"),
            ("1. spider:music-1 a\n2. spider:music-1 a", "line 2 repeats problem 1"),
            ("1. spider:music-9 a", "names a spider exercise Kedami doesn't have: 'music-9'"),
            ("1. pgexercises:basic/selectall.html a", "names a pgexercises page Kedami doesn't have"),
            ("1. pgexercises:../etc/passwd a", "names a pgexercises page Kedami doesn't have"),
            ("1. leetcode:two-sum a", "line 1 isn't a recommended problem"),
            ("1. Two Sum", "line 1 isn't a recommended problem"),
            ("1 spider:music-1 a", "line 1 isn't a recommended problem"),
            ("1. spider: music-1", "line 1 isn't a recommended problem"),
        ],
    )
    def test_a_bad_line_is_refused_with_its_reason(self, text, message):
        with pytest.raises(ProblemListError, match="can't be read") as error:
            parse_recommended(text, BANK)
        assert message in str(error.value)

    def test_every_bad_line_is_named(self):
        with pytest.raises(ProblemListError) as error:
            parse_recommended("1. spider:nope a\nx\n", BANK)
        assert "line 1" in str(error.value) and "line 2" in str(error.value)

    def test_one_bad_line_doesnt_make_the_later_numbers_wrong(self):
        with pytest.raises(ProblemListError) as error:
            parse_recommended("1. spider:nope a\n2. spider:music-1 b\n3. spider:zoo-1 c", BANK)
        assert "line 1" in str(error.value)
        assert "line 2" not in str(error.value) and "line 3" not in str(error.value)

    def test_an_empty_list_is_refused(self):
        with pytest.raises(ProblemListError, match="at least one"):
            parse_recommended("# Recommended problems\n\n", BANK)

    def test_at_most_ten_problems(self):
        pages = ["date/timestamp", "date/interval", "date/series", "date/extract", "date/interval2",
                 "date/daysinmonth", "date/daysremaining", "date/endtimes", "date/bookingspermonth",
                 "date/utilisationpermonth"]
        text = "\n".join(f"{n}. pgexercises:{path}.html t" for n, path in enumerate(pages, start=1))
        assert len(parse_recommended(text, BANK)) == 10
        with pytest.raises(ProblemListError, match="at most 10"):
            parse_recommended(text + "\n11. pgexercises:basic/date.html t", BANK)

    def test_with_nothing_imported_spider_problems_are_unknown(self):
        with pytest.raises(ProblemListError, match="spider exercise"):
            parse_recommended("1. spider:music-1 a", [])
        assert len(parse_recommended("1. pgexercises:joins/self.html a", [])) == 1


def test_bank_databases_are_named_once_in_order():
    text = "1. spider:zoo-1 a\n2. pgexercises:joins/self.html b\n3. spider:music-1 c\n4. spider:music-2 d"
    problems = parse_recommended(text, BANK)
    assert bank_databases(problems) == ["bank/zoo", "bank/music"]


class TestExtraction:
    problems = staticmethod(lambda: parse_recommended("1. spider:music-1 a\n2. pgexercises:joins/self.html b", BANK))

    def test_problems_with_the_models_concepts_and_the_servers_answers(self):
        problems = self.problems()
        extraction = build_extraction(problems, concept_map(1, 2))
        assert [(p.source_ref, p.parts[0].label, p.parts[0].prompt, p.concepts) for p in extraction.problems] == [
            ("Problem 1", "1", "List every singer's name.", ["where"]),
            ("Problem 2", "2", 'Solve "Produce a list of all members who have recommended another member" on pgexercises.',
             ["where"]),
        ]
        assert extraction.answers == {"problem-1": problems[0].answer, "problem-2": problems[1].answer}

    @pytest.mark.parametrize("numbers, message", [
        ((1,), "problems missing: 2"),
        ((1, 2, 2), "more than once: 2"),
        ((1, 2, 3), "aren't in the list: 3"),
    ])
    def test_a_concept_map_that_doesnt_cover_each_problem_once_is_sent_back(self, numbers, message):
        with pytest.raises(ConceptMapError, match=message):
            build_extraction(self.problems(), concept_map(*numbers))
