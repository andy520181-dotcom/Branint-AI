import re

css_file = "frontend/src/app/page.module.css"
with open(css_file, "r") as f:
    css = f.read()

# Restore Agents Section
css = re.sub(
    r"\.agentsSection\s*\{[^}]+\}",
    ".agentsSection {\n  width: 100%;\n  display: flex;\n  flex-direction: column;\n  align-items: center;\n}",
    css
)

# Restore agentPill to use semantic variables
css = re.sub(
    r"\.agentPill\s*\{[^}]+\}",
    ".agentPill {\n  display: flex;\n  flex-direction: column;\n  gap: 8px;\n  background: var(--color-surface);\n  border: 1px solid var(--color-border);\n  border-radius: 12px;\n  padding: 16px;\n  flex: 1;\n  min-width: 0;\n  transition: all var(--transition-normal);\n  box-shadow: var(--shadow-card);\n}",
    css
)

# Restore text colors
css = re.sub(r"(\.agentPillName\s*\{[^\}]*color:\s*)#1d1d1f(;)", r"\1var(--text-primary)\2", css)
css = re.sub(r"(\.agentPillCharName\s*\{[^\}]*color:\s*)#86868b(;)", r"\1var(--text-muted)\2", css)
css = re.sub(r"(\.agentPillTags\s*\{[^\}]*color:\s*)#86868b(;)", r"\1var(--text-muted)\2", css)

with open(css_file, "w") as f:
    f.write(css)

print("Page CSS restored!")
