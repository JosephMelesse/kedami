import { useId, useState } from 'react'
import { Markdown } from '../Markdown'
import type { Answer, ChoiceAnswer, MultiChoiceAnswer } from '../types'

// Inputs for each answer kind. Checking arrives in build step 2, so the action is disabled.
export function AnswerInput({ answer }: { answer: Answer }) {
  switch (answer.kind) {
    case 'numeric':
      return <TextAnswer inputMode="decimal" placeholder="Number" unit={answer.unit} />
    case 'expression':
      return <TextAnswer placeholder="Expression" unit={null} />
    case 'self_check':
      return <Action label="Show rubric" />
    case 'choice':
      return <ChoiceInput answer={answer} />
    case 'multi_choice':
      return <MultiChoiceInput answer={answer} />
  }
}

function Action({ label = 'Check' }: { label?: string }) {
  return (
    <div className="answer-actions">
      <button type="button" className="button button-primary" disabled>
        {label}
      </button>
    </div>
  )
}

interface TextAnswerProps {
  placeholder: string
  unit: string | null
  inputMode?: 'decimal'
}

function TextAnswer({ placeholder, unit, inputMode }: TextAnswerProps) {
  const [value, setValue] = useState('')
  return (
    <div className="answer-row">
      <input
        className="text-input"
        type="text"
        inputMode={inputMode}
        spellCheck={false}
        placeholder={placeholder}
        aria-label={placeholder}
        value={value}
        onChange={(event) => setValue(event.target.value)}
      />
      {unit && <span className="unit">{unit}</span>}
      <Action />
    </div>
  )
}

function ChoiceInput({ answer }: { answer: ChoiceAnswer }) {
  const name = useId()
  const [selected, setSelected] = useState<number | null>(null)
  return (
    <>
      <fieldset className="options">
        {answer.options.map((option, index) => (
          <label key={index} className="option">
            <input type="radio" name={name} checked={selected === index} onChange={() => setSelected(index)} />
            <Markdown inline>{option}</Markdown>
          </label>
        ))}
      </fieldset>
      <Action />
    </>
  )
}

function MultiChoiceInput({ answer }: { answer: MultiChoiceAnswer }) {
  const [selected, setSelected] = useState<ReadonlySet<number>>(new Set())
  const toggle = (index: number) => {
    const next = new Set(selected)
    if (next.has(index)) next.delete(index)
    else next.add(index)
    setSelected(next)
  }
  return (
    <>
      <fieldset className="options">
        {answer.options.map((option, index) => (
          <label key={index} className="option">
            <input type="checkbox" checked={selected.has(index)} onChange={() => toggle(index)} />
            <Markdown inline>{option}</Markdown>
          </label>
        ))}
      </fieldset>
      <Action />
    </>
  )
}
