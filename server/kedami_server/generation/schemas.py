"""What each generation stage asks the model to return.

Lesson IDs, problem text, hints, and the verified flag are not in these schemas: the
server derives IDs, copies problem text verbatim from extraction, generates hints in a
later call, and sets verified only in the verification pass.
"""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from ..ids import slugify
from ..lesson import MAX_HINTS, Answer, Model, PlotFunction, PlotParameter, Range

# Stage 2: extraction


class Concept(Model):
    id: str = Field(description="Short unique identifier, such as 'projectile-components'.")
    name: str
    summary: str = Field(description="One or two sentences on what the concept covers.")


class ExtractedPart(Model):
    label: str = Field(description="The part label as written, such as '(a)'. For a problem with no parts, its number.")
    prompt: str = Field(description="The part's text, verbatim, as Markdown with LaTeX.")


class ExtractedProblem(Model):
    source_ref: str = Field(description="Where the problem comes from, such as 'PS3 #4'.")
    prompt: str = Field(description="Text shared by all parts, verbatim. Empty if there is none.")
    parts: Annotated[list[ExtractedPart], Field(min_length=1)]
    concepts: list[str] = Field(description="IDs of the concepts a student needs to solve this problem.")


class Extraction(Model):
    concepts: list[Concept]
    problems: Annotated[list[ExtractedProblem], Field(min_length=1)]

    @model_validator(mode="after")
    def references_are_consistent(self) -> "Extraction":
        concept_ids = [c.id for c in self.concepts]
        _require_unique(concept_ids, "concept ids")
        _require_unique([slugify(p.source_ref) for p in self.problems], "problem source references")
        for problem in self.problems:
            _require_unique([slugify(part.label) for part in problem.parts], f"part labels in {problem.source_ref}")
            unknown = set(problem.concepts) - set(concept_ids)
            if unknown:
                raise ValueError(f"{problem.source_ref} needs unknown concepts: {', '.join(sorted(unknown))}")
        return self

    def problem(self, problem_id: str) -> ExtractedProblem:
        return next(p for p in self.problems if slugify(p.source_ref) == problem_id)


def _require_unique(values: list[str], what: str) -> None:
    duplicates = sorted({v for v in values if values.count(v) > 1})
    if duplicates:
        raise ValueError(f"{what} must be unique; repeated: {', '.join(duplicates)}")


# Stage 3: plan


class PlannedSection(Model):
    title: str
    goal: str = Field(description="One line: what the student can do after this section.")
    concepts: list[str] = Field(description="IDs of the concepts this section introduces, in teaching order.")


class Plan(Model):
    title: str = Field(description="A short title for the whole lesson.")
    sections: Annotated[list[PlannedSection], Field(min_length=1)]


# Stage 4: section content


class ExplanationDraft(Model):
    type: Literal["explanation"]
    body: str


class WorkedExampleDraft(Model):
    type: Literal["worked_example"]
    prompt: str
    steps: Annotated[list[str], Field(min_length=1)]


class PlotDraft(Model):
    type: Literal["plot"]
    functions: Annotated[list[PlotFunction], Field(min_length=1)]
    parameters: list[PlotParameter] = []
    x_domain: Range
    y_domain: Range | None = None
    caption: str


class DiagramDraft(Model):
    type: Literal["diagram"]
    svg: str
    caption: str


class CheckpointDraft(Model):
    type: Literal["checkpoint"]
    prompt: str
    answer: Answer


class PartAnswerDraft(Model):
    label: str = Field(description="The part label exactly as given.")
    answer: Answer


class ProblemDraft(Model):
    """Marks where a homework problem goes, with its stored answers. Its text is inserted by the server."""

    type: Literal["problem"]
    source_ref: str
    parts: list[PartAnswerDraft]


SectionBlockDraft = Annotated[
    ExplanationDraft | WorkedExampleDraft | PlotDraft | DiagramDraft | CheckpointDraft | ProblemDraft,
    Field(discriminator="type"),
]


class SectionDraft(Model):
    blocks: Annotated[list[SectionBlockDraft], Field(min_length=1)]


# Hints


class TargetHints(Model):
    target: str = Field(description="The target ID exactly as given.")
    hints: Annotated[list[str], Field(max_length=MAX_HINTS)]


class HintDraft(Model):
    items: list[TargetHints]


class HintReplacement(Model):
    target: str
    index: int
    hint: str


class HintReplacements(Model):
    replacements: list[HintReplacement]


class HintJudgement(Model):
    target: str
    index: int
    gives_away: bool


class HintJudgements(Model):
    results: list[HintJudgement]
