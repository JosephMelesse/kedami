import { type FormEvent, useId, useState } from 'react'
import { Markdown } from '../Markdown'
import type { Answer, ChoiceAnswer, MultiChoiceAnswer, SelfCheckAnswer } from '../types'

interface InputProps<A> {
  answer: A
  /** The last submitted response, used to restore the input. */
  initial: unknown
  /** True once the part is done; the input is read-only. */
  locked: boolean
  onSubmit: (response: unknown) => Promise<void>
}

export function AnswerInput(props: InputProps<Answer>) {
  const { answer } = props
  switch (answer.kind) {
    case 'numeric':
      return <TextAnswer {...props} inputMode="decimal" placeholder="Number" unit={answer.unit} />
    case 'expression':
      return <TextAnswer {...props} placeholder="Expression" unit={null} />
    case 'self_check':
      return <SelfCheckInput {...props} answer={answer} />
    case 'choice':
      return <ChoiceInput {...props} answer={answer} />
    case 'multi_choice':
      return <MultiChoiceInput {...props} answer={answer} />
  }
}

/** Tracks an in-flight submission so the action can't be sent twice. */
function useSubmit(onSubmit: (response: unknown) => Promise<void>) {
  const [pending, setPending] = useState(false)
  const submit = async (response: unknown) => {
    setPending(true)
    try {
      await onSubmit(response)
    } finally {
      setPending(false)
    }
  }
  return { pending, submit }
}

interface TextAnswerProps extends InputProps<Answer> {
  placeholder: string
  unit: string | null
  inputMode?: 'decimal'
}

function TextAnswer({ initial, locked, onSubmit, placeholder, unit, inputMode }: TextAnswerProps) {
  const [value, setValue] = useState(typeof initial === 'string' ? initial : '')
  const { pending, submit } = useSubmit(onSubmit)
  const handle = (event: FormEvent) => {
    event.preventDefault()
    if (value.trim() && !pending) submit(value)
  }
  return (
    <form className="answer-row" onSubmit={handle}>
      <input
        className="text-input"
        type="text"
        inputMode={inputMode}
        spellCheck={false}
        placeholder={placeholder}
        aria-label={placeholder}
        value={value}
        disabled={locked}
        onChange={(event) => setValue(event.target.value)}
      />
      {unit && <span className="unit">{unit}</span>}
      {!locked && (
        <button type="submit" className="button button-primary" disabled={!value.trim() || pending}>
          Check
        </button>
      )}
    </form>
  )
}

function CheckAction({ disabled, onClick }: { disabled: boolean; onClick: () => void }) {
  return (
    <div className="answer-actions">
      <button type="button" className="button button-primary" disabled={disabled} onClick={onClick}>
        Check
      </button>
    </div>
  )
}

function ChoiceInput({ answer, initial, locked, onSubmit }: InputProps<ChoiceAnswer>) {
  const name = useId()
  const [selected, setSelected] = useState<number | null>(typeof initial === 'number' ? initial : null)
  const { pending, submit } = useSubmit(onSubmit)
  return (
    <>
      <fieldset className="options" disabled={locked}>
        {answer.options.map((option, index) => (
          <label key={index} className="option">
            <input type="radio" name={name} checked={selected === index} onChange={() => setSelected(index)} />
            <Markdown inline>{option}</Markdown>
          </label>
        ))}
      </fieldset>
      {!locked && <CheckAction disabled={selected === null || pending} onClick={() => submit(selected)} />}
    </>
  )
}

function MultiChoiceInput({ answer, initial, locked, onSubmit }: InputProps<MultiChoiceAnswer>) {
  const [selected, setSelected] = useState<ReadonlySet<number>>(
    () => new Set(Array.isArray(initial) ? initial.filter((i): i is number => typeof i === 'number') : [])
  )
  const { pending, submit } = useSubmit(onSubmit)
  const toggle = (index: number) => {
    const next = new Set(selected)
    if (next.has(index)) next.delete(index)
    else next.add(index)
    setSelected(next)
  }
  return (
    <>
      <fieldset className="options" disabled={locked}>
        {answer.options.map((option, index) => (
          <label key={index} className="option">
            <input type="checkbox" checked={selected.has(index)} onChange={() => toggle(index)} />
            <Markdown inline>{option}</Markdown>
          </label>
        ))}
      </fieldset>
      {!locked && (
        <CheckAction
          disabled={selected.size === 0 || pending}
          onClick={() => submit([...selected].sort((a, b) => a - b))}
        />
      )}
    </>
  )
}

/** The student commits, sees the rubric, then grades themselves. */
function SelfCheckInput({ answer, initial, locked, onSubmit }: InputProps<SelfCheckAnswer>) {
  const previous = initial as { text?: unknown } | null
  const [text, setText] = useState(typeof previous?.text === 'string' ? previous.text : '')
  const [committed, setCommitted] = useState(previous !== null || locked)
  const { pending, submit } = useSubmit(onSubmit)
  return (
    <>
      <textarea
        className="text-input"
        rows={4}
        placeholder="Your answer"
        aria-label="Your answer"
        value={text}
        disabled={locked}
        onChange={(event) => setText(event.target.value)}
      />
      {committed ? (
        <div className="rubric fade-in">
          <span className="eyebrow">Rubric</span>
          <Markdown>{answer.rubric}</Markdown>
        </div>
      ) : (
        <div className="answer-actions">
          <button type="button" className="button button-primary" onClick={() => setCommitted(true)}>
            Show rubric
          </button>
        </div>
      )}
      {committed && !locked && (
        <div className="answer-actions">
          <span className="muted">Did your answer meet the rubric?</span>
          <button type="button" className="button" disabled={pending} onClick={() => submit({ text, correct: false })}>
            Not yet
          </button>
          <button
            type="button"
            className="button button-primary"
            disabled={pending}
            onClick={() => submit({ text, correct: true })}
          >
            I got it
          </button>
        </div>
      )}
    </>
  )
}
