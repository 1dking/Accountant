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


def all_variants() -> list[dict]:
    """All seed variants across categories. Commit 5 expands beyond
    Hero to flagships across all 12 categories."""
    return [*HERO_VARIANTS, *FEATURES_VARIANTS]
