import { Link } from 'react-router'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

/** Renders a legal document (Privacy / Terms) from Markdown, with cross-links.
 *  Public — reachable without authentication. */
export default function LegalDocument({ content }: { content: string }) {
  return (
    <div className="min-h-screen bg-white dark:bg-gray-950 text-gray-800 dark:text-gray-200">
      <div className="max-w-3xl mx-auto px-6 py-10">
        <div className="mb-6 flex items-center justify-between text-sm">
          <Link to="/" className="text-blue-600 dark:text-blue-400 hover:underline">
            ← Back to home
          </Link>
          <div className="flex gap-4">
            <Link to="/privacy" className="text-blue-600 dark:text-blue-400 hover:underline">
              Privacy
            </Link>
            <Link to="/terms" className="text-blue-600 dark:text-blue-400 hover:underline">
              Terms
            </Link>
          </div>
        </div>
        <article className="prose prose-sm dark:prose-invert max-w-none prose-a:text-blue-600 dark:prose-a:text-blue-400">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
        </article>
      </div>
    </div>
  )
}
