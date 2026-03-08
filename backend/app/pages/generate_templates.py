"""Generate 30 premium platform templates by COPYING reference HTML and swapping content.

The key insight: Gemini produces garbage when asked to "build a new website".
Instead, we give it the EXACT reference HTML and tell it to ONLY replace content.
Every CSS animation, every JS function, every HTML structure stays intact.

Run via admin endpoint:
    POST /pages/templates/generate-library?replace=true
"""
import asyncio
import json
import logging
import random
import re
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
        "ref_base": "bensimon",
        "ref_mix": "biscayne",
        "color": "#007AFF",
        "content": {
            "business_name": "{{company_name}}",
            "tagline": "Advanced Family Dentistry & Cosmetic Care",
            "services": "Preventive Care, Cosmetic Dentistry, Orthodontics, Emergency Care, Implants, Pediatric Dentistry",
            "testimonials": "3 patient testimonials with names and photos",
            "faq": "Do you accept insurance? | What should I expect on my first visit? | How often should I visit the dentist?",
            "cta": "Book Your Appointment Today",
            "team": "3 dentists with specialties",
        },
    },
    {
        "name": "Chiropractor & Physiotherapy",
        "description": "Clean, trustworthy chiropractic and physiotherapy clinic website",
        "category_industry": "healthcare",
        "category_type": "homepage",
        "ref_base": "parkdale",
        "ref_mix": "biscayne",
        "color": "#00bf63",
        "content": {
            "business_name": "{{company_name}}",
            "tagline": "Restore Your Body. Reclaim Your Life.",
            "services": "Spinal Adjustment, Sports Rehabilitation, Massage Therapy, Posture Correction, Dry Needling, Shockwave Therapy",
            "testimonials": "4 patient testimonials about recovery and pain relief",
            "faq": "Is chiropractic safe? | How many sessions will I need? | Do you direct-bill insurance?",
            "cta": "Book Your Assessment",
            "team": "3 practitioners with specialties",
        },
    },
    {
        "name": "Med Spa & Aesthetics",
        "description": "Elegant medical spa website with treatments, before/after gallery, and booking",
        "category_industry": "healthcare",
        "category_type": "homepage",
        "ref_base": "biscayne",
        "ref_mix": "bensimon",
        "color": "#C8952E",
        "content": {
            "business_name": "{{company_name}}",
            "tagline": "Luxury Aesthetics & Rejuvenation",
            "services": "Botox, Dermal Fillers, Chemical Peels, Laser Hair Removal, Microneedling, IV Therapy",
            "testimonials": "3 client testimonials about transformation",
            "faq": "Is Botox safe? | How long do fillers last? | What's the recovery time?",
            "cta": "Book Your Consultation",
            "team": "Lead aesthetician and doctor profiles",
        },
    },
    {
        "name": "Veterinary Clinic",
        "description": "Friendly veterinary clinic website with services, team, and emergency info",
        "category_industry": "healthcare",
        "category_type": "homepage",
        "ref_base": "maydental",
        "ref_mix": "parkdale",
        "color": "#F43F5E",
        "content": {
            "business_name": "{{company_name}}",
            "tagline": "Compassionate Care for Your Furry Family",
            "services": "Wellness Exams, Vaccinations, Surgery, Dental Care, Emergency Services, Boarding",
            "testimonials": "3 pet parent testimonials with pet names",
            "faq": "Do you handle emergencies? | What vaccines does my puppy need? | How often should I bring my pet in?",
            "cta": "Schedule a Visit",
            "team": "3 veterinarians with specialties",
        },
    },
    {
        "name": "Mental Health & Therapy",
        "description": "Calming, professional therapy practice website with specialties and booking",
        "category_industry": "healthcare",
        "category_type": "homepage",
        "ref_base": "parkdale",
        "ref_mix": "biscayne",
        "color": "#0d9488",
        "content": {
            "business_name": "{{company_name}}",
            "tagline": "A Safe Space for Healing & Growth",
            "services": "Anxiety, Depression, PTSD, Couples Therapy, Family Counseling, Grief Support",
            "testimonials": "3 anonymous client testimonials (first names only)",
            "faq": "Is therapy confidential? | Do you accept insurance? | What happens in the first session?",
            "cta": "Begin Your Journey",
            "team": "3 therapist profiles with approach descriptions",
        },
    },
    # --- FOOD & HOSPITALITY ---
    {
        "name": "Restaurant & Fine Dining",
        "description": "Warm, inviting restaurant website with menu highlights, reservations, and ambiance",
        "category_industry": "restaurant",
        "category_type": "homepage",
        "ref_base": "biscayne",
        "ref_mix": "bensimon",
        "color": "#C8952E",
        "content": {
            "business_name": "{{company_name}}",
            "tagline": "An Unforgettable Dining Experience",
            "services": "Prix Fixe Menu, Private Dining, Wine Pairings, Chef's Table, Catering, Events",
            "testimonials": "3 guest testimonials about dining experience",
            "faq": "Do you take reservations? | Do you accommodate dietary restrictions? | Is there parking?",
            "cta": "Reserve Your Table",
            "team": "Head Chef bio and sommelier profile",
        },
    },
    {
        "name": "Cafe & Coffee Shop",
        "description": "Clean, minimal coffee shop website with menu, story, and locations",
        "category_industry": "restaurant",
        "category_type": "homepage",
        "ref_base": "parkdale",
        "ref_mix": "maydental",
        "color": "#92400e",
        "content": {
            "business_name": "{{company_name}}",
            "tagline": "Artisan Coffee. Made With Love.",
            "services": "Espresso Drinks, Pour Overs, Pastries, Breakfast, Lunch Bowls, Smoothies",
            "testimonials": "3 customer testimonials about favorite drinks",
            "faq": "Do you have oat milk? | Do you serve food? | Can I work from your cafe?",
            "cta": "Visit Us Today",
            "team": "Our Story — sourcing and roasting journey",
        },
    },
    {
        "name": "Catering & Event Food",
        "description": "Elegant catering company website with menus, gallery, and quote request",
        "category_industry": "restaurant",
        "category_type": "homepage",
        "ref_base": "bensimon",
        "ref_mix": "biscayne",
        "color": "#1e3a5f",
        "content": {
            "business_name": "{{company_name}}",
            "tagline": "Exceptional Catering for Exceptional Events",
            "services": "Wedding Catering, Corporate Events, Private Parties, Holiday Meals, Cocktail Receptions, Brunch",
            "testimonials": "3 client testimonials about events",
            "faq": "How far in advance should I book? | What's your minimum guest count? | Do you handle dietary restrictions?",
            "cta": "Get a Free Quote",
            "team": "Executive chef and event coordinator profiles",
        },
    },
    {
        "name": "Bar & Lounge",
        "description": "Dark, moody bar and lounge website with cocktail menu and events",
        "category_industry": "restaurant",
        "category_type": "homepage",
        "ref_base": "ocidm",
        "ref_mix": "bensimon",
        "color": "#d97706",
        "content": {
            "business_name": "{{company_name}}",
            "tagline": "Craft Cocktails. Live Music. Unforgettable Nights.",
            "services": "Signature Cocktails, Craft Beer, Wine, VIP Bottle Service, Private Events, Live Music",
            "testimonials": "3 patron testimonials about atmosphere",
            "faq": "Do you have a dress code? | Can I book for private events? | Do you serve food?",
            "cta": "Reserve a Table",
            "team": "Head mixologist and weekly events schedule",
        },
    },
    # --- PROFESSIONAL SERVICES ---
    {
        "name": "Law Firm",
        "description": "Authoritative law firm website with practice areas, attorney profiles, and consultations",
        "category_industry": "professional",
        "category_type": "homepage",
        "ref_base": "parkdale",
        "ref_mix": "biscayne",
        "color": "#1e3a5f",
        "content": {
            "business_name": "{{company_name}}",
            "tagline": "Trusted Legal Counsel. Proven Results.",
            "services": "Personal Injury, Criminal Defense, Family Law, Estate Planning, Business Law, Immigration",
            "testimonials": "3 client testimonials about case results",
            "faq": "How much does a consultation cost? | What is your success rate? | How long will my case take?",
            "cta": "Free Consultation",
            "team": "4 attorneys with credentials and headshots",
        },
    },
    {
        "name": "Accounting & CPA Firm",
        "description": "Professional accounting firm website with services, team, and client portal",
        "category_industry": "professional",
        "category_type": "homepage",
        "ref_base": "biscayne",
        "ref_mix": "parkdale",
        "color": "#2563eb",
        "content": {
            "business_name": "{{company_name}}",
            "tagline": "Strategic Financial Solutions for Growing Businesses",
            "services": "Tax Preparation, Bookkeeping, Payroll, Business Advisory, Audit & Assurance, CFO Services",
            "testimonials": "3 client testimonials with business results",
            "faq": "When is tax season? | Do you work with small businesses? | What documents do I need?",
            "cta": "Schedule a Free Consultation",
            "team": "Lead CPA and senior accountant profiles",
        },
    },
    {
        "name": "Consulting Agency",
        "description": "Bold consulting agency website with framework methodology and case studies",
        "category_industry": "professional",
        "category_type": "homepage",
        "ref_base": "ocidm",
        "ref_mix": "bensimon",
        "color": "#7c3aed",
        "content": {
            "business_name": "{{company_name}}",
            "tagline": "Transform Your Business. Accelerate Growth.",
            "services": "Digital Transformation, Growth Strategy, Operations, Change Management, Data Analytics, M&A Advisory",
            "testimonials": "3 client testimonials with metrics (e.g. 200% revenue growth)",
            "faq": "What industries do you serve? | How long is a typical engagement? | What's your pricing model?",
            "cta": "Book a Strategy Call",
            "team": "Managing partners and methodology framework (Discover, Strategy, Execute, Scale)",
        },
    },
    {
        "name": "Insurance & Financial Advisor",
        "description": "Trustworthy financial advisory website with services and client resources",
        "category_industry": "professional",
        "category_type": "homepage",
        "ref_base": "parkdale",
        "ref_mix": "biscayne",
        "color": "#16a34a",
        "content": {
            "business_name": "{{company_name}}",
            "tagline": "Protecting Your Family. Securing Your Future.",
            "services": "Life Insurance, Retirement Planning, Wealth Management, Estate Planning, Business Insurance, Tax Strategy",
            "testimonials": "3 client testimonials about peace of mind",
            "faq": "How much life insurance do I need? | When should I start saving for retirement? | Are consultations free?",
            "cta": "Get Your Free Plan",
            "team": "Lead advisor profile with credentials",
        },
    },
    {
        "name": "Marketing & Digital Agency",
        "description": "Dark luxury marketing agency website with portfolio and capabilities",
        "category_industry": "agency",
        "category_type": "homepage",
        "ref_base": "ocidm",
        "ref_mix": "bensimon",
        "color": "#f97316",
        "content": {
            "business_name": "{{company_name}}",
            "tagline": "We Build Brands That Dominate Markets",
            "services": "SEO, PPC, Social Media, Content Marketing, Web Design, Brand Strategy",
            "testimonials": "3 client testimonials with results metrics (300% ROI, 5x traffic)",
            "faq": "What's your minimum retainer? | How do you measure results? | Do you work with startups?",
            "cta": "Start Your Growth",
            "team": "Creative director and strategist profiles, plus case study cards",
        },
    },
    # --- REAL ESTATE & HOME ---
    {
        "name": "Real Estate Agent",
        "description": "Premium real estate agent website with listings, search, and agent profile",
        "category_industry": "real-estate",
        "category_type": "homepage",
        "ref_base": "biscayne",
        "ref_mix": "parkdale",
        "color": "#1e3a5f",
        "content": {
            "business_name": "{{company_name}}",
            "tagline": "Find Your Dream Home With a Trusted Expert",
            "services": "Buying, Selling, Investment Properties, Relocation, Commercial, First-Time Buyers",
            "testimonials": "3 client testimonials about home buying experience",
            "faq": "How do I get pre-approved? | What are closing costs? | How long does it take to buy a home?",
            "cta": "Search Listings",
            "team": "Lead agent profile with credentials and areas served",
        },
    },
    {
        "name": "Home Renovation & Contractor",
        "description": "Contractor website with services, project gallery, and free estimate",
        "category_industry": "real-estate",
        "category_type": "homepage",
        "ref_base": "maydental",
        "ref_mix": "parkdale",
        "color": "#ea580c",
        "content": {
            "business_name": "{{company_name}}",
            "tagline": "Quality Craftsmanship. On Time. On Budget.",
            "services": "Kitchen Remodeling, Bathroom Renovation, Additions, Roofing, Flooring, Painting",
            "testimonials": "3 client testimonials about project results",
            "faq": "How long does a renovation take? | Do you provide free estimates? | Are you licensed and insured?",
            "cta": "Get a Free Estimate",
            "team": "Before/after project gallery and team credentials",
        },
    },
    {
        "name": "Interior Design Studio",
        "description": "Elegant interior design website with portfolio, process, and consultation booking",
        "category_industry": "real-estate",
        "category_type": "homepage",
        "ref_base": "bensimon",
        "ref_mix": "biscayne",
        "color": "#a16207",
        "content": {
            "business_name": "{{company_name}}",
            "tagline": "Spaces That Inspire. Designs That Endure.",
            "services": "Residential, Commercial, Staging, Color Consultation, Space Planning, Custom Furniture",
            "testimonials": "3 client testimonials about design transformations",
            "faq": "What's your design process? | How much does interior design cost? | Do you work remotely?",
            "cta": "Book a Consultation",
            "team": "Lead designer portfolio and Our Process (4 steps)",
        },
    },
    # --- FITNESS & LIFESTYLE ---
    {
        "name": "Gym & Fitness Studio",
        "description": "High-energy gym website with classes, memberships, and trainer profiles",
        "category_industry": "fitness",
        "category_type": "homepage",
        "ref_base": "ocidm",
        "ref_mix": "bensimon",
        "color": "#dc2626",
        "content": {
            "business_name": "{{company_name}}",
            "tagline": "Push Your Limits. Transform Your Body.",
            "services": "HIIT, CrossFit, Yoga, Spin, Boxing, Strength Training",
            "testimonials": "3 member transformation testimonials",
            "faq": "Can I cancel anytime? | Do you offer trial passes? | What should I bring?",
            "cta": "Start Your Free Trial",
            "team": "3 trainer profiles with specialties and certifications, membership tiers (Basic $29/mo, Premium $59/mo, Elite $99/mo)",
        },
    },
    {
        "name": "Yoga & Pilates Studio",
        "description": "Calm, minimal yoga studio website with class schedule and instructor profiles",
        "category_industry": "fitness",
        "category_type": "homepage",
        "ref_base": "parkdale",
        "ref_mix": "biscayne",
        "color": "#65a30d",
        "content": {
            "business_name": "{{company_name}}",
            "tagline": "Find Your Balance. Find Your Peace.",
            "services": "Vinyasa Flow, Yin Yoga, Hot Yoga, Pilates Mat, Aerial Yoga, Meditation",
            "testimonials": "3 student testimonials about mindfulness journey",
            "faq": "Do I need experience? | What should I wear? | Can I drop in?",
            "cta": "View Class Schedule",
            "team": "3 instructor profiles with certifications, pricing (Drop-in $20, 10-Class $150, Unlimited $120/mo)",
        },
    },
    {
        "name": "Personal Trainer",
        "description": "Bold personal trainer website with programs, transformations, and booking",
        "category_industry": "fitness",
        "category_type": "homepage",
        "ref_base": "bensimon",
        "ref_mix": "ocidm",
        "color": "#2563eb",
        "content": {
            "business_name": "{{company_name}}",
            "tagline": "Your Goals. My Expertise. Real Results.",
            "services": "1-on-1 Training, Online Coaching, Nutrition Plans, Group Sessions, Competition Prep, Recovery",
            "testimonials": "3 client testimonials with transformation results (lost 30lbs, etc.)",
            "faq": "How often should I train? | Do you offer online coaching? | What's included in my package?",
            "cta": "Book Your First Session Free",
            "team": "Trainer bio with credentials, transformation gallery",
        },
    },
    # --- EDUCATION & CREATIVE ---
    {
        "name": "Online Course & Coaching",
        "description": "Course creator website with curriculum, pricing, and enrollment",
        "category_industry": "education",
        "category_type": "landing",
        "ref_base": "ocidm",
        "ref_mix": "biscayne",
        "color": "#7c3aed",
        "content": {
            "business_name": "{{company_name}}",
            "tagline": "Master New Skills. Transform Your Career.",
            "services": "Video Lessons, Live Q&A, Community Access, Downloadable Resources, Certificate, Mentorship",
            "testimonials": "3 student testimonials with career outcomes",
            "faq": "How long is the course? | Is there a refund policy? | Do I get lifetime access?",
            "cta": "Enroll Now — Limited Spots",
            "team": "Instructor bio with credentials, curriculum breakdown, pricing tiers (Self-Paced $297, Guided $597, VIP $997)",
        },
    },
    {
        "name": "Photography & Videography",
        "description": "Visual portfolio website for photographers and videographers",
        "category_industry": "creative",
        "category_type": "portfolio",
        "ref_base": "bensimon",
        "ref_mix": "biscayne",
        "color": "#111111",
        "content": {
            "business_name": "{{company_name}}",
            "tagline": "Capturing Moments That Last Forever",
            "services": "Wedding Photography, Portrait Sessions, Commercial, Video Production, Drone, Editing",
            "testimonials": "3 client testimonials about photos/videos",
            "faq": "How do I book? | How long until I get my photos? | Do you travel?",
            "cta": "Book Your Session",
            "team": "Photographer bio with portfolio gallery grid",
        },
    },
    {
        "name": "Freelancer & Portfolio",
        "description": "Minimal personal portfolio for freelancers and designers",
        "category_industry": "creative",
        "category_type": "portfolio",
        "ref_base": "parkdale",
        "ref_mix": "maydental",
        "color": "#111111",
        "content": {
            "business_name": "{{company_name}}",
            "tagline": "Creative Design. Strategic Thinking.",
            "services": "Brand Identity, UI/UX Design, Web Development, Print Design, Motion Graphics, Illustration",
            "testimonials": "3 client testimonials about projects",
            "faq": "What's your rate? | How long does a project take? | Do you offer revisions?",
            "cta": "Let's Work Together",
            "team": "About Me section with skills/tools, selected projects grid",
        },
    },
    # --- TECH & SAAS ---
    {
        "name": "SaaS Product",
        "description": "Modern SaaS landing page with features, pricing toggle, and social proof",
        "category_industry": "saas",
        "category_type": "landing",
        "ref_base": "ocidm",
        "ref_mix": "bensimon",
        "color": "#6366f1",
        "content": {
            "business_name": "{{company_name}}",
            "tagline": "The Platform That Scales With You",
            "services": "Analytics Dashboard, Team Collaboration, API Integrations, Enterprise Security, Automation, Reports",
            "testimonials": "3 customer testimonials from companies",
            "faq": "Is there a free trial? | Can I cancel anytime? | Do you offer enterprise plans?",
            "cta": "Start Free Trial",
            "team": "Product features grid, pricing tiers (Starter $19/mo, Pro $49/mo, Enterprise Custom), social proof logos",
        },
    },
    {
        "name": "Mobile App Landing",
        "description": "App store-ready landing page with phone mockup hero and feature showcase",
        "category_industry": "saas",
        "category_type": "landing",
        "ref_base": "maydental",
        "ref_mix": "ocidm",
        "color": "#7c3aed",
        "content": {
            "business_name": "{{company_name}}",
            "tagline": "Your Life, Simplified. Download Today.",
            "services": "Smart Notifications, Offline Mode, Cloud Sync, Custom Themes, Social Sharing, Analytics",
            "testimonials": "3 user testimonials with star ratings",
            "faq": "Is the app free? | Which platforms are supported? | Is my data secure?",
            "cta": "Download on App Store & Google Play",
            "team": "Feature showcase, How It Works (3 steps), stats (100K+ Downloads, 4.9 Stars)",
        },
    },
    {
        "name": "AI & Tech Startup",
        "description": "Futuristic AI/tech startup website with animated elements and gradient design",
        "category_industry": "saas",
        "category_type": "landing",
        "ref_base": "ocidm",
        "ref_mix": "bensimon",
        "color": "#8b5cf6",
        "content": {
            "business_name": "{{company_name}}",
            "tagline": "Intelligence That Drives Results",
            "services": "Natural Language Processing, Predictive Analytics, Computer Vision, Process Automation, API Platform, Custom Models",
            "testimonials": "3 enterprise testimonials with results",
            "faq": "How does your AI work? | Is my data secure? | What's the pricing model?",
            "cta": "Request a Demo",
            "team": "How Our AI Works (4 steps), use cases, API pricing tiers",
        },
    },
    # --- RETAIL & ECOMMERCE ---
    {
        "name": "Boutique & Fashion",
        "description": "Elegant fashion boutique website with collection showcase and shopping",
        "category_industry": "ecommerce",
        "category_type": "homepage",
        "ref_base": "biscayne",
        "ref_mix": "bensimon",
        "color": "#d4a853",
        "content": {
            "business_name": "{{company_name}}",
            "tagline": "Curated Fashion. Timeless Style.",
            "services": "New Arrivals, Women's Collection, Men's Collection, Accessories, Sale, Gift Cards",
            "testimonials": "3 customer reviews about quality and style",
            "faq": "What's your return policy? | Do you ship internationally? | How do I track my order?",
            "cta": "Shop New Collection",
            "team": "About Our Brand story, newsletter signup, categories showcase",
        },
    },
    {
        "name": "Salon & Barbershop",
        "description": "Stylish salon website with services, team, booking, and gallery",
        "category_industry": "beauty",
        "category_type": "homepage",
        "ref_base": "maydental",
        "ref_mix": "biscayne",
        "color": "#e11d48",
        "content": {
            "business_name": "{{company_name}}",
            "tagline": "Where Style Meets Artistry",
            "services": "Haircut $45, Color $120, Highlights $180, Blowout $55, Beard Trim $25, Facial $80",
            "testimonials": "3 client testimonials about their stylist",
            "faq": "Do I need an appointment? | What products do you use? | Do you offer bridal services?",
            "cta": "Book Your Appointment",
            "team": "4 stylist profiles with photos and specialties, gallery of work",
        },
    },
    # --- LOCAL SERVICES ---
    {
        "name": "Auto Repair & Mechanic",
        "description": "Trustworthy auto repair website with services, pricing, and reviews",
        "category_industry": "local-services",
        "category_type": "homepage",
        "ref_base": "parkdale",
        "ref_mix": "maydental",
        "color": "#dc2626",
        "content": {
            "business_name": "{{company_name}}",
            "tagline": "Honest Auto Repair. Fair Prices. Guaranteed.",
            "services": "Oil Change, Brake Service, Engine Repair, Transmission, Tires, Diagnostics",
            "testimonials": "3 customer testimonials about honest service",
            "faq": "Do you offer free estimates? | How long does an oil change take? | Do you work on all makes?",
            "cta": "Schedule Service",
            "team": "ASE Certified mechanics, transparent pricing section, warranty info",
        },
    },
    {
        "name": "Cleaning Service",
        "description": "Friendly cleaning service website with packages, booking, and trust signals",
        "category_industry": "local-services",
        "category_type": "homepage",
        "ref_base": "biscayne",
        "ref_mix": "parkdale",
        "color": "#0ea5e9",
        "content": {
            "business_name": "{{company_name}}",
            "tagline": "Spotless Homes. Happy Families.",
            "services": "Standard Clean $120, Deep Clean $200, Move In/Out $300, Office Cleaning Custom, Carpet Cleaning, Window Washing",
            "testimonials": "3 customer testimonials about cleanliness",
            "faq": "What products do you use? | Do I need to be home? | How do I pay?",
            "cta": "Get an Instant Quote",
            "team": "Trust signals (Insured, Background Checked, Eco-Friendly), How It Works (Book, We Clean, You Relax)",
        },
    },
]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

REQUIRED_CHECKS = [
    ("tailwindcss.com", "Tailwind CSS CDN"),
    ("<section", "Section tags"),
    ("</html>", "Closing HTML tag"),
]

QUALITY_CHECKS = [
    ("IntersectionObserver", "Scroll reveal animations"),
    ("@keyframes", "CSS animations"),
    ("hover:", "Hover effects"),
    ("images.unsplash.com", "Unsplash images"),
]


def validate_template(html: str, name: str) -> tuple[bool, list[str]]:
    """Validate generated HTML meets quality requirements.

    Returns (is_valid, list_of_issues).
    """
    issues = []
    line_count = html.count("\n") + 1

    if line_count < 300:
        issues.append(f"Only {line_count} lines (need 300+)")

    if len(html) < 10000:
        issues.append(f"Only {len(html)} chars (need 10000+)")

    for check, label in REQUIRED_CHECKS:
        if check.lower() not in html.lower():
            issues.append(f"Missing: {label}")

    # Quality checks — warn but don't fail
    quality_score = 0
    for check, label in QUALITY_CHECKS:
        if check.lower() in html.lower():
            quality_score += 1

    if quality_score < 2:
        issues.append(f"Low quality score ({quality_score}/4): missing animations/effects")

    return len(issues) == 0, issues


# ---------------------------------------------------------------------------
# Core generation — COPY reference + swap content
# ---------------------------------------------------------------------------

async def generate_single_template(
    template_def: dict,
    gemini_key: str,
    max_retries: int = 2,
) -> dict | None:
    """Generate a single template by COPYING reference HTML and swapping content only.

    The reference code is sent verbatim. Gemini only changes text content, colors,
    and images — never the structure, animations, or JavaScript.
    """
    import httpx
    from app.pages.references import (
        load_screenshot_base64,
        get_screenshot_mime,
        load_reference_code,
    )

    ref_base = template_def["ref_base"]
    ref_mix = template_def["ref_mix"]
    content = template_def["content"]
    color = template_def["color"]

    # Load the FULL base reference code
    base_code = load_reference_code(ref_base) or ""
    if not base_code:
        logger.error("No reference code for %s", ref_base)
        return None

    # Load mix reference for section inspiration
    mix_code = load_reference_code(ref_mix) or ""

    # Build multimodal parts — send screenshot of base reference
    parts: list[dict] = []
    b64 = load_screenshot_base64(ref_base)
    if b64:
        mime = get_screenshot_mime(ref_base)
        parts.append({"inlineData": {"mimeType": mime, "data": b64}})

    # Build the COPY-AND-SWAP prompt
    content_block = "\n".join(f"  - {k}: {v}" for k, v in content.items())

    prompt_text = (
        "You are a COPY-PASTE web developer. Your job is EXTREMELY simple:\n\n"
        "STEP 1: Take the EXACT HTML code below (the BASE REFERENCE).\n"
        "STEP 2: Replace ONLY the text content (business name, headlines, services, "
        "testimonials, FAQ questions/answers, team member names, descriptions).\n"
        "STEP 3: Replace the primary color throughout.\n"
        "STEP 4: Replace image URLs with relevant Unsplash images for this industry.\n"
        "STEP 5: Return the modified code.\n\n"
        "CRITICAL RULES:\n"
        "- DO NOT remove ANY HTML structure, CSS, or JavaScript\n"
        "- DO NOT remove ANY animations, hover effects, or IntersectionObserver code\n"
        "- DO NOT remove ANY glassmorphism, backdrop-blur, or shadow effects\n"
        "- DO NOT simplify or shorten the code\n"
        "- DO NOT rewrite from scratch — you are EDITING, not creating\n"
        "- KEEP every @keyframes animation, every transition, every transform\n"
        "- KEEP the dark mode toggle if present\n"
        "- KEEP the mobile hamburger menu\n"
        "- KEEP all Lucide icon references\n"
        "- KEEP all scroll reveal JavaScript\n"
        "- The output MUST be roughly the same length as the input (within 20%)\n"
        "- Use {{company_name}} as the business name placeholder\n\n"
        "PRIMARY COLOR TO USE: " + color + "\n\n"
        "NEW CONTENT TO INSERT:\n" + content_block + "\n\n"
        "Replace all Unsplash image URLs with NEW relevant ones for this industry. "
        "Use different photo IDs — don't reuse the dental/medical photos.\n\n"
    )

    # Add section mixing instruction
    if mix_code:
        # Extract a section from the mix reference to blend in
        prompt_text += (
            "BONUS — SECTION MIXING:\n"
            "Look at this SECOND reference code below. Pick 1-2 interesting sections "
            "(like testimonials layout, pricing cards, or FAQ style) and use that STYLE "
            "for those sections in the output. Keep the base structure for everything else.\n\n"
            "SECOND REFERENCE (for section style inspiration ONLY):\n"
            "```html\n" + (mix_code[:15000] if len(mix_code) > 15000 else mix_code) + "\n```\n\n"
        )

    prompt_text += (
        "BASE REFERENCE CODE — COPY THIS AND ONLY CHANGE CONTENT:\n\n"
        "```html\n" + base_code + "\n```\n\n"
        "Return ONLY valid JSON:\n"
        '{"response": "Brief description", '
        '"html_content": "The complete modified HTML from <!DOCTYPE html> to </html>"}\n\n'
        "REMEMBER: The output html_content must be the FULL code with ALL original CSS, "
        "JS, animations, and structure. Only the TEXT CONTENT, COLORS, and IMAGE URLs change."
    )

    parts.append({"text": prompt_text})

    for attempt in range(max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=180) as client:
                resp = await client.post(
                    "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
                    "?key=" + gemini_key,
                    json={
                        "contents": [{"parts": parts}],
                        "generationConfig": {
                            "temperature": 0.3,  # LOW temp — we want faithful copying
                            "maxOutputTokens": 65536,
                            "responseMimeType": "application/json",
                        },
                    },
                )
                resp.raise_for_status()
                data = resp.json()

                # Check for empty/blocked response
                candidates = data.get("candidates", [])
                if not candidates:
                    logger.error("No candidates in Gemini response for %s", template_def["name"])
                    if attempt < max_retries:
                        await asyncio.sleep(5)
                        continue
                    return None

                text = candidates[0]["content"]["parts"][0]["text"]

            # Parse JSON response
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                # Try to find JSON in text
                match = re.search(r'\{[\s\S]*"html_content"[\s\S]*\}', text)
                if match:
                    try:
                        parsed = json.loads(match.group())
                    except json.JSONDecodeError:
                        logger.error("Failed to parse extracted JSON for %s", template_def["name"])
                        if attempt < max_retries:
                            await asyncio.sleep(5)
                            continue
                        return None
                else:
                    logger.error("No JSON found in Gemini response for %s", template_def["name"])
                    if attempt < max_retries:
                        await asyncio.sleep(5)
                        continue
                    return None

            html_content = parsed.get("html_content", "")
            if not html_content:
                logger.error("Empty html_content for %s", template_def["name"])
                if attempt < max_retries:
                    await asyncio.sleep(5)
                    continue
                return None

            # Validate
            is_valid, issues = validate_template(html_content, template_def["name"])
            if not is_valid:
                logger.warning(
                    "Validation failed for %s (attempt %d): %s",
                    template_def["name"], attempt + 1, "; ".join(issues),
                )
                if attempt < max_retries:
                    await asyncio.sleep(5)
                    continue
                # On last attempt, use it anyway if it has basic structure
                if "</html>" in html_content.lower() and len(html_content) > 5000:
                    logger.warning("Using imperfect template for %s despite issues", template_def["name"])
                else:
                    return None

            return {
                "name": template_def["name"],
                "description": template_def["description"],
                "category_industry": template_def["category_industry"],
                "category_type": template_def["category_type"],
                "html_content": html_content,
                "css_content": "",
            }

        except Exception as e:
            logger.error(
                "Gemini call failed for %s (attempt %d): %s",
                template_def["name"], attempt + 1, e,
            )
            if attempt < max_retries:
                await asyncio.sleep(5)
                continue
            return None

    return None


# ---------------------------------------------------------------------------
# Batch generation
# ---------------------------------------------------------------------------

async def generate_all_templates(
    db,
    gemini_key: str,
    replace_existing: bool = False,
) -> dict:
    """Generate all 30 premium templates and store in database.

    Returns: {"generated": int, "failed": int, "skipped": int}
    """
    from sqlalchemy import select
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
            "[%d/%d] Generating '%s' (base=%s, mix=%s)...",
            i + 1, len(TEMPLATE_DEFS), tdef["name"], tdef["ref_base"], tdef["ref_mix"],
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
                    await db.flush()

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

            line_count = result_data["html_content"].count("\n") + 1
            stats["generated"] += 1
            logger.info(
                "[%d/%d] Generated '%s' — %d lines, %d chars",
                i + 1, len(TEMPLATE_DEFS), tdef["name"],
                line_count, len(result_data["html_content"]),
            )
        else:
            stats["failed"] += 1
            logger.warning(
                "[%d/%d] FAILED to generate '%s'",
                i + 1, len(TEMPLATE_DEFS), tdef["name"],
            )

        # Rate limiting — 4 second delay between calls
        if i < len(TEMPLATE_DEFS) - 1:
            await asyncio.sleep(4)

    logger.info(
        "Template generation complete: %d generated, %d failed, %d skipped out of %d total",
        stats["generated"], stats["failed"], stats["skipped"], stats["total"],
    )
    return stats
