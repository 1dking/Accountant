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


# =============================================================================
# FEATURES variants (Commit 5)
# =============================================================================
#
# Convention for non-Hero flagships:
#  - Section-level animations via default_animations (entry on scroll).
#  - Per-card hover effects via Tailwind hover: classes directly in the
#    template (hover:-translate-y-1 hover:shadow-xl etc.). Reason:
#    section.animations.preset = "hover_lift" lifts the WHOLE wrapper;
#    per-card lifts belong in the markup itself. Keeps the preset
#    system focused on section-level effects.
#  - Realistic placeholder content — written for a generic SaaS context
#    so the variant looks production-ready on insert, not "Item One/Two".

FEATURES_VARIANTS = [
    {
        "id": "var_features_3col_icon",
        "category": "features",
        "variant_id": "features_3col_icon",
        "display_name": "3-Column Icon Grid",
        "description": "Six features in a 3-column grid with gradient icon tiles. Best for showcasing capabilities at a glance.",
        "sort_order": 10,
        "default_props": {
            "EYEBROW": "Why teams choose us",
            "HEADLINE": "Everything you need, nothing you don't.",
            "SUBHEADLINE": "Six reasons our customers stay. Built for teams shipping in the real world.",
            "FEATURE_1_TITLE": "Lightning-fast performance",
            "FEATURE_1_BODY": "Sub-100ms response times worldwide. Your team never waits on us.",
            "FEATURE_2_TITLE": "Seamless team collaboration",
            "FEATURE_2_BODY": "Real-time editing, granular permissions, comments where work happens.",
            "FEATURE_3_TITLE": "Bank-grade security",
            "FEATURE_3_BODY": "SOC 2 Type II, end-to-end encryption, and audit logs on every action.",
            "FEATURE_4_TITLE": "Real-time insights",
            "FEATURE_4_BODY": "Dashboards that surface the metric that matters before you ask.",
            "FEATURE_5_TITLE": "Custom integrations",
            "FEATURE_5_BODY": "Connect Slack, Linear, Notion, and 200+ tools your team already uses.",
            "FEATURE_6_TITLE": "White-glove support",
            "FEATURE_6_BODY": "Real humans on chat in under 5 minutes. Pro plans get a dedicated CSM.",
        },
        # Section-level entry: 6 cards stagger up as the section scrolls
        # into view. Per-card hover handled via Tailwind classes inside
        # the template (transition + hover:-translate-y-1 + hover:shadow-xl).
        "default_animations": {
            "preset": "stagger_children",
            "config": {"duration": 0.6, "stagger": 0.08, "ease": "power2.out"},
        },
        # Tailwind notes embedded in the template:
        # - bg-slate-950 base section
        # - bg-white/5 backdrop-blur cards with subtle white/10 border
        # - 6 gradient icon tiles using the OCIDM palette
        #   (indigo→violet→fuchsia, cyan→indigo, amber→pink, etc.)
        # - Per-card hover: lift + shadow + accent border on hover
        # - Lucide-style inline SVG paths (no external icon dep)
        "jsx_template": """<section className="relative isolate overflow-hidden bg-slate-950 py-20 sm:py-24 lg:py-28">
  <div className="absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_top,_rgba(99,102,241,0.18),_transparent_60%)]"></div>
  <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
    <div className="text-center max-w-3xl mx-auto mb-14 sm:mb-16">
      <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-white/5 border border-white/10 backdrop-blur-sm text-indigo-200 rounded-full text-xs font-semibold uppercase tracking-wider mb-5">
        {{EYEBROW}}
      </span>
      <h2 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight text-white leading-tight">
        {{HEADLINE}}
      </h2>
      <p className="mt-4 text-base sm:text-lg text-gray-300 leading-relaxed">
        {{SUBHEADLINE}}
      </p>
    </div>
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5 lg:gap-6">
      <div className="group relative rounded-2xl p-6 bg-white/[0.04] backdrop-blur-xl border border-white/10 transition-all duration-200 hover:-translate-y-1 hover:bg-white/[0.07] hover:border-indigo-400/40 hover:shadow-[0_12px_32px_rgba(99,102,241,0.18)]">
        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-indigo-500 via-violet-500 to-fuchsia-500 flex items-center justify-center mb-5 shadow-lg shadow-indigo-500/30">
          <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
        </div>
        <h3 className="text-lg font-semibold text-white mb-2">{{FEATURE_1_TITLE}}</h3>
        <p className="text-sm text-gray-300 leading-relaxed">{{FEATURE_1_BODY}}</p>
      </div>
      <div className="group relative rounded-2xl p-6 bg-white/[0.04] backdrop-blur-xl border border-white/10 transition-all duration-200 hover:-translate-y-1 hover:bg-white/[0.07] hover:border-violet-400/40 hover:shadow-[0_12px_32px_rgba(139,92,246,0.18)]">
        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-violet-500 via-fuchsia-500 to-pink-500 flex items-center justify-center mb-5 shadow-lg shadow-violet-500/30">
          <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"/></svg>
        </div>
        <h3 className="text-lg font-semibold text-white mb-2">{{FEATURE_2_TITLE}}</h3>
        <p className="text-sm text-gray-300 leading-relaxed">{{FEATURE_2_BODY}}</p>
      </div>
      <div className="group relative rounded-2xl p-6 bg-white/[0.04] backdrop-blur-xl border border-white/10 transition-all duration-200 hover:-translate-y-1 hover:bg-white/[0.07] hover:border-fuchsia-400/40 hover:shadow-[0_12px_32px_rgba(217,70,239,0.18)]">
        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-fuchsia-500 via-pink-500 to-rose-500 flex items-center justify-center mb-5 shadow-lg shadow-fuchsia-500/30">
          <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"/></svg>
        </div>
        <h3 className="text-lg font-semibold text-white mb-2">{{FEATURE_3_TITLE}}</h3>
        <p className="text-sm text-gray-300 leading-relaxed">{{FEATURE_3_BODY}}</p>
      </div>
      <div className="group relative rounded-2xl p-6 bg-white/[0.04] backdrop-blur-xl border border-white/10 transition-all duration-200 hover:-translate-y-1 hover:bg-white/[0.07] hover:border-cyan-400/40 hover:shadow-[0_12px_32px_rgba(6,182,212,0.18)]">
        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-cyan-500 via-sky-500 to-indigo-500 flex items-center justify-center mb-5 shadow-lg shadow-cyan-500/30">
          <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>
        </div>
        <h3 className="text-lg font-semibold text-white mb-2">{{FEATURE_4_TITLE}}</h3>
        <p className="text-sm text-gray-300 leading-relaxed">{{FEATURE_4_BODY}}</p>
      </div>
      <div className="group relative rounded-2xl p-6 bg-white/[0.04] backdrop-blur-xl border border-white/10 transition-all duration-200 hover:-translate-y-1 hover:bg-white/[0.07] hover:border-amber-400/40 hover:shadow-[0_12px_32px_rgba(245,158,11,0.18)]">
        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-amber-500 via-orange-500 to-pink-500 flex items-center justify-center mb-5 shadow-lg shadow-amber-500/30">
          <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M14 10l-2 1m0 0l-2-1m2 1v2.5M20 7l-2 1m2-1l-2-1m2 1v2.5M14 4l-2-1-2 1M4 7l2-1M4 7l2 1M4 7v2.5M12 21l-2-1m2 1l2-1m-2 1v-2.5M6 18l-2-1v-2.5M18 18l2-1v-2.5"/></svg>
        </div>
        <h3 className="text-lg font-semibold text-white mb-2">{{FEATURE_5_TITLE}}</h3>
        <p className="text-sm text-gray-300 leading-relaxed">{{FEATURE_5_BODY}}</p>
      </div>
      <div className="group relative rounded-2xl p-6 bg-white/[0.04] backdrop-blur-xl border border-white/10 transition-all duration-200 hover:-translate-y-1 hover:bg-white/[0.07] hover:border-emerald-400/40 hover:shadow-[0_12px_32px_rgba(16,185,129,0.18)]">
        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-emerald-500 via-teal-500 to-cyan-500 flex items-center justify-center mb-5 shadow-lg shadow-emerald-500/30">
          <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>
        </div>
        <h3 className="text-lg font-semibold text-white mb-2">{{FEATURE_6_TITLE}}</h3>
        <p className="text-sm text-gray-300 leading-relaxed">{{FEATURE_6_BODY}}</p>
      </div>
    </div>
  </div>
</section>""",
    },
]


# =============================================================================
# CTA variants (Commit 5)
# =============================================================================

CTA_VARIANTS = [
    {
        "id": "var_cta_centered_banner",
        "category": "cta",
        "variant_id": "cta_centered_banner",
        "display_name": "Centered Banner",
        "description": "Bold centered headline with dual CTAs on a gradient accent panel. Highest-engagement closing pattern.",
        "sort_order": 10,
        "default_props": {
            "EYEBROW": "Ready when you are",
            "HEADLINE": "Ship faster. Sleep better.",
            "SUBHEADLINE": "Join 500+ teams shipping faster with less friction. Start free — no credit card required.",
            "CTA_PRIMARY_TEXT": "Start free trial",
            "CTA_PRIMARY_HREF": "#signup",
            "CTA_SECONDARY_TEXT": "Book a demo",
            "CTA_SECONDARY_HREF": "#demo",
        },
        "default_animations": {
            "preset": "fade_up",
            "config": {"duration": 0.8, "delay": 0, "ease": "power2.out"},
        },
        "jsx_template": """<section className="relative isolate overflow-hidden bg-slate-950 py-20 sm:py-24 lg:py-32 px-4">
  <div className="absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_center,_rgba(139,92,246,0.20),_transparent_70%)]"></div>
  <div className="relative max-w-5xl mx-auto rounded-3xl overflow-hidden bg-gradient-to-br from-indigo-600 via-violet-600 to-fuchsia-600 shadow-2xl shadow-violet-900/40">
    <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_rgba(255,255,255,0.20),_transparent_60%)] pointer-events-none"></div>
    <div className="relative px-6 sm:px-12 lg:px-16 py-14 sm:py-16 lg:py-20 text-center">
      <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-white/15 backdrop-blur-sm border border-white/20 text-white rounded-full text-xs font-semibold uppercase tracking-wider mb-5">
        {{EYEBROW}}
      </span>
      <h2 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight text-white leading-tight max-w-3xl mx-auto">
        {{HEADLINE}}
      </h2>
      <p className="mt-4 text-base sm:text-lg text-indigo-100 leading-relaxed max-w-2xl mx-auto">
        {{SUBHEADLINE}}
      </p>
      <div className="mt-8 flex flex-col sm:flex-row justify-center gap-3 sm:gap-4">
        <a href="{{CTA_PRIMARY_HREF}}" className="inline-flex items-center justify-center px-7 py-3.5 bg-white text-slate-900 font-bold rounded-full shadow-lg hover:bg-gray-100 hover:scale-105 transition-all duration-200">
          {{CTA_PRIMARY_TEXT}}
        </a>
        <a href="{{CTA_SECONDARY_HREF}}" className="inline-flex items-center justify-center px-7 py-3.5 bg-white/10 backdrop-blur-sm border-2 border-white/40 text-white font-bold rounded-full hover:bg-white/20 hover:scale-105 transition-all duration-200">
          {{CTA_SECONDARY_TEXT}}
        </a>
      </div>
    </div>
  </div>
</section>""",
    },
]


# =============================================================================
# PRICING variants (Commit 5)
# =============================================================================

PRICING_VARIANTS = [
    {
        "id": "var_pricing_3tier_featured",
        "category": "pricing",
        "variant_id": "pricing_3tier_featured",
        "display_name": "3 Tiers with Featured Middle",
        "description": "Three pricing tiers with the recommended tier visually highlighted. Industry standard for SaaS.",
        "sort_order": 10,
        "default_props": {
            "EYEBROW": "Pricing",
            "HEADLINE": "Simple, transparent pricing.",
            "SUBHEADLINE": "Start free. Upgrade when you're ready. Cancel anytime.",
            "TIER_1_NAME": "Starter",
            "TIER_1_PRICE": "$0",
            "TIER_1_PERIOD": "/forever",
            "TIER_1_DESCRIPTION": "Everything to get started solo.",
            "TIER_1_CTA": "Get started",
            "TIER_2_NAME": "Pro",
            "TIER_2_PRICE": "$29",
            "TIER_2_PERIOD": "/user/month",
            "TIER_2_DESCRIPTION": "For small teams shipping every week.",
            "TIER_2_CTA": "Start free trial",
            "TIER_3_NAME": "Enterprise",
            "TIER_3_PRICE": "Custom",
            "TIER_3_PERIOD": "",
            "TIER_3_DESCRIPTION": "Security, SLAs, and a dedicated CSM.",
            "TIER_3_CTA": "Contact sales",
        },
        "default_animations": {
            "preset": "fade_up",
            "config": {"duration": 0.7, "stagger": 0.12, "ease": "power2.out"},
        },
        "jsx_template": """<section className="relative isolate overflow-hidden bg-slate-950 py-20 sm:py-24 lg:py-28">
  <div className="absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_top,_rgba(99,102,241,0.18),_transparent_60%)]"></div>
  <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
    <div className="text-center max-w-3xl mx-auto mb-14 sm:mb-16">
      <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-white/5 border border-white/10 backdrop-blur-sm text-indigo-200 rounded-full text-xs font-semibold uppercase tracking-wider mb-5">
        {{EYEBROW}}
      </span>
      <h2 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight text-white leading-tight">
        {{HEADLINE}}
      </h2>
      <p className="mt-4 text-base sm:text-lg text-gray-300 leading-relaxed">
        {{SUBHEADLINE}}
      </p>
    </div>
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 lg:gap-6 max-w-6xl mx-auto items-stretch">
      <div className="rounded-2xl p-6 sm:p-8 bg-white/[0.04] backdrop-blur-xl border border-white/10 transition-all duration-200 hover:-translate-y-1 hover:bg-white/[0.07] hover:border-white/20 flex flex-col">
        <h3 className="text-lg font-semibold text-white">{{TIER_1_NAME}}</h3>
        <p className="text-sm text-gray-400 mt-1 mb-6">{{TIER_1_DESCRIPTION}}</p>
        <div className="flex items-baseline gap-1 mb-6">
          <span className="text-4xl font-extrabold text-white">{{TIER_1_PRICE}}</span>
          <span className="text-sm text-gray-400">{{TIER_1_PERIOD}}</span>
        </div>
        <ul className="space-y-3 mb-8 flex-1">
          <li className="flex items-start gap-2 text-sm text-gray-300"><svg className="w-4 h-4 text-emerald-400 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="3"><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"/></svg>3 projects</li>
          <li className="flex items-start gap-2 text-sm text-gray-300"><svg className="w-4 h-4 text-emerald-400 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="3"><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"/></svg>Community support</li>
          <li className="flex items-start gap-2 text-sm text-gray-300"><svg className="w-4 h-4 text-emerald-400 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="3"><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"/></svg>Basic integrations</li>
        </ul>
        <a href="#starter" className="block text-center px-5 py-3 bg-white/10 border border-white/20 text-white font-semibold rounded-lg hover:bg-white/15 transition">{{TIER_1_CTA}}</a>
      </div>
      <div className="relative rounded-2xl p-6 sm:p-8 bg-gradient-to-br from-indigo-600/20 via-violet-600/20 to-fuchsia-600/20 backdrop-blur-xl border-2 border-indigo-400/60 shadow-[0_24px_64px_rgba(99,102,241,0.32)] transition-all duration-200 hover:-translate-y-1 lg:scale-105 flex flex-col">
        <span className="absolute -top-3 left-1/2 -translate-x-1/2 inline-flex items-center gap-1 px-3 py-1 bg-gradient-to-r from-indigo-500 to-fuchsia-500 text-white text-[10px] font-bold uppercase tracking-wider rounded-full shadow-lg">Most Popular</span>
        <h3 className="text-lg font-semibold text-white">{{TIER_2_NAME}}</h3>
        <p className="text-sm text-indigo-200 mt-1 mb-6">{{TIER_2_DESCRIPTION}}</p>
        <div className="flex items-baseline gap-1 mb-6">
          <span className="text-4xl font-extrabold bg-gradient-to-br from-white to-indigo-200 bg-clip-text text-transparent">{{TIER_2_PRICE}}</span>
          <span className="text-sm text-indigo-200">{{TIER_2_PERIOD}}</span>
        </div>
        <ul className="space-y-3 mb-8 flex-1">
          <li className="flex items-start gap-2 text-sm text-white"><svg className="w-4 h-4 text-emerald-400 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="3"><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"/></svg>Unlimited projects</li>
          <li className="flex items-start gap-2 text-sm text-white"><svg className="w-4 h-4 text-emerald-400 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="3"><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"/></svg>Priority support (under 5 min)</li>
          <li className="flex items-start gap-2 text-sm text-white"><svg className="w-4 h-4 text-emerald-400 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="3"><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"/></svg>All 200+ integrations</li>
          <li className="flex items-start gap-2 text-sm text-white"><svg className="w-4 h-4 text-emerald-400 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="3"><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"/></svg>Advanced analytics</li>
        </ul>
        <a href="#pro" className="block text-center px-5 py-3 bg-gradient-to-r from-indigo-500 to-fuchsia-500 text-white font-semibold rounded-lg shadow-lg hover:shadow-indigo-500/40 transition">{{TIER_2_CTA}}</a>
      </div>
      <div className="rounded-2xl p-6 sm:p-8 bg-white/[0.04] backdrop-blur-xl border border-white/10 transition-all duration-200 hover:-translate-y-1 hover:bg-white/[0.07] hover:border-white/20 flex flex-col">
        <h3 className="text-lg font-semibold text-white">{{TIER_3_NAME}}</h3>
        <p className="text-sm text-gray-400 mt-1 mb-6">{{TIER_3_DESCRIPTION}}</p>
        <div className="flex items-baseline gap-1 mb-6">
          <span className="text-4xl font-extrabold text-white">{{TIER_3_PRICE}}</span>
          <span className="text-sm text-gray-400">{{TIER_3_PERIOD}}</span>
        </div>
        <ul className="space-y-3 mb-8 flex-1">
          <li className="flex items-start gap-2 text-sm text-gray-300"><svg className="w-4 h-4 text-emerald-400 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="3"><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"/></svg>Everything in Pro</li>
          <li className="flex items-start gap-2 text-sm text-gray-300"><svg className="w-4 h-4 text-emerald-400 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="3"><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"/></svg>SOC 2, SSO, audit logs</li>
          <li className="flex items-start gap-2 text-sm text-gray-300"><svg className="w-4 h-4 text-emerald-400 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="3"><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"/></svg>99.99% uptime SLA</li>
          <li className="flex items-start gap-2 text-sm text-gray-300"><svg className="w-4 h-4 text-emerald-400 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="3"><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"/></svg>Dedicated CSM</li>
        </ul>
        <a href="#enterprise" className="block text-center px-5 py-3 bg-white/10 border border-white/20 text-white font-semibold rounded-lg hover:bg-white/15 transition">{{TIER_3_CTA}}</a>
      </div>
    </div>
  </div>
</section>""",
    },
]


# =============================================================================
# TESTIMONIALS variants (Commit 5)
# =============================================================================

TESTIMONIALS_VARIANTS = [
    {
        "id": "var_testimonials_3card_grid",
        "category": "testimonials",
        "variant_id": "testimonials_3card_grid",
        "display_name": "3-Card Grid",
        "description": "Three customer quotes with avatar, name, role, and company. Social proof without the noise.",
        "sort_order": 10,
        "default_props": {
            "EYEBROW": "Loved by teams worldwide",
            "HEADLINE": "Don't take our word for it.",
            "SUBHEADLINE": "What customers say after their first 90 days.",
            "Q1_TEXT": "We replaced three tools with this in our first week. The team actually uses it, which is more than I can say for the last six things I rolled out.",
            "Q1_NAME": "Maya Chen",
            "Q1_TITLE": "Head of Product, Aurelis",
            "Q1_INITIALS": "MC",
            "Q2_TEXT": "Support answered me in two minutes — at 11pm on a Saturday. That's not a feature on a deck, that's a real difference when something's broken.",
            "Q2_NAME": "Daniel Okafor",
            "Q2_TITLE": "CTO, Midstream Labs",
            "Q2_INITIALS": "DO",
            "Q3_TEXT": "Our launch window closed two months sooner because we stopped fighting tooling. I genuinely don't know what we did before.",
            "Q3_NAME": "Priya Iyer",
            "Q3_TITLE": "VP Engineering, Lumengrid",
            "Q3_INITIALS": "PI",
        },
        "default_animations": {
            "preset": "fade_up",
            "config": {"duration": 0.7, "stagger": 0.12, "ease": "power2.out"},
        },
        "jsx_template": """<section className="relative isolate overflow-hidden bg-slate-950 py-20 sm:py-24 lg:py-28">
  <div className="absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_bottom,_rgba(236,72,153,0.12),_transparent_60%)]"></div>
  <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
    <div className="text-center max-w-3xl mx-auto mb-14 sm:mb-16">
      <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-white/5 border border-white/10 backdrop-blur-sm text-fuchsia-200 rounded-full text-xs font-semibold uppercase tracking-wider mb-5">
        {{EYEBROW}}
      </span>
      <h2 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight text-white leading-tight">
        {{HEADLINE}}
      </h2>
      <p className="mt-4 text-base sm:text-lg text-gray-300 leading-relaxed">
        {{SUBHEADLINE}}
      </p>
    </div>
    <div className="grid grid-cols-1 md:grid-cols-3 gap-5 lg:gap-6">
      <figure className="rounded-2xl p-6 sm:p-7 bg-white/[0.04] backdrop-blur-xl border border-white/10 transition-all duration-200 hover:-translate-y-1 hover:bg-white/[0.07] hover:border-fuchsia-400/40 hover:shadow-[0_12px_32px_rgba(217,70,239,0.15)] flex flex-col">
        <svg className="w-7 h-7 text-fuchsia-400/70 mb-4" fill="currentColor" viewBox="0 0 24 24"><path d="M9.983 3v7.391c0 5.704-3.731 9.57-8.983 10.609l-.995-2.151c2.432-.917 3.995-3.638 3.995-5.849h-4v-10h9.983zm14.017 0v7.391c0 5.704-3.748 9.571-9 10.609l-.996-2.151c2.433-.917 3.996-3.638 3.996-5.849h-3.983v-10h9.983z"/></svg>
        <blockquote className="text-base text-gray-200 leading-relaxed flex-1">{{Q1_TEXT}}</blockquote>
        <figcaption className="mt-6 flex items-center gap-3">
          <div className="w-11 h-11 rounded-full bg-gradient-to-br from-indigo-500 to-violet-500 flex items-center justify-center text-white font-bold text-sm shadow-lg">{{Q1_INITIALS}}</div>
          <div>
            <div className="text-sm font-semibold text-white">{{Q1_NAME}}</div>
            <div className="text-xs text-gray-400">{{Q1_TITLE}}</div>
          </div>
        </figcaption>
      </figure>
      <figure className="rounded-2xl p-6 sm:p-7 bg-white/[0.04] backdrop-blur-xl border border-white/10 transition-all duration-200 hover:-translate-y-1 hover:bg-white/[0.07] hover:border-cyan-400/40 hover:shadow-[0_12px_32px_rgba(6,182,212,0.15)] flex flex-col">
        <svg className="w-7 h-7 text-cyan-400/70 mb-4" fill="currentColor" viewBox="0 0 24 24"><path d="M9.983 3v7.391c0 5.704-3.731 9.57-8.983 10.609l-.995-2.151c2.432-.917 3.995-3.638 3.995-5.849h-4v-10h9.983zm14.017 0v7.391c0 5.704-3.748 9.571-9 10.609l-.996-2.151c2.433-.917 3.996-3.638 3.996-5.849h-3.983v-10h9.983z"/></svg>
        <blockquote className="text-base text-gray-200 leading-relaxed flex-1">{{Q2_TEXT}}</blockquote>
        <figcaption className="mt-6 flex items-center gap-3">
          <div className="w-11 h-11 rounded-full bg-gradient-to-br from-cyan-500 to-indigo-500 flex items-center justify-center text-white font-bold text-sm shadow-lg">{{Q2_INITIALS}}</div>
          <div>
            <div className="text-sm font-semibold text-white">{{Q2_NAME}}</div>
            <div className="text-xs text-gray-400">{{Q2_TITLE}}</div>
          </div>
        </figcaption>
      </figure>
      <figure className="rounded-2xl p-6 sm:p-7 bg-white/[0.04] backdrop-blur-xl border border-white/10 transition-all duration-200 hover:-translate-y-1 hover:bg-white/[0.07] hover:border-emerald-400/40 hover:shadow-[0_12px_32px_rgba(16,185,129,0.15)] flex flex-col">
        <svg className="w-7 h-7 text-emerald-400/70 mb-4" fill="currentColor" viewBox="0 0 24 24"><path d="M9.983 3v7.391c0 5.704-3.731 9.57-8.983 10.609l-.995-2.151c2.432-.917 3.995-3.638 3.995-5.849h-4v-10h9.983zm14.017 0v7.391c0 5.704-3.748 9.571-9 10.609l-.996-2.151c2.433-.917 3.996-3.638 3.996-5.849h-3.983v-10h9.983z"/></svg>
        <blockquote className="text-base text-gray-200 leading-relaxed flex-1">{{Q3_TEXT}}</blockquote>
        <figcaption className="mt-6 flex items-center gap-3">
          <div className="w-11 h-11 rounded-full bg-gradient-to-br from-emerald-500 to-teal-500 flex items-center justify-center text-white font-bold text-sm shadow-lg">{{Q3_INITIALS}}</div>
          <div>
            <div className="text-sm font-semibold text-white">{{Q3_NAME}}</div>
            <div className="text-xs text-gray-400">{{Q3_TITLE}}</div>
          </div>
        </figcaption>
      </figure>
    </div>
  </div>
</section>""",
    },
]


# =============================================================================
# TEAM variants (Commit 5)
# =============================================================================

TEAM_VARIANTS = [
    {
        "id": "var_team_photo_grid_3col",
        "category": "team",
        "variant_id": "team_photo_grid_3col",
        "display_name": "3-Column Photo Grid",
        "description": "Six team members with avatars, names, roles, and social links. The classic 'meet the team' layout.",
        "sort_order": 10,
        "default_props": {
            "EYEBROW": "The team",
            "HEADLINE": "Built by people who've shipped before.",
            "SUBHEADLINE": "Engineers, designers, and operators who've seen what works and what wastes time.",
            "M1_NAME": "Alex Morgan",
            "M1_ROLE": "Co-founder & CEO",
            "M1_INITIALS": "AM",
            "M2_NAME": "Sana Velasquez",
            "M2_ROLE": "Co-founder & CTO",
            "M2_INITIALS": "SV",
            "M3_NAME": "Tomás Reyes",
            "M3_ROLE": "Head of Design",
            "M3_INITIALS": "TR",
            "M4_NAME": "Kenji Nakamura",
            "M4_ROLE": "Engineering Lead",
            "M4_INITIALS": "KN",
            "M5_NAME": "Amara Okonkwo",
            "M5_ROLE": "Customer Success",
            "M5_INITIALS": "AO",
            "M6_NAME": "Lina Halvorsen",
            "M6_ROLE": "Head of Marketing",
            "M6_INITIALS": "LH",
        },
        "default_animations": {
            "preset": "stagger_children",
            "config": {"duration": 0.6, "stagger": 0.08, "ease": "power2.out"},
        },
        "jsx_template": """<section className="relative isolate overflow-hidden bg-slate-950 py-20 sm:py-24 lg:py-28">
  <div className="absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_top,_rgba(16,185,129,0.12),_transparent_60%)]"></div>
  <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
    <div className="text-center max-w-3xl mx-auto mb-14 sm:mb-16">
      <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-white/5 border border-white/10 backdrop-blur-sm text-emerald-200 rounded-full text-xs font-semibold uppercase tracking-wider mb-5">
        {{EYEBROW}}
      </span>
      <h2 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight text-white leading-tight">
        {{HEADLINE}}
      </h2>
      <p className="mt-4 text-base sm:text-lg text-gray-300 leading-relaxed">
        {{SUBHEADLINE}}
      </p>
    </div>
    <div className="grid grid-cols-2 md:grid-cols-3 gap-5 lg:gap-6">
      <div className="group rounded-2xl p-5 sm:p-6 bg-white/[0.04] backdrop-blur-xl border border-white/10 transition-all duration-200 hover:-translate-y-1 hover:bg-white/[0.07] hover:border-emerald-400/40 text-center">
        <div className="relative w-20 h-20 sm:w-24 sm:h-24 mx-auto mb-4 rounded-full bg-gradient-to-br from-emerald-500 to-cyan-500 flex items-center justify-center text-white text-2xl font-bold shadow-lg shadow-emerald-500/30">{{M1_INITIALS}}</div>
        <h3 className="text-base font-semibold text-white">{{M1_NAME}}</h3>
        <p className="text-xs text-gray-400 mt-1">{{M1_ROLE}}</p>
      </div>
      <div className="group rounded-2xl p-5 sm:p-6 bg-white/[0.04] backdrop-blur-xl border border-white/10 transition-all duration-200 hover:-translate-y-1 hover:bg-white/[0.07] hover:border-cyan-400/40 text-center">
        <div className="relative w-20 h-20 sm:w-24 sm:h-24 mx-auto mb-4 rounded-full bg-gradient-to-br from-cyan-500 to-indigo-500 flex items-center justify-center text-white text-2xl font-bold shadow-lg shadow-cyan-500/30">{{M2_INITIALS}}</div>
        <h3 className="text-base font-semibold text-white">{{M2_NAME}}</h3>
        <p className="text-xs text-gray-400 mt-1">{{M2_ROLE}}</p>
      </div>
      <div className="group rounded-2xl p-5 sm:p-6 bg-white/[0.04] backdrop-blur-xl border border-white/10 transition-all duration-200 hover:-translate-y-1 hover:bg-white/[0.07] hover:border-indigo-400/40 text-center">
        <div className="relative w-20 h-20 sm:w-24 sm:h-24 mx-auto mb-4 rounded-full bg-gradient-to-br from-indigo-500 to-violet-500 flex items-center justify-center text-white text-2xl font-bold shadow-lg shadow-indigo-500/30">{{M3_INITIALS}}</div>
        <h3 className="text-base font-semibold text-white">{{M3_NAME}}</h3>
        <p className="text-xs text-gray-400 mt-1">{{M3_ROLE}}</p>
      </div>
      <div className="group rounded-2xl p-5 sm:p-6 bg-white/[0.04] backdrop-blur-xl border border-white/10 transition-all duration-200 hover:-translate-y-1 hover:bg-white/[0.07] hover:border-violet-400/40 text-center">
        <div className="relative w-20 h-20 sm:w-24 sm:h-24 mx-auto mb-4 rounded-full bg-gradient-to-br from-violet-500 to-fuchsia-500 flex items-center justify-center text-white text-2xl font-bold shadow-lg shadow-violet-500/30">{{M4_INITIALS}}</div>
        <h3 className="text-base font-semibold text-white">{{M4_NAME}}</h3>
        <p className="text-xs text-gray-400 mt-1">{{M4_ROLE}}</p>
      </div>
      <div className="group rounded-2xl p-5 sm:p-6 bg-white/[0.04] backdrop-blur-xl border border-white/10 transition-all duration-200 hover:-translate-y-1 hover:bg-white/[0.07] hover:border-fuchsia-400/40 text-center">
        <div className="relative w-20 h-20 sm:w-24 sm:h-24 mx-auto mb-4 rounded-full bg-gradient-to-br from-fuchsia-500 to-pink-500 flex items-center justify-center text-white text-2xl font-bold shadow-lg shadow-fuchsia-500/30">{{M5_INITIALS}}</div>
        <h3 className="text-base font-semibold text-white">{{M5_NAME}}</h3>
        <p className="text-xs text-gray-400 mt-1">{{M5_ROLE}}</p>
      </div>
      <div className="group rounded-2xl p-5 sm:p-6 bg-white/[0.04] backdrop-blur-xl border border-white/10 transition-all duration-200 hover:-translate-y-1 hover:bg-white/[0.07] hover:border-amber-400/40 text-center">
        <div className="relative w-20 h-20 sm:w-24 sm:h-24 mx-auto mb-4 rounded-full bg-gradient-to-br from-amber-500 to-orange-500 flex items-center justify-center text-white text-2xl font-bold shadow-lg shadow-amber-500/30">{{M6_INITIALS}}</div>
        <h3 className="text-base font-semibold text-white">{{M6_NAME}}</h3>
        <p className="text-xs text-gray-400 mt-1">{{M6_ROLE}}</p>
      </div>
    </div>
  </div>
</section>""",
    },
]


# =============================================================================
# STATS variants (Commit 5)
# =============================================================================

STATS_VARIANTS = [
    {
        "id": "var_stats_4col_horizontal",
        "category": "stats",
        "variant_id": "stats_4col_horizontal",
        "display_name": "4-Column Horizontal Strip",
        "description": "Four big numbers in a row with gradient text + small labels. Numbers count up on scroll.",
        "sort_order": 10,
        "default_props": {
            "EYEBROW": "By the numbers",
            "HEADLINE": "Numbers that move teams forward.",
            "SUBHEADLINE": "What we've built with customers in the last 12 months.",
            "STAT_1_VALUE": "500+",
            "STAT_1_LABEL": "Active customers",
            "STAT_2_VALUE": "10×",
            "STAT_2_LABEL": "Faster shipping",
            "STAT_3_VALUE": "99.9%",
            "STAT_3_LABEL": "Uptime SLA",
            "STAT_4_VALUE": "4.9",
            "STAT_4_LABEL": "Customer rating",
        },
        # Section-level fade_up entry + per-number counter_up animates
        # the gradient stat values 0 → target on scroll into view.
        "default_animations": {
            "preset": "fade_up",
            "config": {"duration": 0.7, "stagger": 0.1, "ease": "power2.out"},
            "counter_up": [
                {"selector": ".stat-value", "duration": 1.5, "ease": "power2.out"},
            ],
        },
        "jsx_template": """<section className="relative isolate overflow-hidden bg-slate-950 py-20 sm:py-24 lg:py-28">
  <div className="absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_center,_rgba(6,182,212,0.14),_transparent_60%)]"></div>
  <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
    <div className="text-center max-w-3xl mx-auto mb-12 sm:mb-14">
      <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-white/5 border border-white/10 backdrop-blur-sm text-cyan-200 rounded-full text-xs font-semibold uppercase tracking-wider mb-5">
        {{EYEBROW}}
      </span>
      <h2 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight text-white leading-tight">
        {{HEADLINE}}
      </h2>
      <p className="mt-4 text-base sm:text-lg text-gray-300 leading-relaxed">
        {{SUBHEADLINE}}
      </p>
    </div>
    <div className="grid grid-cols-2 md:grid-cols-4 gap-6 sm:gap-8 max-w-5xl mx-auto">
      <div className="text-center">
        <div className="stat-value text-4xl sm:text-5xl lg:text-6xl font-extrabold bg-gradient-to-br from-cyan-400 via-indigo-400 to-violet-400 bg-clip-text text-transparent">{{STAT_1_VALUE}}</div>
        <div className="mt-2 text-xs sm:text-sm text-gray-400 uppercase tracking-wider font-medium">{{STAT_1_LABEL}}</div>
      </div>
      <div className="text-center">
        <div className="stat-value text-4xl sm:text-5xl lg:text-6xl font-extrabold bg-gradient-to-br from-indigo-400 via-violet-400 to-fuchsia-400 bg-clip-text text-transparent">{{STAT_2_VALUE}}</div>
        <div className="mt-2 text-xs sm:text-sm text-gray-400 uppercase tracking-wider font-medium">{{STAT_2_LABEL}}</div>
      </div>
      <div className="text-center">
        <div className="stat-value text-4xl sm:text-5xl lg:text-6xl font-extrabold bg-gradient-to-br from-violet-400 via-fuchsia-400 to-pink-400 bg-clip-text text-transparent">{{STAT_3_VALUE}}</div>
        <div className="mt-2 text-xs sm:text-sm text-gray-400 uppercase tracking-wider font-medium">{{STAT_3_LABEL}}</div>
      </div>
      <div className="text-center">
        <div className="stat-value text-4xl sm:text-5xl lg:text-6xl font-extrabold bg-gradient-to-br from-fuchsia-400 via-pink-400 to-amber-400 bg-clip-text text-transparent">{{STAT_4_VALUE}}</div>
        <div className="mt-2 text-xs sm:text-sm text-gray-400 uppercase tracking-wider font-medium">{{STAT_4_LABEL}}</div>
      </div>
    </div>
  </div>
</section>""",
    },
]


# =============================================================================
# FAQ variants (Commit 5)
# =============================================================================

FAQ_VARIANTS = [
    {
        "id": "var_faq_accordion",
        "category": "faq",
        "variant_id": "faq_accordion",
        "display_name": "Accordion List",
        "description": "Six common questions in a clean expandable list. Browser-native <details> for zero-JS open/close.",
        "sort_order": 10,
        "default_props": {
            "EYEBROW": "Questions",
            "HEADLINE": "Common questions, real answers.",
            "SUBHEADLINE": "If yours isn't here, ask us directly — we usually reply within a few hours.",
            "Q1_Q": "Do I need a credit card to start?",
            "Q1_A": "No. The Starter plan is genuinely free forever — no card, no expiring trial, no upgrade nag. You only pay when you outgrow it.",
            "Q2_Q": "What happens to my data if I cancel?",
            "Q2_A": "You can export everything as JSON or CSV anytime. Cancel and we delete your data after 30 days, or immediately if you ask.",
            "Q3_Q": "Can I bring my own domain?",
            "Q3_A": "Yes — custom domains are included on every paid plan. Add a CNAME record, hit verify, you're live in under five minutes.",
            "Q4_Q": "How does pricing scale with team size?",
            "Q4_A": "Pro is per-user-per-month. Enterprise is a flat contract negotiated based on usage. We'd rather you grow into us than feel surprised by a bill.",
            "Q5_Q": "Is my data secure?",
            "Q5_A": "SOC 2 Type II, end-to-end encryption in transit and at rest, audit logs on every action. Enterprise gets SSO + custom DPA.",
            "Q6_Q": "Do you offer onboarding help?",
            "Q6_A": "Pro plans include async onboarding by email. Enterprise plans get a dedicated CSM and a kickoff call within 48 hours of signup.",
        },
        "default_animations": {
            "preset": "stagger_children",
            "config": {"duration": 0.5, "stagger": 0.06, "ease": "power2.out"},
        },
        "jsx_template": """<section className="relative isolate overflow-hidden bg-slate-950 py-20 sm:py-24 lg:py-28">
  <div className="absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_top,_rgba(99,102,241,0.10),_transparent_60%)]"></div>
  <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
    <div className="text-center mb-12 sm:mb-14">
      <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-white/5 border border-white/10 backdrop-blur-sm text-indigo-200 rounded-full text-xs font-semibold uppercase tracking-wider mb-5">
        {{EYEBROW}}
      </span>
      <h2 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight text-white leading-tight">
        {{HEADLINE}}
      </h2>
      <p className="mt-4 text-base sm:text-lg text-gray-300 leading-relaxed">
        {{SUBHEADLINE}}
      </p>
    </div>
    <div className="space-y-3">
      <details className="group rounded-xl bg-white/[0.04] backdrop-blur-xl border border-white/10 transition-colors hover:border-white/20 open:border-indigo-400/40 open:bg-white/[0.06]">
        <summary className="flex items-center justify-between gap-4 px-5 py-4 cursor-pointer list-none">
          <span className="text-base font-semibold text-white">{{Q1_Q}}</span>
          <svg className="w-5 h-5 text-gray-400 transition-transform group-open:rotate-180 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7"/></svg>
        </summary>
        <div className="px-5 pb-5 text-sm text-gray-300 leading-relaxed">{{Q1_A}}</div>
      </details>
      <details className="group rounded-xl bg-white/[0.04] backdrop-blur-xl border border-white/10 transition-colors hover:border-white/20 open:border-indigo-400/40 open:bg-white/[0.06]">
        <summary className="flex items-center justify-between gap-4 px-5 py-4 cursor-pointer list-none">
          <span className="text-base font-semibold text-white">{{Q2_Q}}</span>
          <svg className="w-5 h-5 text-gray-400 transition-transform group-open:rotate-180 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7"/></svg>
        </summary>
        <div className="px-5 pb-5 text-sm text-gray-300 leading-relaxed">{{Q2_A}}</div>
      </details>
      <details className="group rounded-xl bg-white/[0.04] backdrop-blur-xl border border-white/10 transition-colors hover:border-white/20 open:border-indigo-400/40 open:bg-white/[0.06]">
        <summary className="flex items-center justify-between gap-4 px-5 py-4 cursor-pointer list-none">
          <span className="text-base font-semibold text-white">{{Q3_Q}}</span>
          <svg className="w-5 h-5 text-gray-400 transition-transform group-open:rotate-180 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7"/></svg>
        </summary>
        <div className="px-5 pb-5 text-sm text-gray-300 leading-relaxed">{{Q3_A}}</div>
      </details>
      <details className="group rounded-xl bg-white/[0.04] backdrop-blur-xl border border-white/10 transition-colors hover:border-white/20 open:border-indigo-400/40 open:bg-white/[0.06]">
        <summary className="flex items-center justify-between gap-4 px-5 py-4 cursor-pointer list-none">
          <span className="text-base font-semibold text-white">{{Q4_Q}}</span>
          <svg className="w-5 h-5 text-gray-400 transition-transform group-open:rotate-180 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7"/></svg>
        </summary>
        <div className="px-5 pb-5 text-sm text-gray-300 leading-relaxed">{{Q4_A}}</div>
      </details>
      <details className="group rounded-xl bg-white/[0.04] backdrop-blur-xl border border-white/10 transition-colors hover:border-white/20 open:border-indigo-400/40 open:bg-white/[0.06]">
        <summary className="flex items-center justify-between gap-4 px-5 py-4 cursor-pointer list-none">
          <span className="text-base font-semibold text-white">{{Q5_Q}}</span>
          <svg className="w-5 h-5 text-gray-400 transition-transform group-open:rotate-180 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7"/></svg>
        </summary>
        <div className="px-5 pb-5 text-sm text-gray-300 leading-relaxed">{{Q5_A}}</div>
      </details>
      <details className="group rounded-xl bg-white/[0.04] backdrop-blur-xl border border-white/10 transition-colors hover:border-white/20 open:border-indigo-400/40 open:bg-white/[0.06]">
        <summary className="flex items-center justify-between gap-4 px-5 py-4 cursor-pointer list-none">
          <span className="text-base font-semibold text-white">{{Q6_Q}}</span>
          <svg className="w-5 h-5 text-gray-400 transition-transform group-open:rotate-180 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7"/></svg>
        </summary>
        <div className="px-5 pb-5 text-sm text-gray-300 leading-relaxed">{{Q6_A}}</div>
      </details>
    </div>
  </div>
</section>""",
    },
]


# =============================================================================
# CONTACT variants (Commit 5)
# =============================================================================

CONTACT_VARIANTS = [
    {
        "id": "var_contact_form_plus_info",
        "category": "contact",
        "variant_id": "contact_form_plus_info",
        "display_name": "Form + Info Two-Column",
        "description": "Contact form on the left, business info (phone, email, address) on the right. Classic and proven.",
        "sort_order": 10,
        "default_props": {
            "EYEBROW": "Get in touch",
            "HEADLINE": "Tell us what you're working on.",
            "SUBHEADLINE": "We read every message. Expect a personal response within one business day.",
            "PHONE": "+1 (555) 555-0100",
            "EMAIL": "hello@yourcompany.com",
            "ADDRESS_LINE_1": "1234 Market Street",
            "ADDRESS_LINE_2": "Suite 500, San Francisco, CA 94103",
            "CTA_SUBMIT": "Send message",
        },
        "default_animations": {
            "preset": "fade_up",
            "config": {"duration": 0.7, "ease": "power2.out"},
        },
        "jsx_template": """<section className="relative isolate overflow-hidden bg-slate-950 py-20 sm:py-24 lg:py-28">
  <div className="absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_bottom_right,_rgba(99,102,241,0.14),_transparent_60%)]"></div>
  <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
    <div className="text-center max-w-3xl mx-auto mb-12 sm:mb-14">
      <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-white/5 border border-white/10 backdrop-blur-sm text-indigo-200 rounded-full text-xs font-semibold uppercase tracking-wider mb-5">
        {{EYEBROW}}
      </span>
      <h2 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight text-white leading-tight">
        {{HEADLINE}}
      </h2>
      <p className="mt-4 text-base sm:text-lg text-gray-300 leading-relaxed">
        {{SUBHEADLINE}}
      </p>
    </div>
    <div className="grid lg:grid-cols-5 gap-8 lg:gap-12 max-w-6xl mx-auto">
      <form className="lg:col-span-3 rounded-2xl p-6 sm:p-8 bg-white/[0.04] backdrop-blur-xl border border-white/10 space-y-5" action="#" method="post">
        <div className="grid sm:grid-cols-2 gap-5">
          <div>
            <label className="block text-xs font-medium text-gray-300 mb-1.5 uppercase tracking-wider">Name</label>
            <input type="text" name="name" required className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-lg text-white placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-400/60" placeholder="Jane Smith" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-300 mb-1.5 uppercase tracking-wider">Work email</label>
            <input type="email" name="email" required className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-lg text-white placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-400/60" placeholder="jane@company.com" />
          </div>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-300 mb-1.5 uppercase tracking-wider">Company</label>
          <input type="text" name="company" className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-lg text-white placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-400/60" placeholder="Acme Inc" />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-300 mb-1.5 uppercase tracking-wider">What are you working on?</label>
          <textarea name="message" rows="4" required className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-lg text-white placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-400/60 resize-none" placeholder="A few sentences about your project, timeline, or anything else we should know."></textarea>
        </div>
        <button type="submit" className="w-full px-6 py-3 bg-gradient-to-r from-indigo-500 via-violet-500 to-fuchsia-500 text-white font-semibold rounded-lg shadow-lg shadow-indigo-500/30 hover:shadow-indigo-500/50 hover:scale-[1.01] transition-all">
          {{CTA_SUBMIT}}
        </button>
        <p className="text-xs text-gray-500 text-center">By submitting, you agree to our terms. We respect your inbox.</p>
      </form>
      <div className="lg:col-span-2 space-y-5">
        <div className="rounded-2xl p-5 sm:p-6 bg-white/[0.04] backdrop-blur-xl border border-white/10 flex items-start gap-4">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-500 flex items-center justify-center shadow-lg shadow-indigo-500/30 flex-shrink-0"><svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"/></svg></div>
          <div>
            <div className="text-xs uppercase tracking-wider text-gray-500 font-medium">Phone</div>
            <a href="tel:{{PHONE}}" className="text-sm text-white font-medium hover:text-indigo-300 transition">{{PHONE}}</a>
          </div>
        </div>
        <div className="rounded-2xl p-5 sm:p-6 bg-white/[0.04] backdrop-blur-xl border border-white/10 flex items-start gap-4">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-violet-500 to-fuchsia-500 flex items-center justify-center shadow-lg shadow-violet-500/30 flex-shrink-0"><svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg></div>
          <div>
            <div className="text-xs uppercase tracking-wider text-gray-500 font-medium">Email</div>
            <a href="mailto:{{EMAIL}}" className="text-sm text-white font-medium hover:text-violet-300 transition">{{EMAIL}}</a>
          </div>
        </div>
        <div className="rounded-2xl p-5 sm:p-6 bg-white/[0.04] backdrop-blur-xl border border-white/10 flex items-start gap-4">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-fuchsia-500 to-pink-500 flex items-center justify-center shadow-lg shadow-fuchsia-500/30 flex-shrink-0"><svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/><path strokeLinecap="round" strokeLinejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"/></svg></div>
          <div>
            <div className="text-xs uppercase tracking-wider text-gray-500 font-medium">Office</div>
            <div className="text-sm text-white font-medium">{{ADDRESS_LINE_1}}</div>
            <div className="text-sm text-gray-400">{{ADDRESS_LINE_2}}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</section>""",
    },
]


# =============================================================================
# FOOTER variants (Commit 5)
# =============================================================================

FOOTER_VARIANTS = [
    {
        "id": "var_footer_4col",
        "category": "footer",
        "variant_id": "footer_4col",
        "display_name": "4-Column with Brand + Links",
        "description": "Logo + tagline + 3 link columns + bottom row with social icons and copyright. Production-ready out of the box.",
        "sort_order": 10,
        "default_props": {
            "BRAND_NAME": "Your Company",
            "BRAND_TAGLINE": "Building tools teams actually want to use.",
            "COL_1_HEADING": "Product",
            "COL_1_LINK_1": "Features",
            "COL_1_LINK_2": "Pricing",
            "COL_1_LINK_3": "Integrations",
            "COL_1_LINK_4": "Changelog",
            "COL_2_HEADING": "Company",
            "COL_2_LINK_1": "About",
            "COL_2_LINK_2": "Careers",
            "COL_2_LINK_3": "Customers",
            "COL_2_LINK_4": "Contact",
            "COL_3_HEADING": "Resources",
            "COL_3_LINK_1": "Documentation",
            "COL_3_LINK_2": "Blog",
            "COL_3_LINK_3": "Help center",
            "COL_3_LINK_4": "Status",
            "COPYRIGHT": "© 2026 Your Company. All rights reserved.",
        },
        "default_animations": {
            "preset": "fade_up",
            "config": {"duration": 0.6, "ease": "power2.out"},
        },
        "jsx_template": """<footer className="relative isolate overflow-hidden bg-slate-950 border-t border-white/10 pt-16 sm:pt-20 pb-10">
  <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
    <div className="grid grid-cols-2 lg:grid-cols-5 gap-8 lg:gap-12 mb-12 sm:mb-16">
      <div className="col-span-2">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-indigo-500 via-violet-500 to-fuchsia-500 flex items-center justify-center shadow-lg shadow-indigo-500/30">
            <svg className="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2L2 7v10l10 5 10-5V7l-10-5z" opacity="0.4"/><path d="M12 2L2 7l10 5 10-5-10-5z"/></svg>
          </div>
          <span className="text-lg font-bold text-white">{{BRAND_NAME}}</span>
        </div>
        <p className="text-sm text-gray-400 leading-relaxed max-w-xs">{{BRAND_TAGLINE}}</p>
      </div>
      <div>
        <h4 className="text-xs font-semibold text-white uppercase tracking-wider mb-4">{{COL_1_HEADING}}</h4>
        <ul className="space-y-2.5">
          <li><a href="#features" className="text-sm text-gray-400 hover:text-white transition">{{COL_1_LINK_1}}</a></li>
          <li><a href="#pricing" className="text-sm text-gray-400 hover:text-white transition">{{COL_1_LINK_2}}</a></li>
          <li><a href="#integrations" className="text-sm text-gray-400 hover:text-white transition">{{COL_1_LINK_3}}</a></li>
          <li><a href="#changelog" className="text-sm text-gray-400 hover:text-white transition">{{COL_1_LINK_4}}</a></li>
        </ul>
      </div>
      <div>
        <h4 className="text-xs font-semibold text-white uppercase tracking-wider mb-4">{{COL_2_HEADING}}</h4>
        <ul className="space-y-2.5">
          <li><a href="#about" className="text-sm text-gray-400 hover:text-white transition">{{COL_2_LINK_1}}</a></li>
          <li><a href="#careers" className="text-sm text-gray-400 hover:text-white transition">{{COL_2_LINK_2}}</a></li>
          <li><a href="#customers" className="text-sm text-gray-400 hover:text-white transition">{{COL_2_LINK_3}}</a></li>
          <li><a href="#contact" className="text-sm text-gray-400 hover:text-white transition">{{COL_2_LINK_4}}</a></li>
        </ul>
      </div>
      <div>
        <h4 className="text-xs font-semibold text-white uppercase tracking-wider mb-4">{{COL_3_HEADING}}</h4>
        <ul className="space-y-2.5">
          <li><a href="#docs" className="text-sm text-gray-400 hover:text-white transition">{{COL_3_LINK_1}}</a></li>
          <li><a href="#blog" className="text-sm text-gray-400 hover:text-white transition">{{COL_3_LINK_2}}</a></li>
          <li><a href="#help" className="text-sm text-gray-400 hover:text-white transition">{{COL_3_LINK_3}}</a></li>
          <li><a href="#status" className="text-sm text-gray-400 hover:text-white transition">{{COL_3_LINK_4}}</a></li>
        </ul>
      </div>
    </div>
    <div className="pt-8 border-t border-white/10 flex flex-col sm:flex-row items-center justify-between gap-4">
      <p className="text-xs text-gray-500">{{COPYRIGHT}}</p>
      <div className="flex items-center gap-3">
        <a href="#twitter" aria-label="Twitter" className="w-9 h-9 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center text-gray-400 hover:text-white hover:bg-white/10 transition"><svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg></a>
        <a href="#linkedin" aria-label="LinkedIn" className="w-9 h-9 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center text-gray-400 hover:text-white hover:bg-white/10 transition"><svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.063 2.063 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg></a>
        <a href="#github" aria-label="GitHub" className="w-9 h-9 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center text-gray-400 hover:text-white hover:bg-white/10 transition"><svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.4 3-.405 1.02.005 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12"/></svg></a>
      </div>
    </div>
  </div>
</footer>""",
    },
]


# =============================================================================
# GALLERY variants (Commit 5)
# =============================================================================

GALLERY_VARIANTS = [
    {
        "id": "var_gallery_masonry",
        "category": "gallery",
        "variant_id": "gallery_masonry",
        "display_name": "Masonry Grid",
        "description": "Pinterest-style masonry layout — items flow into varied-height columns. Best for portfolios and visual showcases.",
        "sort_order": 10,
        "default_props": {
            "EYEBROW": "Selected work",
            "HEADLINE": "Recent projects.",
            "SUBHEADLINE": "A selection of work shipped with partners in the last twelve months.",
            "ITEM_1_URL": "https://images.unsplash.com/photo-1497366216548-37526070297c?auto=format&fit=crop&w=600&q=80",
            "ITEM_1_CAPTION": "Workspace redesign",
            "ITEM_2_URL": "https://images.unsplash.com/photo-1542744173-8e7e53415bb0?auto=format&fit=crop&w=600&q=80",
            "ITEM_2_CAPTION": "Discovery workshop",
            "ITEM_3_URL": "https://images.unsplash.com/photo-1551434678-e076c223a692?auto=format&fit=crop&w=600&q=80",
            "ITEM_3_CAPTION": "Brand sprint",
            "ITEM_4_URL": "https://images.unsplash.com/photo-1556761175-5973dc0f32e7?auto=format&fit=crop&w=600&q=80",
            "ITEM_4_CAPTION": "Product launch",
            "ITEM_5_URL": "https://images.unsplash.com/photo-1606857521015-7f9fcf423740?auto=format&fit=crop&w=600&q=80",
            "ITEM_5_CAPTION": "Strategy offsite",
            "ITEM_6_URL": "https://images.unsplash.com/photo-1521737711867-e3b97375f902?auto=format&fit=crop&w=600&q=80",
            "ITEM_6_CAPTION": "Team retreat",
            "ITEM_7_URL": "https://images.unsplash.com/photo-1517245386807-bb43f82c33c4?auto=format&fit=crop&w=600&q=80",
            "ITEM_7_CAPTION": "Founder portrait",
            "ITEM_8_URL": "https://images.unsplash.com/photo-1531545514256-b1400bc00f31?auto=format&fit=crop&w=600&q=80",
            "ITEM_8_CAPTION": "Annual report cover",
        },
        "default_animations": {
            "preset": "stagger_children",
            "config": {"duration": 0.5, "stagger": 0.06, "ease": "power2.out"},
        },
        # Masonry via CSS columns. Each item: <figure> with overflow
        # hidden + hover scale via Tailwind. break-inside-avoid keeps
        # items from splitting across columns.
        "jsx_template": """<section className="relative isolate overflow-hidden bg-slate-950 py-20 sm:py-24 lg:py-28">
  <div className="absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_top,_rgba(236,72,153,0.10),_transparent_60%)]"></div>
  <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
    <div className="text-center max-w-3xl mx-auto mb-12 sm:mb-14">
      <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-white/5 border border-white/10 backdrop-blur-sm text-fuchsia-200 rounded-full text-xs font-semibold uppercase tracking-wider mb-5">
        {{EYEBROW}}
      </span>
      <h2 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight text-white leading-tight">
        {{HEADLINE}}
      </h2>
      <p className="mt-4 text-base sm:text-lg text-gray-300 leading-relaxed">
        {{SUBHEADLINE}}
      </p>
    </div>
    <div className="columns-2 md:columns-3 gap-4 lg:gap-5">
      <figure className="break-inside-avoid mb-4 lg:mb-5 group relative overflow-hidden rounded-xl bg-white/[0.04] border border-white/10 transition-all duration-300 hover:border-fuchsia-400/40 hover:shadow-[0_12px_32px_rgba(217,70,239,0.18)]">
        <img src="{{ITEM_1_URL}}" alt="{{ITEM_1_CAPTION}}" className="w-full h-auto block transition-transform duration-500 group-hover:scale-105" />
        <figcaption className="absolute bottom-0 left-0 right-0 p-3 bg-gradient-to-t from-slate-950/95 via-slate-950/60 to-transparent text-xs font-medium text-white opacity-0 translate-y-2 group-hover:opacity-100 group-hover:translate-y-0 transition-all">{{ITEM_1_CAPTION}}</figcaption>
      </figure>
      <figure className="break-inside-avoid mb-4 lg:mb-5 group relative overflow-hidden rounded-xl bg-white/[0.04] border border-white/10 transition-all duration-300 hover:border-fuchsia-400/40 hover:shadow-[0_12px_32px_rgba(217,70,239,0.18)]">
        <img src="{{ITEM_2_URL}}" alt="{{ITEM_2_CAPTION}}" className="w-full h-auto block transition-transform duration-500 group-hover:scale-105" />
        <figcaption className="absolute bottom-0 left-0 right-0 p-3 bg-gradient-to-t from-slate-950/95 via-slate-950/60 to-transparent text-xs font-medium text-white opacity-0 translate-y-2 group-hover:opacity-100 group-hover:translate-y-0 transition-all">{{ITEM_2_CAPTION}}</figcaption>
      </figure>
      <figure className="break-inside-avoid mb-4 lg:mb-5 group relative overflow-hidden rounded-xl bg-white/[0.04] border border-white/10 transition-all duration-300 hover:border-fuchsia-400/40 hover:shadow-[0_12px_32px_rgba(217,70,239,0.18)]">
        <img src="{{ITEM_3_URL}}" alt="{{ITEM_3_CAPTION}}" className="w-full h-auto block transition-transform duration-500 group-hover:scale-105" />
        <figcaption className="absolute bottom-0 left-0 right-0 p-3 bg-gradient-to-t from-slate-950/95 via-slate-950/60 to-transparent text-xs font-medium text-white opacity-0 translate-y-2 group-hover:opacity-100 group-hover:translate-y-0 transition-all">{{ITEM_3_CAPTION}}</figcaption>
      </figure>
      <figure className="break-inside-avoid mb-4 lg:mb-5 group relative overflow-hidden rounded-xl bg-white/[0.04] border border-white/10 transition-all duration-300 hover:border-fuchsia-400/40 hover:shadow-[0_12px_32px_rgba(217,70,239,0.18)]">
        <img src="{{ITEM_4_URL}}" alt="{{ITEM_4_CAPTION}}" className="w-full h-auto block transition-transform duration-500 group-hover:scale-105" />
        <figcaption className="absolute bottom-0 left-0 right-0 p-3 bg-gradient-to-t from-slate-950/95 via-slate-950/60 to-transparent text-xs font-medium text-white opacity-0 translate-y-2 group-hover:opacity-100 group-hover:translate-y-0 transition-all">{{ITEM_4_CAPTION}}</figcaption>
      </figure>
      <figure className="break-inside-avoid mb-4 lg:mb-5 group relative overflow-hidden rounded-xl bg-white/[0.04] border border-white/10 transition-all duration-300 hover:border-fuchsia-400/40 hover:shadow-[0_12px_32px_rgba(217,70,239,0.18)]">
        <img src="{{ITEM_5_URL}}" alt="{{ITEM_5_CAPTION}}" className="w-full h-auto block transition-transform duration-500 group-hover:scale-105" />
        <figcaption className="absolute bottom-0 left-0 right-0 p-3 bg-gradient-to-t from-slate-950/95 via-slate-950/60 to-transparent text-xs font-medium text-white opacity-0 translate-y-2 group-hover:opacity-100 group-hover:translate-y-0 transition-all">{{ITEM_5_CAPTION}}</figcaption>
      </figure>
      <figure className="break-inside-avoid mb-4 lg:mb-5 group relative overflow-hidden rounded-xl bg-white/[0.04] border border-white/10 transition-all duration-300 hover:border-fuchsia-400/40 hover:shadow-[0_12px_32px_rgba(217,70,239,0.18)]">
        <img src="{{ITEM_6_URL}}" alt="{{ITEM_6_CAPTION}}" className="w-full h-auto block transition-transform duration-500 group-hover:scale-105" />
        <figcaption className="absolute bottom-0 left-0 right-0 p-3 bg-gradient-to-t from-slate-950/95 via-slate-950/60 to-transparent text-xs font-medium text-white opacity-0 translate-y-2 group-hover:opacity-100 group-hover:translate-y-0 transition-all">{{ITEM_6_CAPTION}}</figcaption>
      </figure>
      <figure className="break-inside-avoid mb-4 lg:mb-5 group relative overflow-hidden rounded-xl bg-white/[0.04] border border-white/10 transition-all duration-300 hover:border-fuchsia-400/40 hover:shadow-[0_12px_32px_rgba(217,70,239,0.18)]">
        <img src="{{ITEM_7_URL}}" alt="{{ITEM_7_CAPTION}}" className="w-full h-auto block transition-transform duration-500 group-hover:scale-105" />
        <figcaption className="absolute bottom-0 left-0 right-0 p-3 bg-gradient-to-t from-slate-950/95 via-slate-950/60 to-transparent text-xs font-medium text-white opacity-0 translate-y-2 group-hover:opacity-100 group-hover:translate-y-0 transition-all">{{ITEM_7_CAPTION}}</figcaption>
      </figure>
      <figure className="break-inside-avoid mb-4 lg:mb-5 group relative overflow-hidden rounded-xl bg-white/[0.04] border border-white/10 transition-all duration-300 hover:border-fuchsia-400/40 hover:shadow-[0_12px_32px_rgba(217,70,239,0.18)]">
        <img src="{{ITEM_8_URL}}" alt="{{ITEM_8_CAPTION}}" className="w-full h-auto block transition-transform duration-500 group-hover:scale-105" />
        <figcaption className="absolute bottom-0 left-0 right-0 p-3 bg-gradient-to-t from-slate-950/95 via-slate-950/60 to-transparent text-xs font-medium text-white opacity-0 translate-y-2 group-hover:opacity-100 group-hover:translate-y-0 transition-all">{{ITEM_8_CAPTION}}</figcaption>
      </figure>
    </div>
  </div>
</section>""",
    },
]


# =============================================================================
# LOGOS variants (Commit 5)
# =============================================================================

LOGOS_VARIANTS = [
    {
        "id": "var_logos_marquee",
        "category": "logos",
        "variant_id": "logos_marquee",
        "display_name": "Continuous Marquee",
        "description": "Infinite-scrolling strip of brand logos. CSS-only animation. Plug in real logos via the Visual editor.",
        "sort_order": 10,
        "default_props": {
            "EYEBROW": "Trusted by",
            "HEADLINE": "Teams shipping faster with us.",
            "LOGO_1_NAME": "Aurelis",
            "LOGO_2_NAME": "Midstream",
            "LOGO_3_NAME": "Lumengrid",
            "LOGO_4_NAME": "Nimbus & Co",
            "LOGO_5_NAME": "Pillar Labs",
            "LOGO_6_NAME": "Westmark",
            "LOGO_7_NAME": "Hexavolt",
            "LOGO_8_NAME": "Brightway",
        },
        # No section-level entry animation — the marquee IS the
        # animation. Set preset to "none" so the section renders
        # without an entry trigger, letting the inline CSS keyframe
        # handle everything.
        "default_animations": {
            "preset": "fade_up",
            "config": {"duration": 0.6, "ease": "power2.out"},
        },
        # Marquee technique: two copies of the logo strip side by side,
        # translate -50% over a long duration, infinite. The seam between
        # the two strips is invisible because they're identical content.
        # Pure CSS, GPU-accelerated, zero JS.
        "jsx_template": """<section className="relative isolate overflow-hidden bg-slate-950 py-16 sm:py-20 lg:py-24">
  <div className="text-center mb-10 sm:mb-12">
    <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-white/5 border border-white/10 backdrop-blur-sm text-cyan-200 rounded-full text-xs font-semibold uppercase tracking-wider mb-4">
      {{EYEBROW}}
    </span>
    <h3 className="text-lg sm:text-xl text-gray-300 font-medium">{{HEADLINE}}</h3>
  </div>
  <style>
    @keyframes logo-marquee {
      from { transform: translateX(0); }
      to { transform: translateX(-50%); }
    }
    .logo-marquee-track {
      display: flex;
      width: max-content;
      animation: logo-marquee 30s linear infinite;
    }
    .logo-marquee-track:hover { animation-play-state: paused; }
    @media (prefers-reduced-motion: reduce) {
      .logo-marquee-track { animation: none; }
    }
  </style>
  <div className="relative">
    <div className="absolute left-0 top-0 bottom-0 w-24 z-10 bg-gradient-to-r from-slate-950 to-transparent pointer-events-none"></div>
    <div className="absolute right-0 top-0 bottom-0 w-24 z-10 bg-gradient-to-l from-slate-950 to-transparent pointer-events-none"></div>
    <div className="logo-marquee-track gap-12 sm:gap-16">
      <div className="flex items-center gap-12 sm:gap-16 px-6 shrink-0">
        <span className="text-2xl font-bold text-white/40 tracking-tight whitespace-nowrap hover:text-white/80 transition-colors">{{LOGO_1_NAME}}</span>
        <span className="text-2xl font-bold text-white/40 tracking-tight whitespace-nowrap hover:text-white/80 transition-colors">{{LOGO_2_NAME}}</span>
        <span className="text-2xl font-bold text-white/40 tracking-tight whitespace-nowrap hover:text-white/80 transition-colors">{{LOGO_3_NAME}}</span>
        <span className="text-2xl font-bold text-white/40 tracking-tight whitespace-nowrap hover:text-white/80 transition-colors">{{LOGO_4_NAME}}</span>
        <span className="text-2xl font-bold text-white/40 tracking-tight whitespace-nowrap hover:text-white/80 transition-colors">{{LOGO_5_NAME}}</span>
        <span className="text-2xl font-bold text-white/40 tracking-tight whitespace-nowrap hover:text-white/80 transition-colors">{{LOGO_6_NAME}}</span>
        <span className="text-2xl font-bold text-white/40 tracking-tight whitespace-nowrap hover:text-white/80 transition-colors">{{LOGO_7_NAME}}</span>
        <span className="text-2xl font-bold text-white/40 tracking-tight whitespace-nowrap hover:text-white/80 transition-colors">{{LOGO_8_NAME}}</span>
      </div>
      <div className="flex items-center gap-12 sm:gap-16 px-6 shrink-0" aria-hidden="true">
        <span className="text-2xl font-bold text-white/40 tracking-tight whitespace-nowrap hover:text-white/80 transition-colors">{{LOGO_1_NAME}}</span>
        <span className="text-2xl font-bold text-white/40 tracking-tight whitespace-nowrap hover:text-white/80 transition-colors">{{LOGO_2_NAME}}</span>
        <span className="text-2xl font-bold text-white/40 tracking-tight whitespace-nowrap hover:text-white/80 transition-colors">{{LOGO_3_NAME}}</span>
        <span className="text-2xl font-bold text-white/40 tracking-tight whitespace-nowrap hover:text-white/80 transition-colors">{{LOGO_4_NAME}}</span>
        <span className="text-2xl font-bold text-white/40 tracking-tight whitespace-nowrap hover:text-white/80 transition-colors">{{LOGO_5_NAME}}</span>
        <span className="text-2xl font-bold text-white/40 tracking-tight whitespace-nowrap hover:text-white/80 transition-colors">{{LOGO_6_NAME}}</span>
        <span className="text-2xl font-bold text-white/40 tracking-tight whitespace-nowrap hover:text-white/80 transition-colors">{{LOGO_7_NAME}}</span>
        <span className="text-2xl font-bold text-white/40 tracking-tight whitespace-nowrap hover:text-white/80 transition-colors">{{LOGO_8_NAME}}</span>
      </div>
    </div>
  </div>
</section>""",
    },
]


def all_variants() -> list[dict]:
    """All seed variants across categories. Commit 5 expands beyond
    Hero to flagships across all 12 categories."""
    return [
        *HERO_VARIANTS,
        *FEATURES_VARIANTS,
        *CTA_VARIANTS,
        *PRICING_VARIANTS,
        *TESTIMONIALS_VARIANTS,
        *TEAM_VARIANTS,
        *STATS_VARIANTS,
        *FAQ_VARIANTS,
        *CONTACT_VARIANTS,
        *FOOTER_VARIANTS,
        *GALLERY_VARIANTS,
        *LOGOS_VARIANTS,
    ]
