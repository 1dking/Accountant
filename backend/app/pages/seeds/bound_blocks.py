"""Data-bound seed blocks (S5) — services list, reviews feed, FAQ from your data.

Each one declares a `data_source` (catalog | reviews | faqs). The compiler
calls `resolve_page_bindings` at publish time and swaps in the workspace's
real rows via the block's own template. The stored `sections_json` is
untouched, so the editor keeps showing the block's default sample copy.
"""
from __future__ import annotations

_T = lambda k, l, **kw: {"key": k, "type": "text", "label": l, "max_len": 160, **kw}   # noqa: E731
_TA = lambda k, l, **kw: {"key": k, "type": "textarea", "label": l, "max_len": 600, **kw}  # noqa: E731

BOUND_BLOCKS: list[dict] = [
    # ------------------------------------------------ services list (catalog)
    {
        "id": "var_dyn_services_from_catalog",
        "category": "services",
        "variant_id": "services_from_catalog",
        "display_name": "Services (from your catalogue)",
        "description": "Grid of services, filled from your Site Content → Services at publish time. Edit a service once and every page updates on the next republish.",
        "sort_order": 5,
        "schema_version": 2,
        "data_source": "catalog",
        "data_mode": "compile",
        "capabilities": ["dynamic", "bound_data"],
        "motion_preset": "css_reveal_up",
        "default_props": {
            "EYEBROW": "What we do",
            "HEADLINE": "Services for growing businesses",
            "SUBHEADLINE": "Pick the piece you need — or ask us for the whole package.",
            "SERVICES": [
                {"NAME": "Bookkeeping", "SUMMARY": "Monthly books, reconciled and ready for taxes.", "PRICE_DISPLAY": "From $299", "PRICE_PERIOD": "/mo", "CTA_TEXT": "Learn more", "CTA_HREF": "#contact", "IMAGE_URL": ""},
                {"NAME": "GST/HST filing", "SUMMARY": "Quarterly filing done for you.", "PRICE_DISPLAY": "$149", "PRICE_PERIOD": "/quarter", "CTA_TEXT": "Learn more", "CTA_HREF": "#contact", "IMAGE_URL": ""},
                {"NAME": "Personal tax", "SUMMARY": "T1 preparation for you and your family.", "PRICE_DISPLAY": "From $89", "PRICE_PERIOD": "/return", "CTA_TEXT": "Learn more", "CTA_HREF": "#contact", "IMAGE_URL": ""},
            ],
        },
        "locale_props": {"fr-CA": {
            "EYEBROW": "Nos services", "HEADLINE": "Des services pour votre croissance",
            "SUBHEADLINE": "Choisissez ce qu’il vous faut — ou confiez-nous l’ensemble.",
        }},
        "fields_schema": [
            _T("EYEBROW", "Eyebrow", max_len=40),
            _T("HEADLINE", "Headline", required=True, max_len=80),
            _TA("SUBHEADLINE", "Subheadline", max_len=240),
            {"key": "SERVICES", "type": "list", "label": "Services (used until real data is published)",
             "hint": "This is placeholder copy. Real content comes from Site Content → Services on publish.",
             "max_items": 12, "item_fields": [
                _T("NAME", "Name", required=True, max_len=80),
                _TA("SUMMARY", "Summary", max_len=240),
                _T("PRICE_DISPLAY", "Price", max_len=30),
                _T("PRICE_PERIOD", "Period", max_len=20),
                _T("CTA_TEXT", "Button text", max_len=30),
                {"key": "CTA_HREF", "type": "url", "label": "Button link"},
                {"key": "IMAGE_URL", "type": "image", "label": "Image"},
             ]},
        ],
        "jsx_template": """<section className="services bg-white py-24 px-6">
  <div className="max-w-6xl mx-auto">
    <div className="text-center mb-14">
      <span className="text-sm font-semibold tracking-widest uppercase text-indigo-600">{{EYEBROW}}</span>
      <h2 className="text-4xl font-bold text-slate-900 mt-3 mb-3">{{HEADLINE}}</h2>
      <p className="text-lg text-slate-500 max-w-2xl mx-auto">{{SUBHEADLINE}}</p>
    </div>
    <div className="grid md:grid-cols-3 gap-6">
      {{#SERVICES}}<article className="flex flex-col rounded-2xl border border-slate-200 bg-white overflow-hidden hover:shadow-xl transition">
        {{#IMAGE_URL}}<img src="{{IMAGE_URL}}" alt="{{NAME}}" className="w-full aspect-[4/3] object-cover"/>{{/IMAGE_URL}}
        <div className="p-6 flex-1 flex flex-col">
          <h3 className="text-lg font-semibold text-slate-900">{{NAME}}</h3>
          <p className="mt-2 text-slate-500 leading-relaxed flex-1">{{SUMMARY}}</p>
          {{#PRICE_DISPLAY}}<p className="mt-4 text-2xl font-extrabold text-slate-900">{{PRICE_DISPLAY}}<span className="text-sm font-medium text-slate-400"> {{PRICE_PERIOD}}</span></p>{{/PRICE_DISPLAY}}
          {{#CTA_TEXT}}<a href="{{CTA_HREF}}" className="mt-5 inline-block text-center px-5 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white font-semibold transition">{{CTA_TEXT}}</a>{{/CTA_TEXT}}
        </div>
      </article>{{/SERVICES}}
    </div>
  </div>
</section>""",
    },
    # ------------------------------------------------ reviews feed (reviews)
    {
        "id": "var_dyn_reviews_from_data",
        "category": "testimonials",
        "variant_id": "reviews_feed",
        "display_name": "Reviews feed (from your data)",
        "description": "Testimonial wall backed by the reviews you add in Site Content → Reviews. Later, Google review imports flow into the same feed.",
        "sort_order": 5,
        "schema_version": 2,
        "data_source": "reviews",
        "data_mode": "compile",
        "capabilities": ["dynamic", "bound_data"],
        "motion_preset": "css_reveal_up",
        "default_props": {
            "EYEBROW": "Reviews",
            "HEADLINE": "What our clients say",
            "SUBHEADLINE": "Real words from the people we work with.",
            "REVIEWS": [
                {"QUOTE": "Add real reviews in Site Content → Reviews. They'll replace this sample on your next publish.", "AUTHOR_NAME": "Jane Doe", "AUTHOR_TITLE": "Owner, Acme Co.", "STARS": "★★★★★", "INITIALS": "JD", "AUTHOR_AVATAR_URL": ""},
                {"QUOTE": "A second sample quote — pick real ones that answer your customers' biggest doubt.", "AUTHOR_NAME": "Mark Smith", "AUTHOR_TITLE": "Director, Bright LLC", "STARS": "★★★★★", "INITIALS": "MS", "AUTHOR_AVATAR_URL": ""},
                {"QUOTE": "A third sample quote — specific results (numbers, timelines) convert best.", "AUTHOR_NAME": "Amy Lee", "AUTHOR_TITLE": "Founder, Northside", "STARS": "★★★★★", "INITIALS": "AL", "AUTHOR_AVATAR_URL": ""},
            ],
        },
        "locale_props": {"fr-CA": {"EYEBROW": "Avis", "HEADLINE": "Ce que disent nos clients", "SUBHEADLINE": "De vraies paroles de nos partenaires."}},
        "fields_schema": [
            _T("EYEBROW", "Eyebrow", max_len=40),
            _T("HEADLINE", "Headline", required=True, max_len=80),
            _TA("SUBHEADLINE", "Subheadline", max_len=240),
            {"key": "REVIEWS", "type": "list", "label": "Sample reviews (until real ones are published)",
             "max_items": 12, "item_fields": [
                _TA("QUOTE", "Quote", required=True, max_len=600),
                _T("AUTHOR_NAME", "Author", required=True, max_len=120),
                _T("AUTHOR_TITLE", "Author title", max_len=120),
                _T("STARS", "Stars (★★★★★)", max_len=5),
                _T("INITIALS", "Initials", max_len=3),
                {"key": "AUTHOR_AVATAR_URL", "type": "image", "label": "Author photo"},
             ]},
        ],
        "jsx_template": """<section className="testimonials bg-slate-50 py-24 px-6">
  <div className="max-w-6xl mx-auto">
    <div className="text-center mb-14">
      <span className="text-sm font-semibold tracking-widest uppercase text-indigo-600">{{EYEBROW}}</span>
      <h2 className="text-4xl font-bold text-slate-900 mt-3 mb-3">{{HEADLINE}}</h2>
      <p className="text-lg text-slate-500">{{SUBHEADLINE}}</p>
    </div>
    <div className="grid md:grid-cols-3 gap-6">
      {{#REVIEWS}}<article className="p-6 rounded-2xl bg-white border border-slate-200">
        {{#STARS}}<p className="text-amber-400 text-lg mb-3">{{STARS}}</p>{{/STARS}}
        <p className="text-slate-700 leading-relaxed">“{{QUOTE}}”</p>
        <div className="mt-5 flex items-center gap-3">
          {{#AUTHOR_AVATAR_URL}}<img src="{{AUTHOR_AVATAR_URL}}" alt="{{AUTHOR_NAME}}" className="w-11 h-11 rounded-full object-cover"/>{{/AUTHOR_AVATAR_URL}}
          {{^AUTHOR_AVATAR_URL}}<div className="w-11 h-11 rounded-full bg-indigo-100 text-indigo-700 font-bold flex items-center justify-center">{{INITIALS}}</div>{{/AUTHOR_AVATAR_URL}}
          <div>
            <p className="font-semibold text-slate-900">{{AUTHOR_NAME}}</p>
            <p className="text-sm text-slate-500">{{AUTHOR_TITLE}}</p>
          </div>
        </div>
      </article>{{/REVIEWS}}
    </div>
  </div>
</section>""",
    },
    # --------------------------------------------------------- FAQ (faqs)
    {
        "id": "var_dyn_faqs_from_data",
        "category": "faq",
        "variant_id": "faqs_from_data",
        "display_name": "FAQ (from your data)",
        "description": "Accordion FAQ backed by Site Content → FAQs. Editing a question there updates every page it appears on.",
        "sort_order": 6,
        "schema_version": 2,
        "data_source": "faqs",
        "data_mode": "compile",
        "capabilities": ["dynamic", "bound_data"],
        "motion_preset": "css_reveal_up",
        "default_props": {
            "HEADLINE": "Frequently asked questions",
            "FAQS": [
                {"QUESTION": "Add real questions in Site Content → FAQs.", "ANSWER": "Answers live there too. They replace this sample on your next publish."},
                {"QUESTION": "How much does it cost?", "ANSWER": "Answer the pricing question directly — vagueness loses customers."},
                {"QUESTION": "How long does it take?", "ANSWER": "Set an honest expectation from first contact to done."},
            ],
        },
        "locale_props": {"fr-CA": {"HEADLINE": "Foire aux questions"}},
        "fields_schema": [
            _T("HEADLINE", "Headline", required=True, max_len=80),
            {"key": "FAQS", "type": "list", "label": "Sample questions (until real ones are published)", "max_items": 20, "item_fields": [
                _T("QUESTION", "Question", required=True, max_len=200),
                _TA("ANSWER", "Answer", required=True, max_len=600),
            ]},
        ],
        "jsx_template": """<section className="faq bg-white py-24 px-6">
  <div className="max-w-3xl mx-auto">
    <h2 className="text-4xl font-bold text-slate-900 text-center mb-10">{{HEADLINE}}</h2>
    <div className="space-y-3">
      {{#FAQS}}<details className="group p-5 rounded-2xl bg-slate-50 border border-slate-200 open:shadow-md">
        <summary className="flex items-center justify-between cursor-pointer list-none text-lg font-semibold text-slate-900">
          <span>{{QUESTION}}</span>
          <span className="ml-4 text-slate-400 group-open:rotate-45 transition">+</span>
        </summary>
        <p className="mt-3 text-slate-600 leading-relaxed">{{ANSWER}}</p>
      </details>{{/FAQS}}
    </div>
  </div>
</section>""",
    },
]
