/**
 * MarkdownContent Component
 * 
 * Renders markdown content from AI responses with proper styling.
 * Supports GFM (GitHub Flavored Markdown) including:
 * - Tables, strikethrough, task lists
 * - Code blocks with syntax highlighting
 * - Links, images, blockquotes
 */

import { memo, useState, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { EuiCode, EuiLink } from '@elastic/eui'

interface MarkdownContentProps {
  content: string
}

/**
 * Image component with error handling.
 * Hides broken images gracefully instead of showing broken image icons.
 */
function MarkdownImage({ src, alt }: { src?: string; alt?: string }) {
  const [hasError, setHasError] = useState(false)

  const handleError = useCallback(() => {
    setHasError(true)
  }, [])

  // Don't render anything if there's no src or if image failed to load
  if (!src || hasError) {
    return null
  }

  return (
    <img 
      src={src} 
      alt={alt || ''} 
      onError={handleError}
      style={{
        maxWidth: '100%',
        borderRadius: '8px',
        margin: '0.5em 0',
        display: 'block',
      }}
    />
  )
}

function MarkdownContentComponent({ content }: MarkdownContentProps) {
  return (
    <div className="markdown-content">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // Paragraphs
          p: ({ children }) => (
            <p style={{ margin: '0 0 0.75em 0', lineHeight: '1.6' }}>
              {children}
            </p>
          ),
          
          // Headings
          h1: ({ children }) => (
            <h3 style={{ 
              fontSize: '1.25em', 
              fontWeight: 600, 
              margin: '1em 0 0.5em 0',
              color: 'var(--euiTextColor)'
            }}>
              {children}
            </h3>
          ),
          h2: ({ children }) => (
            <h4 style={{ 
              fontSize: '1.1em', 
              fontWeight: 600, 
              margin: '1em 0 0.5em 0',
              color: 'var(--euiTextColor)'
            }}>
              {children}
            </h4>
          ),
          h3: ({ children }) => (
            <h5 style={{ 
              fontSize: '1em', 
              fontWeight: 600, 
              margin: '0.75em 0 0.4em 0',
              color: 'var(--euiTextColor)'
            }}>
              {children}
            </h5>
          ),
          
          // Links
          a: ({ href, children }) => (
            <EuiLink href={href} target="_blank" external>
              {children}
            </EuiLink>
          ),
          
          // Lists
          ul: ({ children }) => (
            <ul style={{ 
              margin: '0.5em 0', 
              paddingLeft: '1.5em',
              listStyleType: 'disc'
            }}>
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol style={{ 
              margin: '0.5em 0', 
              paddingLeft: '1.5em' 
            }}>
              {children}
            </ol>
          ),
          li: ({ children }) => (
            <li style={{ 
              margin: '0.25em 0',
              lineHeight: '1.5'
            }}>
              {children}
            </li>
          ),
          
          // Code
          code: ({ className, children, ...props }) => {
            const isInline = !className
            if (isInline) {
              return (
                <EuiCode 
                  transparentBackground 
                  style={{ 
                    padding: '0.1em 0.3em',
                    fontSize: '0.9em'
                  }}
                >
                  {children}
                </EuiCode>
              )
            }
            // Code block
            return (
              <pre style={{
                background: 'var(--euiColorLightestShade)',
                borderRadius: '6px',
                padding: '12px',
                margin: '0.75em 0',
                overflow: 'auto',
                fontSize: '0.85em',
                lineHeight: '1.5'
              }}>
                <code className={className} {...props}>
                  {children}
                </code>
              </pre>
            )
          },
          
          // Blockquote
          blockquote: ({ children }) => (
            <blockquote style={{
              borderLeft: '3px solid var(--euiColorPrimary)',
              margin: '0.75em 0',
              paddingLeft: '1em',
              color: 'var(--euiTextSubduedColor)',
              fontStyle: 'italic'
            }}>
              {children}
            </blockquote>
          ),
          
          // Horizontal rule
          hr: () => (
            <hr style={{
              border: 'none',
              borderTop: '1px solid var(--euiColorLightShade)',
              margin: '1em 0'
            }} />
          ),
          
          // Tables
          table: ({ children }) => (
            <div style={{ overflowX: 'auto', margin: '0.75em 0' }}>
              <table style={{
                borderCollapse: 'collapse',
                width: '100%',
                fontSize: '0.9em'
              }}>
                {children}
              </table>
            </div>
          ),
          th: ({ children }) => (
            <th style={{
              border: '1px solid var(--euiColorLightShade)',
              padding: '8px 12px',
              textAlign: 'left',
              background: 'var(--euiColorLightestShade)',
              fontWeight: 600
            }}>
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td style={{
              border: '1px solid var(--euiColorLightShade)',
              padding: '8px 12px'
            }}>
              {children}
            </td>
          ),
          
          // Strong and emphasis
          strong: ({ children }) => (
            <strong style={{ fontWeight: 600 }}>{children}</strong>
          ),
          em: ({ children }) => (
            <em>{children}</em>
          ),
          
          // Images - uses custom component with error handling
          img: ({ src, alt }) => <MarkdownImage src={src} alt={alt} />,
        }}
      >
        {content}
      </ReactMarkdown>
      
      <style>{`
        .markdown-content p:last-child {
          margin-bottom: 0;
        }
        .markdown-content ul:last-child,
        .markdown-content ol:last-child {
          margin-bottom: 0;
        }
      `}</style>
    </div>
  )
}

export const MarkdownContent = memo(MarkdownContentComponent)

