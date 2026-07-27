import { Link } from 'react-router'

/** Privacy Policy + Terms links.
 *
 * One component so every surface points at the same routes: the signed-in app
 * shell, the client portal, and the signed-out login/register pages. The routes
 * themselves are public, so this works whether or not someone is logged in.
 */
export default function LegalFooter({ className = '' }: { className?: string }) {
  return (
    <footer
      className={`flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-400 dark:text-gray-500 ${className}`}
    >
      <Link to="/privacy" className="hover:underline">Privacy Policy</Link>
      <Link to="/terms" className="hover:underline">Terms of Service</Link>
      <span className="text-gray-300 dark:text-gray-600">© OCIDM</span>
    </footer>
  )
}
