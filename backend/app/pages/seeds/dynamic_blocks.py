"""Dynamic blocks — wave 0 (S2). Every block here has a `behaviour` the
pages runtime initialises (frontend/src/pages-runtime/blocks/*.ts) and a
`fields_schema` the editor + AI fill. Templates are Tailwind, mobile-
first, with the runtime's data-* hooks documented per block.

Runtime config contract: fields flagged `runtime: True` are emitted into
the section wrapper's data-block-config by compile_page.
"""
from __future__ import annotations

_T = lambda key, label, **kw: {"key": key, "type": "text", "label": label, "max_len": 160, **kw}  # noqa: E731
_TA = lambda key, label, **kw: {"key": key, "type": "textarea", "label": label, "max_len": 600, **kw}  # noqa: E731
_URL = lambda key, label, **kw: {"key": key, "type": "url", "label": label, **kw}  # noqa: E731

DYNAMIC_BLOCKS: list[dict] = [
    # ------------------------------------------------------------ lead form
    {
        "id": "var_dyn_contact_lead_form",
        "category": "contact",
        "variant_id": "contact_lead_form",
        "display_name": "Lead form (wired)",
        "description": "Two-column contact block. The form posts to the site's lead endpoint: contact + submission + 'New lead' workflow, with honeypot and timing protection.",
        "sort_order": 5,
        "schema_version": 2,
        "behaviour": "lead_form",
        "capabilities": ["dynamic", "submits_lead"],
        "motion_preset": "css_reveal_up",
        "default_props": {
            "EYEBROW": "Contact",
            "HEADLINE": "Tell us about your project",
            "SUBHEADLINE": "We reply within one business day. No obligation, no pressure.",
            "NAME_LABEL": "Your name", "EMAIL_LABEL": "Email", "PHONE_LABEL": "Phone", "MESSAGE_LABEL": "How can we help?",
            "SUBMIT_TEXT": "Send message",
            "SUCCESS_TEXT": "Thanks — we’ll be in touch shortly.",
            "SIDE_TITLE": "Prefer to talk?",
            "SIDE_TEXT": "Call or text us and a real person answers.",
            "PHONE_NUMBER": "+1 (613) 555-0100",
            "EMAIL_ADDRESS": "hello@example.com",
        },
        "locale_props": {"fr-CA": {
            "EYEBROW": "Contact", "HEADLINE": "Parlez-nous de votre projet",
            "SUBHEADLINE": "Nous répondons en un jour ouvrable. Sans engagement.",
            "NAME_LABEL": "Votre nom", "EMAIL_LABEL": "Courriel", "PHONE_LABEL": "Téléphone", "MESSAGE_LABEL": "Comment pouvons-nous aider?",
            "SUBMIT_TEXT": "Envoyer", "SUCCESS_TEXT": "Merci — nous vous répondrons sous peu.",
            "SIDE_TITLE": "Vous préférez parler?", "SIDE_TEXT": "Appelez ou textez-nous : une vraie personne répond.",
        }},
        "fields_schema": [
            _T("EYEBROW", "Eyebrow", max_len=40), _T("HEADLINE", "Headline", required=True, max_len=80),
            _TA("SUBHEADLINE", "Subheadline"),
            _T("NAME_LABEL", "Name label", max_len=40), _T("EMAIL_LABEL", "Email label", max_len=40),
            _T("PHONE_LABEL", "Phone label", max_len=40), _T("MESSAGE_LABEL", "Message label", max_len=60),
            _T("SUBMIT_TEXT", "Button text", max_len=40), _T("SUCCESS_TEXT", "Success message", max_len=200),
            _T("SIDE_TITLE", "Side title", max_len=60), _TA("SIDE_TEXT", "Side text", max_len=200),
            _T("PHONE_NUMBER", "Phone number", max_len=30, bind="company.phone"),
            _T("EMAIL_ADDRESS", "Email address", max_len=120, bind="company.email"),
        ],
        "jsx_template": """<section className="contact bg-white py-24 px-6">
  <div className="max-w-6xl mx-auto grid md:grid-cols-5 gap-12">
    <div className="md:col-span-2">
      <span className="text-sm font-semibold tracking-widest uppercase text-indigo-600">{{EYEBROW}}</span>
      <h2 className="text-4xl font-bold text-slate-900 mt-3 mb-4">{{HEADLINE}}</h2>
      <p className="text-lg text-slate-500 mb-10">{{SUBHEADLINE}}</p>
      <div className="p-6 rounded-2xl bg-slate-50 border border-slate-200">
        <h3 className="font-semibold text-slate-900 mb-1">{{SIDE_TITLE}}</h3>
        <p className="text-sm text-slate-500 mb-4">{{SIDE_TEXT}}</p>
        <a href="tel:{{PHONE_NUMBER}}" className="block font-semibold text-indigo-600">{{PHONE_NUMBER}}</a>
        <a href="mailto:{{EMAIL_ADDRESS}}" className="block text-slate-700">{{EMAIL_ADDRESS}}</a>
      </div>
    </div>
    <div className="md:col-span-3">
      <form data-lead-form className="grid gap-4 p-8 rounded-3xl bg-slate-900 text-white shadow-2xl">
        <div className="grid sm:grid-cols-2 gap-4">
          <label className="block text-sm"><span className="text-slate-300">{{NAME_LABEL}}</span><input name="name" required autocomplete="name" className="mt-1 w-full rounded-xl bg-white/10 border border-white/10 px-4 py-3 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-400"/></label>
          <label className="block text-sm"><span className="text-slate-300">{{EMAIL_LABEL}}</span><input name="email" type="email" required autocomplete="email" className="mt-1 w-full rounded-xl bg-white/10 border border-white/10 px-4 py-3 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-400"/></label>
        </div>
        <label className="block text-sm"><span className="text-slate-300">{{PHONE_LABEL}}</span><input name="phone" type="tel" autocomplete="tel" className="mt-1 w-full rounded-xl bg-white/10 border border-white/10 px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-indigo-400"/></label>
        <label className="block text-sm"><span className="text-slate-300">{{MESSAGE_LABEL}}</span><textarea name="message" rows="4" className="mt-1 w-full rounded-xl bg-white/10 border border-white/10 px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-indigo-400"></textarea></label>
        <button type="submit" className="mt-2 px-8 py-3.5 rounded-xl bg-indigo-500 hover:bg-indigo-400 font-semibold transition">{{SUBMIT_TEXT}}</button>
        <p data-error className="text-rose-300 text-sm"></p>
      </form>
      <div data-success className="p-8 rounded-3xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-lg font-medium">{{SUCCESS_TEXT}}</div>
    </div>
  </div>
</section>""",
    },
    # ------------------------------------------------------- booking picker
    {
        "id": "var_dyn_booking_picker",
        "category": "booking",
        "variant_id": "booking_inline_picker",
        "display_name": "Inline booking picker",
        "description": "Shows the next open slots from one of your calendars and books them in place — no redirect. Guest gets a confirmation; the booking lands in Scheduling.",
        "sort_order": 10,
        "schema_version": 2,
        "behaviour": "booking_picker",
        "data_source": "availability",
        "data_mode": "live",
        "capabilities": ["dynamic", "live_data", "needs_calendar"],
        "motion_preset": "css_reveal_fade",
        "default_props": {
            "EYEBROW": "Book online",
            "HEADLINE": "Pick a time that works for you",
            "SUBHEADLINE": "Real availability, confirmed instantly.",
            "CALENDAR_SLUG": "",
            "DAYS": 7,
            "NOTE": "Free 30-minute consultation. Reschedule any time from your confirmation email.",
        },
        "locale_props": {"fr-CA": {
            "EYEBROW": "Réservez en ligne", "HEADLINE": "Choisissez un moment qui vous convient",
            "SUBHEADLINE": "Disponibilités réelles, confirmées sur-le-champ.",
            "NOTE": "Consultation gratuite de 30 minutes. Reportez en tout temps depuis votre courriel de confirmation.",
        }},
        "fields_schema": [
            _T("EYEBROW", "Eyebrow", max_len=40), _T("HEADLINE", "Headline", required=True, max_len=80),
            _TA("SUBHEADLINE", "Subheadline", max_len=200),
            {"key": "CALENDAR_SLUG", "type": "select", "label": "Calendar", "label_fr": "Calendrier",
             "options_from": "calendars", "required": True, "runtime": True,
             "hint": "Scheduling → Calendars → the public link slug"},
            {"key": "DAYS", "type": "number", "label": "Days to show", "min": 1, "max": 31, "default": 7, "runtime": True},
            _TA("NOTE", "Note under the picker", max_len=240),
        ],
        "jsx_template": """<section className="booking bg-slate-50 py-24 px-6">
  <div className="max-w-3xl mx-auto">
    <div className="text-center mb-10">
      <span className="text-sm font-semibold tracking-widest uppercase text-indigo-600">{{EYEBROW}}</span>
      <h2 className="text-4xl font-bold text-slate-900 mt-3 mb-3">{{HEADLINE}}</h2>
      <p className="text-lg text-slate-500">{{SUBHEADLINE}}</p>
    </div>
    <div className="p-6 md:p-8 rounded-3xl bg-white border border-slate-200 shadow-xl">
      <div data-booking data-calendar="{{CALENDAR_SLUG}}" className="text-slate-900"></div>
    </div>
    <p className="mt-6 text-center text-sm text-slate-500">{{NOTE}}</p>
  </div>
</section>""",
    },
    # ------------------------------------------------------ quote calculator
    {
        "id": "var_dyn_quote_calc",
        "category": "pricing",
        "variant_id": "pricing_quote_calculator",
        "display_name": "Instant quote calculator",
        "description": "Visitors pick quantities, see a live estimate and send it with their details. The lead lands in the CRM with the quote as a timeline note.",
        "sort_order": 5,
        "schema_version": 2,
        "behaviour": "quote_calc",
        "capabilities": ["dynamic", "submits_lead"],
        "motion_preset": "css_reveal_up",
        "default_props": {
            "EYEBROW": "Instant estimate",
            "HEADLINE": "Get a price in 30 seconds",
            "SUBHEADLINE": "Adjust the numbers — the estimate updates live. Send it and we’ll confirm the final quote.",
            "BASE_PRICE": 0,
            "CURRENCY": "CAD",
            "ITEMS": [
                {"LABEL": "Rooms", "PRICE": 45, "UNIT": "per room", "DEFAULT_QTY": 3},
                {"LABEL": "Bathrooms", "PRICE": 35, "UNIT": "each", "DEFAULT_QTY": 1},
                {"LABEL": "Windows", "PRICE": 8, "UNIT": "each", "DEFAULT_QTY": 0},
            ],
            "TOTAL_LABEL": "Estimated total",
            "NAME_LABEL": "Your name", "EMAIL_LABEL": "Email", "PHONE_LABEL": "Phone",
            "SUBMIT_TEXT": "Send my estimate",
            "SUCCESS_TEXT": "Got it — your estimate is on its way and we’ll confirm the details shortly.",
            "FINE_PRINT": "Estimates are indicative; final pricing confirmed after a quick call.",
        },
        "locale_props": {"fr-CA": {
            "EYEBROW": "Estimation instantanée", "HEADLINE": "Obtenez un prix en 30 secondes",
            "SUBHEADLINE": "Ajustez les quantités : l’estimation se met à jour en direct. Envoyez-la et nous confirmerons la soumission finale.",
            "ITEMS": [
                {"LABEL": "Pièces", "PRICE": 45, "UNIT": "par pièce", "DEFAULT_QTY": 3},
                {"LABEL": "Salles de bain", "PRICE": 35, "UNIT": "chacune", "DEFAULT_QTY": 1},
                {"LABEL": "Fenêtres", "PRICE": 8, "UNIT": "chacune", "DEFAULT_QTY": 0},
            ],
            "TOTAL_LABEL": "Total estimé", "NAME_LABEL": "Votre nom", "EMAIL_LABEL": "Courriel", "PHONE_LABEL": "Téléphone",
            "SUBMIT_TEXT": "Envoyer mon estimation",
            "SUCCESS_TEXT": "Reçu — votre estimation est en route et nous confirmerons les détails sous peu.",
            "FINE_PRINT": "Les estimations sont indicatives; le prix final est confirmé après un court appel.",
        }},
        "fields_schema": [
            _T("EYEBROW", "Eyebrow", max_len=40), _T("HEADLINE", "Headline", required=True, max_len=80),
            _TA("SUBHEADLINE", "Subheadline", max_len=240),
            {"key": "BASE_PRICE", "type": "number", "label": "Base price (call-out fee)", "min": 0, "default": 0, "runtime": True},
            {"key": "CURRENCY", "type": "select", "label": "Currency", "options": ["CAD", "USD"], "default": "CAD", "runtime": True},
            {"key": "ITEMS", "type": "list", "label": "Priced items", "min_items": 1, "max_items": 8, "item_fields": [
                _T("LABEL", "Label", required=True, max_len=40),
                {"key": "PRICE", "type": "number", "label": "Price per unit", "min": 0, "required": True},
                _T("UNIT", "Unit", max_len=20),
                {"key": "DEFAULT_QTY", "type": "number", "label": "Default quantity", "min": 0, "default": 1},
            ]},
            _T("TOTAL_LABEL", "Total label", max_len=40),
            _T("NAME_LABEL", "Name label", max_len=40), _T("EMAIL_LABEL", "Email label", max_len=40), _T("PHONE_LABEL", "Phone label", max_len=40),
            _T("SUBMIT_TEXT", "Button text", max_len=40), _T("SUCCESS_TEXT", "Success message", max_len=240),
            _TA("FINE_PRINT", "Fine print", max_len=200),
        ],
        "jsx_template": """<section className="pricing bg-slate-950 text-white py-24 px-6">
  <div className="max-w-5xl mx-auto grid md:grid-cols-2 gap-10 items-start">
    <div>
      <span className="text-sm font-semibold tracking-widest uppercase text-indigo-400">{{EYEBROW}}</span>
      <h2 className="text-4xl font-bold mt-3 mb-4">{{HEADLINE}}</h2>
      <p className="text-lg text-slate-400 mb-8">{{SUBHEADLINE}}</p>
      <div className="space-y-4">
        {{#ITEMS}}<label className="flex items-center justify-between gap-4 p-4 rounded-2xl bg-white/5 border border-white/10">
          <span><span className="block font-semibold">{{LABEL}}</span><span className="text-sm text-slate-400">{{PRICE}} {{UNIT}}</span></span>
          <input type="number" min="0" step="1" value="{{DEFAULT_QTY}}" data-quote-item data-price="{{PRICE}}" data-label="{{LABEL}}" name="qty_{{@INDEX}}" className="w-24 rounded-xl bg-white/10 border border-white/10 px-3 py-2 text-right text-white focus:outline-none focus:ring-2 focus:ring-indigo-400"/>
        </label>{{/ITEMS}}
      </div>
      <p className="mt-4 text-xs text-slate-500">{{FINE_PRINT}}</p>
    </div>
    <div className="p-8 rounded-3xl bg-white text-slate-900 shadow-2xl">
      <p className="text-sm font-semibold text-slate-500 uppercase tracking-widest">{{TOTAL_LABEL}}</p>
      <p data-quote-total className="text-5xl font-extrabold mt-2 mb-6">—</p>
      <form data-lead-form className="grid gap-3">
        <input name="name" required placeholder="{{NAME_LABEL}}" autocomplete="name" className="rounded-xl border border-slate-300 px-4 py-3 focus:outline-none focus:ring-2 focus:ring-indigo-500"/>
        <input name="email" type="email" required placeholder="{{EMAIL_LABEL}}" autocomplete="email" className="rounded-xl border border-slate-300 px-4 py-3 focus:outline-none focus:ring-2 focus:ring-indigo-500"/>
        <input name="phone" type="tel" placeholder="{{PHONE_LABEL}}" autocomplete="tel" className="rounded-xl border border-slate-300 px-4 py-3 focus:outline-none focus:ring-2 focus:ring-indigo-500"/>
        <button type="submit" className="mt-2 px-8 py-3.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold transition">{{SUBMIT_TEXT}}</button>
        <p data-error className="text-rose-600 text-sm"></p>
      </form>
      <div data-success className="text-emerald-700 font-medium">{{SUCCESS_TEXT}}</div>
    </div>
  </div>
</section>""",
    },
    # -------------------------------------------------------- pricing toggle
    {
        "id": "var_dyn_pricing_toggle",
        "category": "pricing",
        "variant_id": "pricing_toggle_table",
        "display_name": "Monthly / annual toggle",
        "description": "Three plans with a monthly ↔ annual switch. Prices, features and buttons are fields; the featured plan is highlighted.",
        "sort_order": 6,
        "schema_version": 2,
        "behaviour": "pricing_toggle",
        "capabilities": ["dynamic"],
        "motion_preset": "css_reveal_up",
        "default_props": {
            "HEADLINE": "Simple, honest pricing",
            "SUBHEADLINE": "Switch to annual and save two months.",
            "MONTHLY_LABEL": "Monthly", "ANNUAL_LABEL": "Annual", "SAVE_BADGE": "Save 17%",
            "PERIOD_MONTHLY": "/month", "PERIOD_ANNUAL": "/month, billed yearly",
            "PLANS": [
                {"NAME": "Starter", "TAGLINE": "For individuals getting going", "MONTHLY": "$29", "ANNUAL": "$24",
                 "FEATURES": ["First key feature", "Second key feature", "Email support"], "CTA_TEXT": "Choose Starter", "CTA_HREF": "#contact", "FEATURED": False},
                {"NAME": "Professional", "TAGLINE": "For growing businesses", "MONTHLY": "$79", "ANNUAL": "$66",
                 "FEATURES": ["Everything in Starter", "A more advanced feature", "Priority support", "Another compelling extra"], "CTA_TEXT": "Choose Professional", "CTA_HREF": "#contact", "FEATURED": True},
                {"NAME": "Enterprise", "TAGLINE": "For teams with custom needs", "MONTHLY": "$199", "ANNUAL": "$166",
                 "FEATURES": ["Everything in Professional", "Dedicated account manager", "Custom onboarding"], "CTA_TEXT": "Contact sales", "CTA_HREF": "#contact", "FEATURED": False},
            ],
            "FEATURED_BADGE": "Most popular",
        },
        "locale_props": {"fr-CA": {
            "HEADLINE": "Des prix simples et honnêtes", "SUBHEADLINE": "Passez à l’annuel et économisez deux mois.",
            "MONTHLY_LABEL": "Mensuel", "ANNUAL_LABEL": "Annuel", "SAVE_BADGE": "Économisez 17 %",
            "PERIOD_MONTHLY": "/mois", "PERIOD_ANNUAL": "/mois, facturé annuellement",
            "PLANS": [
                {"NAME": "Départ", "TAGLINE": "Pour les travailleurs autonomes", "MONTHLY": "29 $", "ANNUAL": "24 $",
                 "FEATURES": ["Première fonction clé", "Deuxième fonction clé", "Soutien par courriel"], "CTA_TEXT": "Choisir Départ", "CTA_HREF": "#contact", "FEATURED": False},
                {"NAME": "Professionnel", "TAGLINE": "Pour les entreprises en croissance", "MONTHLY": "79 $", "ANNUAL": "66 $",
                 "FEATURES": ["Tout ce qui est dans Départ", "Une fonction plus avancée", "Soutien prioritaire", "Un autre extra convaincant"], "CTA_TEXT": "Choisir Professionnel", "CTA_HREF": "#contact", "FEATURED": True},
                {"NAME": "Entreprise", "TAGLINE": "Pour les équipes aux besoins particuliers", "MONTHLY": "199 $", "ANNUAL": "166 $",
                 "FEATURES": ["Tout ce qui est dans Professionnel", "Gestionnaire de compte dédié", "Intégration sur mesure"], "CTA_TEXT": "Contacter les ventes", "CTA_HREF": "#contact", "FEATURED": False},
            ],
            "FEATURED_BADGE": "Le plus populaire",
        }},
        "fields_schema": [
            _T("HEADLINE", "Headline", required=True, max_len=80), _TA("SUBHEADLINE", "Subheadline", max_len=200),
            _T("MONTHLY_LABEL", "Monthly label", max_len=20), _T("ANNUAL_LABEL", "Annual label", max_len=20),
            _T("SAVE_BADGE", "Savings badge", max_len=20),
            _T("PERIOD_MONTHLY", "Period text (monthly)", max_len=40), _T("PERIOD_ANNUAL", "Period text (annual)", max_len=40),
            {"key": "PLANS", "type": "list", "label": "Plans", "min_items": 1, "max_items": 4, "item_fields": [
                _T("NAME", "Plan name", required=True, max_len=40), _T("TAGLINE", "Tagline", max_len=80),
                _T("MONTHLY", "Monthly price", required=True, max_len=20), _T("ANNUAL", "Annual price (per month)", required=True, max_len=20),
                {"key": "FEATURES", "type": "list", "label": "Features", "max_items": 8, "item_fields": [_T("VALUE", "Feature", max_len=80)]},
                _T("CTA_TEXT", "Button text", max_len=40), _URL("CTA_HREF", "Button link", default="#contact"),
                {"key": "FEATURED", "type": "boolean", "label": "Highlight this plan"},
            ]},
            _T("FEATURED_BADGE", "Featured badge", max_len=30),
        ],
        "jsx_template": """<section className="pricing bg-slate-50 py-24 px-6" data-period="monthly">
  <div className="max-w-6xl mx-auto">
    <div className="text-center mb-12">
      <h2 className="text-4xl font-bold text-slate-900 mb-3">{{HEADLINE}}</h2>
      <p className="text-lg text-slate-500 mb-8">{{SUBHEADLINE}}</p>
      <div className="inline-flex items-center gap-1 p-1 rounded-full bg-white border border-slate-200 shadow-sm">
        <button type="button" data-period="monthly" aria-pressed="true" className="px-5 py-2 rounded-full text-sm font-semibold text-slate-700 aria-pressed:bg-slate-900 aria-pressed:text-white transition">{{MONTHLY_LABEL}}</button>
        <button type="button" data-period="annual" aria-pressed="false" className="px-5 py-2 rounded-full text-sm font-semibold text-slate-700 aria-pressed:bg-slate-900 aria-pressed:text-white transition">{{ANNUAL_LABEL}} <span className="ml-1 text-xs text-emerald-600">{{SAVE_BADGE}}</span></button>
      </div>
    </div>
    <div className="grid md:grid-cols-3 gap-8 items-start">
      {{#PLANS}}<div className="relative p-8 rounded-2xl {{#FEATURED}}bg-slate-900 text-white shadow-2xl md:-mt-4{{/FEATURED}}{{^FEATURED}}bg-white border border-slate-200 text-slate-900{{/FEATURED}}">
        {{#FEATURED}}<span className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full bg-indigo-500 text-white text-xs font-semibold uppercase">{{FEATURED_BADGE}}</span>{{/FEATURED}}
        <h3 className="text-lg font-semibold mb-1">{{NAME}}</h3>
        <p className="text-sm opacity-70 mb-6">{{TAGLINE}}</p>
        <p className="text-5xl font-extrabold mb-1"><span data-price-monthly="{{MONTHLY}}" data-price-annual="{{ANNUAL}}">{{MONTHLY}}</span></p>
        <p className="text-sm opacity-60 mb-6" data-period-label data-label-monthly="{{PERIOD_MONTHLY}}" data-label-annual="{{PERIOD_ANNUAL}}">{{PERIOD_MONTHLY}}</p>
        <ul className="space-y-3 opacity-90 mb-8">{{#FEATURES}}<li>✓ {{VALUE}}</li>{{/FEATURES}}</ul>
        <a href="{{CTA_HREF}}" className="block text-center px-6 py-3 rounded-xl font-semibold transition {{#FEATURED}}bg-indigo-500 hover:bg-indigo-400 text-white{{/FEATURED}}{{^FEATURED}}border border-slate-300 text-slate-700 hover:bg-slate-50{{/FEATURED}}">{{CTA_TEXT}}</a>
      </div>{{/PLANS}}
    </div>
  </div>
</section>""",
    },
    # ------------------------------------------------------------- count up
    {
        "id": "var_dyn_stats_count_up",
        "category": "stats",
        "variant_id": "stats_count_up",
        "display_name": "Count-up stats",
        "description": "Four numbers that count up when they scroll into view. No GSAP — a 1 KB runtime module.",
        "sort_order": 5,
        "schema_version": 2,
        "behaviour": "count_up",
        "capabilities": ["dynamic", "motion_js"],
        "default_props": {
            "HEADLINE": "Numbers that move forward",
            "STATS": [
                {"VALUE": 500, "PREFIX": "", "SUFFIX": "+", "LABEL": "Projects delivered"},
                {"VALUE": 10, "PREFIX": "", "SUFFIX": "×", "LABEL": "Average ROI"},
                {"VALUE": 99.9, "PREFIX": "", "SUFFIX": "%", "LABEL": "Uptime"},
                {"VALUE": 4.9, "PREFIX": "", "SUFFIX": "★", "LABEL": "Client rating"},
            ],
        },
        "locale_props": {"fr-CA": {
            "HEADLINE": "Des chiffres qui parlent",
            "STATS": [
                {"VALUE": 500, "PREFIX": "", "SUFFIX": "+", "LABEL": "Projets livrés"},
                {"VALUE": 10, "PREFIX": "", "SUFFIX": "×", "LABEL": "Rendement moyen"},
                {"VALUE": 99.9, "PREFIX": "", "SUFFIX": "%", "LABEL": "Disponibilité"},
                {"VALUE": 4.9, "PREFIX": "", "SUFFIX": "★", "LABEL": "Note des clients"},
            ],
        }},
        "fields_schema": [
            _T("HEADLINE", "Headline", max_len=80),
            {"key": "STATS", "type": "list", "label": "Stats", "min_items": 1, "max_items": 6, "item_fields": [
                {"key": "VALUE", "type": "number", "label": "Value", "required": True},
                _T("PREFIX", "Prefix", max_len=5), _T("SUFFIX", "Suffix", max_len=5), _T("LABEL", "Label", required=True, max_len=40),
            ]},
        ],
        "jsx_template": """<section className="stats bg-slate-950 text-white py-20 px-6">
  <div className="max-w-6xl mx-auto">
    <h2 className="text-3xl md:text-4xl font-bold text-center mb-14">{{HEADLINE}}</h2>
    <div className="grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
      {{#STATS}}<div>
        <p className="text-5xl font-extrabold text-indigo-400 tabular-nums" data-count-to="{{VALUE}}" data-count-prefix="{{PREFIX}}" data-count-suffix="{{SUFFIX}}">{{PREFIX}}0{{SUFFIX}}</p>
        <p className="mt-2 text-sm text-slate-400 font-medium">{{LABEL}}</p>
      </div>{{/STATS}}
    </div>
  </div>
</section>""",
    },
    # ------------------------------------------------------------ countdown
    {
        "id": "var_dyn_cta_countdown",
        "category": "cta",
        "variant_id": "cta_countdown_offer",
        "display_name": "Countdown offer",
        "description": "A limited-time offer with a live days/hours/minutes/seconds countdown. Shows an 'offer ended' message after the deadline.",
        "sort_order": 5,
        "schema_version": 2,
        "behaviour": "countdown",
        "capabilities": ["dynamic"],
        "motion_preset": "css_reveal_fade",
        "default_props": {
            "EYEBROW": "Limited time",
            "HEADLINE": "Spring tune-up special — 20% off",
            "SUBHEADLINE": "Book before the timer runs out and the discount is locked in.",
            "DEADLINE": "2026-12-31",
            "DAYS_LABEL": "days", "HOURS_LABEL": "hours", "MINUTES_LABEL": "min", "SECONDS_LABEL": "sec",
            "CTA_TEXT": "Claim the offer", "CTA_HREF": "#contact",
            "EXPIRED_TEXT": "This offer has ended — but we still have great rates. Reach out!",
        },
        "locale_props": {"fr-CA": {
            "EYEBROW": "Offre limitée", "HEADLINE": "Spécial mise au point du printemps : 20 % de rabais",
            "SUBHEADLINE": "Réservez avant la fin du compte à rebours et le rabais est garanti.",
            "DAYS_LABEL": "jours", "HOURS_LABEL": "heures", "MINUTES_LABEL": "min", "SECONDS_LABEL": "s",
            "CTA_TEXT": "Profiter de l’offre", "EXPIRED_TEXT": "Cette offre est terminée, mais nos tarifs restent avantageux. Écrivez-nous!",
        }},
        "fields_schema": [
            _T("EYEBROW", "Eyebrow", max_len=40), _T("HEADLINE", "Headline", required=True, max_len=80),
            _TA("SUBHEADLINE", "Subheadline", max_len=200),
            {"key": "DEADLINE", "type": "text", "label": "Deadline (YYYY-MM-DD or ISO datetime)", "required": True, "runtime": True, "max_len": 30},
            _T("DAYS_LABEL", "Days label", max_len=12), _T("HOURS_LABEL", "Hours label", max_len=12),
            _T("MINUTES_LABEL", "Minutes label", max_len=12), _T("SECONDS_LABEL", "Seconds label", max_len=12),
            _T("CTA_TEXT", "Button text", max_len=40), _URL("CTA_HREF", "Button link", default="#contact"),
            _TA("EXPIRED_TEXT", "Text after the deadline", max_len=200),
        ],
        "jsx_template": """<section className="cta bg-gradient-to-r from-rose-600 to-orange-500 text-white py-20 px-6">
  <div className="max-w-4xl mx-auto text-center" data-countdown>
    <span className="inline-block px-4 py-1.5 rounded-full bg-white/15 text-sm font-semibold uppercase tracking-widest">{{EYEBROW}}</span>
    <h2 className="text-4xl md:text-5xl font-extrabold mt-5 mb-4">{{HEADLINE}}</h2>
    <p className="text-lg text-white/85 mb-10">{{SUBHEADLINE}}</p>
    <div data-cd-live>
      <div className="flex justify-center gap-4 md:gap-8 mb-10 tabular-nums">
        <div className="w-20 md:w-24 p-3 rounded-2xl bg-white/15"><p className="text-4xl font-extrabold" data-cd-days>0</p><p className="text-xs uppercase tracking-widest text-white/80">{{DAYS_LABEL}}</p></div>
        <div className="w-20 md:w-24 p-3 rounded-2xl bg-white/15"><p className="text-4xl font-extrabold" data-cd-hours>00</p><p className="text-xs uppercase tracking-widest text-white/80">{{HOURS_LABEL}}</p></div>
        <div className="w-20 md:w-24 p-3 rounded-2xl bg-white/15"><p className="text-4xl font-extrabold" data-cd-minutes>00</p><p className="text-xs uppercase tracking-widest text-white/80">{{MINUTES_LABEL}}</p></div>
        <div className="w-20 md:w-24 p-3 rounded-2xl bg-white/15"><p className="text-4xl font-extrabold" data-cd-seconds>00</p><p className="text-xs uppercase tracking-widest text-white/80">{{SECONDS_LABEL}}</p></div>
      </div>
      <a href="{{CTA_HREF}}" className="inline-block px-10 py-4 rounded-xl bg-white text-rose-700 font-bold text-lg shadow-xl hover:bg-rose-50 transition">{{CTA_TEXT}}</a>
    </div>
    <p data-cd-expired className="text-lg font-medium">{{EXPIRED_TEXT}}</p>
  </div>
</section>""",
    },
    # --------------------------------------------------------- before/after
    {
        "id": "var_dyn_gallery_before_after",
        "category": "gallery",
        "variant_id": "gallery_before_after",
        "display_name": "Before / after slider",
        "description": "Drag the handle to compare two photos. Perfect for trades, cleaning, renovations, fitness and beauty.",
        "sort_order": 5,
        "schema_version": 2,
        "behaviour": "before_after",
        "capabilities": ["dynamic"],
        "motion_preset": "css_scale_on_scroll",
        "default_props": {
            "EYEBROW": "Results",
            "HEADLINE": "See the difference",
            "SUBHEADLINE": "Drag the handle to compare.",
            "BEFORE_URL": "https://images.unsplash.com/photo-1484154218962-a197022b5858?auto=format&fit=crop&w=1400&q=80",
            "AFTER_URL": "https://images.unsplash.com/photo-1556911220-bff31c812dba?auto=format&fit=crop&w=1400&q=80",
            "BEFORE_LABEL": "Before", "AFTER_LABEL": "After",
        },
        "locale_props": {"fr-CA": {"EYEBROW": "Résultats", "HEADLINE": "Voyez la différence", "SUBHEADLINE": "Glissez la poignée pour comparer.", "BEFORE_LABEL": "Avant", "AFTER_LABEL": "Après"}},
        "fields_schema": [
            _T("EYEBROW", "Eyebrow", max_len=40), _T("HEADLINE", "Headline", required=True, max_len=80),
            _TA("SUBHEADLINE", "Subheadline", max_len=160),
            {"key": "BEFORE_URL", "type": "image", "label": "Before photo", "required": True},
            {"key": "AFTER_URL", "type": "image", "label": "After photo", "required": True},
            _T("BEFORE_LABEL", "Before label", max_len=20), _T("AFTER_LABEL", "After label", max_len=20),
        ],
        "jsx_template": """<section className="gallery bg-white py-24 px-6">
  <div className="max-w-5xl mx-auto">
    <div className="text-center mb-10">
      <span className="text-sm font-semibold tracking-widest uppercase text-indigo-600">{{EYEBROW}}</span>
      <h2 className="text-4xl font-bold text-slate-900 mt-3 mb-3">{{HEADLINE}}</h2>
      <p className="text-lg text-slate-500">{{SUBHEADLINE}}</p>
    </div>
    <div data-before-after className="aspect-[16/10] rounded-3xl shadow-2xl">
      <img data-before src="{{BEFORE_URL}}" alt="{{BEFORE_LABEL}}"/>
      <div data-after><img src="{{AFTER_URL}}" alt="{{AFTER_LABEL}}"/></div>
      <span className="absolute top-4 left-4 px-3 py-1 rounded-full bg-black/60 text-white text-xs font-semibold">{{BEFORE_LABEL}}</span>
      <span className="absolute top-4 right-4 px-3 py-1 rounded-full bg-black/60 text-white text-xs font-semibold">{{AFTER_LABEL}}</span>
      <div data-handle></div>
      <input type="range" min="0" max="100" value="50" aria-label="{{BEFORE_LABEL}} / {{AFTER_LABEL}}"/>
    </div>
  </div>
</section>""",
    },
    # ----------------------------------------------------------- faq search
    {
        "id": "var_dyn_faq_search",
        "category": "faq",
        "variant_id": "faq_searchable",
        "display_name": "Searchable FAQ",
        "description": "Accordion FAQ with an instant filter box. Questions and answers are a list field the AI fills per industry.",
        "sort_order": 5,
        "schema_version": 2,
        "behaviour": "faq_search",
        "capabilities": ["dynamic"],
        "motion_preset": "css_reveal_up",
        "default_props": {
            "HEADLINE": "Frequently asked questions",
            "SEARCH_PLACEHOLDER": "Search questions…",
            "EMPTY_TEXT": "No matching questions — send us yours below.",
            "FAQS": [
                {"QUESTION": "How much does it cost?", "ANSWER": "Answer the pricing question head-on — vagueness here loses customers."},
                {"QUESTION": "How long does it take?", "ANSWER": "Set an honest expectation for timelines from first contact to done."},
                {"QUESTION": "Do you offer a guarantee?", "ANSWER": "Address risk: refunds, warranties, or what happens if something goes wrong."},
                {"QUESTION": "How do I get started?", "ANSWER": "Describe the first step — a call, a form, a visit — and what happens after it."},
            ],
        },
        "locale_props": {"fr-CA": {
            "HEADLINE": "Foire aux questions", "SEARCH_PLACEHOLDER": "Rechercher une question…",
            "EMPTY_TEXT": "Aucune question correspondante : posez-nous la vôtre ci-dessous.",
            "FAQS": [
                {"QUESTION": "Combien ça coûte?", "ANSWER": "Répondez directement à la question du prix : le flou fait fuir les clients."},
                {"QUESTION": "Combien de temps ça prend?", "ANSWER": "Donnez une attente réaliste, du premier contact à la livraison."},
                {"QUESTION": "Offrez-vous une garantie?", "ANSWER": "Abordez le risque : remboursements, garanties, ou ce qui arrive en cas de problème."},
                {"QUESTION": "Comment commencer?", "ANSWER": "Décrivez la première étape (un appel, un formulaire, une visite) et la suite."},
            ],
        }},
        "fields_schema": [
            _T("HEADLINE", "Headline", required=True, max_len=80),
            _T("SEARCH_PLACEHOLDER", "Search placeholder", max_len=60), _T("EMPTY_TEXT", "No-results text", max_len=120),
            {"key": "FAQS", "type": "list", "label": "Questions", "min_items": 1, "max_items": 20, "item_fields": [
                _T("QUESTION", "Question", required=True, max_len=120), _TA("ANSWER", "Answer", required=True, max_len=600),
            ]},
        ],
        "jsx_template": """<section className="faq bg-slate-50 py-24 px-6">
  <div className="max-w-3xl mx-auto">
    <h2 className="text-4xl font-bold text-slate-900 text-center mb-8">{{HEADLINE}}</h2>
    <input type="search" data-faq-search placeholder="{{SEARCH_PLACEHOLDER}}" className="w-full mb-8 rounded-2xl border border-slate-300 bg-white px-5 py-3.5 text-slate-900 shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"/>
    <div className="space-y-3">
      {{#FAQS}}<details data-faq-item className="group p-5 rounded-2xl bg-white border border-slate-200 open:shadow-md">
        <summary className="flex items-center justify-between cursor-pointer list-none text-lg font-semibold text-slate-900"><span>{{QUESTION}}</span><span className="ml-4 text-slate-400 group-open:rotate-45 transition">+</span></summary>
        <p className="mt-3 text-slate-600 leading-relaxed">{{ANSWER}}</p>
      </details>{{/FAQS}}
      <p data-faq-empty className="text-center text-slate-500 py-6">{{EMPTY_TEXT}}</p>
    </div>
  </div>
</section>""",
    },
    # ----------------------------------------------------------- sticky bar
    {
        "id": "var_dyn_cta_sticky_bar",
        "category": "cta",
        "variant_id": "cta_sticky_action_bar",
        "display_name": "Sticky action bar",
        "description": "Call / text / book buttons that slide up after the first screen and stay pinned on mobile. Place it anywhere — it is fixed to the bottom.",
        "sort_order": 6,
        "schema_version": 2,
        "behaviour": "sticky_bar",
        "capabilities": ["dynamic"],
        "default_props": {
            "TEXT": "Ready when you are",
            "CALL_TEXT": "Call", "PHONE_NUMBER": "+16135550100",
            "SMS_TEXT": "Text", "SMS_NUMBER": "+16135550100",
            "BOOK_TEXT": "Book online", "BOOK_HREF": "#booking",
        },
        "locale_props": {"fr-CA": {"TEXT": "Quand vous voulez", "CALL_TEXT": "Appeler", "SMS_TEXT": "Texter", "BOOK_TEXT": "Réserver en ligne"}},
        "fields_schema": [
            _T("TEXT", "Bar text", max_len=60),
            _T("CALL_TEXT", "Call button", max_len=20), _T("PHONE_NUMBER", "Phone (tel: format)", max_len=20, bind="company.phone"),
            _T("SMS_TEXT", "Text button", max_len=20), _T("SMS_NUMBER", "SMS number", max_len=20),
            _T("BOOK_TEXT", "Book button", max_len=24), _URL("BOOK_HREF", "Book link", default="#booking"),
        ],
        "jsx_template": """<div className="cta">
  <div data-sticky-bar className="px-4 pb-4">
    <div className="max-w-3xl mx-auto flex items-center justify-between gap-3 p-3 rounded-2xl bg-slate-900/95 text-white shadow-2xl backdrop-blur border border-white/10">
      <span className="hidden sm:block pl-2 text-sm font-medium text-slate-300">{{TEXT}}</span>
      <div className="flex flex-1 sm:flex-none gap-2">
        <a href="tel:{{PHONE_NUMBER}}" className="flex-1 text-center px-4 py-2.5 rounded-xl bg-white/10 hover:bg-white/20 text-sm font-semibold transition">{{CALL_TEXT}}</a>
        <a href="sms:{{SMS_NUMBER}}" className="flex-1 text-center px-4 py-2.5 rounded-xl bg-white/10 hover:bg-white/20 text-sm font-semibold transition">{{SMS_TEXT}}</a>
        <a href="{{BOOK_HREF}}" className="flex-1 text-center px-4 py-2.5 rounded-xl bg-indigo-500 hover:bg-indigo-400 text-sm font-semibold transition">{{BOOK_TEXT}}</a>
      </div>
    </div>
  </div>
</div>""",
    },
    # ------------------------------------------------------------- open now
    {
        "id": "var_dyn_location_open_now",
        "category": "location",
        "variant_id": "location_map_hours",
        "display_name": "Map, hours & open now",
        "description": "Address, weekly hours and a live 'Open now / Closed' badge computed in the visitor's browser from your hours and timezone. Optional map embed.",
        "sort_order": 10,
        "schema_version": 2,
        "behaviour": "open_now",
        "capabilities": ["dynamic"],
        "motion_preset": "css_reveal_up",
        "default_props": {
            "EYEBROW": "Visit us",
            "HEADLINE": "Find us in the neighbourhood",
            "ADDRESS": "123 Bank Street, Ottawa, ON K2P 1X3",
            "TIMEZONE": "America/Toronto",
            "HOURS": [
                {"DAY": "monday", "DAY_LABEL": "Mon", "OPEN": "09:00", "CLOSE": "17:00"},
                {"DAY": "tuesday", "DAY_LABEL": "Tue", "OPEN": "09:00", "CLOSE": "17:00"},
                {"DAY": "wednesday", "DAY_LABEL": "Wed", "OPEN": "09:00", "CLOSE": "17:00"},
                {"DAY": "thursday", "DAY_LABEL": "Thu", "OPEN": "09:00", "CLOSE": "19:00"},
                {"DAY": "friday", "DAY_LABEL": "Fri", "OPEN": "09:00", "CLOSE": "17:00"},
                {"DAY": "saturday", "DAY_LABEL": "Sat", "OPEN": "10:00", "CLOSE": "14:00"},
            ],
            "MAP_EMBED_URL": "",
            "DIRECTIONS_TEXT": "Get directions", "DIRECTIONS_HREF": "https://maps.google.com/?q=123+Bank+Street+Ottawa",
            "PHONE_NUMBER": "+1 (613) 555-0100",
        },
        "locale_props": {"fr-CA": {
            "EYEBROW": "Visitez-nous", "HEADLINE": "Retrouvez-nous dans le quartier", "DIRECTIONS_TEXT": "Itinéraire",
            "HOURS": [
                {"DAY": "monday", "DAY_LABEL": "Lun", "OPEN": "09:00", "CLOSE": "17:00"},
                {"DAY": "tuesday", "DAY_LABEL": "Mar", "OPEN": "09:00", "CLOSE": "17:00"},
                {"DAY": "wednesday", "DAY_LABEL": "Mer", "OPEN": "09:00", "CLOSE": "17:00"},
                {"DAY": "thursday", "DAY_LABEL": "Jeu", "OPEN": "09:00", "CLOSE": "19:00"},
                {"DAY": "friday", "DAY_LABEL": "Ven", "OPEN": "09:00", "CLOSE": "17:00"},
                {"DAY": "saturday", "DAY_LABEL": "Sam", "OPEN": "10:00", "CLOSE": "14:00"},
            ],
        }},
        "fields_schema": [
            _T("EYEBROW", "Eyebrow", max_len=40), _T("HEADLINE", "Headline", required=True, max_len=80),
            _T("ADDRESS", "Address", required=True, max_len=160, bind="company.address"),
            {"key": "TIMEZONE", "type": "select", "label": "Timezone", "runtime": True, "default": "America/Toronto",
             "options": ["America/St_Johns", "America/Halifax", "America/Toronto", "America/Winnipeg", "America/Regina", "America/Edmonton", "America/Vancouver"]},
            {"key": "HOURS", "type": "list", "label": "Hours", "runtime": True, "max_items": 14, "item_fields": [
                {"key": "DAY", "type": "select", "label": "Day", "required": True, "options": ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]},
                _T("DAY_LABEL", "Day label", max_len=12),
                _T("OPEN", "Opens (HH:MM)", required=True, max_len=5), _T("CLOSE", "Closes (HH:MM)", required=True, max_len=5),
            ]},
            _URL("MAP_EMBED_URL", "Map embed URL (Google Maps → Share → Embed)"),
            _T("DIRECTIONS_TEXT", "Directions button", max_len=30), _URL("DIRECTIONS_HREF", "Directions link"),
            _T("PHONE_NUMBER", "Phone", max_len=30, bind="company.phone"),
        ],
        "jsx_template": """<section className="location bg-white py-24 px-6">
  <div className="max-w-6xl mx-auto grid md:grid-cols-2 gap-12 items-start">
    <div>
      <span className="text-sm font-semibold tracking-widest uppercase text-indigo-600">{{EYEBROW}}</span>
      <h2 className="text-4xl font-bold text-slate-900 mt-3 mb-6">{{HEADLINE}}</h2>
      <p data-open-now className="inline-flex items-center px-3 py-1.5 rounded-full bg-slate-100 text-sm font-semibold text-slate-800 mb-6"><span data-open-dot></span><span data-open-text>—</span></p>
      <p className="text-lg text-slate-700 mb-2">{{ADDRESS}}</p>
      <a href="tel:{{PHONE_NUMBER}}" className="text-indigo-600 font-semibold">{{PHONE_NUMBER}}</a>
      <dl className="mt-8 divide-y divide-slate-100 border-y border-slate-100">
        {{#HOURS}}<div className="flex justify-between py-2.5 text-sm"><dt className="font-medium text-slate-700">{{DAY_LABEL}}</dt><dd className="text-slate-500 tabular-nums">{{OPEN}} – {{CLOSE}}</dd></div>{{/HOURS}}
      </dl>
      <a href="{{DIRECTIONS_HREF}}" target="_blank" rel="noopener" className="inline-block mt-8 px-6 py-3 rounded-xl bg-slate-900 hover:bg-slate-800 text-white font-semibold transition">{{DIRECTIONS_TEXT}}</a>
    </div>
    <div className="aspect-[4/3] rounded-3xl overflow-hidden bg-slate-100 border border-slate-200">
      {{#MAP_EMBED_URL}}<iframe src="{{MAP_EMBED_URL}}" width="100%" height="100%" style="border:0" loading="lazy" referrerpolicy="no-referrer-when-downgrade" allowfullscreen></iframe>{{/MAP_EMBED_URL}}
      {{^MAP_EMBED_URL}}<div className="w-full h-full flex items-center justify-center text-slate-400 text-sm">Map — paste an embed URL in the block fields</div>{{/MAP_EMBED_URL}}
    </div>
  </div>
</section>""",
    },
    # --------------------------------------------------------- team (bound)
    {
        "id": "var_dyn_team_from_users",
        "category": "team",
        "variant_id": "team_from_workspace",
        "display_name": "Team grid (from your users)",
        "description": "Filled from your workspace's users at publish time — names, roles and booking links stay current with every republish.",
        "sort_order": 5,
        "schema_version": 2,
        "data_source": "users",
        "data_mode": "compile",
        "capabilities": ["dynamic", "bound_data"],
        "motion_preset": "css_reveal_up",
        "default_props": {
            "EYEBROW": "Our team",
            "HEADLINE": "The people you’ll actually work with",
            "BOOK_TEXT": "Book with me",
            "TEAM": [
                {"NAME": "Alex Brown", "TITLE": "Founder", "AVATAR_URL": "", "BOOKING_HREF": "", "INITIALS": "AB"},
                {"NAME": "Casey Jones", "TITLE": "Operations", "AVATAR_URL": "", "BOOKING_HREF": "", "INITIALS": "CJ"},
                {"NAME": "Riley Park", "TITLE": "Lead specialist", "AVATAR_URL": "", "BOOKING_HREF": "", "INITIALS": "RP"},
            ],
        },
        "locale_props": {"fr-CA": {"EYEBROW": "Notre équipe", "HEADLINE": "Les personnes avec qui vous travaillerez vraiment", "BOOK_TEXT": "Prendre rendez-vous"}},
        "fields_schema": [
            _T("EYEBROW", "Eyebrow", max_len=40), _T("HEADLINE", "Headline", required=True, max_len=80),
            _T("BOOK_TEXT", "Booking button", max_len=30),
            {"key": "TEAM", "type": "list", "label": "Team (replaced by your users at publish)", "max_items": 12, "item_fields": [
                _T("NAME", "Name", required=True, max_len=60), _T("TITLE", "Title", max_len=60),
                {"key": "AVATAR_URL", "type": "image", "label": "Photo"}, _URL("BOOKING_HREF", "Booking link"), _T("INITIALS", "Initials", max_len=3),
            ]},
        ],
        "jsx_template": """<section className="team bg-white py-24 px-6">
  <div className="max-w-6xl mx-auto">
    <div className="text-center mb-14">
      <span className="text-sm font-semibold tracking-widest uppercase text-indigo-600">{{EYEBROW}}</span>
      <h2 className="text-4xl font-bold text-slate-900 mt-3">{{HEADLINE}}</h2>
    </div>
    <div className="grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
      {{#TEAM}}<div>
        {{#AVATAR_URL}}<img src="{{AVATAR_URL}}" alt="{{NAME}}" className="w-24 h-24 mx-auto rounded-full object-cover mb-4"/>{{/AVATAR_URL}}
        {{^AVATAR_URL}}<div className="w-24 h-24 mx-auto rounded-full bg-gradient-to-br from-indigo-400 to-violet-600 text-white text-2xl font-bold flex items-center justify-center mb-4">{{INITIALS}}</div>{{/AVATAR_URL}}
        <h3 className="font-semibold text-slate-900">{{NAME}}</h3>
        <p className="text-sm text-slate-500">{{TITLE}}</p>
        {{#BOOKING_HREF}}<a href="{{BOOKING_HREF}}" className="inline-block mt-2 text-sm font-semibold text-indigo-600">{{BOOK_TEXT}}</a>{{/BOOKING_HREF}}
      </div>{{/TEAM}}
    </div>
  </div>
</section>""",
    },
]
