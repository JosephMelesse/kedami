"""What each generation stage asks the model to return.

Lesson IDs, problem text, hints, and the verified flag are not in these schemas: the
server derives IDs, copies problem text verbatim from extraction, generates hints in a
later call, and sets verified only in the verification pass.
"""

from typing import Annotated, Literal

from pydantic import Field, PrivateAttr, TypeAdapter, ValidationError, model_validator

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
#
# The schema sent to the model is flat: one block object with a `type` and nullable
# fields, holding one answer object with a `kind`. Nested unions (6 block types, each
# answer one of 5 kinds) compile to a grammar too large for structured output. Each
# flat object converts to its typed form on validation, so a malformed reply is
# rejected with the reason and retried.


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


class PartAnswer(Model):
    label: str
    answer: Answer


class ProblemDraft(Model):
    """Marks where a homework problem goes, with its stored answers. Its text is inserted by the server."""

    type: Literal["problem"]
    source_ref: str
    parts: list[PartAnswer]


TypedBlock = Annotated[
    ExplanationDraft | WorkedExampleDraft | PlotDraft | DiagramDraft | CheckpointDraft | ProblemDraft,
    Field(discriminator="type"),
]
_ANSWER = TypeAdapter(Answer)
_BLOCK = TypeAdapter(TypedBlock)


class AnswerDraft(Model):
    """One answer, flat. Fill the fields for its kind and leave the others null."""

    kind: Literal["numeric", "expression", "self_check", "choice", "multi_choice"]
    value: float | None = Field(default=None, description="numeric: the answer in the unit given.")
    rel_tolerance: float | None = Field(default=None, description="numeric: allowed relative error, such as 0.01.")
    unit: str | None = Field(default=None, description="numeric: the unit shown beside the input, if any.")
    expression: str | None = Field(default=None, description="expression: the answer in SymPy syntax.")
    rubric: str | None = Field(default=None, description="self_check: what a full answer includes.")
    options: list[str] | None = Field(default=None, description="choice and multi_choice: the options.")
    correct: list[int] | None = Field(
        default=None, description="choice: the one correct index; multi_choice: every correct index."
    )
    _typed: Answer = PrivateAttr()

    @model_validator(mode="after")
    def convert(self) -> "AnswerDraft":
        fields: dict = {"kind": self.kind}
        match self.kind:
            case "numeric":
                fields |= {"value": self.value, "unit": self.unit}
                if self.rel_tolerance is not None:
                    fields["rel_tolerance"] = self.rel_tolerance
            case "expression":
                fields["expression"] = self.expression
            case "self_check":
                fields["rubric"] = self.rubric
            case "choice":
                if not self.correct or len(self.correct) != 1:
                    raise ValueError("a choice answer needs exactly one correct index")
                fields |= {"options": self.options, "correct_index": self.correct[0]}
            case "multi_choice":
                fields |= {"options": self.options, "correct_indexes": self.correct}
        try:
            self._typed = _ANSWER.validate_python(fields)
        except ValidationError as error:
            raise ValueError(f"invalid {self.kind} answer: {error}") from error
        return self

    @property
    def typed(self) -> Answer:
        return self._typed


class PartDraft(Model):
    label: str = Field(description="The part label exactly as given.")
    answer: AnswerDraft


class BlockDraft(Model):
    """One block, flat. Fill the fields for its type and leave the others null."""

    type: Literal["explanation", "worked_example", "plot", "diagram", "checkpoint", "problem"]
    body: str | None = Field(default=None, description="explanation")
    prompt: str | None = Field(default=None, description="worked_example, checkpoint")
    steps: list[str] | None = Field(default=None, description="worked_example")
    functions: list[PlotFunction] | None = Field(default=None, description="plot")
    parameters: list[PlotParameter] | None = Field(default=None, description="plot: sliders, or an empty list")
    x_domain: list[float] | None = Field(default=None, description="plot: [min, max]")
    y_domain: list[float] | None = Field(default=None, description="plot: [min, max], or null for automatic")
    svg: str | None = Field(default=None, description="diagram")
    caption: str | None = Field(default=None, description="plot, diagram")
    answer: AnswerDraft | None = Field(default=None, description="checkpoint")
    source_ref: str | None = Field(default=None, description="problem")
    parts: list[PartDraft] | None = Field(default=None, description="problem: an answer for every part")
    _typed: ExplanationDraft | WorkedExampleDraft | PlotDraft | DiagramDraft | CheckpointDraft | ProblemDraft = PrivateAttr()

    @model_validator(mode="after")
    def convert(self) -> "BlockDraft":
        names = {
            "explanation": ("body",),
            "worked_example": ("prompt", "steps"),
            "plot": ("functions", "parameters", "x_domain", "y_domain", "caption"),
            "diagram": ("svg", "caption"),
            "checkpoint": ("prompt",),
            "problem": ("source_ref",),
        }[self.type]
        fields = {"type": self.type} | {name: getattr(self, name) for name in names if getattr(self, name) is not None}
        if self.type == "checkpoint" and self.answer is not None:
            fields["answer"] = self.answer.typed
        if self.type == "problem" and self.parts is not None:
            fields["parts"] = [{"label": p.label, "answer": p.answer.typed} for p in self.parts]
        try:
            self._typed = _BLOCK.validate_python(fields)
        except ValidationError as error:
            raise ValueError(f"invalid {self.type} block: {error}") from error
        return self

    @property
    def typed(self) -> ExplanationDraft | WorkedExampleDraft | PlotDraft | DiagramDraft | CheckpointDraft | ProblemDraft:
        return self._typed


class SectionDraft(Model):
    blocks: Annotated[list[BlockDraft], Field(min_length=1)]


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
