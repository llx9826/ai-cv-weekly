"""Verify the generated report output."""

import re
from pathlib import Path

HTML_PATH = Path(r"D:\code\python\lunaclaw-brief\output\ai_cv_weekly_03.11~03.17_20260317_224228.html")


def main():
    html = HTML_PATH.read_text(encoding="utf-8")
    body = html[html.find("<body"):]

    sections = re.findall(r"<h2[^>]*>(.*?)</h2>", body)
    print("Rendered sections:")
    for s in sections:
        clean = re.sub(r"<[^>]+>", "", s).strip()
        if clean:
            print(f"  - {clean}")

    checks = [
        ("Hero section", "text-center mb-6" in body),
        ("DaisyUI cards", "card bg-base-100" in body),
        ("Claw 锐评 badge", "badge-warning" in body),
        ("KV rows", "font-bold text-primary shrink-0" in body),
        ("Citation note", "来源验证" in body or "citation" in body.lower()),
        ("Footer brand", "ClawCat Brief" in body),
        ("No JSON leak", not re.search(r'\{["\']?\w+["\']?\s*:', body)),
        ("No score/grounding", not re.search(r"(?:score|grounding|confidence)\s*[:=]", body)),
        ("No inline style", 'style="' not in body),
        ("Tag balance", abs(body.count("<div") - body.count("</div")) <= 2),
    ]

    print()
    all_pass = True
    for name, passed in checks:
        icon = "OK" if passed else "XX"
        if not passed:
            all_pass = False
        print(f"  [{icon}] {name}")

    word_count = len(re.sub(r"<[^>]+>", "", body))
    print(f"\n  Total body chars: {word_count}")
    print(f"\n{'ALL PASS' if all_pass else 'SOME FAILED'}")


if __name__ == "__main__":
    main()
