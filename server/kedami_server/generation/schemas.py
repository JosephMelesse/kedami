"""What each generation stage asks the model to return.

Lesson IDs, problem text, hints, and the verified flag are not in these schemas: the
server derives IDs, copies problem text verbatim from extraction, generates hints in a
later call, and sets verified only in the verification pass.
"""

from typing import Annotated, Literal

from pydantic import Field, PrivateAttr, TypeAdapter, ValidationError, field_validator, model_validator

from ..ids import slugify
from ..lesson import MAX_HINTS, Answer, ExternalAnswer, Model, PlotFunction, PlotParameter, Range

# Stage 1: ingestion


class PageCheck(Model):
    page: int
    clean: bool


class TextChecks(Model):
    pages: list[PageCheck]


class Transcription(Model):
    markdown: str = Field(description="The page as Markdown with LaTeX. Empty if the page is blank.")


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


class ProblemsAndConcepts(Model):
    """What the extraction call returns for a math or physics lesson."""

    concepts: list[Concept]
    problems: Annotated[list[ExtractedProblem], Field(min_length=1)]

    @model_validator(mode="after")
    def references_are_consistent(self) -> "ProblemsAndConcepts":
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


class Extraction(ProblemsAndConcepts):
    """The stage 2 output saved to disk and used by later stages."""

    # Problems solved on another site, keyed by problem ID. The server sets these for
    # computer science lessons; the model never writes them.
    externals: dict[str, ExternalAnswer] = {}

    @model_validator(mode="after")
    def externals_name_problems(self) -> "Extraction":
        unknown = set(self.externals) - {slugify(p.source_ref) for p in self.problems}
        if unknown:
            raise ValueError(f"external answers for unknown problems: {', '.join(sorted(unknown))}")
        return self


class ProblemConcepts(Model):
    number: int = Field(description="The LeetCode problem number exactly as given.")
    concepts: list[str] = Field(description="IDs of the concepts a student needs to solve this problem.")


class ConceptMap(Model):
    """What the extraction call returns for a computer science lesson. The server lists the problems."""

    concepts: list[Concept]
    problems: list[ProblemConcepts]

    @model_validator(mode="after")
    def references_are_consistent(self) -> "ConceptMap":
        concept_ids = [c.id for c in self.concepts]
        _require_unique(concept_ids, "concept ids")
        for problem in self.problems:
            unknown = set(problem.concepts) - set(concept_ids)
            if unknown:
                raise ValueError(f"problem {problem.number} needs unknown concepts: {', '.join(sorted(unknown))}")
        return self


def _require_unique(values: list[str], what: str) -> None:
    duplicates = sorted({v for v in values if values.count(v) > 1})
    if duplicates:
        raise ValueError(f"{what} must be unique; repeated: {', '.join(duplicates)}")


# Stage 3: plan


class PlannedSection(Model):
    title: str
    goal: str = Field(description="One line: what the student can do after this section.")
    concepts: list[str] = Field(description="IDs of the concepts this section introduces, in teaching order.")
    simulation: str | None = Field(
        default=None,
        description="A one-line brief for an interactive simulation, only where one would teach something a static "
        "plot or diagram can't. Otherwise null.",
    )


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


class SimulationDraft(Model):
    """Marks where the section's simulation goes. Its code is written by a separate call."""

    type: Literal["simulation"]
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
    ExplanationDraft | WorkedExampleDraft | PlotDraft | DiagramDraft | SimulationDraft | CheckpointDraft | ProblemDraft,
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

    type: Literal["explanation", "worked_example", "plot", "diagram", "simulation", "checkpoint", "problem"]
    body: str | None = Field(default=None, description="explanation")
    prompt: str | None = Field(default=None, description="worked_example, checkpoint")
    steps: list[str] | None = Field(default=None, description="worked_example")
    functions: list[PlotFunction] | None = Field(default=None, description="plot")
    parameters: list[PlotParameter] | None = Field(default=None, description="plot: sliders, or an empty list")
    x_domain: list[float] | None = Field(default=None, description="plot: [min, max]")
    y_domain: list[float] | None = Field(default=None, description="plot: [min, max], or null for automatic")
    svg: str | None = Field(default=None, description="diagram")
    caption: str | None = Field(default=None, description="plot, diagram, simulation")
    answer: AnswerDraft | None = Field(default=None, description="checkpoint")
    source_ref: str | None = Field(default=None, description="problem")
    parts: list[PartDraft] | None = Field(default=None, description="problem: an answer for every part")
    _typed: (
        ExplanationDraft | WorkedExampleDraft | PlotDraft | DiagramDraft | SimulationDraft | CheckpointDraft | ProblemDraft
    ) = PrivateAttr()

    @model_validator(mode="after")
    def convert(self) -> "BlockDraft":
        names = {
            "explanation": ("body",),
            "worked_example": ("prompt", "steps"),
            "plot": ("functions", "parameters", "x_domain", "y_domain", "caption"),
            "diagram": ("svg", "caption"),
            "simulation": ("caption",),
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
    def typed(
        self,
    ) -> ExplanationDraft | WorkedExampleDraft | PlotDraft | DiagramDraft | SimulationDraft | CheckpointDraft | ProblemDraft:
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


# Verification


class FinalAnswer(Model):
    """A final answer, flat. Fill the field for the requested format and leave the others null."""

    value: float | None = Field(default=None, description="number: the answer in the unit given.")
    expression: str | None = Field(default=None, description="expression: the answer in SymPy syntax.")
    correct: list[int] | None = Field(default=None, description="choice: the one correct index; select_all: every correct index.")


class Solution(FinalAnswer):
    """One independently solved answer."""

    target: str = Field(description="The target ID exactly as given.")


class Solutions(Model):
    solutions: list[Solution]


# Solutions on request: labels and LaTeX lines, no sentences

MAX_SOLUTION_LINES = 24
MAX_SOLUTION_LINE = 600
MAX_METHOD = 80


def _latex_lines(lines: list[str], what: str, required: bool = True) -> list[str]:
    """Each line as bare LaTeX. Stray $ delimiters are removed, since the renderer adds display math itself."""
    cleaned = [line.strip().strip("$").strip() for line in lines]
    if required and not cleaned:
        raise ValueError(f"{what} needs at least one line")
    if len(cleaned) > MAX_SOLUTION_LINES:
        raise ValueError(f"{what} has more than {MAX_SOLUTION_LINES} lines")
    if any(not line for line in cleaned):
        raise ValueError(f"{what} has an empty line")
    if any(len(line) > MAX_SOLUTION_LINE for line in cleaned):
        raise ValueError(f"{what} has a line longer than {MAX_SOLUTION_LINE} characters")
    return cleaned


class MathSteps(Model):
    method: str = Field(description="The method in a few words, such as 'Integration by parts'. Plain text, no LaTeX.")
    steps: list[str] = Field(
        description="The working as LaTeX, one step per line, without $ delimiters. The last line boxes the final answer."
    )
    final: FinalAnswer

    @field_validator("method")
    @classmethod
    def short_method(cls, value: str) -> str:
        value = value.strip()
        if not value or len(value) > MAX_METHOD:
            raise ValueError(f"method must be 1 to {MAX_METHOD} characters")
        return value

    @field_validator("steps")
    @classmethod
    def lines(cls, value: list[str]) -> list[str]:
        return _latex_lines(value, "steps")


class PhysicsSteps(Model):
    given: list[str] = Field(description="Each known quantity as LaTeX, such as 'm = 2.0\\,\\mathrm{kg}'.")
    required: list[str] = Field(description="Each quantity asked for as LaTeX, such as 'v_f'.")
    steps: list[str] = Field(
        description="The solution as LaTeX, one step per line, without $ delimiters. The first line is the formula used, "
        "in symbols; the last line boxes the final answer with its unit."
    )
    final: FinalAnswer

    @field_validator("given")
    @classmethod
    def given_lines(cls, value: list[str]) -> list[str]:
        return _latex_lines(value, "given", required=False)

    @field_validator("required")
    @classmethod
    def required_lines(cls, value: list[str]) -> list[str]:
        return _latex_lines(value, "required")

    @field_validator("steps")
    @classmethod
    def lines(cls, value: list[str]) -> list[str]:
        return _latex_lines(value, "steps")


# Simulations

MAX_SIMULATION_CODE = 40_000


class SimulationCode(Model):
    code: str = Field(description="The body of the simulation function, in plain JavaScript.")

    @model_validator(mode="after")
    def usable(self) -> "SimulationCode":
        if not self.code.strip():
            raise ValueError("the code is empty")
        if len(self.code) > MAX_SIMULATION_CODE:
            raise ValueError(f"the code is longer than {MAX_SIMULATION_CODE} characters")
        if "ready(" not in self.code:
            raise ValueError("the code never calls ready()")
        return self
