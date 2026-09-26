"""Check your Foundry setup before the demo:  python -m scripts.smoke_test"""
import asyncio

from app import config, content_safety
from app.pipeline import analyze_comment


def main() -> None:
    print(f"Mode: {config.DEMO_MODE}")
    print("Content Safety:", content_safety.analyze("You are an idiot"))
    for text in ["Love this!", "that's such a dumb take", "nobody wants you here", "kys"]:
        a = asyncio.run(analyze_comment(text))
        errors = [s for s in a["trace"] if s["status"] == "error"]
        print(f"{text!r:32} -> {a['tier']:9} escalation={a['escalation']:16} "
              f"{'ERRORS: ' + '; '.join(e['summary'] for e in errors) if errors else 'ok'}")


if __name__ == "__main__":
    main()
