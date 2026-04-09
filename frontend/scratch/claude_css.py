import re

css_file = "src/app/globals.css"
with open(css_file, "r") as f:
    css = f.read()

# 1. Fonts
css = re.sub(
    r"--font-sans:[^;]+;", 
    "--font-sans: system-ui, -apple-system, BlinkMacSystemFont, Arial, sans-serif;\n  --font-serif: Georgia, Times, 'Times New Roman', serif;", 
    css
)

# 2. Main Color Scheme (Claude Neutral Palette)
replacements = {
    r"--color-bg:\s*#[a-fA-F0-9]+;": "--color-bg: #f5f4ed;",
    r"--color-surface:\s*#[a-fA-F0-9]+;": "--color-surface: #faf9f5;",
    r"--color-surface-2:\s*#[a-fA-F0-9]+;": "--color-surface-2: #e8e6dc;",
    r"--color-border:\s*rgba[^;]+;": "--color-border: #f0eee6;",
    r"--color-border-accent:\s*rgba[^;]+;": "--color-border-accent: #e8e6dc;",
    r"--text-primary:\s*#[a-fA-F0-9]+;": "--text-primary: #141413;",
    r"--text-secondary:\s*#[a-fA-F0-9]+;": "--text-secondary: #4d4c48;",
    r"--text-muted:\s*#[a-fA-F0-9]+;": "--text-muted: #87867f;",
    r"--color-link:\s*#[a-fA-F0-9]+;": "--color-link: #d97757;",
    r"--color-link-hover:\s*#[a-fA-F0-9]+;": "--color-link-hover: #c96442;",
    r"--color-landing-page-fallback:\s*#[a-fA-F0-9]+;": "--color-landing-page-fallback: #f5f4ed;",
    r"--gradient-landing-page:\s*linear-gradient\([^)]+\);": "--gradient-landing-page: none;",
}
for k, v in replacements.items():
    css = re.sub(k, v, css)

# 3. Shadows
css = re.sub(r"--shadow-card:[^;]+;", "--shadow-card: rgba(0, 0, 0, 0.05) 0px 4px 24px;", css)
css = re.sub(r"--shadow-hero-input:[^;]+;", "--shadow-hero-input: rgba(0, 0, 0, 0.05) 0px 4px 24px;", css)

# 4. Buttons
btn_pattern = r"\.btn-primary\s*\{[^}]+\}"
new_btn = """.btn-primary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 8px 16px;
  background: #c96442;
  color: #faf9f5;
  font-weight: 500;
  font-size: 16px;
  border-radius: 8px;
  transition: all var(--transition-normal);
  box-shadow: #c96442 0px 0px 0px 0px, #c96442 0px 0px 0px 1px;
  border: none;
}"""
css = re.sub(btn_pattern, new_btn, css)

# Update hover/focus for btn-primary
css = re.sub(r"\.btn-primary:focus-visible\s*\{[^}]+\}", ".btn-primary:focus-visible { outline: 2px solid #3898ec; outline-offset: 2px; }", css)
css = re.sub(r"\.btn-primary:hover\s*\{[^}]+\}", ".btn-primary:hover { background: #b55a3b; }", css)
css = re.sub(r"\.btn-primary:active\s*\{[^}]+\}", ".btn-primary:active { background: #a24b2f; box-shadow: inset 0px 0px 0px 1px rgba(0,0,0,0.15); }", css)

# btn-ghost (Secondary/Warm Sand)
ghost_pattern = r"\.btn-ghost\s*\{[^}]+\}"
new_ghost = """.btn-ghost {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  color: #4d4c48;
  border: none;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 500;
  background: #e8e6dc;
  transition: all var(--transition-fast);
  box-shadow: #e8e6dc 0px 0px 0px 0px, #d1cfc5 0px 0px 0px 1px;
}"""
css = re.sub(ghost_pattern, new_ghost, css)
css = re.sub(r"\.btn-ghost:hover\s*\{[^}]+\}", ".btn-ghost:hover { text-decoration: none; background: #d1cfc5; }", css)

# 5. Nav bar
nav_pattern = r"(\.site-nav\s*\{[^\}]+)(box-sizing:\s*border-box;)[^\}]+(\})"
css = re.sub(
    nav_pattern,
    r"\1\2\n  background: #f5f4ed;\n  border-bottom: 1px solid #f0eee6;\n\3",
    css
)

# Fix link colors in nav (since we removed dark mode handling for it)
css = re.sub(r"(\.site-nav-logo\s*\{[^\}]*color:\s*)[^;]+;", r"\1var(--text-primary);", css)
css = re.sub(r"(\.site-nav-link\s*\{[^\}]*color:\s*)[^;]+;", r"\1var(--text-secondary);", css)

with open(css_file, "w") as f:
    f.write(css)

print("Globals patched for Claude.")
