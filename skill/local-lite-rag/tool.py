from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv


def bootstrap() -> None:
    current_dir = Path(__file__).resolve().parent
    project_root = current_dir.parent.parent
    load_dotenv(current_dir / ".env", override=False)
    sys.path.insert(0, str(project_root / "src"))


def main() -> None:
    bootstrap()
    from lite_rag.cli import main as cli_main

    cli_main()


if __name__ == "__main__":
    main()
