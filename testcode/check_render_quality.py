"""Quick quality check on rendered HTML files."""

import re
import sys
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent.parent / "output" / "render_test"


def check_html(filepath: Path, label: str):
    html = filepath.read_text(encoding="utf-8")
    print(f"=== {label} ({filepath.name}) ===")

    checks = [
        ("data-theme=light", r'data-theme="light"', True),
        ("DaisyUI CDN", r"cdn\.jsdelivr\.net/npm/daisyui", True),
        ("Tailwind CDN", r"cdn\.tailwindcss\.com", True),
        ("max-w-720px container", r"max-w-\[720px\]", True),
        ("Hero section (centered)", r"text-center mb-6", True),
        ("Stats bar (flex)", r"flex justify-center gap-6", True),
        ("Claw 锐评 card", r"badge-warning", True),
        ("Item card (DaisyUI)", r"card bg-base-100 border", True),
        ("KV row (flex)", r"font-bold text-primary shrink-0", True),
        ("Citation note", r"citation|来源验证", True),
        ("Footer brand", r"ClawCat Brief", True),
        ("No JSON/dict leak", r"\{['\"]?\w+['\"]?\s*:", False),
        ("No score/grounding", r"(?:score|grounding|confidence)\s*[:=]", False),
        ("No inline style", r' style="[^"]+?"', False),
    ]

    all_pass = True
    for name, pattern, expect_found in checks:
        found = bool(re.search(pattern, html))
        passed = found == expect_found
        icon = "OK" if passed else "XX"
        if not passed:
            all_pass = False
        print(f"  [{icon}] {name}")

    tag_balance = html.count("<div") - html.count("</div")
    if abs(tag_balance) > 2:
        print(f"  [XX] Tag balance: <div>={html.count('<div')}, </div>={html.count('</div')}")
        all_pass = False
    else:
        print(f"  [OK] Tag balance OK (diff={tag_balance})")

    print()
    return all_pass


def main():
    htmls = sorted(OUTPUT.glob("*_223207.html"))
    if not htmls:
        htmls = sorted(OUTPUT.glob("*.html"))[-3:]

    labels = ["AI Weekly", "OCR Weekly", "Finance Daily"]
    results = []
    for f, label in zip(htmls, labels):
        results.append(check_html(f, label))

    if all(results):
        print("ALL CHECKS PASSED")
    else:
        print("SOME CHECKS FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
