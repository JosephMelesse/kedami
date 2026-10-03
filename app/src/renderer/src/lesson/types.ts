/* Generated from server/schema/lesson.schema.json by `npm run gen:types`. Do not edit. */

export type SchemaVersion = 1;
export type Id = string;
export type Title = string;
export type Subject = "math" | "physics";
export type SourceFiles = string[];
/**
 * @minItems 1
 */
export type Sections = [Section, ...Section[]];
export type Id1 = string;
export type Title1 = string;
export type Goal = string;
export type Type = "explanation";
export type Id2 = string;
export type Body = string;
export type Type1 = "worked_example";
export type Id3 = string;
export type Prompt = string;
/**
 * @minItems 1
 */
export type Steps = [string, ...string[]];
export type Type2 = "plot";
export type Id4 = string;
/**
 * @minItems 1
 */
export type Functions = [PlotFunction, ...PlotFunction[]];
export type Expression = string;
export type Label = string;
export type Name = string;
export type Min = number;
export type Max = number;
export type Default = number;
export type Parameters = PlotParameter[];
/**
 * @minItems 2
 * @maxItems 2
 */
export type XDomain = [number, number];
export type YDomain = [number, number] | null;
export type Caption = string;
export type Type3 = "diagram";
export type Id5 = string;
export type Svg = string;
export type Caption1 = string;
export type Type4 = "simulation";
export type Id6 = string;
export type Code = string;
export type Caption2 = string;
export type Type5 = "checkpoint";
export type Id7 = string;
export type Prompt1 = string;
export type Answer = NumericAnswer | ExpressionAnswer | SelfCheckAnswer | ChoiceAnswer | MultiChoiceAnswer;
export type Kind = "numeric";
export type Value = number;
export type RelTolerance = number;
export type Unit = string | null;
export type Kind1 = "expression";
export type Expression1 = string;
export type Kind2 = "self_check";
export type Rubric = string;
export type Kind3 = "choice";
/**
 * @minItems 2
 */
export type Options = [string, string, ...string[]];
export type CorrectIndex = number;
export type Kind4 = "multi_choice";
/**
 * @minItems 2
 */
export type Options1 = [string, string, ...string[]];
/**
 * @minItems 1
 */
export type CorrectIndexes = [number, ...number[]];
/**
 * @maxItems 3
 */
export type Hints = [] | [string] | [string, string] | [string, string, string];
export type Verified = boolean;
export type Type6 = "problem";
export type Id8 = string;
export type SourceRef = string;
export type Prompt2 = string;
/**
 * @minItems 1
 */
export type Parts = [Part, ...Part[]];
export type Id9 = string;
export type Label1 = string;
export type Prompt3 = string;
export type Answer1 = NumericAnswer | ExpressionAnswer | SelfCheckAnswer | ChoiceAnswer | MultiChoiceAnswer;
/**
 * @maxItems 3
 */
export type Hints1 = [] | [string] | [string, string] | [string, string, string];
export type Verified1 = boolean;
export type Blocks = (
  ExplanationBlock | WorkedExampleBlock | PlotBlock | DiagramBlock | SimulationBlock | CheckpointBlock | ProblemBlock
)[];

export interface Lesson {
  schema_version: SchemaVersion;
  id: Id;
  title: Title;
  subject: Subject;
  source_files: SourceFiles;
  sections: Sections;
}
/**
 * This interface was referenced by `Lesson`'s JSON-Schema
 * via the `definition` "Section".
 */
export interface Section {
  id: Id1;
  title: Title1;
  goal: Goal;
  blocks: Blocks;
}
/**
 * This interface was referenced by `Lesson`'s JSON-Schema
 * via the `definition` "ExplanationBlock".
 */
export interface ExplanationBlock {
  type: Type;
  id: Id2;
  body: Body;
}
/**
 * This interface was referenced by `Lesson`'s JSON-Schema
 * via the `definition` "WorkedExampleBlock".
 */
export interface WorkedExampleBlock {
  type: Type1;
  id: Id3;
  prompt: Prompt;
  steps: Steps;
}
/**
 * This interface was referenced by `Lesson`'s JSON-Schema
 * via the `definition` "PlotBlock".
 */
export interface PlotBlock {
  type: Type2;
  id: Id4;
  functions: Functions;
  parameters: Parameters;
  x_domain: XDomain;
  y_domain: YDomain;
  caption: Caption;
}
/**
 * This interface was referenced by `Lesson`'s JSON-Schema
 * via the `definition` "PlotFunction".
 */
export interface PlotFunction {
  expression: Expression;
  label: Label;
}
/**
 * This interface was referenced by `Lesson`'s JSON-Schema
 * via the `definition` "PlotParameter".
 */
export interface PlotParameter {
  name: Name;
  min: Min;
  max: Max;
  default: Default;
}
/**
 * This interface was referenced by `Lesson`'s JSON-Schema
 * via the `definition` "DiagramBlock".
 */
export interface DiagramBlock {
  type: Type3;
  id: Id5;
  svg: Svg;
  caption: Caption1;
}
/**
 * This interface was referenced by `Lesson`'s JSON-Schema
 * via the `definition` "SimulationBlock".
 */
export interface SimulationBlock {
  type: Type4;
  id: Id6;
  code: Code;
  caption: Caption2;
}
/**
 * This interface was referenced by `Lesson`'s JSON-Schema
 * via the `definition` "CheckpointBlock".
 */
export interface CheckpointBlock {
  type: Type5;
  id: Id7;
  prompt: Prompt1;
  answer: Answer;
  hints: Hints;
  verified: Verified;
}
/**
 * This interface was referenced by `Lesson`'s JSON-Schema
 * via the `definition` "NumericAnswer".
 */
export interface NumericAnswer {
  kind: Kind;
  value: Value;
  rel_tolerance: RelTolerance;
  unit: Unit;
}
/**
 * This interface was referenced by `Lesson`'s JSON-Schema
 * via the `definition` "ExpressionAnswer".
 */
export interface ExpressionAnswer {
  kind: Kind1;
  expression: Expression1;
}
/**
 * This interface was referenced by `Lesson`'s JSON-Schema
 * via the `definition` "SelfCheckAnswer".
 */
export interface SelfCheckAnswer {
  kind: Kind2;
  rubric: Rubric;
}
/**
 * This interface was referenced by `Lesson`'s JSON-Schema
 * via the `definition` "ChoiceAnswer".
 */
export interface ChoiceAnswer {
  kind: Kind3;
  options: Options;
  correct_index: CorrectIndex;
}
/**
 * This interface was referenced by `Lesson`'s JSON-Schema
 * via the `definition` "MultiChoiceAnswer".
 */
export interface MultiChoiceAnswer {
  kind: Kind4;
  options: Options1;
  correct_indexes: CorrectIndexes;
}
/**
 * This interface was referenced by `Lesson`'s JSON-Schema
 * via the `definition` "ProblemBlock".
 */
export interface ProblemBlock {
  type: Type6;
  id: Id8;
  source_ref: SourceRef;
  prompt: Prompt2;
  parts: Parts;
}
/**
 * This interface was referenced by `Lesson`'s JSON-Schema
 * via the `definition` "Part".
 */
export interface Part {
  id: Id9;
  label: Label1;
  prompt: Prompt3;
  answer: Answer1;
  hints: Hints1;
  verified: Verified1;
}
