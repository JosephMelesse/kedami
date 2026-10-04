// Markdown with LaTeX, GitHub-style tables, and highlighted Python. Raw HTML in the source is not rendered.
import python from 'highlight.js/lib/languages/python'
import ReactMarkdown, { type Components, type Options } from 'react-markdown'
import rehypeHighlight from 'rehype-highlight'
import rehypeKatex from 'rehype-katex'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'

const remarkPlugins: Options['remarkPlugins'] = [remarkGfm, remarkMath]
const rehypePlugins: Options['rehypePlugins'] = [
  [rehypeKatex, { errorColor: 'var(--text-muted)' }],
  // Python only: lessons write all code in Python, and other grammars would only add size.
  [rehypeHighlight, { languages: { python }, detect: false }]
]
const inlineComponents: Components = { p: ({ children }) => <>{children}</> }

export function Markdown({ children, inline = false }: { children: string; inline?: boolean }) {
  const Wrapper = inline ? 'span' : 'div'
  return (
    <Wrapper className={inline ? 'md-inline' : 'md'}>
      <ReactMarkdown
        remarkPlugins={remarkPlugins}
        rehypePlugins={rehypePlugins}
        components={inline ? inlineComponents : undefined}
      >
        {children}
      </ReactMarkdown>
    </Wrapper>
  )
}
