import json
import sys

evento = json.load(sys.stdin)
herramienta = evento["tool_name"]
entrada = evento["tool_input"]

objetivo= entrada.get("file_path") or entrada.get("command") or ""

if ".env" in objetivo:
    print(f"Bloqueado por el hook:{herramienta} no puede tocar .env (contiene secretos).")
    sys.exit(2)

sys.exit(0)