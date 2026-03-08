"""Seed starter platform templates for the page builder."""

import uuid

STARTER_TEMPLATES = [
    {
        "name": "Modern Agency",
        "description": "Bold, minimal landing page for creative and digital agencies",
        "category_industry": "agency",
        "category_type": "landing",
        "html_content": """<nav style="display:flex;align-items:center;justify-content:space-between;padding:1.5rem 2rem;max-width:1200px;margin:0 auto">
  <div style="font-weight:700;font-size:1.5rem;color:#111">{{company_name}}</div>
  <div style="display:flex;gap:2rem;align-items:center">
    <a href="#work" style="text-decoration:none;color:#555;font-size:0.9rem">Work</a>
    <a href="#services" style="text-decoration:none;color:#555;font-size:0.9rem">Services</a>
    <a href="#contact" style="text-decoration:none;color:#555;font-size:0.9rem">Contact</a>
    <a href="#contact" style="background:#111;color:#fff;padding:0.6rem 1.5rem;border-radius:8px;text-decoration:none;font-size:0.9rem">Get Started</a>
  </div>
</nav>
<section style="max-width:1200px;margin:0 auto;padding:6rem 2rem;text-align:center">
  <h1 style="font-size:4rem;font-weight:800;line-height:1.1;color:#111;max-width:800px;margin:0 auto">We build brands that break through the noise</h1>
  <p style="font-size:1.2rem;color:#666;margin-top:1.5rem;max-width:600px;margin-left:auto;margin-right:auto">Strategy, design, and technology — everything your brand needs to stand out in a crowded market.</p>
  <div style="display:flex;gap:1rem;justify-content:center;margin-top:2.5rem">
    <a href="#work" style="background:#111;color:#fff;padding:0.8rem 2rem;border-radius:8px;text-decoration:none;font-weight:600">View Our Work</a>
    <a href="#contact" style="border:2px solid #111;color:#111;padding:0.8rem 2rem;border-radius:8px;text-decoration:none;font-weight:600">Let's Talk</a>
  </div>
</section>
<section id="services" style="background:#f8f8f8;padding:5rem 2rem">
  <div style="max-width:1200px;margin:0 auto">
    <h2 style="font-size:2.5rem;font-weight:700;text-align:center;color:#111">What We Do</h2>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:2rem;margin-top:3rem">
      <div style="background:#fff;padding:2rem;border-radius:12px"><h3 style="font-size:1.3rem;font-weight:600;color:#111">Brand Strategy</h3><p style="color:#666;margin-top:0.8rem;line-height:1.6">Define your positioning, messaging, and visual identity to create lasting impressions.</p></div>
      <div style="background:#fff;padding:2rem;border-radius:12px"><h3 style="font-size:1.3rem;font-weight:600;color:#111">Web Design</h3><p style="color:#666;margin-top:0.8rem;line-height:1.6">Beautiful, responsive websites that convert visitors into customers.</p></div>
      <div style="background:#fff;padding:2rem;border-radius:12px"><h3 style="font-size:1.3rem;font-weight:600;color:#111">Digital Marketing</h3><p style="color:#666;margin-top:0.8rem;line-height:1.6">Data-driven campaigns that grow your audience and drive measurable results.</p></div>
    </div>
  </div>
</section>
<section style="padding:5rem 2rem;text-align:center;background:#111;color:#fff">
  <h2 style="font-size:2.5rem;font-weight:700">Ready to get started?</h2>
  <p style="color:#aaa;margin-top:1rem;font-size:1.1rem">Let's build something great together.</p>
  <a href="#contact" style="display:inline-block;margin-top:2rem;background:#fff;color:#111;padding:0.8rem 2.5rem;border-radius:8px;text-decoration:none;font-weight:600">Contact Us</a>
</section>""",
        "css_content": """* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'Inter', system-ui, sans-serif; color: #111; }
@media (max-width: 768px) {
  nav > div:last-child { display: none; }
  h1 { font-size: 2.5rem !important; }
  [style*="grid-template-columns"] { grid-template-columns: 1fr !important; }
}""",
    },
    {
        "name": "SaaS Startup",
        "description": "Clean, conversion-focused landing page for SaaS products",
        "category_industry": "saas",
        "category_type": "landing",
        "html_content": """<nav style="display:flex;align-items:center;justify-content:space-between;padding:1rem 2rem;max-width:1200px;margin:0 auto">
  <div style="font-weight:700;font-size:1.3rem;color:#0f172a">{{company_name}}</div>
  <div style="display:flex;gap:1.5rem;align-items:center">
    <a href="#features" style="text-decoration:none;color:#64748b;font-size:0.9rem">Features</a>
    <a href="#pricing" style="text-decoration:none;color:#64748b;font-size:0.9rem">Pricing</a>
    <a href="#" style="background:#2563eb;color:#fff;padding:0.5rem 1.2rem;border-radius:6px;text-decoration:none;font-size:0.9rem;font-weight:500">Start Free Trial</a>
  </div>
</nav>
<section style="max-width:1200px;margin:0 auto;padding:5rem 2rem;text-align:center">
  <span style="background:#eff6ff;color:#2563eb;padding:0.4rem 1rem;border-radius:20px;font-size:0.85rem;font-weight:500">Now in Beta — Try it free</span>
  <h1 style="font-size:3.5rem;font-weight:800;line-height:1.1;color:#0f172a;margin-top:1.5rem;max-width:700px;margin-left:auto;margin-right:auto">The smarter way to manage your workflow</h1>
  <p style="font-size:1.15rem;color:#64748b;margin-top:1.5rem;max-width:550px;margin-left:auto;margin-right:auto">Automate repetitive tasks, collaborate seamlessly, and ship faster with our all-in-one platform.</p>
  <div style="display:flex;gap:1rem;justify-content:center;margin-top:2rem">
    <a href="#" style="background:#2563eb;color:#fff;padding:0.75rem 2rem;border-radius:8px;text-decoration:none;font-weight:600">Get Started Free</a>
    <a href="#" style="border:1px solid #e2e8f0;color:#0f172a;padding:0.75rem 2rem;border-radius:8px;text-decoration:none;font-weight:500">Watch Demo</a>
  </div>
  <p style="font-size:0.8rem;color:#94a3b8;margin-top:1rem">No credit card required</p>
</section>
<section id="features" style="background:#f8fafc;padding:5rem 2rem">
  <div style="max-width:1200px;margin:0 auto">
    <h2 style="font-size:2rem;font-weight:700;text-align:center;color:#0f172a">Everything you need</h2>
    <p style="text-align:center;color:#64748b;margin-top:0.5rem">Powerful features to supercharge your productivity</p>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:1.5rem;margin-top:3rem">
      <div style="background:#fff;padding:1.5rem;border-radius:12px;border:1px solid #e2e8f0"><div style="width:40px;height:40px;background:#eff6ff;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:1.2rem">⚡</div><h3 style="font-size:1.1rem;font-weight:600;color:#0f172a;margin-top:1rem">Lightning Fast</h3><p style="color:#64748b;margin-top:0.5rem;font-size:0.9rem;line-height:1.6">Built for speed with real-time collaboration and instant sync across all devices.</p></div>
      <div style="background:#fff;padding:1.5rem;border-radius:12px;border:1px solid #e2e8f0"><div style="width:40px;height:40px;background:#f0fdf4;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:1.2rem">🔒</div><h3 style="font-size:1.1rem;font-weight:600;color:#0f172a;margin-top:1rem">Enterprise Security</h3><p style="color:#64748b;margin-top:0.5rem;font-size:0.9rem;line-height:1.6">SOC 2 compliant with end-to-end encryption and role-based access control.</p></div>
      <div style="background:#fff;padding:1.5rem;border-radius:12px;border:1px solid #e2e8f0"><div style="width:40px;height:40px;background:#fef3c7;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:1.2rem">📊</div><h3 style="font-size:1.1rem;font-weight:600;color:#0f172a;margin-top:1rem">Rich Analytics</h3><p style="color:#64748b;margin-top:0.5rem;font-size:0.9rem;line-height:1.6">Actionable insights with custom dashboards and automated reporting.</p></div>
    </div>
  </div>
</section>
<section id="pricing" style="padding:5rem 2rem">
  <div style="max-width:800px;margin:0 auto;text-align:center">
    <h2 style="font-size:2rem;font-weight:700;color:#0f172a">Simple, transparent pricing</h2>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:1.5rem;margin-top:3rem">
      <div style="border:1px solid #e2e8f0;border-radius:12px;padding:2rem;text-align:left"><h3 style="font-weight:600;color:#0f172a">Starter</h3><div style="font-size:2.5rem;font-weight:800;color:#0f172a;margin-top:0.5rem">$19<span style="font-size:1rem;font-weight:400;color:#64748b">/mo</span></div><p style="color:#64748b;font-size:0.9rem;margin-top:0.5rem">Perfect for small teams</p><a href="#" style="display:block;text-align:center;background:#f1f5f9;color:#0f172a;padding:0.6rem;border-radius:8px;text-decoration:none;font-weight:500;margin-top:1.5rem">Get Started</a></div>
      <div style="border:2px solid #2563eb;border-radius:12px;padding:2rem;text-align:left;position:relative"><span style="position:absolute;top:-10px;right:16px;background:#2563eb;color:#fff;padding:0.2rem 0.8rem;border-radius:12px;font-size:0.75rem;font-weight:500">Popular</span><h3 style="font-weight:600;color:#0f172a">Pro</h3><div style="font-size:2.5rem;font-weight:800;color:#0f172a;margin-top:0.5rem">$49<span style="font-size:1rem;font-weight:400;color:#64748b">/mo</span></div><p style="color:#64748b;font-size:0.9rem;margin-top:0.5rem">For growing businesses</p><a href="#" style="display:block;text-align:center;background:#2563eb;color:#fff;padding:0.6rem;border-radius:8px;text-decoration:none;font-weight:500;margin-top:1.5rem">Get Started</a></div>
    </div>
  </div>
</section>""",
        "css_content": """* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'Inter', system-ui, sans-serif; }
@media (max-width: 768px) {
  h1 { font-size: 2.2rem !important; }
  [style*="grid-template-columns"] { grid-template-columns: 1fr !important; }
  nav > div:last-child { display: none; }
}""",
    },
    {
        "name": "Restaurant & Café",
        "description": "Warm, inviting layout for restaurants, cafés and food businesses",
        "category_industry": "restaurant",
        "category_type": "homepage",
        "html_content": """<nav style="display:flex;align-items:center;justify-content:space-between;padding:1.5rem 2rem;max-width:1100px;margin:0 auto">
  <div style="font-weight:700;font-size:1.4rem;color:#1a1a1a;font-style:italic">{{company_name}}</div>
  <div style="display:flex;gap:2rem;align-items:center">
    <a href="#menu" style="text-decoration:none;color:#555;font-size:0.9rem">Menu</a>
    <a href="#about" style="text-decoration:none;color:#555;font-size:0.9rem">About</a>
    <a href="#reserve" style="background:#b45309;color:#fff;padding:0.5rem 1.2rem;border-radius:6px;text-decoration:none;font-size:0.9rem">Reserve a Table</a>
  </div>
</nav>
<section style="background:linear-gradient(135deg,#fef3c7,#fde68a);padding:5rem 2rem;text-align:center">
  <h1 style="font-size:3.5rem;font-weight:700;color:#1a1a1a;max-width:600px;margin:0 auto;line-height:1.2">A taste of something extraordinary</h1>
  <p style="color:#78350f;margin-top:1rem;font-size:1.1rem">Fresh ingredients, bold flavors, unforgettable experiences</p>
  <div style="display:flex;gap:1rem;justify-content:center;margin-top:2rem">
    <a href="#menu" style="background:#b45309;color:#fff;padding:0.75rem 2rem;border-radius:8px;text-decoration:none;font-weight:600">See the Menu</a>
    <a href="#reserve" style="border:2px solid #b45309;color:#b45309;padding:0.75rem 2rem;border-radius:8px;text-decoration:none;font-weight:600">Book Now</a>
  </div>
</section>
<section id="menu" style="padding:5rem 2rem;max-width:1100px;margin:0 auto">
  <h2 style="font-size:2rem;font-weight:700;text-align:center;color:#1a1a1a">Our Favorites</h2>
  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:2rem;margin-top:3rem">
    <div style="text-align:center"><div style="width:100%;aspect-ratio:1;background:#fef3c7;border-radius:16px;display:flex;align-items:center;justify-content:center;font-size:3rem">🍝</div><h3 style="margin-top:1rem;font-weight:600">Pasta Fresca</h3><p style="color:#666;font-size:0.9rem;margin-top:0.3rem">Handmade daily with seasonal ingredients — $18</p></div>
    <div style="text-align:center"><div style="width:100%;aspect-ratio:1;background:#fef3c7;border-radius:16px;display:flex;align-items:center;justify-content:center;font-size:3rem">🥩</div><h3 style="margin-top:1rem;font-weight:600">Grilled Ribeye</h3><p style="color:#666;font-size:0.9rem;margin-top:0.3rem">28-day dry-aged, herb butter — $34</p></div>
    <div style="text-align:center"><div style="width:100%;aspect-ratio:1;background:#fef3c7;border-radius:16px;display:flex;align-items:center;justify-content:center;font-size:3rem">🍰</div><h3 style="margin-top:1rem;font-weight:600">Tiramisu</h3><p style="color:#666;font-size:0.9rem;margin-top:0.3rem">Classic Italian, espresso-soaked — $12</p></div>
  </div>
</section>
<section id="reserve" style="background:#1a1a1a;color:#fff;padding:4rem 2rem;text-align:center">
  <h2 style="font-size:2rem;font-weight:700">Make a Reservation</h2>
  <p style="color:#aaa;margin-top:0.5rem">Open Tuesday–Sunday, 5pm–11pm</p>
  <a href="tel:+15551234567" style="display:inline-block;margin-top:1.5rem;background:#b45309;color:#fff;padding:0.75rem 2rem;border-radius:8px;text-decoration:none;font-weight:600">Call (555) 123-4567</a>
</section>""",
        "css_content": """* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'Georgia', serif; color: #1a1a1a; }
@media (max-width: 768px) {
  h1 { font-size: 2.2rem !important; }
  [style*="grid-template-columns"] { grid-template-columns: 1fr !important; }
  nav > div:last-child { display: none; }
}""",
    },
    {
        "name": "Real Estate",
        "description": "Professional listing page for real estate agents and agencies",
        "category_industry": "real-estate",
        "category_type": "landing",
        "html_content": """<nav style="display:flex;align-items:center;justify-content:space-between;padding:1rem 2rem;max-width:1200px;margin:0 auto">
  <div style="font-weight:700;font-size:1.3rem;color:#0f172a">{{company_name}}</div>
  <div style="display:flex;gap:1.5rem;align-items:center">
    <a href="#listings" style="text-decoration:none;color:#64748b;font-size:0.9rem">Listings</a>
    <a href="#about" style="text-decoration:none;color:#64748b;font-size:0.9rem">About</a>
    <a href="#contact" style="background:#0f766e;color:#fff;padding:0.5rem 1.2rem;border-radius:6px;text-decoration:none;font-size:0.9rem">Schedule Viewing</a>
  </div>
</nav>
<section style="background:linear-gradient(135deg,#f0fdfa,#ccfbf1);padding:5rem 2rem;text-align:center">
  <h1 style="font-size:3rem;font-weight:800;color:#0f172a;max-width:700px;margin:0 auto">Find your perfect home</h1>
  <p style="color:#475569;margin-top:1rem;font-size:1.1rem">Luxury properties, expert guidance, seamless experience</p>
  <a href="#listings" style="display:inline-block;margin-top:2rem;background:#0f766e;color:#fff;padding:0.75rem 2rem;border-radius:8px;text-decoration:none;font-weight:600">Browse Listings</a>
</section>
<section id="listings" style="padding:5rem 2rem;max-width:1200px;margin:0 auto">
  <h2 style="font-size:2rem;font-weight:700;color:#0f172a;text-align:center">Featured Properties</h2>
  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:1.5rem;margin-top:3rem">
    <div style="border:1px solid #e2e8f0;border-radius:12px;overflow:hidden"><div style="height:180px;background:linear-gradient(135deg,#d1fae5,#a7f3d0);display:flex;align-items:center;justify-content:center;font-size:2rem">🏡</div><div style="padding:1.5rem"><h3 style="font-weight:600;color:#0f172a">Modern Villa</h3><p style="color:#64748b;font-size:0.85rem;margin-top:0.3rem">4 bed · 3 bath · 2,800 sq ft</p><div style="font-size:1.5rem;font-weight:700;color:#0f766e;margin-top:0.8rem">$875,000</div></div></div>
    <div style="border:1px solid #e2e8f0;border-radius:12px;overflow:hidden"><div style="height:180px;background:linear-gradient(135deg,#dbeafe,#93c5fd);display:flex;align-items:center;justify-content:center;font-size:2rem">🏢</div><div style="padding:1.5rem"><h3 style="font-weight:600;color:#0f172a">Downtown Penthouse</h3><p style="color:#64748b;font-size:0.85rem;margin-top:0.3rem">3 bed · 2 bath · 1,900 sq ft</p><div style="font-size:1.5rem;font-weight:700;color:#0f766e;margin-top:0.8rem">$1,200,000</div></div></div>
    <div style="border:1px solid #e2e8f0;border-radius:12px;overflow:hidden"><div style="height:180px;background:linear-gradient(135deg,#fef3c7,#fde68a);display:flex;align-items:center;justify-content:center;font-size:2rem">🏠</div><div style="padding:1.5rem"><h3 style="font-weight:600;color:#0f172a">Family Cottage</h3><p style="color:#64748b;font-size:0.85rem;margin-top:0.3rem">5 bed · 4 bath · 3,200 sq ft</p><div style="font-size:1.5rem;font-weight:700;color:#0f766e;margin-top:0.8rem">$650,000</div></div></div>
  </div>
</section>
<section id="contact" style="background:#0f172a;color:#fff;padding:4rem 2rem;text-align:center">
  <h2 style="font-size:2rem;font-weight:700">Ready to find your dream home?</h2>
  <p style="color:#94a3b8;margin-top:0.5rem">Get in touch for a free consultation</p>
  <a href="#" style="display:inline-block;margin-top:1.5rem;background:#0f766e;color:#fff;padding:0.75rem 2rem;border-radius:8px;text-decoration:none;font-weight:600">Contact Us</a>
</section>""",
        "css_content": """* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'Inter', system-ui, sans-serif; }
@media (max-width: 768px) {
  h1 { font-size: 2rem !important; }
  [style*="grid-template-columns"] { grid-template-columns: 1fr !important; }
  nav > div:last-child { display: none; }
}""",
    },
    {
        "name": "Portfolio",
        "description": "Elegant portfolio page for designers, developers, and creatives",
        "category_industry": "portfolio",
        "category_type": "portfolio",
        "html_content": """<nav style="display:flex;align-items:center;justify-content:space-between;padding:1.5rem 2rem;max-width:1000px;margin:0 auto">
  <div style="font-weight:700;font-size:1.3rem;color:#111">{{company_name}}</div>
  <div style="display:flex;gap:1.5rem;align-items:center">
    <a href="#work" style="text-decoration:none;color:#888;font-size:0.9rem">Work</a>
    <a href="#about" style="text-decoration:none;color:#888;font-size:0.9rem">About</a>
    <a href="#contact" style="text-decoration:none;color:#888;font-size:0.9rem">Contact</a>
  </div>
</nav>
<section style="max-width:1000px;margin:0 auto;padding:5rem 2rem">
  <h1 style="font-size:3rem;font-weight:800;color:#111;line-height:1.2">Designer & Developer</h1>
  <p style="font-size:1.2rem;color:#666;margin-top:1rem;max-width:500px">I craft beautiful digital experiences that make an impact. Currently available for freelance work.</p>
</section>
<section id="work" style="max-width:1000px;margin:0 auto;padding:0 2rem 5rem">
  <h2 style="font-size:1.5rem;font-weight:700;color:#111;margin-bottom:2rem">Selected Work</h2>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:1.5rem">
    <div style="aspect-ratio:4/3;background:linear-gradient(135deg,#e0e7ff,#c7d2fe);border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:1.5rem;color:#4338ca;font-weight:600">Project Alpha</div>
    <div style="aspect-ratio:4/3;background:linear-gradient(135deg,#fce7f3,#fbcfe8);border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:1.5rem;color:#be185d;font-weight:600">Brand Redesign</div>
    <div style="aspect-ratio:4/3;background:linear-gradient(135deg,#d1fae5,#a7f3d0);border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:1.5rem;color:#047857;font-weight:600">Mobile App</div>
    <div style="aspect-ratio:4/3;background:linear-gradient(135deg,#fef3c7,#fde68a);border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:1.5rem;color:#92400e;font-weight:600">Dashboard UI</div>
  </div>
</section>
<section id="contact" style="background:#111;color:#fff;padding:4rem 2rem;text-align:center">
  <h2 style="font-size:2rem;font-weight:700">Let's work together</h2>
  <p style="color:#888;margin-top:0.5rem">Available for freelance projects</p>
  <a href="mailto:hello@example.com" style="display:inline-block;margin-top:1.5rem;background:#fff;color:#111;padding:0.75rem 2rem;border-radius:8px;text-decoration:none;font-weight:600">Say Hello</a>
</section>""",
        "css_content": """* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'Inter', system-ui, sans-serif; }
@media (max-width: 768px) {
  h1 { font-size: 2rem !important; }
  [style*="grid-template-columns"] { grid-template-columns: 1fr !important; }
}""",
    },
    {
        "name": "Event & Conference",
        "description": "Dynamic event page with speakers, schedule, and registration",
        "category_industry": "events",
        "category_type": "landing",
        "html_content": """<section style="background:linear-gradient(135deg,#1e1b4b,#312e81);color:#fff;padding:5rem 2rem;text-align:center">
  <span style="background:rgba(255,255,255,0.15);padding:0.4rem 1rem;border-radius:20px;font-size:0.85rem">March 15–17, 2026</span>
  <h1 style="font-size:3.5rem;font-weight:800;margin-top:1.5rem;max-width:700px;margin-left:auto;margin-right:auto;line-height:1.1">{{company_name}}</h1>
  <p style="color:#c4b5fd;margin-top:1rem;font-size:1.1rem;max-width:500px;margin-left:auto;margin-right:auto">The premier conference for innovators, builders, and visionaries</p>
  <div style="display:flex;gap:1rem;justify-content:center;margin-top:2rem">
    <a href="#register" style="background:#7c3aed;color:#fff;padding:0.75rem 2rem;border-radius:8px;text-decoration:none;font-weight:600">Register Now</a>
    <a href="#speakers" style="border:2px solid rgba(255,255,255,0.3);color:#fff;padding:0.75rem 2rem;border-radius:8px;text-decoration:none;font-weight:500">View Speakers</a>
  </div>
</section>
<section id="speakers" style="padding:5rem 2rem;max-width:1100px;margin:0 auto">
  <h2 style="font-size:2rem;font-weight:700;text-align:center;color:#111">Featured Speakers</h2>
  <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:1.5rem;margin-top:3rem">
    <div style="text-align:center"><div style="width:100px;height:100px;border-radius:50%;background:#e0e7ff;margin:0 auto;display:flex;align-items:center;justify-content:center;font-size:2rem">👩‍💻</div><h3 style="margin-top:1rem;font-weight:600;font-size:1rem">Sarah Chen</h3><p style="color:#666;font-size:0.8rem">CTO, TechCorp</p></div>
    <div style="text-align:center"><div style="width:100px;height:100px;border-radius:50%;background:#fce7f3;margin:0 auto;display:flex;align-items:center;justify-content:center;font-size:2rem">👨‍🔬</div><h3 style="margin-top:1rem;font-weight:600;font-size:1rem">James Rodriguez</h3><p style="color:#666;font-size:0.8rem">AI Researcher</p></div>
    <div style="text-align:center"><div style="width:100px;height:100px;border-radius:50%;background:#d1fae5;margin:0 auto;display:flex;align-items:center;justify-content:center;font-size:2rem">👩‍🎨</div><h3 style="margin-top:1rem;font-weight:600;font-size:1rem">Emily Park</h3><p style="color:#666;font-size:0.8rem">Design Lead, Studio</p></div>
    <div style="text-align:center"><div style="width:100px;height:100px;border-radius:50%;background:#fef3c7;margin:0 auto;display:flex;align-items:center;justify-content:center;font-size:2rem">👨‍💼</div><h3 style="margin-top:1rem;font-weight:600;font-size:1rem">Michael Lee</h3><p style="color:#666;font-size:0.8rem">Founder, StartupXYZ</p></div>
  </div>
</section>
<section id="register" style="background:#1e1b4b;color:#fff;padding:4rem 2rem;text-align:center">
  <h2 style="font-size:2rem;font-weight:700">Secure Your Spot</h2>
  <p style="color:#a5b4fc;margin-top:0.5rem">Early bird pricing ends soon — limited seats available</p>
  <a href="#" style="display:inline-block;margin-top:1.5rem;background:#7c3aed;color:#fff;padding:0.75rem 2.5rem;border-radius:8px;text-decoration:none;font-weight:600;font-size:1.1rem">Register — $299</a>
</section>""",
        "css_content": """* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'Inter', system-ui, sans-serif; }
@media (max-width: 768px) {
  h1 { font-size: 2.2rem !important; }
  [style*="grid-template-columns:repeat(4"] { grid-template-columns: repeat(2, 1fr) !important; }
  [style*="grid-template-columns:repeat(3"] { grid-template-columns: 1fr !important; }
}""",
    },
    {
        "name": "Healthcare & Dental",
        "description": "Trustworthy, clean layout for medical practices and dental offices",
        "category_industry": "healthcare",
        "category_type": "homepage",
        "html_content": """<nav style="display:flex;align-items:center;justify-content:space-between;padding:1rem 2rem;max-width:1200px;margin:0 auto;border-bottom:1px solid #e2e8f0">
  <div style="font-weight:700;font-size:1.3rem;color:#0f766e">{{company_name}}</div>
  <div style="display:flex;gap:1.5rem;align-items:center">
    <a href="#services" style="text-decoration:none;color:#64748b;font-size:0.9rem">Services</a>
    <a href="#team" style="text-decoration:none;color:#64748b;font-size:0.9rem">Our Team</a>
    <a href="#book" style="background:#0f766e;color:#fff;padding:0.5rem 1.2rem;border-radius:6px;text-decoration:none;font-size:0.9rem">Book Appointment</a>
  </div>
</nav>
<section style="max-width:1200px;margin:0 auto;padding:5rem 2rem;display:grid;grid-template-columns:1fr 1fr;gap:4rem;align-items:center">
  <div>
    <h1 style="font-size:2.8rem;font-weight:800;color:#0f172a;line-height:1.2">Your health is our priority</h1>
    <p style="color:#64748b;margin-top:1rem;font-size:1.05rem;line-height:1.7">Compassionate care with the latest technology. Our experienced team is dedicated to giving you the best treatment experience.</p>
    <div style="display:flex;gap:1rem;margin-top:2rem">
      <a href="#book" style="background:#0f766e;color:#fff;padding:0.75rem 2rem;border-radius:8px;text-decoration:none;font-weight:600">Book Now</a>
      <a href="tel:+15551234567" style="border:1px solid #e2e8f0;color:#0f172a;padding:0.75rem 2rem;border-radius:8px;text-decoration:none;font-weight:500">Call Us</a>
    </div>
  </div>
  <div style="background:linear-gradient(135deg,#ccfbf1,#99f6e4);border-radius:20px;aspect-ratio:1;display:flex;align-items:center;justify-content:center;font-size:5rem">🏥</div>
</section>
<section id="services" style="background:#f8fafc;padding:5rem 2rem">
  <div style="max-width:1200px;margin:0 auto">
    <h2 style="font-size:2rem;font-weight:700;text-align:center;color:#0f172a">Our Services</h2>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:1.5rem;margin-top:3rem">
      <div style="background:#fff;padding:1.5rem;border-radius:12px;border:1px solid #e2e8f0;text-align:center"><div style="font-size:2rem;margin-bottom:0.8rem">🦷</div><h3 style="font-weight:600;color:#0f172a">General Dentistry</h3><p style="color:#64748b;margin-top:0.5rem;font-size:0.9rem">Cleanings, fillings, and preventive care</p></div>
      <div style="background:#fff;padding:1.5rem;border-radius:12px;border:1px solid #e2e8f0;text-align:center"><div style="font-size:2rem;margin-bottom:0.8rem">✨</div><h3 style="font-weight:600;color:#0f172a">Cosmetic</h3><p style="color:#64748b;margin-top:0.5rem;font-size:0.9rem">Whitening, veneers, and smile makeovers</p></div>
      <div style="background:#fff;padding:1.5rem;border-radius:12px;border:1px solid #e2e8f0;text-align:center"><div style="font-size:2rem;margin-bottom:0.8rem">🩺</div><h3 style="font-weight:600;color:#0f172a">Emergency Care</h3><p style="color:#64748b;margin-top:0.5rem;font-size:0.9rem">Same-day appointments available</p></div>
    </div>
  </div>
</section>
<section id="book" style="background:#0f766e;color:#fff;padding:4rem 2rem;text-align:center">
  <h2 style="font-size:2rem;font-weight:700">Ready to schedule?</h2>
  <p style="color:#a7f3d0;margin-top:0.5rem">New patients welcome — most insurance accepted</p>
  <a href="#" style="display:inline-block;margin-top:1.5rem;background:#fff;color:#0f766e;padding:0.75rem 2rem;border-radius:8px;text-decoration:none;font-weight:600">Book Appointment</a>
</section>""",
        "css_content": """* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'Inter', system-ui, sans-serif; }
@media (max-width: 768px) {
  h1 { font-size: 2rem !important; }
  [style*="grid-template-columns"] { grid-template-columns: 1fr !important; }
  nav > div:last-child { display: none; }
}""",
    },
    {
        "name": "Professional Services",
        "description": "Clean, corporate page for consultants, lawyers, and accountants",
        "category_industry": "professional",
        "category_type": "landing",
        "html_content": """<nav style="display:flex;align-items:center;justify-content:space-between;padding:1rem 2rem;max-width:1200px;margin:0 auto">
  <div style="font-weight:700;font-size:1.3rem;color:#1e3a5f">{{company_name}}</div>
  <div style="display:flex;gap:1.5rem;align-items:center">
    <a href="#services" style="text-decoration:none;color:#64748b;font-size:0.9rem">Services</a>
    <a href="#why" style="text-decoration:none;color:#64748b;font-size:0.9rem">Why Us</a>
    <a href="#contact" style="background:#1e3a5f;color:#fff;padding:0.5rem 1.2rem;border-radius:6px;text-decoration:none;font-size:0.9rem">Free Consultation</a>
  </div>
</nav>
<section style="max-width:1200px;margin:0 auto;padding:5rem 2rem;display:grid;grid-template-columns:1fr 1fr;gap:4rem;align-items:center">
  <div>
    <h1 style="font-size:3rem;font-weight:800;color:#0f172a;line-height:1.2">Expert guidance for your business</h1>
    <p style="color:#64748b;margin-top:1rem;font-size:1.05rem;line-height:1.7">We help businesses navigate complexity with strategic advisory, compliance, and growth planning tailored to your industry.</p>
    <div style="display:flex;gap:3rem;margin-top:2rem">
      <div><div style="font-size:2rem;font-weight:800;color:#1e3a5f">500+</div><div style="font-size:0.8rem;color:#64748b">Clients Served</div></div>
      <div><div style="font-size:2rem;font-weight:800;color:#1e3a5f">15+</div><div style="font-size:0.8rem;color:#64748b">Years Experience</div></div>
      <div><div style="font-size:2rem;font-weight:800;color:#1e3a5f">98%</div><div style="font-size:0.8rem;color:#64748b">Client Retention</div></div>
    </div>
    <a href="#contact" style="display:inline-block;margin-top:2rem;background:#1e3a5f;color:#fff;padding:0.75rem 2rem;border-radius:8px;text-decoration:none;font-weight:600">Get Started</a>
  </div>
  <div style="background:linear-gradient(135deg,#dbeafe,#bfdbfe);border-radius:20px;aspect-ratio:1;display:flex;align-items:center;justify-content:center;font-size:5rem">📊</div>
</section>
<section id="services" style="background:#f8fafc;padding:5rem 2rem">
  <div style="max-width:1200px;margin:0 auto">
    <h2 style="font-size:2rem;font-weight:700;text-align:center;color:#0f172a">Our Services</h2>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:1.5rem;margin-top:3rem">
      <div style="background:#fff;padding:2rem;border-radius:12px;border:1px solid #e2e8f0"><h3 style="font-weight:600;color:#0f172a;font-size:1.1rem">Strategic Consulting</h3><p style="color:#64748b;margin-top:0.5rem;font-size:0.9rem;line-height:1.6">Business strategy, market analysis, and growth roadmaps for long-term success.</p></div>
      <div style="background:#fff;padding:2rem;border-radius:12px;border:1px solid #e2e8f0"><h3 style="font-weight:600;color:#0f172a;font-size:1.1rem">Tax & Compliance</h3><p style="color:#64748b;margin-top:0.5rem;font-size:0.9rem;line-height:1.6">Full-service tax planning, compliance, and regulatory advisory.</p></div>
      <div style="background:#fff;padding:2rem;border-radius:12px;border:1px solid #e2e8f0"><h3 style="font-weight:600;color:#0f172a;font-size:1.1rem">Financial Advisory</h3><p style="color:#64748b;margin-top:0.5rem;font-size:0.9rem;line-height:1.6">Investment guidance, risk management, and financial planning.</p></div>
    </div>
  </div>
</section>
<section id="contact" style="background:#1e3a5f;color:#fff;padding:4rem 2rem;text-align:center">
  <h2 style="font-size:2rem;font-weight:700">Schedule a free consultation</h2>
  <p style="color:#93c5fd;margin-top:0.5rem">No obligation — let's discuss how we can help</p>
  <a href="#" style="display:inline-block;margin-top:1.5rem;background:#fff;color:#1e3a5f;padding:0.75rem 2rem;border-radius:8px;text-decoration:none;font-weight:600">Book a Call</a>
</section>""",
        "css_content": """* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'Inter', system-ui, sans-serif; }
@media (max-width: 768px) {
  h1 { font-size: 2rem !important; }
  [style*="grid-template-columns"] { grid-template-columns: 1fr !important; }
  nav > div:last-child { display: none; }
}""",
    },
    {
        "name": "E-Commerce",
        "description": "Product showcase page for online shops and retailers",
        "category_industry": "ecommerce",
        "category_type": "landing",
        "html_content": """<nav style="display:flex;align-items:center;justify-content:space-between;padding:1rem 2rem;max-width:1200px;margin:0 auto">
  <div style="font-weight:700;font-size:1.3rem;color:#111">{{company_name}}</div>
  <div style="display:flex;gap:1.5rem;align-items:center">
    <a href="#products" style="text-decoration:none;color:#555;font-size:0.9rem">Products</a>
    <a href="#" style="text-decoration:none;color:#555;font-size:0.9rem">About</a>
    <a href="#" style="background:#111;color:#fff;padding:0.5rem 1.2rem;border-radius:6px;text-decoration:none;font-size:0.9rem">Shop Now</a>
  </div>
</nav>
<section style="background:linear-gradient(135deg,#faf5ff,#f3e8ff);padding:5rem 2rem;text-align:center">
  <span style="background:#7c3aed;color:#fff;padding:0.3rem 1rem;border-radius:20px;font-size:0.8rem;font-weight:500">NEW COLLECTION</span>
  <h1 style="font-size:3.5rem;font-weight:800;color:#111;margin-top:1.5rem;max-width:600px;margin-left:auto;margin-right:auto;line-height:1.1">Elevate your everyday</h1>
  <p style="color:#666;margin-top:1rem;font-size:1.1rem">Premium quality. Sustainable materials. Timeless design.</p>
  <a href="#products" style="display:inline-block;margin-top:2rem;background:#111;color:#fff;padding:0.75rem 2rem;border-radius:8px;text-decoration:none;font-weight:600">Shop the Collection</a>
</section>
<section id="products" style="padding:5rem 2rem;max-width:1200px;margin:0 auto">
  <h2 style="font-size:2rem;font-weight:700;text-align:center;color:#111">Best Sellers</h2>
  <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:1.5rem;margin-top:3rem">
    <div style="text-align:center"><div style="aspect-ratio:3/4;background:#f8f8f8;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:2.5rem">👜</div><h3 style="margin-top:0.8rem;font-weight:600;font-size:1rem">Classic Tote</h3><p style="color:#7c3aed;font-weight:600;margin-top:0.3rem">$89</p></div>
    <div style="text-align:center"><div style="aspect-ratio:3/4;background:#f8f8f8;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:2.5rem">⌚</div><h3 style="margin-top:0.8rem;font-weight:600;font-size:1rem">Minimalist Watch</h3><p style="color:#7c3aed;font-weight:600;margin-top:0.3rem">$199</p></div>
    <div style="text-align:center"><div style="aspect-ratio:3/4;background:#f8f8f8;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:2.5rem">🧣</div><h3 style="margin-top:0.8rem;font-weight:600;font-size:1rem">Cashmere Scarf</h3><p style="color:#7c3aed;font-weight:600;margin-top:0.3rem">$65</p></div>
    <div style="text-align:center"><div style="aspect-ratio:3/4;background:#f8f8f8;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:2.5rem">🕶️</div><h3 style="margin-top:0.8rem;font-weight:600;font-size:1rem">Aviator Shades</h3><p style="color:#7c3aed;font-weight:600;margin-top:0.3rem">$129</p></div>
  </div>
</section>
<section style="background:#111;color:#fff;padding:4rem 2rem;text-align:center">
  <h2 style="font-size:2rem;font-weight:700">Join our community</h2>
  <p style="color:#888;margin-top:0.5rem">Get 10% off your first order when you sign up</p>
  <a href="#" style="display:inline-block;margin-top:1.5rem;background:#7c3aed;color:#fff;padding:0.75rem 2rem;border-radius:8px;text-decoration:none;font-weight:600">Sign Up</a>
</section>""",
        "css_content": """* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'Inter', system-ui, sans-serif; }
@media (max-width: 768px) {
  h1 { font-size: 2.2rem !important; }
  [style*="grid-template-columns:repeat(4"] { grid-template-columns: repeat(2, 1fr) !important; }
  [style*="grid-template-columns:repeat(3"] { grid-template-columns: 1fr !important; }
  nav > div:last-child { display: none; }
}""",
    },
]


async def seed_starter_templates(db):
    """Insert starter platform templates if none exist."""
    from sqlalchemy import select, func
    from app.pages.models import PageTemplate, TemplateScope

    count = (await db.execute(
        select(func.count()).select_from(PageTemplate).where(PageTemplate.scope == TemplateScope.PLATFORM)
    )).scalar() or 0

    if count > 0:
        return 0

    import uuid as _uuid
    inserted = 0
    for t in STARTER_TEMPLATES:
        template = PageTemplate(
            id=_uuid.uuid4(),
            name=t["name"],
            description=t["description"],
            category_industry=t["category_industry"],
            category_type=t["category_type"],
            html_content=t["html_content"],
            css_content=t["css_content"],
            scope=TemplateScope.PLATFORM,
            is_active=True,
            created_by=None,
        )
        db.add(template)
        inserted += 1

    await db.commit()
    return inserted
