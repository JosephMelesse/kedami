"""Lesson format. These models are the source of truth for lesson JSON.

See architecture/lesson-format.md.
"""

from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    WithJsonSchema,
    field_validator,
    model_validator,
)

from .ids import ID_PATTERN, slugify
from .mathparse import parse_math

MAX_HINTS = 3

Id = Annotated[str, StringConstraints(pattern=ID_PATTERN)]
Hints = Annotated[list[str], Field(max_length=MAX_HINTS)]
# A plain array schema, since tuple schemas don't survive conversion to TypeScript.
Range = Annotated[
    tuple[float, float],
    WithJsonSchema({"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2}),
]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)


def _check_math(value: str, allowed_symbols: set[str] | None = None) -> str:
    parse_math(value, allowed_symbols)
    return value


# Answer kinds


class NumericAnswer(Model):
    kind: Literal["numeric"]
    value: float
    rel_tolerance: float = Field(default=0.01, gt=0)
    unit: str | None = None


class ExpressionAnswer(Model):
    kind: Literal["expression"]
    expression: str

    @field_validator("expression")
    @classmethod
    def parses(cls, value: str) -> str:
        return _check_math(value)


class SelfCheckAnswer(Model):
    kind: Literal["self_check"]
    rubric: str


class ChoiceAnswer(Model):
    kind: Literal["choice"]
    options: Annotated[list[str], Field(min_length=2)]
    correct_index: int

    @model_validator(mode="after")
    def index_in_range(self) -> "ChoiceAnswer":
        if not 0 <= self.correct_index < len(self.options):
            raise ValueError("correct_index is out of range")
        return self


class MultiChoiceAnswer(Model):
    kind: Literal["multi_choice"]
    options: Annotated[list[str], Field(min_length=2)]
    correct_indexes: Annotated[list[int], Field(min_length=1)]

    @model_validator(mode="after")
    def indexes_valid(self) -> "MultiChoiceAnswer":
        if len(set(self.correct_indexes)) != len(self.correct_indexes):
            raise ValueError("correct_indexes has duplicates")
        if any(not 0 <= i < len(self.options) for i in self.correct_indexes):
            raise ValueError("correct_indexes is out of range")
        return self


Answer = Annotated[
    NumericAnswer | ExpressionAnswer | SelfCheckAnswer | ChoiceAnswer | MultiChoiceAnswer,
    Field(discriminator="kind"),
]


# Blocks


class ExplanationBlock(Model):
    type: Literal["explanation"]
    id: Id
    body: str


class WorkedExampleBlock(Model):
    type: Literal["worked_example"]
    id: Id
    prompt: str
    steps: Annotated[list[str], Field(min_length=1)]


class PlotFunction(Model):
    expression: str
    label: str


class PlotParameter(Model):
    name: Annotated[str, StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9_]*$")]
    min: float
    max: float
    default: float

    @model_validator(mode="after")
    def default_in_range(self) -> "PlotParameter":
        if not self.min < self.max:
            raise ValueError("min must be less than max")
        if not self.min <= self.default <= self.max:
            raise ValueError("default must be between min and max")
        return self


def _check_range(bounds: Range) -> Range:
    if not bounds[0] < bounds[1]:
        raise ValueError("range start must be less than its end")
    return bounds


class PlotBlock(Model):
    type: Literal["plot"]
    id: Id
    functions: Annotated[list[PlotFunction], Field(min_length=1)]
    parameters: list[PlotParameter] = []
    x_domain: Range
    y_domain: Range | None = None
    caption: str

    @field_validator("x_domain", "y_domain")
    @classmethod
    def ordered(cls, value: Range | None) -> Range | None:
        return None if value is None else _check_range(value)

    @model_validator(mode="after")
    def expressions_use_known_names(self) -> "PlotBlock":
        names = [p.name for p in self.parameters]
        if len(set(names)) != len(names):
            raise ValueError("parameter names must be unique")
        if "x" in names:
            raise ValueError("'x' is the plot variable and cannot be a parameter")
        allowed = {"x", *names}
        for function in self.functions:
            _check_math(function.expression, allowed)
        return self


class DiagramBlock(Model):
    type: Literal["diagram"]
    id: Id
    svg: str
    caption: str


class SimulationBlock(Model):
    type: Literal["simulation"]
    id: Id
    code: str
    caption: str


class CheckpointBlock(Model):
    type: Literal["checkpoint"]
    id: Id
    prompt: str
    answer: Answer
    hints: Hints = []
    verified: bool = False


def _derive_id(data: Any, source_field: str) -> Any:
    """Fill a missing id from `source_field`, or reject an id that doesn't match it."""
    if not isinstance(data, dict) or not isinstance(data.get(source_field), str):
        return data
    derived = slugify(data[source_field])
    if "id" not in data:
        return {**data, "id": derived}
    if data["id"] != derived:
        raise ValueError(f"id {data['id']!r} does not match {source_field} (expected {derived!r})")
    return data


class Part(Model):
    id: Id
    label: str
    prompt: str
    answer: Answer
    hints: Hints = []
    verified: bool = False

    @model_validator(mode="before")
    @classmethod
    def id_from_label(cls, data: Any) -> Any:
        return _derive_id(data, "label")


class ProblemBlock(Model):
    type: Literal["problem"]
    id: Id
    source_ref: str
    prompt: str = ""
    parts: Annotated[list[Part], Field(min_length=1)]

    @model_validator(mode="before")
    @classmethod
    def id_from_source_ref(cls, data: Any) -> Any:
        return _derive_id(data, "source_ref")

    @model_validator(mode="after")
    def part_ids_unique(self) -> "ProblemBlock":
        ids = [part.id for part in self.parts]
        if len(set(ids)) != len(ids):
            raise ValueError("part labels must give unique ids")
        return self


Block = Annotated[
    ExplanationBlock
    | WorkedExampleBlock
    | PlotBlock
    | DiagramBlock
    | SimulationBlock
    | CheckpointBlock
    | ProblemBlock,
    Field(discriminator="type"),
]


# Lesson


class Section(Model):
    id: Id
    title: str
    goal: str
    blocks: list[Block]


class Lesson(Model):
    schema_version: Literal[1]
    id: Id
    title: str
    subject: Literal["math", "physics"]
    source_files: list[str]
    sections: Annotated[list[Section], Field(min_length=1)]

    @model_validator(mode="after")
    def ids_unique(self) -> "Lesson":
        section_ids = [section.id for section in self.sections]
        if len(set(section_ids)) != len(section_ids):
            raise ValueError("section ids must be unique")
        block_ids = [block.id for section in self.sections for block in section.blocks]
        duplicates = sorted({i for i in block_ids if block_ids.count(i) > 1})
        if duplicates:
            raise ValueError(f"block ids must be unique within a lesson: {', '.join(duplicates)}")
        return self

    def find_block(self, block_id: str) -> Block | None:
        for section in self.sections:
            for block in section.blocks:
                if block.id == block_id:
                    return block
        return None
