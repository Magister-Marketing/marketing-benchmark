<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Harborline Sleep Education | Virtual Sleep-Routine Consultation</title>
  <style>
    /* Reset & Base Variables */
    *, *::before, *::after {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    :root {
      --font-stack: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      --color-bg: #f8fafc;
      --color-surface: #ffffff;
      --color-surface-subtle: #f1f5f9;
      --color-surface-warm: #fcfbf9;
      --color-border: #e2e8f0;
      --color-border-strong: #cbd5e1;
      --color-text-main: #0f172a;
      --color-text-muted: #334155;
      --color-text-light: #64748b;
      --color-brand-deep: #132a45;
      --color-brand-primary: #1e3a5f;
      --color-brand-hover: #152943;
      --color-brand-accent: #2b5383;
      --color-accent-teal: #0f766e;
      --color-accent-teal-bg: #f0fdfa;
      --color-accent-teal-border: #99f6e4;
      --color-warning-red: #991b1b;
      --color-warning-red-bg: #fff1f2;
      --color-warning-red-border: #fecdd3;
      --color-warning-amber: #9a3412;
      --color-warning-amber-bg: #fff7ed;
      --color-warning-amber-border: #fed7aa;
      --max-width: 1080px;
      --content-max-width: 720px;
      --radius-sm: 6px;
      --radius-md: 10px;
      --radius-lg: 16px;
      --shadow-sm: 0 1px 2px 0 rgba(15, 23, 42, 0.05);
      --shadow-md: 0 4px 6px -1px rgba(15, 23, 42, 0.07), 0 2px 4px -2px rgba(15, 23, 42, 0.05);
      --shadow-lg: 0 10px 15px -3px rgba(15, 23, 42, 0.08), 0 4px 6px -4px rgba(15, 23, 42, 0.04);
    }

    body {
      font-family: var(--font-stack);
      background-color: var(--color-bg);
      color: var(--color-text-main);
      line-height: 1.65;
      font-size: 1rem;
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
    }

    a {
      color: var(--color-brand-primary);
      text-decoration: underline;
      text-underline-offset: 3px;
    }

    a:hover {
      color: var(--color-brand-hover);
    }

    a:focus-visible, button:focus-visible, summary:focus-visible {
      outline: 3px solid var(--color-brand-accent);
      outline-offset: 3px;
      border-radius: var(--radius-sm);
    }

    /* Container Utilities */
    .container {
      width: 100%;
      max-width: var(--max-width);
      margin-left: auto;
      margin-right: auto;
      padding-left: 1.5rem;
      padding-right: 1.5rem;
    }

    /* Header */
    .site-header {
      background-color: var(--color-surface);
      border-bottom: 1px solid var(--color-border);
      position: sticky;
      top: 0;
      z-index: 50;
    }

    .header-inner {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 1.125rem 0;
    }

    .brand-mark {
      display: flex;
      align-items: center;
      gap: 0.625rem;
      font-weight: 700;
      font-size: 1.15rem;
      color: var(--color-brand-deep);
      text-decoration: none;
      letter-spacing: -0.01em;
    }

    .brand-mark svg {
      color: var(--color-brand-primary);
    }

    .nav-list {
      display: flex;
      gap: 1.5rem;
      list-style: none;
    }

    .nav-list a {
      text-decoration: none;
      color: var(--color-text-muted);
      font-size: 0.9rem;
      font-weight: 500;
      transition: color 0.15s ease;
    }

    .nav-list a:hover {
      color: var(--color-brand-deep);
    }

    @media (max-width: 768px) {
      .nav-list {
        display: none;
      }
    }

    /* Badges & Tags */
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 0.375rem;
      padding: 0.3125rem 0.75rem;
      border-radius: 9999px;
      font-size: 0.8125rem;
      font-weight: 600;
      letter-spacing: 0.02em;
      text-transform: uppercase;
    }

    .badge-educational {
      background-color: var(--color-surface-subtle);
      color: var(--color-brand-deep);
      border: 1px solid var(--color-border-strong);
    }

    .badge-neutral {
      background-color: #f8fafc;
      color: var(--color-text-muted);
      border: 1px solid var(--color-border);
    }

    /* Primary CTA Button */
    .primary-cta-btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 0.9375rem 2rem;
      background-color: var(--color-brand-primary);
      color: #ffffff !important;
      font-weight: 600;
      font-size: 1.0625rem;
      border-radius: var(--radius-md);
      text-decoration: none;
      box-shadow: var(--shadow-sm);
      transition: background-color 0.15s ease, transform 0.1s ease, box-shadow 0.15s ease;
      cursor: pointer;
      border: none;
      text-align: center;
    }

    .primary-cta-btn:hover {
      background-color: var(--color-brand-hover);
      box-shadow: var(--shadow-md);
      transform: translateY(-1px);
    }

    .primary-cta-btn:active {
      transform: translateY(0);
      box-shadow: var(--shadow-sm);
    }

    /* Section Base */
    .section {
      padding: 4.5rem 0;
      border-bottom: 1px solid var(--color-border);
    }

    .section-header {
      max-width: var(--content-max-width);
      margin-bottom: 2.75rem;
    }

    .section-header.center {
      margin-left: auto;
      margin-right: auto;
      text-align: center;
    }

    .section-eyebrow {
      font-size: 0.8125rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--color-brand-accent);
      margin-bottom: 0.5rem;
    }

    .section-title {
      font-size: 2rem;
      line-height: 1.25;
      font-weight: 700;
      color: var(--color-brand-deep);
      letter-spacing: -0.02em;
      margin-bottom: 0.875rem;
    }

    .section-desc {
      font-size: 1.125rem;
      color: var(--color-text-muted);
      line-height: 1.6;
    }

    /* Section 1: Overview & Fit */
    .hero-layout {
      display: grid;
      grid-template-columns: 1fr;
      gap: 2.5rem;
    }

    .hero-copy {
      max-width: 780px;
    }

    .hero-title {
      font-size: 2.625rem;
      line-height: 1.18;
      font-weight: 800;
      color: var(--color-brand-deep);
      letter-spacing: -0.03em;
      margin-top: 1rem;
      margin-bottom: 1.25rem;
    }

    .hero-lead {
      font-size: 1.2rem;
      line-height: 1.6;
      color: var(--color-text-muted);
      margin-bottom: 1.75rem;
    }

    .hero-cta-group {
      display: flex;
      flex-direction: column;
      align-items: flex-start;
      gap: 0.75rem;
      margin-bottom: 2.5rem;
    }

    .hero-cta-microcopy {
      font-size: 0.875rem;
      color: var(--color-text-light);
      display: flex;
      align-items: center;
      gap: 0.5rem;
      flex-wrap: wrap;
    }

    .hero-cta-microcopy span {
      display: inline-flex;
      align-items: center;
      gap: 0.25rem;
    }

    .split-cards {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 1.5rem;
      margin-top: 1rem;
    }

    @media (max-width: 768px) {
      .hero-title {
        font-size: 2rem;
      }
      .split-cards {
        grid-template-columns: 1fr;
      }
    }

    .card {
      background-color: var(--color-surface);
      border: 1px solid var(--color-border);
      border-radius: var(--radius-lg);
      padding: 1.875rem;
      box-shadow: var(--shadow-sm);
    }

    .card-title {
      font-size: 1.2rem;
      font-weight: 700;
      color: var(--color-brand-deep);
      margin-bottom: 1rem;
      display: flex;
      align-items: center;
      gap: 0.625rem;
    }

    .item-list {
      list-style: none;
      display: flex;
      flex-direction: column;
      gap: 0.875rem;
    }

    .item-list li {
      display: flex;
      align-items: flex-start;
      gap: 0.75rem;
      font-size: 0.95rem;
      color: var(--color-text-muted);
      line-height: 1.55;
    }

    .item-list svg {
      flex-shrink: 0;
      margin-top: 0.2rem;
    }

    /* Section 2: Process / How it works */
    .process-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 1.5rem;
    }

    @media (max-width: 860px) {
      .process-grid {
        grid-template-columns: 1fr;
      }
    }

    .process-step {
      background-color: var(--color-surface);
      border: 1px solid var(--color-border);
      border-radius: var(--radius-lg);
      padding: 1.75rem;
      display: flex;
      flex-direction: column;
      position: relative;
    }

    .step-number {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 2.25rem;
      height: 2.25rem;
      background-color: var(--color-surface-subtle);
      border: 1px solid var(--color-border-strong);
      border-radius: var(--radius-sm);
      font-weight: 700;
      font-size: 0.9rem;
      color: var(--color-brand-primary);
      margin-bottom: 1.25rem;
    }

    .step-title {
      font-size: 1.15rem;
      font-weight: 700;
      color: var(--color-brand-deep);
      margin-bottom: 0.625rem;
    }

    .step-desc {
      font-size: 0.9375rem;
      color: var(--color-text-muted);
      line-height: 1.55;
    }

    /* Section 3: What is included */
    .included-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 1.5rem;
    }

    @media (max-width: 860px) {
      .included-grid {
        grid-template-columns: 1fr;
      }
    }

    .included-card {
      background-color: var(--color-surface);
      border: 1px solid var(--color-border);
      border-radius: var(--radius-lg);
      padding: 1.75rem;
      display: flex;
      flex-direction: column;
    }

    .included-icon-box {
      width: 2.75rem;
      height: 2.75rem;
      border-radius: var(--radius-md);
      background-color: var(--color-accent-teal-bg);
      border: 1px solid var(--color-accent-teal-border);
      color: var(--color-accent-teal);
      display: flex;
      align-items: center;
      justify-content: center;
      margin-bottom: 1.25rem;
    }

    .included-title {
      font-size: 1.125rem;
      font-weight: 700;
      color: var(--color-brand-deep);
      margin-bottom: 0.5rem;
    }

    .included-desc {
      font-size: 0.9375rem;
      color: var(--color-text-muted);
      line-height: 1.55;
    }

    /* Section 4: Price */
    .pricing-card-wrap {
      max-width: 680px;
      margin: 0 auto;
    }

    .pricing-card {
      background-color: var(--color-surface);
      border: 2px solid var(--color-brand-primary);
      border-radius: var(--radius-lg);
      padding: 2.5rem;
      box-shadow: var(--shadow-md);
    }

    .pricing-header {
      border-bottom: 1px solid var(--color-border);
      padding-bottom: 1.75rem;
      margin-bottom: 1.75rem;
      text-align: center;
    }

    .price-value-row {
      display: flex;
      align-items: baseline;
      justify-content: center;
      gap: 0.375rem;
      margin: 0.75rem 0 0.5rem 0;
    }

    .price-currency {
      font-size: 1.75rem;
      font-weight: 700;
      color: var(--color-brand-deep);
    }

    .price-amount {
      font-size: 3.5rem;
      font-weight: 800;
      line-height: 1;
      color: var(--color-brand-deep);
      letter-spacing: -0.03em;
    }

    .price-terms {
      font-size: 0.9375rem;
      color: var(--color-text-muted);
      font-weight: 500;
    }

    .pricing-details-list {
      list-style: none;
      display: flex;
      flex-direction: column;
      gap: 1rem;
      margin-bottom: 2rem;
    }

    .pricing-details-list li {
      display: flex;
      align-items: flex-start;
      gap: 0.75rem;
      font-size: 0.975rem;
      color: var(--color-text-muted);
    }

    .pricing-details-list svg {
      flex-shrink: 0;
      margin-top: 0.2rem;
      color: var(--color-accent-teal);
    }

    .pricing-terms-callout {
      background-color: var(--color-surface-subtle);
      border: 1px solid var(--color-border);
      border-radius: var(--radius-md);
      padding: 1rem 1.25rem;
      font-size: 0.875rem;
      color: var(--color-text-muted);
      line-height: 1.5;
    }

    /* Section 5: Limitations & Boundary Statement */
    .limitations-section {
      background-color: #fbfcfe;
    }

    .limitations-box {
      background-color: var(--color-surface);
      border: 1px solid var(--color-warning-amber-border);
      border-left: 6px solid var(--color-warning-amber);
      border-radius: var(--radius-lg);
      padding: 2.25rem;
      box-shadow: var(--shadow-sm);
      margin-bottom: 2rem;
    }

    .limitations-box-header {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      margin-bottom: 1rem;
    }

    .limitations-box-title {
      font-size: 1.35rem;
      font-weight: 700;
      color: var(--color-warning-amber);
    }

    .limitations-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 1.5rem;
    }

    @media (max-width: 768px) {
      .limitations-grid {
        grid-template-columns: 1fr;
      }
    }

    .limit-item {
      background-color: var(--color-surface);
      border: 1px solid var(--color-border);
      border-radius: var(--radius-md);
      padding: 1.25rem 1.5rem;
    }

    .limit-item h3 {
      font-size: 1.05rem;
      font-weight: 700;
      color: var(--color-brand-deep);
      margin-bottom: 0.5rem;
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }

    .limit-item p {
      font-size: 0.9375rem;
      color: var(--color-text-muted);
      line-height: 1.55;
    }

    .emergency-alert {
      margin-top: 1.5rem;
      background-color: var(--color-warning-red-bg);
      border: 1px solid var(--color-warning-red-border);
      border-radius: var(--radius-md);
      padding: 1.125rem 1.5rem;
      display: flex;
      align-items: flex-start;
      gap: 0.875rem;
    }

    .emergency-alert svg {
      color: var(--color-warning-red);
      flex-shrink: 0;
      margin-top: 0.2rem;
    }

    .emergency-alert-content h4 {
      font-size: 0.95rem;
      font-weight: 700;
      color: var(--color-warning-red);
      margin-bottom: 0.25rem;
    }

    .emergency-alert-content p {
      font-size: 0.875rem;
      color: #7f1d1d;
      line-height: 1.5;
    }

    /* Section 6: Common Objections & FAQs */
    .faq-accordion {
      max-width: var(--content-max-width);
      margin: 0 auto;
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }

    .faq-item {
      background-color: var(--color-surface);
      border: 1px solid var(--color-border);
      border-radius: var(--radius-md);
      overflow: hidden;
      box-shadow: var(--shadow-sm);
    }

    .faq-summary {
      padding: 1.25rem 1.5rem;
      font-weight: 700;
      font-size: 1.05rem;
      color: var(--color-brand-deep);
      cursor: pointer;
      list-style: none;
      display: flex;
      justify-content: space-between;
      align-items: center;
      user-select: none;
    }

    .faq-summary::-webkit-details-marker {
      display: none;
    }

    .faq-summary svg {
      transition: transform 0.2s ease;
      color: var(--color-brand-primary);
      flex-shrink: 0;
    }

    details[open] .faq-summary svg {
      transform: rotate(180deg);
    }

    .faq-answer {
      padding: 0 1.5rem 1.5rem 1.5rem;
      font-size: 0.95rem;
      color: var(--color-text-muted);
      line-height: 1.6;
      border-top: 1px solid var(--color-surface-subtle);
      padding-top: 1rem;
    }

    /* Section 7: Next Step */
    .next-step-section {
      background-color: var(--color-surface);
      text-align: center;
      padding: 5rem 0;
    }

    .next-step-card {
      max-width: 720px;
      margin: 0 auto;
      background-color: var(--color-surface-warm);
      border: 1px solid var(--color-border-strong);
      border-radius: var(--radius-lg);
      padding: 3rem 2rem;
      box-shadow: var(--shadow-md);
    }

    .next-step-steps {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 1.25rem;
      margin: 2.25rem 0;
      text-align: left;
    }

    @media (max-width: 700px) {
      .next-step-steps {
        grid-template-columns: 1fr;
      }
    }

    .next-step-mini {
      background-color: var(--color-surface);
      border: 1px solid var(--color-border);
      border-radius: var(--radius-md);
      padding: 1.125rem;
    }

    .next-step-mini-num {
      font-size: 0.8125rem;
      font-weight: 700;
      color: var(--color-brand-accent);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 0.25rem;
    }

    .next-step-mini-text {
      font-size: 0.9rem;
      font-weight: 600;
      color: var(--color-brand-deep);
      line-height: 1.4;
    }

    .next-step-action {
      margin-top: 2rem;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 0.875rem;
    }

    /* Footer */
    .site-footer {
      background-color: var(--color-brand-deep);
      color: #94a3b8;
      padding: 3.5rem 0 2.5rem 0;
      font-size: 0.875rem;
      line-height: 1.6;
    }

    .footer-content {
      display: grid;
      grid-template-columns: 1fr;
      gap: 2rem;
      border-bottom: 1px solid #1e293b;
      padding-bottom: 2rem;
      margin-bottom: 2rem;
    }

    .footer-brand {
      color: #ffffff;
      font-size: 1.125rem;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 0.5rem;
      margin-bottom: 0.75rem;
    }

    .footer-disclaimer-box {
      background-color: #0b1727;
      border: 1px solid #1e293b;
      border-radius: var(--radius-md);
      padding: 1.25rem;
      font-size: 0.8125rem;
      color: #94a3b8;
    }

    .footer-bottom {
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 1rem;
      font-size: 0.8125rem;
    }

    .footer-links {
      display: flex;
      gap: 1.25rem;
      list-style: none;
    }

    .footer-links a {
      color: #cbd5e1;
      text-decoration: none;
    }

    .footer-links a:hover {
      color: #ffffff;
    }
  .primary-cta-btn { display: none !important; }
</style>
</head>
<body>

  <!-- Header -->
  <header class="site-header">
    <div class="container header-inner">
      <a href="#overview" class="brand-mark" aria-label="Harborline Sleep Education Home">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"></path>
        </svg>
        <span>Harborline Sleep Education</span>
      </a>
      <nav aria-label="Primary page navigation">
        <ul class="nav-list">
          <li><a href="#overview">Overview</a></li>
          <li><a href="#how-it-works">How It Works</a></li>
          <li><a href="#included">Included</a></li>
          <li><a href="#pricing">Price</a></li>
          <li><a href="#limitations">Limitations</a></li>
          <li><a href="#faq">Questions</a></li>
        </ul>
      </nav>
    </div>
  </header>

  <main>
    <!-- Section 1: What this is and who it is for -->
    <section id="overview" class="section" aria-labelledby="hero-title">
      <div class="container">
        <div class="hero-layout">
          <div class="hero-copy">
            <span class="badge badge-educational">
              Educational Routine Coaching
            </span>
            <h1 id="hero-title" class="hero-title">
              Organize your evening habits with focused, educational guidance.
            </h1>
            <p class="hero-lead">
              A 45-minute virtual routine-planning consultation ($160) for adults who want to replace irregular evenings with a calm, repeatable bedtime sequence. Non-clinical, structured, and focused purely on habit architecture.
            </p>
            <div class="hero-cta-group">
              <a href="#next-step" class="primary-cta-btn">Book a consultation</a>
              <div class="hero-cta-microcopy">
                <span>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
                  45-minute virtual session
                </span>
                <span>•</span>
                <span>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path></svg>
                  $160 direct self-pay
                </span>
                <span>•</span>
                <span>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
                  Educational &amp; non-clinical
                </span>
              </div>
            </div>
          </div>

          <div class="split-cards">
            <article class="card">
              <h2 class="card-title">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#0f766e" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
                What this consultation is
              </h2>
              <ul class="item-list">
                <li>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#0f766e" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"></polyline></svg>
                  <span><strong>One-on-one educational coaching:</strong> A collaborative review of your daily schedule, evening pacing, and bedtime environment.</span>
                </li>
                <li>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#0f766e" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"></polyline></svg>
                  <span><strong>Habit architecture:</strong> Identification of friction points, screen boundaries, and wind-down transitions.</span>
                </li>
                <li>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#0f766e" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"></polyline></svg>
                  <span><strong>Actionable documentation:</strong> Delivery of an educational routine plan and questions you may choose to discuss with a licensed clinician.</span>
                </li>
              </ul>
            </article>

            <article class="card">
              <h2 class="card-title">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#1e3a5f" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M22 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>
                Who it is for
              </h2>
              <ul class="item-list">
                <li>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#1e3a5f" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"></polyline></svg>
                  <span><strong>Adults with variable bedtimes:</strong> People experiencing schedule drift, evening procrastination, or erratic pre-sleep hours.</span>
                </li>
                <li>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#1e3a5f" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"></polyline></svg>
                  <span><strong>Individuals seeking routine clarity:</strong> Adults looking to organize non-clinical lifestyle habits into a predictable routine.</span>
                </li>
                <li>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#1e3a5f" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"></polyline></svg>
                  <span><strong>Proactive health communicators:</strong> Clients who want structured, organized observations to share with their own doctor.</span>
                </li>
              </ul>
            </article>
          </div>
        </div>
      </div>
    </section>

    <!-- Section 2: How the consultation works -->
    <section id="how-it-works" class="section" aria-labelledby="how-it-works-title">
      <div class="container">
        <header class="section-header">
          <p class="section-eyebrow">The Process</p>
          <h2 id="how-it-works-title" class="section-title">How the consultation works</h2>
          <p class="section-desc">
            A clear three-stage educational workflow designed to identify routine friction, build consistency, and provide written reference materials.
          </p>
        </header>

        <div class="process-grid">
          <div class="process-step">
            <span class="step-number" aria-hidden="true">01</span>
            <h3 class="step-title">Intake review</h3>
            <p class="step-desc">
              Before your session, you complete a structured intake questionnaire covering your current evening timeline, work schedule, environment, and habit patterns. We review this thoroughly prior to our call so our conversation is targeted from the first minute.
            </p>
          </div>

          <div class="process-step">
            <span class="step-number" aria-hidden="true">02</span>
            <h3 class="step-title">Routine-planning conversation</h3>
            <p class="step-desc">
              We meet for a dedicated 45-minute virtual video consultation. We walk through your typical evening, evaluate where habits break down, assess environmental pacing, and collaboratively co-create an achievable, non-clinical routine sequence tailored to your life.
            </p>
          </div>

          <div class="process-step">
            <span class="step-number" aria-hidden="true">03</span>
            <h3 class="step-title">Written educational summary</h3>
            <p class="step-desc">
              Following the conversation, you receive a concise written educational routine plan detailing your target wind-down steps, along with structured questions you may choose to discuss with a licensed clinician or primary care doctor.
            </p>
          </div>
        </div>
      </div>
    </section>

    <!-- Section 3: What is included -->
    <section id="included" class="section" aria-labelledby="included-title">
      <div class="container">
        <header class="section-header">
          <p class="section-eyebrow">Deliverables</p>
          <h2 id="included-title" class="section-title">What is included</h2>
          <p class="section-desc">
            Your single $160 consultation fee includes complete preparation, live one-on-one coaching, and reference documentation.
          </p>
        </header>

        <div class="included-grid">
          <div class="included-card">
            <div class="included-icon-box" aria-hidden="true">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
            </div>
            <h3 class="included-title">Pre-session intake review</h3>
            <p class="included-desc">
              Dedicated educator review of your submitted schedule, habits, and bedtime environment before the call begins, ensuring focused use of consultation time.
            </p>
          </div>

          <div class="included-card">
            <div class="included-icon-box" aria-hidden="true">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
            </div>
            <h3 class="included-title">45-minute live consultation</h3>
            <p class="included-desc">
              One-on-one virtual coaching focused on practical habit design, environmental factors, schedule pacing, and realistic evening transitions.
            </p>
          </div>

          <div class="included-card">
            <div class="included-icon-box" aria-hidden="true">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path></svg>
            </div>
            <h3 class="included-title">Written educational summary</h3>
            <p class="included-desc">
              A structured, post-session routine plan summarizing your customized wind-down schedule plus specific questions you can choose to bring to your physician.
            </p>
          </div>
        </div>
      </div>
    </section>

    <!-- Section 4: Price -->
    <section id="pricing" class="section" aria-labelledby="pricing-title">
      <div class="container">
        <header class="section-header center">
          <p class="section-eyebrow">Investment</p>
          <h2 id="pricing-title" class="section-title">Transparent, direct pricing</h2>
          <p class="section-desc">
            One flat fee. Paid directly by the client with no ongoing subscriptions, hidden charges, or unexpected billing.
          </p>
        </header>

        <div class="pricing-card-wrap">
          <div class="pricing-card">
            <div class="pricing-header">
              <span class="badge badge-neutral">Single Consultation</span>
              <div class="price-value-row">
                <span class="price-currency" aria-hidden="true">$</span>
                <span class="price-amount">160</span>
              </div>
              <p class="price-terms">One-time payment for one 45-minute virtual consultation</p>
            </div>

            <ul class="pricing-details-list">
              <li>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"></polyline></svg>
                <span>Full intake questionnaire analysis prior to our meeting</span>
              </li>
              <li>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"></polyline></svg>
                <span>45 minutes of live, one-on-one virtual coaching via secure video</span>
              </li>
              <li>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"></polyline></svg>
                <span>Written educational routine plan delivered after the session</span>
              </li>
              <li>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"></polyline></svg>
                <span>Curated list of routine questions to discuss with a licensed clinician</span>
              </li>
              <li>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"></polyline></svg>
                <span>Direct client self-pay; no recurring billing or automatic renewals</span>
              </li>
            </ul>

            <div class="pricing-terms-callout">
              <strong>Payment terms:</strong> $160 is paid directly by the client when reserving a session. Insurance billing is not provided, and insurance coverage is not represented.
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Section 5: Limitations & who it is NOT for -->
    <section id="limitations" class="section limitations-section" aria-labelledby="limitations-title">
      <div class="container">
        <header class="section-header">
          <p class="section-eyebrow">Scope &amp; Safety</p>
          <h2 id="limitations-title" class="section-title">Limitations &amp; who it is NOT for</h2>
          <p class="section-desc">
            We provide clear boundaries so you can decide if educational coaching is appropriate for your situation. Please read our operational limitations carefully before booking.
          </p>
        </header>

        <div class="limitations-box">
          <div class="limitations-box-header">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#9a3412" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
            <h3 class="limitations-box-title">Important Scope of Service Notice</h3>
          </div>
          <p style="color: var(--color-text-muted); font-size: 0.975rem; line-height: 1.6;">
            Harborline Sleep Education is an educational coaching service, <strong>not a medical clinic</strong>. We help adults organize non-clinical bedtime routines. We do not provide clinical treatment or medical evaluation.
          </p>
        </div>

        <div class="limitations-grid">
          <div class="limit-item">
            <h3>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#991b1b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>
              Not a medical clinic
            </h3>
            <p>
              This is educational coaching only. We do not practice medicine, nursing, psychology, or licensed sleep medicine. Our consultations do not establish a patient-provider relationship.
            </p>
          </div>

          <div class="limit-item">
            <h3>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#991b1b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>
              Does not diagnose or treat sleep disorders
            </h3>
            <p>
              We do not screen, diagnose, or treat medical conditions such as obstructive sleep apnea, clinical insomnia, restless legs syndrome, or narcolepsy. We do not issue prescriptions or therapy.
            </p>
          </div>

          <div class="limit-item">
            <h3>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#991b1b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>
              Outcomes are not guaranteed
            </h3>
            <p>
              Bedtime habits depend on multiple personal, biological, and environmental factors. We provide educational routine frameworks, but improvements to sleep quality or schedule consistency cannot be guaranteed.
            </p>
          </div>

          <div class="limit-item">
            <h3>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#991b1b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>
              Insurance is not represented
            </h3>
            <p>
              All consultations are direct client self-pay ($160). Insurance coverage is not represented, and we do not provide billing codes, superbills, or claims paperwork for insurance reimbursement.
            </p>
          </div>
        </div>

        <div class="emergency-alert" role="alert">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
          <div class="emergency-alert-content">
            <h4>Not emergency care</h4>
            <p>
              Harborline Sleep Education is an educational service and cannot assist with medical emergencies, psychiatric crises, or urgent physical symptoms. People with urgent symptoms or safety concerns should contact local emergency services immediately or consult an appropriate licensed clinician.
            </p>
          </div>
        </div>
      </div>
    </section>

    <!-- Section 6: Common objections -->
    <section id="faq" class="section" aria-labelledby="faq-title">
      <div class="container">
        <header class="section-header center">
          <p class="section-eyebrow">Common Questions</p>
          <h2 id="faq-title" class="section-title">Common objections &amp; questions</h2>
          <p class="section-desc">
            Direct, realistic answers to help you evaluate if routine coaching fits your expectations.
          </p>
        </header>

        <div class="faq-accordion">
          <details class="faq-item" open>
            <summary class="faq-summary">
              <span>How does this differ from clinical sleep medicine or medical care?</span>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="6 9 12 15 18 9"></polyline></svg>
            </summary>
            <div class="faq-answer">
              Clinical sleep medicine involves medical doctors diagnosing conditions, conducting diagnostic sleep studies, interpreting polysomnograms, and prescribing medical treatments or medical devices (such as CPAP). Harborline Sleep Education is an educational coaching service that focuses strictly on non-clinical daily habits, environmental wind-down adjustments, and evening scheduling. It is not medical care and does not diagnose or treat medical conditions.
            </div>
          </details>

          <details class="faq-item">
            <summary class="faq-summary">
              <span>Can I submit this consultation to health insurance or HSA/FSA?</span>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="6 9 12 15 18 9"></polyline></svg>
            </summary>
            <div class="faq-answer">
              No. The $160 fee is paid directly by the client. Insurance coverage is not represented, and we do not provide insurance billing, medical diagnostic codes (ICD), procedure codes (CPT), or medical superbills. This is an educational coaching offering paid directly out of pocket.
            </div>
          </details>

          <details class="faq-item">
            <summary class="faq-summary">
              <span>What if I have or suspect a sleep disorder like sleep apnea or insomnia?</span>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="6 9 12 15 18 9"></polyline></svg>
            </summary>
            <div class="faq-answer">
              If you experience symptoms of a sleep disorder—such as persistent inability to fall asleep, gasping for air, severe daytime sleepiness, or restless sensations in your legs—you should consult a licensed clinician or physician. Our consultation does not diagnose or treat sleep disorders. The written educational summary we provide includes structured questions you may choose to take to a licensed medical doctor for clinical evaluation.
            </div>
          </details>

          <details class="faq-item">
            <summary class="faq-summary">
              <span>Are sleep improvements or specific outcomes guaranteed?</span>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="6 9 12 15 18 9"></polyline></svg>
            </summary>
            <div class="faq-answer">
              No. Outcomes are not guaranteed. Developing a consistent evening routine depends on personal implementation, lifestyle circumstances, and individual factors. We provide clear educational planning and objective feedback on your routine, but we do not guarantee specific results.
            </div>
          </details>

          <details class="faq-item">
            <summary class="faq-summary">
              <span>What happens if my schedule changes or I work varied shifts?</span>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="6 9 12 15 18 9"></polyline></svg>
            </summary>
            <div class="faq-answer">
              During the 45-minute conversation, we address the practical realities of your actual week. While educational coaching cannot alter external work demands, we focus on identifying anchor habits and consistent transition rituals that can be adapted across variable schedules.
            </div>
          </details>

          <details class="faq-item">
            <summary class="faq-summary">
              <span>What will I receive in the written educational summary?</span>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="6 9 12 15 18 9"></polyline></svg>
            </summary>
            <div class="faq-answer">
              You will receive an educational summary documenting the routine plan co-designed during the call. This includes target timing sequences, habit cues, and a concise list of observations and questions you may choose to discuss with a licensed healthcare clinician.
            </div>
          </details>
        </div>
      </div>
    </section>

    <!-- Section 7: Next step -->
    <section id="next-step" class="section next-step-section" aria-labelledby="next-step-title">
      <div class="container">
        <div class="next-step-card">
          <p class="section-eyebrow">Ready To Plan Your Routine?</p>
          <h2 id="next-step-title" class="section-title">The next step</h2>
          <p class="section-desc">
            If you are an adult seeking structured, non-clinical routine education and you understand our operational limitations, here is how to get started:
          </p>

          <div class="next-step-steps">
            <div class="next-step-mini">
              <p class="next-step-mini-num">Step 1</p>
              <p class="next-step-mini-text">Select a time for your 45-minute virtual video session</p>
            </div>
            <div class="next-step-mini">
              <p class="next-step-mini-num">Step 2</p>
              <p class="next-step-mini-text">Complete the $160 direct self-pay consultation payment</p>
            </div>
            <div class="next-step-mini">
              <p class="next-step-mini-num">Step 3</p>
              <p class="next-step-mini-text">Submit your pre-session routine intake questionnaire</p>
            </div>
          </div>

          <div class="next-step-action" id="booking">
            <a href="#booking" class="primary-cta-btn">Book a consultation</a>
            <p style="font-size: 0.85rem; color: var(--color-text-light);">
              Direct client payment ($160) • Non-clinical educational coaching • No recurring subscription
            </p>
          </div>
        </div>
      </div>
    </section>
  </main>

  <!-- Footer -->
  <footer class="site-footer">
    <div class="container">
      <div class="footer-content">
        <div>
          <div class="footer-brand">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"></path>
            </svg>
            <span>Harborline Sleep Education</span>
          </div>
          <p style="max-width: 620px; margin-bottom: 1.25rem;">
            Harborline Sleep Education provides virtual educational coaching for adults who want to organize non-clinical bedtime routines.
          </p>
        </div>

        <div class="footer-disclaimer-box">
          <strong style="color: #f1f5f9; display: block; margin-bottom: 0.35rem;">Educational Coaching Disclaimer &amp; Emergency Notice:</strong>
          Harborline Sleep Education is an educational coaching service and is not a medical clinic. We do not diagnose, evaluate, manage, or treat sleep disorders, medical conditions, or mental health disorders. This service is not emergency care and does not provide prescriptions or insurance billing. Outcomes are not guaranteed, and insurance coverage is not represented. People with urgent symptoms or safety concerns should contact local emergency services immediately or consult an appropriate licensed clinician.
        </div>
      </div>

      <div class="footer-bottom">
        <p>&copy; 2026 Harborline Sleep Education. All rights reserved.</p>
        <ul class="footer-links">
          <li><a href="#overview">Overview</a></li>
          <li><a href="#how-it-works">How It Works</a></li>
          <li><a href="#included">What Is Included</a></li>
          <li><a href="#pricing">Price ($160)</a></li>
          <li><a href="#limitations">Limitations</a></li>
          <li><a href="#faq">Questions</a></li>
        </ul>
      </div>
    </div>
  </footer>

</body>
</html>