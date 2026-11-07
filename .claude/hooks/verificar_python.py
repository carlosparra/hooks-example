
import json
import subprocess
import sys
from pathlib import Path

def main():
    event = json.load(sys.stdin)

    file_path = event.get("tool_input", {}).get("file_path")
    if not file_path:
        return

    path = Path(file_path).resolve()

    # Solo archivos Python existentes
    if path.suffix != ".py" or not path.is_file():
        return

    result = subprocess.run(
        ["uv", "run", "ruff", "check", str(path)],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(
            f"Validación Ruff fallida:\n{result.stdout}\n{result.stderr}",
            file=sys.stderr,
        )
        sys.exit(2)

if __name__ == "__main__":
    main()
