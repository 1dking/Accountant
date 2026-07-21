import { useState, useRef, useCallback, useEffect } from 'react'
import {
  Trash2, Copy, Plus, Undo2, Redo2, AlignLeft,
  AlignCenter, AlignRight, AlignJustify,
} from 'lucide-react'

// ---------------------------------------------------------------------------
// Doc-shape helpers (Pages v2 compat)
// ---------------------------------------------------------------------------

/**
 * If `input` is a full <!DOCTYPE html> document, return just the body's
 * innerHTML. Otherwise return the input untouched.
 *
 * Why: compile_page() in Pages v2 emits a full HTML5 doc into
 * page.html_content. Wrapping that again inside the editor's iframe
 * srcdoc (`<body>${html}${editorScript}</body>`) produced nested
 * <!DOCTYPE>/<html>/<head>/<body> which the browser's HTML parser
 * "cleaned up" by discarding the inner structure — sections vanished
 * from the DOM, and the subsequent autosave persisted the wreckage.
 * Unwrapping before composition keeps the parser happy.
 */
function bodyInnerFromFullDoc(input: string): string {
  if (!input) return ''
  const trimmed = input.trim()
  if (!/^<!doctype/i.test(trimmed)) return input
  const match = trimmed.match(/<body[^>]*>([\s\S]*)<\/body>/i)
  return match ? match[1] : input
}

/**
 * Read body.innerHTML from the editor iframe AFTER stripping the
 * editor's own injected DOM (overlay div, editor <script>, any
 * data-editor-* attributes, and any lingering contenteditable=true
 * attribute from a blur edge case). Prevents the editor from
 * accidentally serializing itself back into the saved html_content.
 */
function getCleanBodyHtml(iframeDoc: Document | null | undefined): string {
  if (!iframeDoc) return ''
  const clone = iframeDoc.body.cloneNode(true) as HTMLElement
  clone.querySelectorAll('#__editor_overlay').forEach((n) => n.remove())
  clone.querySelectorAll('script').forEach((n) => n.remove())
  clone.querySelectorAll('*').forEach((el) => {
    Array.from(el.attributes).forEach((attr) => {
      if (attr.name.startsWith('data-editor-')) {
        el.removeAttribute(attr.name)
      }
    })
    if (el.hasAttribute('contenteditable')) {
      el.removeAttribute('contenteditable')
    }
  })
  return clone.innerHTML
}

interface VisualEditorProps {
  html: string
  css: string
  onHtmlChange: (html: string) => void
  onCssChange: (css: string) => void
  onVideoUpload?: (file: File) => Promise<{ mp4_url: string; webm_url: string; poster_url: string }>
}

interface SelectedElement {
  selector: string
  tagName: string
  text: string
  styles: Record<string, string>
  rect: { x: number; y: number; width: number; height: number }
}

const FONTS = [
  'Inter', 'Open Sans', 'Roboto', 'Lato', 'Montserrat', 'Poppins',
  'Playfair Display', 'Merriweather', 'Raleway', 'Nunito',
  'Source Sans Pro', 'Oswald', 'PT Sans', 'Work Sans', 'DM Sans',
  'Space Grotesk', 'Outfit', 'Plus Jakarta Sans', 'Manrope', 'Libre Baskerville',
]

const FONT_WEIGHTS = [
  { label: 'Thin', value: '100' }, { label: 'Light', value: '300' },
  { label: 'Regular', value: '400' }, { label: 'Medium', value: '500' },
  { label: 'Semi-Bold', value: '600' }, { label: 'Bold', value: '700' },
  { label: 'Extra-Bold', value: '800' }, { label: 'Black', value: '900' },
]

const SECTION_CATEGORIES = [
  'Hero', 'Features', 'Pricing', 'Testimonials', 'CTA', 'FAQ',
  'Team', 'Stats', 'Contact', 'Footer', 'Gallery', 'Logos',
]

// Self-contained gradient placeholders for image slots — no external
// hotlinks that can rot; users swap in real URLs via the Image panel.
const PLACEHOLDER_IMGS = [
  "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='600' height='450'%3E%3Cdefs%3E%3ClinearGradient id='g' x1='0' y1='0' x2='1' y2='1'%3E%3Cstop offset='0' stop-color='%236366f1'/%3E%3Cstop offset='1' stop-color='%23c7d2fe'/%3E%3C/linearGradient%3E%3C/defs%3E%3Crect width='600' height='450' fill='url(%23g)'/%3E%3C/svg%3E",
  "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='600' height='450'%3E%3Cdefs%3E%3ClinearGradient id='g' x1='0' y1='0' x2='1' y2='1'%3E%3Cstop offset='0' stop-color='%238b5cf6'/%3E%3Cstop offset='1' stop-color='%23ddd6fe'/%3E%3C/linearGradient%3E%3C/defs%3E%3Crect width='600' height='450' fill='url(%23g)'/%3E%3C/svg%3E",
  "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='600' height='450'%3E%3Cdefs%3E%3ClinearGradient id='g' x1='0' y1='0' x2='1' y2='1'%3E%3Cstop offset='0' stop-color='%230ea5e9'/%3E%3Cstop offset='1' stop-color='%23bae6fd'/%3E%3C/linearGradient%3E%3C/defs%3E%3Crect width='600' height='450' fill='url(%23g)'/%3E%3C/svg%3E",
]

// Real, designed defaults for each section category. Pure Tailwind
// utilities (the editor iframe, Preview tab, and compile_page() all load
// the Tailwind CDN, so these render identically everywhere). Text lives
// in click-to-edit tags (h1-h6/p/a/span/li), CTAs are <a> so the Button
// panel's link/color controls apply, and copy doubles as instructions
// for what to write there.
const SECTION_SNIPPETS: Record<string, string> = {
  Hero: `<section class="hero relative overflow-hidden bg-slate-950 text-white"><div class="absolute inset-0 bg-gradient-to-br from-indigo-950 via-slate-950 to-slate-900"></div><div class="absolute -top-32 -right-32 w-96 h-96 rounded-full bg-indigo-600/20 blur-3xl"></div><div class="relative max-w-4xl mx-auto text-center py-28 px-6"><span class="inline-block px-4 py-1.5 rounded-full bg-white/10 border border-white/20 text-sm font-medium text-indigo-200 mb-6">New — now serving your area</span><h1 class="text-5xl md:text-6xl font-extrabold tracking-tight mb-6 leading-tight">Grow your business with confidence</h1><p class="text-xl text-slate-300 mb-10 max-w-2xl mx-auto">Say exactly what you do and who you do it for — one clear sentence that makes a visitor want to keep reading.</p><div class="flex flex-wrap items-center justify-center gap-4"><a href="#" class="px-8 py-3.5 rounded-xl bg-indigo-500 hover:bg-indigo-400 text-white font-semibold shadow-lg shadow-indigo-500/30 transition">Get Started</a><a href="#" class="px-8 py-3.5 rounded-xl border border-white/20 text-white font-semibold hover:bg-white/10 transition">Learn More</a></div><p class="mt-8 text-sm text-slate-400">Trusted by 200+ local businesses</p></div></section>`,
  Features: `<section class="features bg-white py-24 px-6"><div class="max-w-6xl mx-auto"><div class="text-center mb-16"><span class="text-sm font-semibold tracking-widest uppercase text-indigo-600">Why choose us</span><h2 class="text-4xl font-bold text-slate-900 mt-3 mb-4">Everything you need, in one place</h2><p class="text-lg text-slate-500 max-w-2xl mx-auto">Swap these three cards for your strongest selling points.</p></div><div class="grid md:grid-cols-3 gap-8"><div class="p-8 rounded-2xl border border-slate-200 bg-slate-50 hover:shadow-xl hover:-translate-y-1 transition"><div class="w-12 h-12 rounded-xl bg-indigo-100 text-2xl flex items-center justify-center mb-5">⚡</div><h3 class="text-xl font-semibold text-slate-900 mb-2">Fast turnaround</h3><p class="text-slate-500 leading-relaxed">Describe the first big benefit a customer gets from working with you.</p></div><div class="p-8 rounded-2xl border border-slate-200 bg-slate-50 hover:shadow-xl hover:-translate-y-1 transition"><div class="w-12 h-12 rounded-xl bg-violet-100 text-2xl flex items-center justify-center mb-5">🛡️</div><h3 class="text-xl font-semibold text-slate-900 mb-2">Guaranteed quality</h3><p class="text-slate-500 leading-relaxed">Describe the second benefit — proof, guarantees, or credentials work well here.</p></div><div class="p-8 rounded-2xl border border-slate-200 bg-slate-50 hover:shadow-xl hover:-translate-y-1 transition"><div class="w-12 h-12 rounded-xl bg-sky-100 text-2xl flex items-center justify-center mb-5">💬</div><h3 class="text-xl font-semibold text-slate-900 mb-2">Real support</h3><p class="text-slate-500 leading-relaxed">Describe the third benefit — how easy it is to reach a real person, for example.</p></div></div></div></section>`,
  Pricing: `<section class="pricing bg-slate-50 py-24 px-6"><div class="max-w-6xl mx-auto"><div class="text-center mb-16"><h2 class="text-4xl font-bold text-slate-900 mb-4">Simple, honest pricing</h2><p class="text-lg text-slate-500">No hidden fees. Cancel anytime.</p></div><div class="grid md:grid-cols-3 gap-8 items-start"><div class="p-8 rounded-2xl bg-white border border-slate-200"><h3 class="text-lg font-semibold text-slate-900 mb-1">Starter</h3><p class="text-slate-500 text-sm mb-6">For individuals getting going</p><p class="text-5xl font-extrabold text-slate-900 mb-6">$29<span class="text-base font-medium text-slate-400">/mo</span></p><ul class="space-y-3 text-slate-600 mb-8"><li>✓ First key feature</li><li>✓ Second key feature</li><li>✓ Email support</li></ul><a href="#" class="block text-center px-6 py-3 rounded-xl border border-slate-300 font-semibold text-slate-700 hover:bg-slate-50 transition">Choose Starter</a></div><div class="relative p-8 rounded-2xl bg-slate-900 text-white shadow-2xl md:-mt-4"><span class="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full bg-indigo-500 text-xs font-semibold">MOST POPULAR</span><h3 class="text-lg font-semibold mb-1">Professional</h3><p class="text-slate-400 text-sm mb-6">For growing businesses</p><p class="text-5xl font-extrabold mb-6">$79<span class="text-base font-medium text-slate-400">/mo</span></p><ul class="space-y-3 text-slate-300 mb-8"><li>✓ Everything in Starter</li><li>✓ A more advanced feature</li><li>✓ Priority support</li><li>✓ Another compelling extra</li></ul><a href="#" class="block text-center px-6 py-3 rounded-xl bg-indigo-500 hover:bg-indigo-400 font-semibold text-white transition">Choose Professional</a></div><div class="p-8 rounded-2xl bg-white border border-slate-200"><h3 class="text-lg font-semibold text-slate-900 mb-1">Enterprise</h3><p class="text-slate-500 text-sm mb-6">For teams with custom needs</p><p class="text-5xl font-extrabold text-slate-900 mb-6">$199<span class="text-base font-medium text-slate-400">/mo</span></p><ul class="space-y-3 text-slate-600 mb-8"><li>✓ Everything in Professional</li><li>✓ Dedicated account manager</li><li>✓ Custom onboarding</li></ul><a href="#" class="block text-center px-6 py-3 rounded-xl border border-slate-300 font-semibold text-slate-700 hover:bg-slate-50 transition">Contact Sales</a></div></div></div></section>`,
  Testimonials: `<section class="testimonials bg-white py-24 px-6"><div class="max-w-6xl mx-auto"><div class="text-center mb-16"><h2 class="text-4xl font-bold text-slate-900 mb-4">What our clients say</h2><p class="text-lg text-slate-500">Real words from real customers build more trust than anything you write yourself.</p></div><div class="grid md:grid-cols-3 gap-8"><div class="p-8 rounded-2xl bg-slate-50 border border-slate-200"><p class="text-amber-400 text-lg mb-4">★★★★★</p><p class="text-slate-700 leading-relaxed mb-6">“Replace this with a short, specific quote — the result the customer got, in their own words.”</p><div class="flex items-center gap-3"><div class="w-11 h-11 rounded-full bg-indigo-100 text-indigo-700 font-bold flex items-center justify-center">JD</div><div><p class="font-semibold text-slate-900">Jane Doe</p><p class="text-sm text-slate-500">Owner, Acme Co.</p></div></div></div><div class="p-8 rounded-2xl bg-slate-50 border border-slate-200"><p class="text-amber-400 text-lg mb-4">★★★★★</p><p class="text-slate-700 leading-relaxed mb-6">“A second quote. Numbers are persuasive — ‘cut our costs 30%’ beats ‘great service’.”</p><div class="flex items-center gap-3"><div class="w-11 h-11 rounded-full bg-violet-100 text-violet-700 font-bold flex items-center justify-center">MS</div><div><p class="font-semibold text-slate-900">Mark Smith</p><p class="text-sm text-slate-500">Director, Bright LLC</p></div></div></div><div class="p-8 rounded-2xl bg-slate-50 border border-slate-200"><p class="text-amber-400 text-lg mb-4">★★★★★</p><p class="text-slate-700 leading-relaxed mb-6">“A third quote. Pick one that answers the biggest doubt a new customer might have.”</p><div class="flex items-center gap-3"><div class="w-11 h-11 rounded-full bg-sky-100 text-sky-700 font-bold flex items-center justify-center">AL</div><div><p class="font-semibold text-slate-900">Amy Lee</p><p class="text-sm text-slate-500">Founder, Northside</p></div></div></div></div></div></section>`,
  CTA: `<section class="cta px-6 py-24 bg-gradient-to-r from-indigo-600 to-violet-600 text-white"><div class="max-w-3xl mx-auto text-center"><h2 class="text-4xl md:text-5xl font-extrabold mb-4">Ready to get started?</h2><p class="text-xl text-indigo-100 mb-10">One sentence of reassurance — free consultation, no commitment, fast reply.</p><a href="#" class="inline-block px-10 py-4 rounded-xl bg-white text-indigo-700 font-bold text-lg shadow-xl hover:bg-indigo-50 transition">Book a Free Call</a></div></section>`,
  FAQ: `<section class="faq bg-slate-50 py-24 px-6"><div class="max-w-3xl mx-auto"><h2 class="text-4xl font-bold text-slate-900 text-center mb-14">Frequently asked questions</h2><div class="space-y-4"><div class="p-6 rounded-2xl bg-white border border-slate-200"><h3 class="text-lg font-semibold text-slate-900 mb-2">How much does it cost?</h3><p class="text-slate-600 leading-relaxed">Answer the pricing question head-on — vagueness here loses customers.</p></div><div class="p-6 rounded-2xl bg-white border border-slate-200"><h3 class="text-lg font-semibold text-slate-900 mb-2">How long does it take?</h3><p class="text-slate-600 leading-relaxed">Set an honest expectation for timelines from first contact to done.</p></div><div class="p-6 rounded-2xl bg-white border border-slate-200"><h3 class="text-lg font-semibold text-slate-900 mb-2">Do you offer a guarantee?</h3><p class="text-slate-600 leading-relaxed">Address risk: refunds, warranties, or what happens if something goes wrong.</p></div><div class="p-6 rounded-2xl bg-white border border-slate-200"><h3 class="text-lg font-semibold text-slate-900 mb-2">How do I get started?</h3><p class="text-slate-600 leading-relaxed">Describe the first step — a call, a form, a visit — and what happens after it.</p></div></div></div></section>`,
  Team: `<section class="team bg-white py-24 px-6"><div class="max-w-6xl mx-auto"><div class="text-center mb-16"><h2 class="text-4xl font-bold text-slate-900 mb-4">Meet the team</h2><p class="text-lg text-slate-500">The people your customers will actually work with.</p></div><div class="grid grid-cols-2 md:grid-cols-4 gap-8 text-center"><div><div class="w-24 h-24 mx-auto rounded-full bg-gradient-to-br from-indigo-400 to-indigo-600 text-white text-2xl font-bold flex items-center justify-center mb-4">AB</div><h3 class="font-semibold text-slate-900">Alex Brown</h3><p class="text-sm text-slate-500">Founder &amp; CEO</p></div><div><div class="w-24 h-24 mx-auto rounded-full bg-gradient-to-br from-violet-400 to-violet-600 text-white text-2xl font-bold flex items-center justify-center mb-4">CJ</div><h3 class="font-semibold text-slate-900">Casey Jones</h3><p class="text-sm text-slate-500">Head of Operations</p></div><div><div class="w-24 h-24 mx-auto rounded-full bg-gradient-to-br from-sky-400 to-sky-600 text-white text-2xl font-bold flex items-center justify-center mb-4">RP</div><h3 class="font-semibold text-slate-900">Riley Park</h3><p class="text-sm text-slate-500">Lead Specialist</p></div><div><div class="w-24 h-24 mx-auto rounded-full bg-gradient-to-br from-emerald-400 to-emerald-600 text-white text-2xl font-bold flex items-center justify-center mb-4">SM</div><h3 class="font-semibold text-slate-900">Sam Morgan</h3><p class="text-sm text-slate-500">Client Success</p></div></div></div></section>`,
  Stats: `<section class="stats bg-slate-900 text-white py-20 px-6"><div class="max-w-6xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-10 text-center"><div><p class="text-5xl font-extrabold text-indigo-400 mb-2">250+</p><p class="text-slate-400 font-medium">Happy clients</p></div><div><p class="text-5xl font-extrabold text-indigo-400 mb-2">12</p><p class="text-slate-400 font-medium">Years in business</p></div><div><p class="text-5xl font-extrabold text-indigo-400 mb-2">98%</p><p class="text-slate-400 font-medium">Satisfaction rate</p></div><div><p class="text-5xl font-extrabold text-indigo-400 mb-2">24h</p><p class="text-slate-400 font-medium">Average response</p></div></div></section>`,
  Contact: `<section class="contact bg-white py-24 px-6"><div class="max-w-6xl mx-auto grid md:grid-cols-2 gap-14 items-start"><div><h2 class="text-4xl font-bold text-slate-900 mb-4">Get in touch</h2><p class="text-lg text-slate-500 mb-8">Tell visitors how quickly you reply and what happens after they reach out.</p><div class="space-y-4"><p class="flex items-center gap-3 text-slate-700"><span class="w-10 h-10 rounded-lg bg-indigo-100 flex items-center justify-center">📧</span> hello@yourbusiness.com</p><p class="flex items-center gap-3 text-slate-700"><span class="w-10 h-10 rounded-lg bg-indigo-100 flex items-center justify-center">📞</span> (555) 123-4567</p><p class="flex items-center gap-3 text-slate-700"><span class="w-10 h-10 rounded-lg bg-indigo-100 flex items-center justify-center">📍</span> 123 Main Street, Your City</p></div></div><div class="p-8 rounded-2xl bg-slate-50 border border-slate-200"><div class="space-y-4"><div><label class="block text-sm font-medium text-slate-700 mb-1.5">Name</label><input type="text" placeholder="Your name" class="w-full px-4 py-3 rounded-xl border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"/></div><div><label class="block text-sm font-medium text-slate-700 mb-1.5">Email</label><input type="email" placeholder="you@example.com" class="w-full px-4 py-3 rounded-xl border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"/></div><div><label class="block text-sm font-medium text-slate-700 mb-1.5">Message</label><textarea rows="4" placeholder="How can we help?" class="w-full px-4 py-3 rounded-xl border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"></textarea></div><a href="#" class="block text-center px-6 py-3.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold transition">Send Message</a></div></div></div></section>`,
  Footer: `<section class="footer bg-slate-950 text-slate-300 pt-20 pb-10 px-6"><div class="max-w-6xl mx-auto"><div class="grid md:grid-cols-4 gap-10 mb-14"><div><h3 class="text-xl font-bold text-white mb-3">Your Business</h3><p class="text-sm text-slate-400 leading-relaxed">One line about who you are and the area you serve.</p></div><div><h4 class="font-semibold text-white mb-4">Company</h4><ul class="space-y-2.5 text-sm"><li><a href="#" class="hover:text-white transition">About</a></li><li><a href="#" class="hover:text-white transition">Services</a></li><li><a href="#" class="hover:text-white transition">Pricing</a></li></ul></div><div><h4 class="font-semibold text-white mb-4">Resources</h4><ul class="space-y-2.5 text-sm"><li><a href="#" class="hover:text-white transition">Blog</a></li><li><a href="#" class="hover:text-white transition">FAQ</a></li><li><a href="#" class="hover:text-white transition">Contact</a></li></ul></div><div><h4 class="font-semibold text-white mb-4">Contact</h4><ul class="space-y-2.5 text-sm"><li>hello@yourbusiness.com</li><li>(555) 123-4567</li><li>123 Main Street, Your City</li></ul></div></div><div class="pt-8 border-t border-slate-800 flex flex-wrap items-center justify-between gap-4"><p class="text-sm text-slate-500">© 2026 Your Business. All rights reserved.</p><p class="text-sm text-slate-500">Privacy · Terms</p></div></div></section>`,
  Gallery: `<section class="gallery bg-slate-50 py-24 px-6"><div class="max-w-6xl mx-auto"><div class="text-center mb-16"><h2 class="text-4xl font-bold text-slate-900 mb-4">Our work</h2><p class="text-lg text-slate-500">Click any tile and use the Image panel to swap in real photos.</p></div><div class="grid grid-cols-2 md:grid-cols-3 gap-5"><img src="${PLACEHOLDER_IMGS[0]}" alt="Project photo" class="w-full aspect-[4/3] object-cover rounded-2xl shadow-sm hover:shadow-xl transition"/><img src="${PLACEHOLDER_IMGS[1]}" alt="Project photo" class="w-full aspect-[4/3] object-cover rounded-2xl shadow-sm hover:shadow-xl transition"/><img src="${PLACEHOLDER_IMGS[2]}" alt="Project photo" class="w-full aspect-[4/3] object-cover rounded-2xl shadow-sm hover:shadow-xl transition"/><img src="${PLACEHOLDER_IMGS[2]}" alt="Project photo" class="w-full aspect-[4/3] object-cover rounded-2xl shadow-sm hover:shadow-xl transition"/><img src="${PLACEHOLDER_IMGS[0]}" alt="Project photo" class="w-full aspect-[4/3] object-cover rounded-2xl shadow-sm hover:shadow-xl transition"/><img src="${PLACEHOLDER_IMGS[1]}" alt="Project photo" class="w-full aspect-[4/3] object-cover rounded-2xl shadow-sm hover:shadow-xl transition"/></div></div></section>`,
  Logos: `<section class="logos bg-white py-16 px-6"><div class="max-w-5xl mx-auto text-center"><p class="text-sm font-semibold tracking-widest uppercase text-slate-400 mb-8">Trusted by teams at</p><div class="flex flex-wrap items-center justify-center gap-x-14 gap-y-6"><span class="text-2xl font-extrabold text-slate-300 hover:text-slate-400 transition">NORTHWIND</span><span class="text-2xl font-extrabold text-slate-300 hover:text-slate-400 transition">Apex&amp;Co</span><span class="text-2xl font-extrabold text-slate-300 hover:text-slate-400 transition">brightside</span><span class="text-2xl font-extrabold text-slate-300 hover:text-slate-400 transition">SUMMIT</span><span class="text-2xl font-extrabold text-slate-300 hover:text-slate-400 transition">Lakeview</span></div></div></section>`,
}

export default function VisualEditor({ html, css, onHtmlChange, onCssChange, onVideoUpload }: VisualEditorProps) {
  const iframeRef = useRef<HTMLIFrameElement>(null)
  const [selected, setSelected] = useState<SelectedElement | null>(null)
  const [panelOpen, setPanelOpen] = useState(false)
  const [panelTab, setPanelTab] = useState<'typography' | 'colors' | 'image' | 'spacing' | 'section' | 'button' | 'layout' | 'video'>('typography')
  const [undoStack, setUndoStack] = useState<string[]>([])
  const [redoStack, setRedoStack] = useState<string[]>([])
  const [showSectionLibrary, setShowSectionLibrary] = useState(false)

  // Inject editor overlay script into iframe
  const editorScript = `
    <script>
      let selectedEl = null;
      let overlay = null;

      function createOverlay() {
        if (overlay) overlay.remove();
        overlay = document.createElement('div');
        overlay.id = '__editor_overlay';
        overlay.style.cssText = 'position:absolute;border:2px solid #3b82f6;pointer-events:none;z-index:99999;transition:all 0.15s;';
        document.body.appendChild(overlay);
      }

      var TEXT_TAGS = ['H1','H2','H3','H4','H5','H6','P','SPAN','A','LI','BUTTON','LABEL','TD','TH'];

      document.addEventListener('click', function(e) {
        var clicked = e.target;
        var isText = TEXT_TAGS.indexOf(clicked.tagName) !== -1;

        // For NON-text elements (sections, divs, etc.) preventDefault
        // so links don't navigate and forms don't submit. For text
        // elements we let the browser handle the click so the caret
        // positions correctly inside contentEditable.
        if (!isText) {
          e.preventDefault();
        }
        e.stopPropagation();

        selectedEl = clicked;

        // Single-click → caret. Make text elements editable on first
        // selection. Was dblclick — undiscoverable; users thought edits
        // were broken. State-of-the-art editors (Lovable, v0, Framer)
        // all do single-click → caret.
        if (isText && clicked.getAttribute('contenteditable') !== 'true') {
          clicked.contentEditable = 'true';
          clicked.focus();
          clicked.addEventListener('blur', function() {
            clicked.contentEditable = 'false';
            window.parent.postMessage({ type: 'content-changed', html: __cleanBodyHtml() }, '*');
          }, { once: true });
        }

        if (!overlay) createOverlay();

        var rect = selectedEl.getBoundingClientRect();
        overlay.style.top = (rect.top + window.scrollY) + 'px';
        overlay.style.left = (rect.left + window.scrollX) + 'px';
        overlay.style.width = rect.width + 'px';
        overlay.style.height = rect.height + 'px';
        overlay.style.display = 'block';

        var computed = getComputedStyle(selectedEl);
        var path = [];
        var el = selectedEl;
        while (el && el !== document.body) {
          var idx = Array.from(el.parentNode.children).indexOf(el);
          path.unshift(el.tagName.toLowerCase() + ':nth-child(' + (idx+1) + ')');
          el = el.parentNode;
        }

        window.parent.postMessage({
          type: 'element-selected',
          data: {
            selector: path.join(' > '),
            tagName: selectedEl.tagName,
            text: selectedEl.textContent?.substring(0, 200) || '',
            styles: {
              fontFamily: computed.fontFamily,
              fontSize: computed.fontSize,
              fontWeight: computed.fontWeight,
              color: computed.color,
              backgroundColor: computed.backgroundColor,
              textAlign: computed.textAlign,
              lineHeight: computed.lineHeight,
              letterSpacing: computed.letterSpacing,
              paddingTop: computed.paddingTop,
              paddingRight: computed.paddingRight,
              paddingBottom: computed.paddingBottom,
              paddingLeft: computed.paddingLeft,
              marginTop: computed.marginTop,
              marginRight: computed.marginRight,
              marginBottom: computed.marginBottom,
              marginLeft: computed.marginLeft,
              borderRadius: computed.borderRadius,
              opacity: computed.opacity,
              width: computed.width,
              height: computed.height,
            },
            rect: { x: rect.left, y: rect.top, width: rect.width, height: rect.height },
          }
        }, '*');
      }, true);

      // Read body.innerHTML stripped of editor-only DOM: the overlay
      // div, the editor script tag, data-editor-* attributes, and any
      // lingering contenteditable=true. Keep this in lockstep with the
      // parent-side getCleanBodyHtml() helper.
      function __cleanBodyHtml() {
        var clone = document.body.cloneNode(true);
        var ov = clone.querySelectorAll('#__editor_overlay');
        for (var i = 0; i < ov.length; i++) ov[i].remove();
        var sc = clone.querySelectorAll('script');
        for (var j = 0; j < sc.length; j++) sc[j].remove();
        var all = clone.querySelectorAll('*');
        for (var k = 0; k < all.length; k++) {
          var el = all[k];
          var attrs = Array.prototype.slice.call(el.attributes);
          for (var a = 0; a < attrs.length; a++) {
            if (attrs[a].name.indexOf('data-editor-') === 0) {
              el.removeAttribute(attrs[a].name);
            }
          }
          if (el.hasAttribute('contenteditable')) {
            el.removeAttribute('contenteditable');
          }
        }
        return clone.innerHTML;
      }

      // (dblclick handler removed — single-click now owns enter-edit.)
    </script>
  `

  // Pages v2 emits full HTML5 docs into html_content. Unwrap to
  // body-inner before composing srcdoc so we don't nest <!DOCTYPE>
  // inside <body> (the browser parser destroys the structure if we do).
  // Body-fragment input (legacy v1) passes through untouched.
  const innerHtml = bodyInnerFromFullDoc(html)
  const srcdoc = `<!DOCTYPE html><html><head><script src="https://cdn.tailwindcss.com"></script><style>${css}</style></head><body style="cursor:pointer;">${innerHtml}${editorScript}</body></html>`

  useEffect(() => {
    const handler = (e: MessageEvent) => {
      if (e.data?.type === 'element-selected') {
        setSelected(e.data.data)
        setPanelOpen(true)
        // Auto-detect panel tab
        const tag = e.data.data.tagName
        if (['IMG'].includes(tag)) setPanelTab('image')
        else if (['BUTTON', 'A'].includes(tag) && e.data.data.text.length < 50) setPanelTab('button')
        else if (['SECTION', 'DIV', 'HEADER', 'FOOTER', 'MAIN'].includes(tag)) setPanelTab('section')
        else setPanelTab('typography')
      } else if (e.data?.type === 'content-changed') {
        pushUndo()
        onHtmlChange(e.data.html)
      }
    }
    window.addEventListener('message', handler)
    return () => window.removeEventListener('message', handler)
  }, [html])

  const pushUndo = useCallback(() => {
    setUndoStack(prev => [...prev.slice(-20), html])
    setRedoStack([])
  }, [html])

  const undo = useCallback(() => {
    if (undoStack.length === 0) return
    const prev = undoStack[undoStack.length - 1]
    setUndoStack(s => s.slice(0, -1))
    setRedoStack(s => [...s, html])
    onHtmlChange(prev)
  }, [undoStack, html, onHtmlChange])

  const redo = useCallback(() => {
    if (redoStack.length === 0) return
    const next = redoStack[redoStack.length - 1]
    setRedoStack(s => s.slice(0, -1))
    setUndoStack(s => [...s, html])
    onHtmlChange(next)
  }, [redoStack, html, onHtmlChange])

  // Apply style to selected element via iframe postMessage
  const applyStyle = useCallback((prop: string, value: string) => {
    if (!selected || !iframeRef.current?.contentWindow) return
    pushUndo()
    const iframeDoc = iframeRef.current.contentDocument
    if (!iframeDoc) return

    // Find element by selector
    try {
      const el = iframeDoc.querySelector(selected.selector) || iframeDoc.body
      ;(el as HTMLElement).style.setProperty(prop, value)
      onHtmlChange(getCleanBodyHtml(iframeDoc))
      // Update selected styles
      const computed = iframeDoc.defaultView?.getComputedStyle(el as Element)
      if (computed) {
        setSelected(prev => prev ? { ...prev, styles: { ...prev.styles, [prop]: value } } : null)
      }
    } catch {
      // Fallback: inject CSS rule
      const rule = `${selected.selector} { ${prop}: ${value} !important; }`
      onCssChange(css + '\n' + rule)
    }
  }, [selected, html, css, pushUndo, onHtmlChange, onCssChange])

  const deleteSelected = useCallback(() => {
    if (!selected || !iframeRef.current?.contentDocument) return
    pushUndo()
    try {
      const doc = iframeRef.current.contentDocument
      const el = doc.querySelector(selected.selector)
      el?.remove()
      onHtmlChange(getCleanBodyHtml(doc))
      setSelected(null)
      setPanelOpen(false)
    } catch { /* ignore */ }
  }, [selected, pushUndo, onHtmlChange])

  const duplicateSelected = useCallback(() => {
    if (!selected || !iframeRef.current?.contentDocument) return
    pushUndo()
    try {
      const doc = iframeRef.current.contentDocument
      const el = doc.querySelector(selected.selector)
      if (el) {
        const clone = el.cloneNode(true) as HTMLElement
        el.parentNode?.insertBefore(clone, el.nextSibling)
        onHtmlChange(getCleanBodyHtml(doc))
      }
    } catch { /* ignore */ }
  }, [selected, pushUndo, onHtmlChange])

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey) { e.preventDefault(); undo() }
      if ((e.ctrlKey || e.metaKey) && e.key === 'z' && e.shiftKey) { e.preventDefault(); redo() }
      if (e.key === 'Delete' && selected) { e.preventDefault(); deleteSelected() }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [undo, redo, selected, deleteSelected])

  const parsePixels = (v: string) => parseInt(v) || 0

  return (
    <div className="flex h-full relative">
      {/* Toolbar */}
      <div className="absolute top-0 left-0 right-0 z-10 flex items-center gap-1 px-3 py-1.5 bg-white dark:bg-gray-800 border-b text-xs">
        <button onClick={undo} disabled={undoStack.length === 0} className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-30" title="Undo">
          <Undo2 className="w-4 h-4" />
        </button>
        <button onClick={redo} disabled={redoStack.length === 0} className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-30" title="Redo">
          <Redo2 className="w-4 h-4" />
        </button>
        <div className="w-px h-5 bg-gray-200 dark:bg-gray-600 mx-1" />
        <button onClick={() => setShowSectionLibrary(true)} className="flex items-center gap-1 px-2 py-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-300">
          <Plus className="w-3.5 h-3.5" /> Add Section
        </button>
        {selected && (
          <>
            <div className="w-px h-5 bg-gray-200 dark:bg-gray-600 mx-1" />
            <span className="text-gray-400 dark:text-gray-500">{selected.tagName}</span>
            <button onClick={duplicateSelected} className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700" title="Duplicate">
              <Copy className="w-3.5 h-3.5" />
            </button>
            <button onClick={deleteSelected} className="p-1.5 rounded hover:bg-red-50 dark:hover:bg-red-900/20 text-red-500" title="Delete">
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </>
        )}
      </div>

      {/* Canvas */}
      <div className="flex-1 pt-9 bg-gray-100 dark:bg-gray-900 overflow-auto">
        <iframe
          ref={iframeRef}
          srcDoc={srcdoc}
          className="w-full h-full border-0 bg-white"
          sandbox="allow-scripts allow-same-origin"
          title="Visual Editor"
        />
      </div>

      {/* Properties Panel */}
      {panelOpen && selected && (
        <div className="w-72 border-l bg-white dark:bg-gray-800 pt-9 overflow-y-auto shrink-0">
          {/* Panel tabs */}
          <div className="flex flex-wrap gap-1 p-2 border-b">
            {(['typography', 'colors', 'spacing', 'section', 'image', 'button', 'layout', 'video'] as const).map(tab => (
              <button
                key={tab}
                onClick={() => setPanelTab(tab)}
                className={`px-2 py-1 text-xs rounded ${panelTab === tab ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-600' : 'text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700'}`}
              >
                {tab.charAt(0).toUpperCase() + tab.slice(1)}
              </button>
            ))}
          </div>

          <div className="p-3 space-y-4 text-xs">
            {/* Typography */}
            {panelTab === 'typography' && (
              <>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Font Family</label>
                  <select
                    className="w-full p-1.5 border rounded bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
                    value={selected.styles.fontFamily?.split(',')[0]?.replace(/"/g, '').trim() || 'Inter'}
                    onChange={e => applyStyle('font-family', `"${e.target.value}", sans-serif`)}
                  >
                    {FONTS.map(f => <option key={f} value={f}>{f}</option>)}
                  </select>
                </div>
                <div className="flex gap-2">
                  <div className="flex-1">
                    <label className="block text-gray-500 dark:text-gray-400 mb-1">Size (px)</label>
                    <input
                      type="range" min="8" max="120" step="1"
                      value={parsePixels(selected.styles.fontSize)}
                      onChange={e => applyStyle('font-size', `${e.target.value}px`)}
                      className="w-full"
                    />
                    <span className="text-gray-600 dark:text-gray-300">{parsePixels(selected.styles.fontSize)}px</span>
                  </div>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Weight</label>
                  <select
                    className="w-full p-1.5 border rounded bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
                    value={selected.styles.fontWeight || '400'}
                    onChange={e => applyStyle('font-weight', e.target.value)}
                  >
                    {FONT_WEIGHTS.map(fw => <option key={fw.value} value={fw.value}>{fw.label} ({fw.value})</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Color</label>
                  <div className="flex gap-2">
                    <input type="color" value={selected.styles.color || '#000000'} onChange={e => applyStyle('color', e.target.value)} className="w-8 h-8 rounded cursor-pointer" />
                    <input type="text" value={selected.styles.color || ''} onChange={e => applyStyle('color', e.target.value)}
                      className="flex-1 p-1.5 border rounded font-mono bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200" />
                  </div>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Alignment</label>
                  <div className="flex gap-1">
                    {[
                      { icon: AlignLeft, val: 'left' }, { icon: AlignCenter, val: 'center' },
                      { icon: AlignRight, val: 'right' }, { icon: AlignJustify, val: 'justify' },
                    ].map(({ icon: Icon, val }) => (
                      <button key={val} onClick={() => applyStyle('text-align', val)}
                        className={`p-1.5 rounded ${selected.styles.textAlign === val ? 'bg-blue-100 dark:bg-blue-900/30' : 'hover:bg-gray-100 dark:hover:bg-gray-700'}`}>
                        <Icon className="w-4 h-4" />
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Line Height</label>
                  <input type="range" min="0.8" max="3" step="0.1"
                    value={parseFloat(selected.styles.lineHeight) || 1.5}
                    onChange={e => applyStyle('line-height', e.target.value)}
                    className="w-full" />
                  <span className="text-gray-600 dark:text-gray-300">{parseFloat(selected.styles.lineHeight)?.toFixed(1) || '1.5'}</span>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Letter Spacing</label>
                  <input type="range" min="-2" max="10" step="0.5"
                    value={parsePixels(selected.styles.letterSpacing)}
                    onChange={e => applyStyle('letter-spacing', `${e.target.value}px`)}
                    className="w-full" />
                </div>
              </>
            )}

            {/* Colors */}
            {panelTab === 'colors' && (
              <>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Background Color</label>
                  <div className="flex gap-2">
                    <input type="color" value="#ffffff" onChange={e => applyStyle('background-color', e.target.value)} className="w-8 h-8 rounded cursor-pointer" />
                    <input type="text" placeholder="#ffffff" onChange={e => applyStyle('background-color', e.target.value)}
                      className="flex-1 p-1.5 border rounded font-mono bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200" />
                  </div>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Text Color</label>
                  <div className="flex gap-2">
                    <input type="color" value={selected.styles.color || '#000000'} onChange={e => applyStyle('color', e.target.value)} className="w-8 h-8 rounded cursor-pointer" />
                    <input type="text" value={selected.styles.color || ''} onChange={e => applyStyle('color', e.target.value)}
                      className="flex-1 p-1.5 border rounded font-mono bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200" />
                  </div>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Opacity</label>
                  <input type="range" min="0" max="100" step="1"
                    value={Math.round((parseFloat(selected.styles.opacity) || 1) * 100)}
                    onChange={e => applyStyle('opacity', String(parseInt(e.target.value) / 100))}
                    className="w-full" />
                  <span className="text-gray-600 dark:text-gray-300">{Math.round((parseFloat(selected.styles.opacity) || 1) * 100)}%</span>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Border Radius</label>
                  <input type="range" min="0" max="50" step="1"
                    value={parsePixels(selected.styles.borderRadius)}
                    onChange={e => applyStyle('border-radius', `${e.target.value}px`)}
                    className="w-full" />
                  <span className="text-gray-600 dark:text-gray-300">{parsePixels(selected.styles.borderRadius)}px</span>
                </div>
              </>
            )}

            {/* Spacing */}
            {panelTab === 'spacing' && (
              <>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1 font-medium">Padding</label>
                  <div className="grid grid-cols-2 gap-2">
                    {(['Top', 'Right', 'Bottom', 'Left'] as const).map(side => (
                      <div key={side}>
                        <label className="text-gray-400 text-[10px]">{side}</label>
                        <input type="number" min="0" max="200"
                          value={parsePixels(selected.styles[`padding${side}` as keyof typeof selected.styles] || '0')}
                          onChange={e => applyStyle(`padding-${side.toLowerCase()}`, `${e.target.value}px`)}
                          className="w-full p-1 border rounded text-center bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200" />
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1 font-medium">Margin</label>
                  <div className="grid grid-cols-2 gap-2">
                    {(['Top', 'Right', 'Bottom', 'Left'] as const).map(side => (
                      <div key={side}>
                        <label className="text-gray-400 text-[10px]">{side}</label>
                        <input type="number" min="-100" max="200"
                          value={parsePixels(selected.styles[`margin${side}` as keyof typeof selected.styles] || '0')}
                          onChange={e => applyStyle(`margin-${side.toLowerCase()}`, `${e.target.value}px`)}
                          className="w-full p-1 border rounded text-center bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200" />
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Width</label>
                  <input type="text" value={selected.styles.width || 'auto'}
                    onChange={e => applyStyle('width', e.target.value)}
                    className="w-full p-1.5 border rounded bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200" />
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Height</label>
                  <input type="text" value={selected.styles.height || 'auto'}
                    onChange={e => applyStyle('height', e.target.value)}
                    className="w-full p-1.5 border rounded bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200" />
                </div>
              </>
            )}

            {/* Section controls */}
            {panelTab === 'section' && (
              <>
                <div className="space-y-2">
                  <button onClick={() => setShowSectionLibrary(true)}
                    className="w-full flex items-center gap-2 px-3 py-2 border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300">
                    <Plus className="w-4 h-4" /> Add Section Below
                  </button>
                  <button onClick={duplicateSelected}
                    className="w-full flex items-center gap-2 px-3 py-2 border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300">
                    <Copy className="w-4 h-4" /> Duplicate Section
                  </button>
                  <button onClick={deleteSelected}
                    className="w-full flex items-center gap-2 px-3 py-2 border border-red-200 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 text-red-600">
                    <Trash2 className="w-4 h-4" /> Delete Section
                  </button>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1 font-medium">Background</label>
                  <div className="flex gap-2">
                    <input type="color" value="#ffffff" onChange={e => applyStyle('background-color', e.target.value)} className="w-8 h-8 rounded cursor-pointer" />
                    <input type="text" placeholder="Color or gradient" onChange={e => applyStyle('background', e.target.value)}
                      className="flex-1 p-1.5 border rounded font-mono bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200" />
                  </div>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Max Width</label>
                  <input type="range" min="800" max="1400" step="50"
                    value={1200}
                    onChange={e => applyStyle('max-width', `${e.target.value}px`)}
                    className="w-full" />
                </div>
              </>
            )}

            {/* Image controls */}
            {panelTab === 'image' && (
              <>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Image Source</label>
                  <input type="text" placeholder="Image URL"
                    className="w-full p-1.5 border rounded bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
                    onChange={e => {
                      if (!iframeRef.current?.contentDocument || !selected) return
                      try {
                        const el = iframeRef.current.contentDocument.querySelector(selected.selector) as HTMLImageElement
                        if (el) { el.src = e.target.value; onHtmlChange(getCleanBodyHtml(iframeRef.current.contentDocument)) }
                      } catch { /* ignore */ }
                    }} />
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Object Fit</label>
                  <select className="w-full p-1.5 border rounded bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
                    onChange={e => applyStyle('object-fit', e.target.value)}>
                    <option value="cover">Cover</option>
                    <option value="contain">Contain</option>
                    <option value="fill">Fill</option>
                    <option value="none">None</option>
                  </select>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Alt Text</label>
                  <input type="text" placeholder="Describe the image"
                    className="w-full p-1.5 border rounded bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
                    onChange={e => {
                      if (!iframeRef.current?.contentDocument || !selected) return
                      try {
                        const el = iframeRef.current.contentDocument.querySelector(selected.selector) as HTMLImageElement
                        if (el) { el.alt = e.target.value; onHtmlChange(getCleanBodyHtml(iframeRef.current.contentDocument)) }
                      } catch { /* ignore */ }
                    }} />
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Border Radius</label>
                  <input type="range" min="0" max="50" step="1" value={0}
                    onChange={e => applyStyle('border-radius', `${e.target.value}px`)} className="w-full" />
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Shadow</label>
                  <select className="w-full p-1.5 border rounded bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
                    onChange={e => applyStyle('box-shadow', e.target.value)}>
                    <option value="none">None</option>
                    <option value="0 1px 3px rgba(0,0,0,0.12)">Small</option>
                    <option value="0 4px 6px rgba(0,0,0,0.1)">Medium</option>
                    <option value="0 10px 25px rgba(0,0,0,0.15)">Large</option>
                  </select>
                </div>
              </>
            )}

            {/* Button controls */}
            {panelTab === 'button' && (
              <>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Background</label>
                  <div className="flex gap-2">
                    <input type="color" value="#3b82f6" onChange={e => applyStyle('background-color', e.target.value)} className="w-8 h-8 rounded cursor-pointer" />
                    <input type="text" placeholder="#3b82f6" onChange={e => applyStyle('background-color', e.target.value)}
                      className="flex-1 p-1.5 border rounded font-mono bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200" />
                  </div>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Text Color</label>
                  <div className="flex gap-2">
                    <input type="color" value="#ffffff" onChange={e => applyStyle('color', e.target.value)} className="w-8 h-8 rounded cursor-pointer" />
                    <input type="text" placeholder="#ffffff" onChange={e => applyStyle('color', e.target.value)}
                      className="flex-1 p-1.5 border rounded font-mono bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200" />
                  </div>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Border Radius</label>
                  <input type="range" min="0" max="50" value={8}
                    onChange={e => applyStyle('border-radius', `${e.target.value}px`)} className="w-full" />
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Size</label>
                  <div className="flex gap-1">
                    {[
                      { label: 'S', padding: '6px 16px' },
                      { label: 'M', padding: '10px 24px' },
                      { label: 'L', padding: '14px 32px' },
                      { label: 'Full', padding: '14px 32px', width: '100%' },
                    ].map(s => (
                      <button key={s.label} onClick={() => {
                        applyStyle('padding', s.padding)
                        if (s.width) applyStyle('width', s.width)
                      }}
                        className="flex-1 px-2 py-1 border rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-center">
                        {s.label}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Link URL</label>
                  <input type="text" placeholder="https://..."
                    className="w-full p-1.5 border rounded bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
                    onChange={e => {
                      if (!iframeRef.current?.contentDocument || !selected) return
                      try {
                        const el = iframeRef.current.contentDocument.querySelector(selected.selector) as HTMLAnchorElement
                        if (el && 'href' in el) { el.href = e.target.value; onHtmlChange(getCleanBodyHtml(iframeRef.current.contentDocument)) }
                      } catch { /* ignore */ }
                    }} />
                </div>
              </>
            )}

            {/* Layout */}
            {panelTab === 'layout' && (
              <>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Columns</label>
                  <div className="flex gap-1">
                    {[1, 2, 3, 4].map(n => (
                      <button key={n} onClick={() => applyStyle('grid-template-columns', `repeat(${n}, 1fr)`)}
                        className="flex-1 px-2 py-2 border rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-center">
                        {n}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Gap</label>
                  <input type="range" min="0" max="60" step="4" value={16}
                    onChange={e => applyStyle('gap', `${e.target.value}px`)} className="w-full" />
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Display</label>
                  <select className="w-full p-1.5 border rounded bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
                    onChange={e => applyStyle('display', e.target.value)}>
                    <option value="block">Block</option>
                    <option value="flex">Flex</option>
                    <option value="grid">Grid</option>
                    <option value="inline-flex">Inline Flex</option>
                  </select>
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Align Items</label>
                  <div className="flex gap-1">
                    {['flex-start', 'center', 'flex-end'].map(v => (
                      <button key={v} onClick={() => applyStyle('align-items', v)}
                        className="flex-1 px-2 py-1 border rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-center text-[10px]">
                        {v.replace('flex-', '')}
                      </button>
                    ))}
                  </div>
                </div>
              </>
            )}

            {/* Video background */}
            {panelTab === 'video' && (
              <>
                <p className="text-gray-500 dark:text-gray-400 mb-2">Add a video background to this section.</p>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Upload Video</label>
                  <input type="file" accept="video/mp4,video/webm,video/quicktime"
                    className="w-full text-xs"
                    onChange={async (e) => {
                      const file = e.target.files?.[0]
                      if (!file || !onVideoUpload) return
                      try {
                        const result = await onVideoUpload(file)
                        // Inject video background into selected section
                        if (iframeRef.current?.contentDocument && selected) {
                          const el = iframeRef.current.contentDocument.querySelector(selected.selector) as HTMLElement
                          if (el) {
                            el.style.position = 'relative'
                            el.style.overflow = 'hidden'
                            const video = iframeRef.current.contentDocument.createElement('video')
                            video.autoplay = true
                            video.muted = true
                            video.loop = true
                            video.playsInline = true
                            video.poster = result.poster_url
                            video.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;object-fit:cover;z-index:0;'
                            const sourceWebm = iframeRef.current.contentDocument.createElement('source')
                            sourceWebm.src = result.webm_url
                            sourceWebm.type = 'video/webm'
                            const sourceMp4 = iframeRef.current.contentDocument.createElement('source')
                            sourceMp4.src = result.mp4_url
                            sourceMp4.type = 'video/mp4'
                            video.appendChild(sourceWebm)
                            video.appendChild(sourceMp4)
                            el.insertBefore(video, el.firstChild)
                            // Add overlay
                            const overlay = iframeRef.current.contentDocument.createElement('div')
                            overlay.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.4);z-index:0;'
                            el.insertBefore(overlay, video.nextSibling)
                            // Make content relative
                            Array.from(el.children).forEach((child, i) => {
                              if (i > 1) (child as HTMLElement).style.position = 'relative'
                              if (i > 1) (child as HTMLElement).style.zIndex = '1'
                            })
                            onHtmlChange(getCleanBodyHtml(iframeRef.current.contentDocument))
                          }
                        }
                      } catch { /* ignore */ }
                    }} />
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Or paste URL</label>
                  <input type="text" placeholder="https://..."
                    className="w-full p-1.5 border rounded bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200" />
                </div>
                <div>
                  <label className="block text-gray-500 dark:text-gray-400 mb-1">Overlay Opacity</label>
                  <input type="range" min="0" max="80" step="5" value={40} className="w-full" />
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* Section Library Modal */}
      {showSectionLibrary && (
        <div className="absolute inset-0 z-50 bg-black/40 flex items-center justify-center" onClick={() => setShowSectionLibrary(false)}>
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-[600px] max-h-[80vh] overflow-hidden" onClick={e => e.stopPropagation()}>
            <div className="p-4 border-b flex items-center justify-between">
              <h3 className="font-semibold text-gray-900 dark:text-gray-100">Add Section</h3>
              <button onClick={() => setShowSectionLibrary(false)} className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700">✕</button>
            </div>
            <div className="p-4 grid grid-cols-3 gap-3 overflow-y-auto max-h-[60vh]">
              {SECTION_CATEGORIES.map(cat => (
                <button key={cat}
                  onClick={() => {
                    pushUndo()
                    const sectionHtml = SECTION_SNIPPETS[cat]
                      ?? `<section class="${cat.toLowerCase()} py-20 px-6"><div class="container mx-auto text-center"><h2 class="text-3xl font-bold mb-6">${cat} Section</h2><p class="text-gray-600">Edit this ${cat.toLowerCase()} section content.</p></div></section>`
                    onHtmlChange(html + '\n' + sectionHtml)
                    setShowSectionLibrary(false)
                  }}
                  className="p-4 border rounded-lg hover:border-blue-300 hover:bg-blue-50 dark:hover:bg-blue-900/20 text-center transition-colors">
                  <div className="w-10 h-10 mx-auto mb-2 rounded bg-gray-100 dark:bg-gray-700 flex items-center justify-center text-lg">
                    {cat === 'Hero' ? '🦸' : cat === 'Features' ? '⭐' : cat === 'Pricing' ? '💰' :
                     cat === 'Testimonials' ? '💬' : cat === 'CTA' ? '🎯' : cat === 'FAQ' ? '❓' :
                     cat === 'Team' ? '👥' : cat === 'Stats' ? '📊' : cat === 'Contact' ? '📧' :
                     cat === 'Footer' ? '📑' : cat === 'Gallery' ? '🖼️' : '🏢'}
                  </div>
                  <span className="text-sm font-medium text-gray-700 dark:text-gray-300">{cat}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
