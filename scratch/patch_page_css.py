import re

css_file = "frontend/src/app/page.module.css"
with open(css_file, "r") as f:
    css = f.read()

# Hardcode Agents Section to Light Gray
css = re.sub(
    r"\.agentsSection\s*\{[^}]+\}",
    ".agentsSection {\n  width: 100%;\n  display: flex;\n  flex-direction: column;\n  align-items: center;\n  background-color: #f5f5f7;\n  padding: 80px 24px;\n}",
    css
)

css = re.sub(
    r"\.agentPill\s*\{[^}]+\}",
    ".agentPill {\n  display: flex;\n  flex-direction: column;\n  gap: 8px;\n  background: #ffffff;\n  border: none;\n  border-radius: 12px;\n  padding: 16px;\n  flex: 1;\n  min-width: 0;\n  transition: all var(--transition-normal);\n  box-shadow: rgba(0, 0, 0, 0.05) 3px 5px 20px 0px;\n}",
    css
)

# Text inside agentPill must be dark even if global mode is dark
css = re.sub(r"(\.agentPillName\s*\{[^\}]*color:\s*)[^;]+(;)", r"\1#1d1d1f\2", css)
css = re.sub(r"(\.agentPillCharName\s*\{[^\}]*color:\s*)[^;]+(;)", r"\1#86868b\2", css)
css = re.sub(r"(\.agentPillTags\s*\{[^\}]*color:\s*)[^;]+(;)", r"\1#86868b\2", css)

with open(css_file, "w") as f:
    f.write(css)

print("Page CSS patched!")
