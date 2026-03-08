"""Generate 30 premium platform templates using Gemini + reference designs.

Run via admin endpoint or CLI:
    python -m app.pages.generate_templates
"""
import asyncio
import json
import logging
import uuid

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Template definitions — 30 industry templates
# ---------------------------------------------------------------------------

TEMPLATE_DEFS = [
    # --- HEALTH & MEDICAL ---
    {
        "name": "Dental Practice",
        "description": "Premium dental office website with appointment booking, services grid, and patient testimonials",
        "category_industry": "healthcare",
        "category_type": "homepage",
        "ref_style": "bensimon",
        "prompt": (
            "Build a premium dental practice website. Business name: {{company_name}}. "
            "Blue accent (#007AFF). Include: hero with smiling patient photo, services (Preventive Care, "
            "Cosmetic Dentistry, Orthodontics, Emergency Care, Implants, Pediatric Dentistry), "
            "3 patient testimonials with names and photos, FAQ (Do you accept insurance?, What should I "
            "expect on my first visit?, How often should I visit the dentist?), team section with 3 dentists, "
            "appointment booking CTA, and footer with hours/location."
        ),
    },
    {
        "name": "Chiropractor & Physiotherapy",
        "description": "Clean, trustworthy chiropractic and physiotherapy clinic website",
        "category_industry": "healthcare",
        "category_type": "homepage",
        "ref_style": "parkdale",
        "prompt": (
            "Build a chiropractor/physiotherapy clinic website. Business: {{company_name}}. "
            "Green accent (#00bf63). Include: hero with spine/wellness imagery, services (Spinal Adjustment, "
            "Sports Rehabilitation, Massage Therapy, Posture Correction, Dry Needling), How We're Different "
            "section with numbered steps, 4 patient testimonials, FAQ (Is chiropractic safe?, How many sessions "
            "will I need?, Do you direct-bill insurance?), team section, booking CTA."
        ),
    },
    {
        "name": "Med Spa & Aesthetics",
        "description": "Elegant medical spa website with treatments, before/after gallery, and booking",
        "category_industry": "healthcare",
        "category_type": "homepage",
        "ref_style": "biscayne",
        "prompt": (
            "Build a medical spa / aesthetics clinic website. Business: {{company_name}}. "
            "Gold accent (#C8952E). Include: hero with luxury spa imagery, treatments (Botox, Dermal Fillers, "
            "Chemical Peels, Laser Hair Removal, Microneedling, IV Therapy), before/after gallery section, "
            "3 client testimonials, pricing section, FAQ (Is Botox safe?, How long do fillers last?, "
            "What's the recovery time?), elegant booking CTA."
        ),
    },
    {
        "name": "Veterinary Clinic",
        "description": "Friendly veterinary clinic website with services, team, and emergency info",
        "category_industry": "healthcare",
        "category_type": "homepage",
        "ref_style": "maydental",
        "prompt": (
            "Build a veterinary clinic website. Business: {{company_name}}. "
            "Rose/coral accent (#F43F5E). Include: hero with happy pets imagery, services (Wellness Exams, "
            "Vaccinations, Surgery, Dental Care, Emergency Services, Boarding), team section with 3 vets "
            "and their specialties, 3 pet parent testimonials, FAQ (Do you handle emergencies?, What vaccines "
            "does my puppy need?, How often should I bring my pet in?), location map, appointment CTA."
        ),
    },
    {
        "name": "Mental Health & Therapy",
        "description": "Calming, professional therapy practice website with specialties and booking",
        "category_industry": "healthcare",
        "category_type": "homepage",
        "ref_style": "parkdale",
        "prompt": (
            "Build a mental health / therapy practice website. Business: {{company_name}}. "
            "Soft teal accent (#0d9488). Include: hero with calming nature imagery, specialties (Anxiety, "
            "Depression, PTSD, Couples Therapy, Family Counseling, Grief Support), Our Approach section, "
            "therapist profiles with photos, 3 client testimonials (anonymous first names only), "
            "FAQ (Is therapy confidential?, Do you accept insurance?, What happens in the first session?), "
            "gentle booking CTA. Warm, inviting, non-clinical tone."
        ),
    },
    # --- FOOD & HOSPITALITY ---
    {
        "name": "Restaurant & Fine Dining",
        "description": "Warm, inviting restaurant website with menu highlights, reservations, and ambiance",
        "category_industry": "restaurant",
        "category_type": "homepage",
        "ref_style": "biscayne",
        "prompt": (
            "Build a fine dining restaurant website. Business: {{company_name}}. "
            "Warm gold accent (#C8952E). Include: hero with restaurant interior/food photography, "
            "menu highlights (4-5 signature dishes with descriptions and prices), About The Chef section, "
            "private dining/events section, 3 guest testimonials, hours/location, reservation CTA "
            "with phone number. Use warm, inviting typography. Elegant and sophisticated."
        ),
    },
    {
        "name": "Cafe & Coffee Shop",
        "description": "Clean, minimal coffee shop website with menu, story, and locations",
        "category_industry": "restaurant",
        "category_type": "homepage",
        "ref_style": "parkdale",
        "prompt": (
            "Build a cafe/coffee shop website. Business: {{company_name}}. "
            "Warm brown accent (#92400e). Include: hero with coffee/cafe imagery, menu categories "
            "(Espresso Drinks, Pour Overs, Pastries, Breakfast, Lunch), Our Story section about sourcing "
            "and roasting, 3 customer testimonials, location with hours, Instagram gallery section. "
            "Clean, minimal, cozy vibes."
        ),
    },
    {
        "name": "Catering & Event Food",
        "description": "Elegant catering company website with menus, gallery, and quote request",
        "category_industry": "restaurant",
        "category_type": "homepage",
        "ref_style": "bensimon",
        "prompt": (
            "Build a catering company website. Business: {{company_name}}. "
            "Elegant navy accent (#1e3a5f). Include: hero with catering event photography, "
            "services (Wedding Catering, Corporate Events, Private Parties, Holiday Meals, Cocktail Receptions), "
            "menu packages with pricing tiers, event gallery, 3 client testimonials, "
            "FAQ (How far in advance should I book?, What's your minimum guest count?, "
            "Do you handle dietary restrictions?), quote request CTA."
        ),
    },
    {
        "name": "Bar & Lounge",
        "description": "Dark, moody bar and lounge website with cocktail menu and events",
        "category_industry": "restaurant",
        "category_type": "homepage",
        "ref_style": "ocidm",
        "prompt": (
            "Build a bar/lounge website. Business: {{company_name}}. "
            "DARK THEME with amber/gold accent (#d97706). Include: hero with moody bar interior, "
            "signature cocktails section (4-5 drinks with descriptions), weekly events schedule, "
            "live music calendar, gallery section, 3 patron testimonials, VIP/bottle service section, "
            "hours and location. Dark, sophisticated, nightlife energy."
        ),
    },
    # --- PROFESSIONAL SERVICES ---
    {
        "name": "Law Firm",
        "description": "Authoritative law firm website with practice areas, attorney profiles, and consultations",
        "category_industry": "professional",
        "category_type": "homepage",
        "ref_style": "parkdale",
        "prompt": (
            "Build a law firm website. Business: {{company_name}}. "
            "Navy accent (#1e3a5f). Include: hero with courthouse/legal imagery, practice areas "
            "(Personal Injury, Criminal Defense, Family Law, Estate Planning, Business Law, Immigration), "
            "attorney profiles with photos and credentials, case results/stats section, "
            "3 client testimonials, FAQ (How much does a consultation cost?, What is your success rate?, "
            "How long will my case take?), free consultation CTA. Authoritative, trustworthy tone."
        ),
    },
    {
        "name": "Accounting & CPA Firm",
        "description": "Professional accounting firm website with services, team, and client portal",
        "category_industry": "professional",
        "category_type": "homepage",
        "ref_style": "biscayne",
        "prompt": (
            "Build an accounting/CPA firm website. Business: {{company_name}}. "
            "Professional blue accent (#2563eb). Include: hero with professional office imagery, "
            "services (Tax Preparation, Bookkeeping, Payroll, Business Advisory, Audit & Assurance, "
            "CFO Services), Why Choose Us section with stats (500+ clients, 15+ years), "
            "3 client testimonials, FAQ (When is tax season?, Do you work with small businesses?, "
            "What documents do I need?), free consultation CTA."
        ),
    },
    {
        "name": "Consulting Agency",
        "description": "Bold consulting agency website with framework methodology and case studies",
        "category_industry": "professional",
        "category_type": "homepage",
        "ref_style": "ocidm",
        "prompt": (
            "Build a consulting agency website. Business: {{company_name}}. "
            "DARK THEME with purple accent (#7c3aed). Include: hero with bold headline, "
            "methodology/framework section with 4 pillars (Discover, Strategy, Execute, Scale), "
            "services (Digital Transformation, Growth Strategy, Operations, Change Management), "
            "case study cards with results, 3 client testimonials, pricing/engagement tiers, "
            "stats counters (200+ projects, 50+ clients, 95% retention), CTA. Bold, authoritative."
        ),
    },
    {
        "name": "Insurance & Financial Advisor",
        "description": "Trustworthy financial advisory website with services and client resources",
        "category_industry": "professional",
        "category_type": "homepage",
        "ref_style": "parkdale",
        "prompt": (
            "Build a financial advisor / insurance website. Business: {{company_name}}. "
            "Green accent (#16a34a). Include: hero with professional/family imagery, "
            "services (Life Insurance, Retirement Planning, Wealth Management, Estate Planning, "
            "Business Insurance, Tax Strategy), How We Help numbered steps, "
            "3 client testimonials, FAQ (How much life insurance do I need?, When should I start "
            "saving for retirement?, Are consultations free?), consultation CTA."
        ),
    },
    {
        "name": "Marketing & Digital Agency",
        "description": "Dark luxury marketing agency website with portfolio and capabilities",
        "category_industry": "agency",
        "category_type": "homepage",
        "ref_style": "ocidm",
        "prompt": (
            "Build a digital marketing agency website. Business: {{company_name}}. "
            "DARK LUXURY theme with orange/purple gradient accents. Include: hero with animated elements, "
            "capabilities (SEO, PPC, Social Media, Content Marketing, Web Design, Brand Strategy), "
            "portfolio/case study cards with results metrics, process section (4 steps), "
            "3 client testimonials, pricing packages (Starter, Growth, Enterprise), stats counters, "
            "bold CTA. Dark, modern, high-energy."
        ),
    },
    # --- REAL ESTATE & HOME ---
    {
        "name": "Real Estate Agent",
        "description": "Premium real estate agent website with listings, search, and agent profile",
        "category_industry": "real-estate",
        "category_type": "homepage",
        "ref_style": "biscayne",
        "prompt": (
            "Build a real estate agent website. Business: {{company_name}}. "
            "Navy/gold accent (#1e3a5f, #d4a853). Include: hero with luxury home photo and search bar concept, "
            "featured listings section (3-4 property cards with photos, beds/baths, prices), "
            "agent profile with photo and credentials, areas served, services (Buying, Selling, "
            "Investment Properties, Relocation), 3 client testimonials, market stats, contact CTA."
        ),
    },
    {
        "name": "Home Renovation & Contractor",
        "description": "Contractor website with services, project gallery, and free estimate",
        "category_industry": "real-estate",
        "category_type": "homepage",
        "ref_style": "maydental",
        "prompt": (
            "Build a home renovation/contractor website. Business: {{company_name}}. "
            "Orange accent (#ea580c). Include: hero with before/after renovation photo, "
            "services (Kitchen Remodeling, Bathroom Renovation, Additions, Roofing, Flooring, Painting), "
            "project gallery with before/after, Why Choose Us section, 3 client testimonials, "
            "FAQ (How long does a renovation take?, Do you provide free estimates?, Are you licensed?), "
            "free estimate CTA."
        ),
    },
    {
        "name": "Interior Design Studio",
        "description": "Elegant interior design website with portfolio, process, and consultation booking",
        "category_industry": "real-estate",
        "category_type": "homepage",
        "ref_style": "bensimon",
        "prompt": (
            "Build an interior design studio website. Business: {{company_name}}. "
            "Warm beige/gold accent (#a16207). Include: hero with stunning interior photo, "
            "portfolio gallery of completed projects, services (Residential, Commercial, Staging, "
            "Color Consultation, Space Planning), Our Process section (4 steps), "
            "3 client testimonials, press/publications section, consultation booking CTA. "
            "Elegant, visually rich, aspirational."
        ),
    },
    # --- FITNESS & LIFESTYLE ---
    {
        "name": "Gym & Fitness Studio",
        "description": "High-energy gym website with classes, memberships, and trainer profiles",
        "category_industry": "fitness",
        "category_type": "homepage",
        "ref_style": "ocidm",
        "prompt": (
            "Build a gym/fitness studio website. Business: {{company_name}}. "
            "DARK THEME with red accent (#dc2626). Include: hero with gym action photo, "
            "classes (HIIT, CrossFit, Yoga, Spin, Boxing, Strength Training), membership tiers "
            "(Basic $29/mo, Premium $59/mo, Elite $99/mo), trainer profiles with specialties, "
            "3 member testimonials, facility gallery, FAQ (Can I cancel anytime?, Do you offer "
            "trial passes?, What should I bring?), join now CTA. Dark, energetic, motivating."
        ),
    },
    {
        "name": "Yoga & Pilates Studio",
        "description": "Calm, minimal yoga studio website with class schedule and instructor profiles",
        "category_industry": "fitness",
        "category_type": "homepage",
        "ref_style": "parkdale",
        "prompt": (
            "Build a yoga/pilates studio website. Business: {{company_name}}. "
            "Sage green accent (#65a30d). Include: hero with serene yoga imagery, "
            "classes (Vinyasa Flow, Yin Yoga, Hot Yoga, Pilates Mat, Aerial Yoga, Meditation), "
            "class schedule section, instructor profiles with photos and certifications, "
            "3 student testimonials, pricing (Drop-in $20, 10-Class $150, Unlimited $120/mo), "
            "FAQ, CTA. Calm, minimal, peaceful aesthetic."
        ),
    },
    {
        "name": "Personal Trainer",
        "description": "Bold personal trainer website with programs, transformations, and booking",
        "category_industry": "fitness",
        "category_type": "homepage",
        "ref_style": "bensimon",
        "prompt": (
            "Build a personal trainer website. Business: {{company_name}}. "
            "Electric blue accent (#2563eb). Include: hero with trainer action photo and bold headline "
            "'Push Your Limits. Transform Your Body.', programs (1-on-1 Training, Online Coaching, "
            "Nutrition Plans, Group Sessions), transformation gallery, 3 client testimonials with "
            "results, credentials/certifications section, pricing packages, booking CTA."
        ),
    },
    # --- EDUCATION & CREATIVE ---
    {
        "name": "Online Course & Coaching",
        "description": "Course creator website with curriculum, pricing, and enrollment",
        "category_industry": "education",
        "category_type": "landing",
        "ref_style": "ocidm",
        "prompt": (
            "Build an online course/coaching website. Business: {{company_name}}. "
            "DARK THEME with gradient purple/blue accents. Include: hero with compelling headline, "
            "course curriculum section with module breakdown, What You'll Learn section, "
            "instructor bio with credentials, 3 student testimonials with results, "
            "pricing tiers (Self-Paced $297, Guided $597, VIP $997), FAQ (How long is the course?, "
            "Is there a refund policy?, Do I get lifetime access?), enrollment CTA with urgency."
        ),
    },
    {
        "name": "Photography & Videography",
        "description": "Visual portfolio website for photographers and videographers",
        "category_industry": "creative",
        "category_type": "portfolio",
        "ref_style": "bensimon",
        "prompt": (
            "Build a photography/videography portfolio website. Business: {{company_name}}. "
            "Dark accent (#111). Include: hero with dramatic portfolio image, portfolio gallery grid "
            "(weddings, portraits, commercial, events), About section with photographer photo, "
            "services (Wedding Photography, Portrait Sessions, Commercial, Video Production), "
            "packages with pricing, 3 client testimonials, booking CTA. Visually immersive, "
            "minimal text, let images speak."
        ),
    },
    {
        "name": "Freelancer & Portfolio",
        "description": "Minimal personal portfolio for freelancers and designers",
        "category_industry": "creative",
        "category_type": "portfolio",
        "ref_style": "parkdale",
        "prompt": (
            "Build a freelancer/designer portfolio website. Business: {{company_name}}. "
            "Clean minimal with black accent (#111). Include: hero with name and title, "
            "selected projects grid (4-6 projects with images and descriptions), skills/tools section, "
            "About Me section with photo, 3 client testimonials, availability status, "
            "contact CTA. Clean, minimal, typography-focused."
        ),
    },
    # --- TECH & SAAS ---
    {
        "name": "SaaS Product",
        "description": "Modern SaaS landing page with features, pricing toggle, and social proof",
        "category_industry": "saas",
        "category_type": "landing",
        "ref_style": "ocidm",
        "prompt": (
            "Build a SaaS product landing page. Business: {{company_name}}. "
            "DARK THEME with blue/purple gradient accents. Include: hero with product screenshot mockup "
            "and headline 'The Platform That Scales With You', feature grid (Analytics Dashboard, "
            "Team Collaboration, API Integrations, Enterprise Security, Automation, Reports), "
            "social proof logos section, 3 customer testimonials, pricing tiers (Starter $19/mo, "
            "Pro $49/mo, Enterprise Custom), FAQ, CTA. Modern, tech-forward."
        ),
    },
    {
        "name": "Mobile App Landing",
        "description": "App store-ready landing page with phone mockup hero and feature showcase",
        "category_industry": "saas",
        "category_type": "landing",
        "ref_style": "maydental",
        "prompt": (
            "Build a mobile app landing page. Business: {{company_name}}. "
            "Vibrant purple accent (#7c3aed). Include: hero with phone mockup and app store badges, "
            "feature showcase (4-6 features with icons), How It Works section (3 steps), "
            "app screenshots carousel concept, 3 user testimonials with star ratings, "
            "stats (100K+ Downloads, 4.9 Stars, 50K+ Active Users), download CTA. "
            "Clean, playful, modern."
        ),
    },
    {
        "name": "AI & Tech Startup",
        "description": "Futuristic AI/tech startup website with animated elements and gradient design",
        "category_industry": "saas",
        "category_type": "landing",
        "ref_style": "ocidm",
        "prompt": (
            "Build an AI/tech startup website. Business: {{company_name}}. "
            "DARK THEME with gradient purple-to-blue accents, animated floating shapes. "
            "Include: hero with futuristic imagery and headline, product capabilities section, "
            "How Our AI Works section (3-4 steps), use cases (Healthcare, Finance, E-commerce, Legal), "
            "3 enterprise testimonials, pricing/API tiers, stats, CTA. Futuristic, cutting-edge."
        ),
    },
    # --- RETAIL & ECOMMERCE ---
    {
        "name": "Boutique & Fashion",
        "description": "Elegant fashion boutique website with collection showcase and shopping",
        "category_industry": "ecommerce",
        "category_type": "homepage",
        "ref_style": "biscayne",
        "prompt": (
            "Build a fashion boutique website. Business: {{company_name}}. "
            "Warm black/gold accent (#111, #d4a853). Include: hero with fashion model photo, "
            "new collection showcase (4-6 products with photos and prices), About Our Brand story, "
            "categories (Women, Men, Accessories, Sale), 3 customer reviews, newsletter signup, "
            "shipping/returns info, elegant footer. Sophisticated, aspirational, editorial feel."
        ),
    },
    {
        "name": "Salon & Barbershop",
        "description": "Stylish salon website with services, team, booking, and gallery",
        "category_industry": "beauty",
        "category_type": "homepage",
        "ref_style": "maydental",
        "prompt": (
            "Build a salon/barbershop website. Business: {{company_name}}. "
            "Rose accent (#e11d48). Include: hero with salon interior photo, "
            "services with pricing (Haircut $45, Color $120, Highlights $180, Blowout $55, "
            "Beard Trim $25, Facial $80), stylist profiles with photos and specialties, "
            "gallery of work, 3 client testimonials, FAQ, booking CTA. Stylish, trendy."
        ),
    },
    # --- LOCAL SERVICES ---
    {
        "name": "Auto Repair & Mechanic",
        "description": "Trustworthy auto repair website with services, pricing, and reviews",
        "category_industry": "local-services",
        "category_type": "homepage",
        "ref_style": "parkdale",
        "prompt": (
            "Build an auto repair/mechanic website. Business: {{company_name}}. "
            "Red accent (#dc2626). Include: hero with auto shop imagery, "
            "services (Oil Change, Brake Service, Engine Repair, Transmission, Tires, Diagnostics), "
            "transparent pricing section, Why Choose Us (ASE Certified, Honest Pricing, Warranty), "
            "3 customer testimonials, FAQ (Do you offer free estimates?, How long does an oil change take?, "
            "Do you work on all makes?), appointment CTA."
        ),
    },
    {
        "name": "Cleaning Service",
        "description": "Friendly cleaning service website with packages, booking, and trust signals",
        "category_industry": "local-services",
        "category_type": "homepage",
        "ref_style": "biscayne",
        "prompt": (
            "Build a cleaning service website. Business: {{company_name}}. "
            "Fresh blue accent (#0ea5e9). Include: hero with clean home imagery, "
            "service packages (Standard Clean $120, Deep Clean $200, Move In/Out $300, "
            "Office Cleaning Custom), trust signals (Insured, Background Checked, Eco-Friendly Products), "
            "How It Works (Book, We Clean, You Relax), 3 customer testimonials, "
            "FAQ (What products do you use?, Do I need to be home?, How do I pay?), "
            "instant quote CTA."
        ),
    },
]

# Map reference styles to reference names for the reference system
STYLE_TO_REFS = {
    "bensimon": (["bensimon", "biscayne"], "bensimon"),
    "biscayne": (["biscayne", "parkdale"], "biscayne"),
    "maydental": (["maydental", "biscayne"], "maydental"),
    "ocidm": (["ocidm", "bensimon"], "ocidm"),
    "parkdale": (["parkdale", "biscayne"], "parkdale"),
}


async def generate_single_template(
    template_def: dict,
    gemini_key: str,
    db_session=None,
) -> dict | None:
    """Generate a single template using Gemini with reference designs.

    Returns the generated template data dict, or None on failure.
    """
    import httpx
    from app.pages.references import (
        load_screenshot_base64,
        get_screenshot_mime,
        load_reference_code,
        REFERENCE_DESCRIPTIONS,
    )

    ref_style = template_def["ref_style"]
    screenshot_names, code_name = STYLE_TO_REFS.get(ref_style, (["bensimon"], "bensimon"))

    # Build multimodal parts
    parts: list[dict] = []

    # Add reference screenshots
    for name in screenshot_names:
        b64 = load_screenshot_base64(name)
        if b64:
            mime = get_screenshot_mime(name)
            parts.append({"inlineData": {"mimeType": mime, "data": b64}})

    # Add reference code
    ref_code = load_reference_code(code_name) or ""
    if len(ref_code) > 40000:
        ref_code = ref_code[:40000]

    desc_lines = []
    for name in screenshot_names:
        desc = REFERENCE_DESCRIPTIONS.get(name, "")
        desc_lines.append(f"  - {name}: {desc}")

    # Build the prompt
    system_text = (
        "You are an elite web designer. The images above show the EXACT quality level I want. "
        "Study them carefully — these are $50,000 premium websites.\n\n"
        "Reference designs shown:\n" + "\n".join(desc_lines) + "\n\n"
        "Here is the code that produced one of these designs — use the same patterns:\n\n"
        + ref_code + "\n\n"
        "Now build a NEW website with the SAME premium quality but for a DIFFERENT industry.\n\n"
        "REQUIREMENTS:\n"
        "- Match the quality of the reference designs EXACTLY\n"
        "- Use Tailwind CSS via CDN: <script src=\"https://cdn.tailwindcss.com\"></script>\n"
        "- Use Google Fonts Inter: <link href=\"https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap\" rel=\"stylesheet\">\n"
        "- Use Lucide icons: <script src=\"https://unpkg.com/lucide@latest/dist/umd/lucide.js\"></script>\n"
        "- Use REAL images from Unsplash (https://images.unsplash.com/photo-...)\n"
        "- Include scroll reveal animations via IntersectionObserver\n"
        "- Glassmorphic navigation with blur on scroll\n"
        "- Hover lift effects on cards\n"
        "- Mobile responsive with hamburger menu\n"
        "- Use {{company_name}} as placeholder for business name\n"
        "- Make it look DIFFERENT from the reference — same quality, different layout\n\n"
        "TOPIC: " + template_def["prompt"] + "\n\n"
        "Return ONLY valid JSON with this structure:\n"
        '{"response": "Brief description of what was built", '
        '"html_content": "Complete <!DOCTYPE html> to </html>", '
        '"css_content": ""}'
    )

    parts.append({"text": system_text})

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
                "?key=" + gemini_key,
                json={
                    "contents": [{"parts": parts}],
                    "generationConfig": {
                        "temperature": 0.85,
                        "maxOutputTokens": 65536,
                        "responseMimeType": "application/json",
                    },
                },
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]

        # Parse JSON response
        import re
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON in text
            match = re.search(r'\{[\s\S]*"html_content"[\s\S]*\}', text)
            if match:
                parsed = json.loads(match.group())
            else:
                logger.error("Failed to parse Gemini response for %s", template_def["name"])
                return None

        html_content = parsed.get("html_content", "")
        if not html_content or len(html_content) < 200:
            logger.error("Empty/short HTML for %s", template_def["name"])
            return None

        return {
            "name": template_def["name"],
            "description": template_def["description"],
            "category_industry": template_def["category_industry"],
            "category_type": template_def["category_type"],
            "html_content": html_content,
            "css_content": parsed.get("css_content", ""),
        }

    except Exception as e:
        logger.error("Gemini generation failed for %s: %s", template_def["name"], e)
        return None


async def generate_all_templates(
    db,
    gemini_key: str,
    replace_existing: bool = False,
) -> dict:
    """Generate all 30 premium templates and store in database.

    Returns: {"generated": int, "failed": int, "skipped": int}
    """
    from sqlalchemy import select, func
    from app.pages.models import PageTemplate, TemplateScope

    stats = {"generated": 0, "failed": 0, "skipped": 0, "total": len(TEMPLATE_DEFS)}

    # Get existing template names to skip duplicates
    existing_q = select(PageTemplate.name).where(
        PageTemplate.scope == TemplateScope.PLATFORM
    )
    result = await db.execute(existing_q)
    existing_names = {row[0] for row in result.all()}

    for i, tdef in enumerate(TEMPLATE_DEFS):
        # Skip if already exists (unless replacing)
        if tdef["name"] in existing_names and not replace_existing:
            logger.info(
                "[%d/%d] Skipping '%s' (already exists)",
                i + 1, len(TEMPLATE_DEFS), tdef["name"],
            )
            stats["skipped"] += 1
            continue

        logger.info(
            "[%d/%d] Generating '%s' (%s style)...",
            i + 1, len(TEMPLATE_DEFS), tdef["name"], tdef["ref_style"],
        )

        result_data = await generate_single_template(tdef, gemini_key)

        if result_data:
            # Delete existing if replacing
            if replace_existing and tdef["name"] in existing_names:
                del_q = select(PageTemplate).where(
                    PageTemplate.name == tdef["name"],
                    PageTemplate.scope == TemplateScope.PLATFORM,
                )
                existing = (await db.execute(del_q)).scalar_one_or_none()
                if existing:
                    await db.delete(existing)

            template = PageTemplate(
                id=uuid.uuid4(),
                name=result_data["name"],
                description=result_data["description"],
                category_industry=result_data["category_industry"],
                category_type=result_data["category_type"],
                html_content=result_data["html_content"],
                css_content=result_data["css_content"],
                scope=TemplateScope.PLATFORM,
                is_active=True,
                created_by=None,
            )
            db.add(template)
            await db.commit()

            stats["generated"] += 1
            logger.info(
                "[%d/%d] Generated '%s' successfully (%d chars HTML)",
                i + 1, len(TEMPLATE_DEFS), tdef["name"], len(result_data["html_content"]),
            )
        else:
            stats["failed"] += 1
            logger.warning(
                "[%d/%d] FAILED to generate '%s'",
                i + 1, len(TEMPLATE_DEFS), tdef["name"],
            )

        # Rate limiting — 3 second delay between calls
        if i < len(TEMPLATE_DEFS) - 1:
            await asyncio.sleep(3)

    logger.info(
        "Template generation complete: %d generated, %d failed, %d skipped out of %d total",
        stats["generated"], stats["failed"], stats["skipped"], stats["total"],
    )
    return stats
