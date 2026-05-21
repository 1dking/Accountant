"""Seed data for the section_variants table — Hero category, Commit 2.

Each template uses {{TOKEN}} placeholders that the variant picker
substitutes from default_props on insert, AND from the previous
section's edited_html when matching tokens are found (best-effort
content migration during ⟳ Change Variant).

Token contract:
  {{HEADLINE}}            — H1 / hero headline
  {{SUBHEADLINE}}         — supporting paragraph below headline
  {{CTA_PRIMARY_TEXT}}    — primary button label
  {{CTA_PRIMARY_HREF}}    — primary button href
  {{CTA_SECONDARY_TEXT}}  — secondary button label
  {{CTA_SECONDARY_HREF}}  — secondary button href
  {{IMAGE_URL}}           — hero image (where applicable)
  {{PHONE_NUMBER}}        — tel: link target

Variants follow Tailwind 4 conventions, mobile-first, semantic HTML,
JSX-flavored attributes (className) so they round-trip through
_jsx_to_html cleanly.
"""
from __future__ import annotations

HERO_VARIANTS = [
    {
        "id": "var_hero_video",
        "category": "hero",
        "variant_id": "hero_video",
        "display_name": "Video Background",
        "description": "Full-screen video background with text overlay and dual CTAs. Best for cinematic brand introductions.",
        "sort_order": 10,
        "default_animations": {
            "scroll_reveal": [
                {"selector": "h1", "from": {"y": 40, "opacity": 0},
                 "to": {"y": 0, "opacity": 1}, "duration": 0.9, "ease": "power2.out"},
                {"selector": "p", "from": {"y": 30, "opacity": 0},
                 "to": {"y": 0, "opacity": 1}, "duration": 0.7, "delay": 0.15, "ease": "power2.out"},
                {"selector": "a", "from": {"y": 20, "opacity": 0},
                 "to": {"y": 0, "opacity": 1}, "duration": 0.5, "delay": 0.3, "stagger": 0.1, "ease": "power2.out"},
            ],
        },
        # VIDEO_URL is in the MEDIA_TOKENS whitelist — kept literal in
        # jsx_content at insert time, substituted only at compile_page
        # from default_props ⊕ section.media_overrides. Lets the user
        # change the video without re-rendering the whole template.
        "default_props": {
            "HEADLINE": "Elevate Your Brand. Define Your Future.",
            "SUBHEADLINE": "We craft unique identities that resonate and drive growth.",
            "CTA_PRIMARY_TEXT": "Get a Free Consultation",
            "CTA_PRIMARY_HREF": "#contact",
            "CTA_SECONDARY_TEXT": "Watch our reel",
            "CTA_SECONDARY_HREF": "#reel",
            # Default: a calm Mixkit clip (CC0). Replaced via the
            # VIDEO_URL slot — pasting a YouTube or Vimeo URL renders
            # an iframe, mp4 renders a <video> element, etc.
            "VIDEO_URL": "https://assets.mixkit.co/videos/preview/mixkit-stars-in-space-1610-large.mp4",
            "VIDEO_POSTER_URL": "https://images.unsplash.com/photo-1462331940025-496dfbfc7564?auto=format&fit=crop&w=1920&q=80",
        },
        # VIDEO_EMBED expands at compile time to the right element for
        # the URL value: <iframe> for YouTube/Vimeo, <video> for mp4.
        # Closes the Commit 3 bug where <video src=youtube_embed_url>
        # silently failed (browsers can't play iframe URLs in <video>).
        "jsx_template": """<section className="relative isolate overflow-hidden text-white min-h-[80vh] flex items-center justify-center py-16 px-4">
  <div className="absolute inset-0 z-0 overflow-hidden">{{VIDEO_EMBED}}</div>
  <div className="absolute inset-0 z-10 bg-gradient-to-br from-slate-950/85 via-slate-950/65 to-indigo-950/70 pointer-events-none"></div>
  <div className="relative z-20 max-w-4xl mx-auto text-center space-y-8">
    <h1 className="text-4xl sm:text-5xl md:text-6xl font-extrabold leading-tight tracking-tight">
      {{HEADLINE}}
    </h1>
    <p className="text-lg sm:text-xl text-slate-200 max-w-2xl mx-auto">
      {{SUBHEADLINE}}
    </p>
    <div className="flex flex-col sm:flex-row justify-center gap-4 pt-4">
      <a href="{{CTA_PRIMARY_HREF}}" className="px-8 py-3 bg-white text-slate-900 font-bold rounded-full shadow-lg hover:bg-gray-100 transition transform hover:scale-105">
        {{CTA_PRIMARY_TEXT}}
      </a>
      <a href="{{CTA_SECONDARY_HREF}}" className="px-8 py-3 bg-transparent border-2 border-white/60 text-white font-bold rounded-full shadow-lg hover:bg-white/10 transition transform hover:scale-105">
        {{CTA_SECONDARY_TEXT}}
      </a>
    </div>
  </div>
</section>""",
    },
    {
        "id": "var_hero_two_col_image",
        "category": "hero",
        "variant_id": "hero_two_col_image",
        "display_name": "Two-Column with Image",
        "description": "Copy on the left, image on the right. Classic converter for SaaS and services.",
        "sort_order": 20,
        "default_animations": {
            "scroll_reveal": [
                {"selector": "h1, p", "from": {"x": -30, "opacity": 0},
                 "to": {"x": 0, "opacity": 1}, "duration": 0.8, "stagger": 0.1, "ease": "power2.out"},
                {"selector": "a", "from": {"y": 20, "opacity": 0},
                 "to": {"y": 0, "opacity": 1}, "duration": 0.5, "delay": 0.3, "stagger": 0.1, "ease": "power2.out"},
                {"selector": "img, video, iframe", "from": {"x": 40, "opacity": 0},
                 "to": {"x": 0, "opacity": 1}, "duration": 0.9, "delay": 0.2, "ease": "power2.out"},
            ],
        },
        "default_props": {
            "HEADLINE": "Built for teams that move fast.",
            "SUBHEADLINE": "Everything you need to ship — from idea to revenue — without the friction. Trusted by 500+ growing companies.",
            "CTA_PRIMARY_TEXT": "Start Free Trial",
            "CTA_PRIMARY_HREF": "#signup",
            "CTA_SECONDARY_TEXT": "Watch Demo",
            "CTA_SECONDARY_HREF": "#demo",
            # MEDIA_URL backs the flexible MEDIA_EMBED slot. Default is
            # an image; user can swap to YouTube / Vimeo / mp4 from the
            # picker without changing the variant.
            "MEDIA_URL": "https://images.unsplash.com/photo-1551434678-e076c223a692?auto=format&fit=crop&w=1200&q=80",
        },
        # MEDIA_EMBED expands at compile time to <img>, <video>, or
        # <iframe> depending on the URL pattern. Lets the right-column
        # slot accept any media type while keeping the same layout.
        "jsx_template": """<section className="relative overflow-hidden bg-white py-16 sm:py-24 lg:py-32">
  <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
    <div className="grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">
      <div className="space-y-8">
        <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight text-gray-900 leading-tight">
          {{HEADLINE}}
        </h1>
        <p className="text-lg sm:text-xl text-gray-600 leading-relaxed max-w-xl">
          {{SUBHEADLINE}}
        </p>
        <div className="flex flex-col sm:flex-row gap-4 pt-2">
          <a href="{{CTA_PRIMARY_HREF}}" className="inline-flex items-center justify-center px-7 py-3.5 bg-gray-900 text-white font-semibold rounded-lg shadow-sm hover:bg-gray-800 transition">
            {{CTA_PRIMARY_TEXT}}
          </a>
          <a href="{{CTA_SECONDARY_HREF}}" className="inline-flex items-center justify-center px-7 py-3.5 bg-gray-100 text-gray-900 font-semibold rounded-lg hover:bg-gray-200 transition">
            {{CTA_SECONDARY_TEXT}}
          </a>
        </div>
      </div>
      <div className="relative">
        <div className="absolute inset-0 -m-4 bg-gradient-to-br from-indigo-200 to-purple-200 rounded-3xl blur-2xl opacity-40 pointer-events-none"></div>
        <div className="relative rounded-2xl shadow-2xl w-full aspect-[4/3] overflow-hidden bg-gray-100">{{MEDIA_EMBED}}</div>
      </div>
    </div>
  </div>
</section>""",
    },
    {
        "id": "var_hero_two_col_form",
        "category": "hero",
        "variant_id": "hero_two_col_form",
        "display_name": "Two-Column with Lead Form",
        "description": "Copy left, capture form right. Built for lead generation and consultation booking.",
        "sort_order": 30,
        "default_animations": {
            "scroll_reveal": [
                {"selector": "h1, p, ul", "from": {"x": -30, "opacity": 0},
                 "to": {"x": 0, "opacity": 1}, "duration": 0.8, "stagger": 0.1, "ease": "power2.out"},
                {"selector": "form", "from": {"y": 30, "opacity": 0},
                 "to": {"y": 0, "opacity": 1}, "duration": 0.8, "delay": 0.2, "ease": "power2.out"},
                {"selector": "form > div, form > button", "from": {"y": 15, "opacity": 0},
                 "to": {"y": 0, "opacity": 1}, "duration": 0.5, "delay": 0.4, "stagger": 0.08, "ease": "power2.out"},
            ],
        },
        "default_props": {
            "HEADLINE": "Book your free strategy session.",
            "SUBHEADLINE": "Tell us what you're building. We'll send a personalized plan within 24 hours — no obligations, no upsells.",
            "CTA_PRIMARY_TEXT": "Send My Plan",
            "CTA_PRIMARY_HREF": "#",
        },
        "jsx_template": """<section className="relative overflow-hidden bg-gradient-to-br from-slate-50 via-white to-indigo-50 py-16 sm:py-20 lg:py-24">
  <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
    <div className="grid lg:grid-cols-2 gap-12 items-center">
      <div className="space-y-6">
        <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-indigo-100 text-indigo-700 rounded-full text-xs font-semibold uppercase tracking-wider">
          <span className="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-pulse"></span>
          Free Strategy Session
        </span>
        <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight text-gray-900 leading-tight">
          {{HEADLINE}}
        </h1>
        <p className="text-lg text-gray-600 leading-relaxed max-w-xl">
          {{SUBHEADLINE}}
        </p>
        <ul className="space-y-2 pt-2">
          <li className="flex items-center gap-2 text-sm text-gray-700">
            <svg className="w-5 h-5 text-emerald-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path></svg>
            <span>Personalized plan within 24 hours</span>
          </li>
          <li className="flex items-center gap-2 text-sm text-gray-700">
            <svg className="w-5 h-5 text-emerald-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path></svg>
            <span>No credit card required</span>
          </li>
          <li className="flex items-center gap-2 text-sm text-gray-700">
            <svg className="w-5 h-5 text-emerald-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path></svg>
            <span>Cancel anytime, no questions asked</span>
          </li>
        </ul>
      </div>
      <div className="bg-white rounded-2xl shadow-xl border border-gray-100 p-6 sm:p-8">
        <form action="{{CTA_PRIMARY_HREF}}" method="post" className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Full name</label>
            <input type="text" name="name" required className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none" placeholder="Jane Smith" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Work email</label>
            <input type="email" name="email" required className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none" placeholder="jane@company.com" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Phone (optional)</label>
            <input type="tel" name="phone" className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none" placeholder="+1 (555) 000-0000" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">What are you working on?</label>
            <textarea name="message" rows="3" required className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none resize-none" placeholder="A few sentences about your project..."></textarea>
          </div>
          <button type="submit" className="w-full px-6 py-3 bg-indigo-600 text-white font-semibold rounded-lg shadow-sm hover:bg-indigo-700 transition">
            {{CTA_PRIMARY_TEXT}}
          </button>
          <p className="text-xs text-gray-500 text-center">By submitting, you agree to our terms. We respect your privacy.</p>
        </form>
      </div>
    </div>
  </div>
</section>""",
    },
    {
        "id": "var_hero_with_stats",
        "category": "hero",
        "variant_id": "hero_with_stats",
        "display_name": "Hero with Stats",
        "description": "Lead with your numbers. Hero + 4-stat horizontal strip for instant credibility.",
        "sort_order": 40,
        "default_animations": {
            "scroll_reveal": [
                {"selector": "h1", "from": {"y": 40, "opacity": 0},
                 "to": {"y": 0, "opacity": 1}, "duration": 0.9, "ease": "power2.out"},
                {"selector": "p", "from": {"y": 30, "opacity": 0},
                 "to": {"y": 0, "opacity": 1}, "duration": 0.7, "delay": 0.15, "ease": "power2.out"},
                {"selector": "a", "from": {"y": 20, "opacity": 0},
                 "to": {"y": 0, "opacity": 1}, "duration": 0.5, "delay": 0.3, "stagger": 0.1, "ease": "power2.out"},
                {"selector": ".stat-label, [data-stat-label]", "from": {"opacity": 0},
                 "to": {"opacity": 1}, "duration": 0.5, "delay": 0.6, "stagger": 0.1, "ease": "power2.out"},
            ],
            # Stats are large gradient-text numbers in the hero_with_stats
            # template — the selector picks them up via the
            # bg-clip-text + gradient classes.
            "counter_up": [
                {"selector": ".text-4xl.sm\\:text-5xl.font-extrabold", "duration": 1.6, "ease": "power2.out"},
            ],
        },
        "default_props": {
            "HEADLINE": "Trusted by founders. Loved by teams.",
            "SUBHEADLINE": "The numbers speak for themselves. Real results from real customers, built into every release.",
            "CTA_PRIMARY_TEXT": "Get Started Free",
            "CTA_PRIMARY_HREF": "#signup",
            "CTA_SECONDARY_TEXT": "See Customers",
            "CTA_SECONDARY_HREF": "#customers",
            "STAT_1_VALUE": "500+",
            "STAT_1_LABEL": "Active Customers",
            "STAT_2_VALUE": "10×",
            "STAT_2_LABEL": "Faster Workflow",
            "STAT_3_VALUE": "99.9%",
            "STAT_3_LABEL": "Uptime SLA",
            "STAT_4_VALUE": "4.9★",
            "STAT_4_LABEL": "Customer Rating",
        },
        "jsx_template": """<section className="relative overflow-hidden bg-gradient-to-b from-gray-50 to-white py-16 sm:py-20 lg:py-24">
  <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
    <div className="text-center max-w-3xl mx-auto space-y-6">
      <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight text-gray-900 leading-tight">
        {{HEADLINE}}
      </h1>
      <p className="text-lg sm:text-xl text-gray-600 leading-relaxed">
        {{SUBHEADLINE}}
      </p>
      <div className="flex flex-col sm:flex-row justify-center gap-4 pt-4">
        <a href="{{CTA_PRIMARY_HREF}}" className="inline-flex items-center justify-center px-7 py-3.5 bg-gray-900 text-white font-semibold rounded-lg shadow-sm hover:bg-gray-800 transition">
          {{CTA_PRIMARY_TEXT}}
        </a>
        <a href="{{CTA_SECONDARY_HREF}}" className="inline-flex items-center justify-center px-7 py-3.5 bg-white text-gray-900 font-semibold rounded-lg border border-gray-200 hover:bg-gray-50 transition">
          {{CTA_SECONDARY_TEXT}}
        </a>
      </div>
    </div>
    <div className="mt-16 sm:mt-20 grid grid-cols-2 md:grid-cols-4 gap-8 sm:gap-12 max-w-5xl mx-auto">
      <div className="text-center">
        <div className="text-4xl sm:text-5xl font-extrabold bg-gradient-to-br from-indigo-600 to-purple-600 bg-clip-text text-transparent">{{STAT_1_VALUE}}</div>
        <div className="mt-2 text-sm text-gray-500 uppercase tracking-wider font-medium">{{STAT_1_LABEL}}</div>
      </div>
      <div className="text-center">
        <div className="text-4xl sm:text-5xl font-extrabold bg-gradient-to-br from-indigo-600 to-purple-600 bg-clip-text text-transparent">{{STAT_2_VALUE}}</div>
        <div className="mt-2 text-sm text-gray-500 uppercase tracking-wider font-medium">{{STAT_2_LABEL}}</div>
      </div>
      <div className="text-center">
        <div className="text-4xl sm:text-5xl font-extrabold bg-gradient-to-br from-indigo-600 to-purple-600 bg-clip-text text-transparent">{{STAT_3_VALUE}}</div>
        <div className="mt-2 text-sm text-gray-500 uppercase tracking-wider font-medium">{{STAT_3_LABEL}}</div>
      </div>
      <div className="text-center">
        <div className="text-4xl sm:text-5xl font-extrabold bg-gradient-to-br from-indigo-600 to-purple-600 bg-clip-text text-transparent">{{STAT_4_VALUE}}</div>
        <div className="mt-2 text-sm text-gray-500 uppercase tracking-wider font-medium">{{STAT_4_LABEL}}</div>
      </div>
    </div>
  </div>
</section>""",
    },
]


def all_variants() -> list[dict]:
    """All seed variants across categories. Currently Hero only;
    Commit 3 will add the remaining 11 categories."""
    return list(HERO_VARIANTS)
