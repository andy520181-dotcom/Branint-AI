import re

css_file = "frontend/src/app/globals.css"
with open(css_file, "r") as f:
    css = f.read()

# 1. Colors & Basics
css = re.sub(r"--color-bg:\s*#F8F7F2;", "--color-bg:         #f5f5f7;", css)
css = re.sub(r"--color-surface-2:\s*#F0EFE9;", "--color-surface-2:  #fafafc;", css)

# link colors
css = re.sub(r"--color-link:\s*#2563eb;", "--color-link: #0066cc;", css)
css = re.sub(r"--color-link-hover:\s*#1d4ed8;", "--color-link-hover: #0071e3;", css)

# Landing page backgrounds
css = re.sub(r"--color-landing-page-fallback:\s*#ffffff;", "--color-landing-page-fallback: #000000;", css)
css = re.sub(r"--gradient-landing-page:\s*linear-gradient\([^)]+\);", "--gradient-landing-page: #000000;", css)

# Hero glows (remove them according to Apple "no distractions" rule)
css = re.sub(r"--hero-glow-neutral:[^;]+;", "--hero-glow-neutral: none;", css)
css = re.sub(r"--hero-glow-accent:[^;]+;", "--hero-glow-accent: none;", css)

# Button styling (make it Apple Blue)
css = re.sub(r"--color-btn-primary-start:[^;]+;", "--color-btn-primary-start: #0071e3;", css)
css = re.sub(r"--color-btn-primary-end:[^;]+;", "--color-btn-primary-end: #0071e3;", css)

# Nav styling
css = re.sub(r"--nav-bg:\s*rgba[^;]+;", "--nav-bg: rgba(0, 0, 0, 0.8);", css)
css = re.sub(r"--nav-link-hover-bg:\s*rgba[^;]+;", "--nav-link-hover-bg: rgba(255, 255, 255, 0.08);", css)

# Dark theme overrides
css = re.sub(r"--color-bg:\s*#1a1a1c;", "--color-bg:         #000000;", css)
css = re.sub(r"--color-surface:\s*#2c2c2e;", "--color-surface:    #272729;", css)
css = re.sub(r"--color-surface-2:\s*#3a3a3c;", "--color-surface-2:  #262628;", css)
css = re.sub(r"--color-link:\s*#60a5fa;", "--color-link: #2997ff;", css)
css = re.sub(r"--color-link-hover:\s*#93c5fd;", "--color-link-hover: #0071e3;", css)
css = re.sub(r"--gradient-landing-page:\s*linear-gradient\([^)]+\);", "--gradient-landing-page: #000000;", css)

# Base layout tracking & font
css = re.sub(r"body\s*{\s*background-color", "body {\n  letter-spacing: -0.02em;\n  background-color", css)

# Buttons css block
btn_pattern = r"\.btn-primary\s*\{[^}]+\}"
new_btn = """.btn-primary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 8px 24px;
  background: var(--gradient-btn-primary);
  color: #ffffff;
  font-weight: 500;
  font-size: var(--font-size-body);
  border-radius: 980px;
  transition: all var(--transition-normal);
  letter-spacing: -0.01em;
}"""
css = re.sub(btn_pattern, new_btn, css)

btn_hover_pattern = r"\.btn-primary:hover\s*\{[^}]+\}"
css = re.sub(btn_hover_pattern, ".btn-primary:hover { background: #0077ED; }", css)

# Card shadow override
css = re.sub(r"--shadow-card:[^;]+;", "--shadow-card: rgba(0, 0, 0, 0.22) 3px 5px 30px 0px;", css)
css = re.sub(r"--shadow-hero-input:[^;]+;", "--shadow-hero-input: rgba(0, 0, 0, 0.4) 0 0 0 1px, rgba(0, 0, 0, 0.22) 3px 5px 30px 0px;", css)

# Nav Glass
nav_pattern = r"(\.site-nav\s*\{[^\}]+)(box-sizing:\s*border-box;)"
css = re.sub(nav_pattern, r"\1\2\n  backdrop-filter: saturate(180%) blur(20px);\n  -webkit-backdrop-filter: saturate(180%) blur(20px);\n", css)

# Since Apple nav is always dark, we must force the text color in site-nav-logo and site-nav-link
css = re.sub(r"(\.site-nav-logo\s*\{[^\}]*color:\s*)var\(--text-primary\)", r"\1#ffffff", css)
css = re.sub(r"(\.site-nav-link\s*\{[^\}]*color:\s*)var\(--text-muted\)", r"\1#c7c7cc", css)
css = re.sub(r"\.site-nav-link:hover\s*\{[^\}]*color:\s*var\(--text-primary\);", ".site-nav-link:hover {\n  background: var(--nav-link-hover-bg);\n  color: #ffffff;", css)

with open(css_file, "w") as f:
    f.write(css)

print("Globals CSS overhauled!")
