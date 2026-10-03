// Markdown with LaTeX. Raw HTML in the source is not rendered.
import ReactMarkdown, { type Components, type Options } from 'react-markdown'
import rehypeKatex from 'rehype-katex'
import remarkMath from 'remark-math'

const remarkPlugins: Options['remarkPlugins'] = [remarkMath]
const rehypePlugins: Options['rehypePlugins'] = [[rehypeKatex, { errorColor: 'var(--text-muted)' }]]
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
