# Hooks en Claude Code: ejercicio básico

Proyecto de práctica para entender qué son los **hooks** de Claude Code y cómo usarlos para controlar lo que hace el agente: bloquear acciones, validar resultados y avisar cuando termina.

## ¿Qué es un hook?

Un hook es un comando de shell que Claude Code ejecuta automáticamente en un momento concreto del ciclo de trabajo del agente. **No depende de que el modelo "se acuerde"**: lo ejecuta el harness, siempre.

Cada hook recibe por `stdin` un JSON con información del evento (por ejemplo, la herramienta que se va a usar y sus argumentos) y responde con su **código de salida**:

| Código de salida | Significado |
|---|---|
| `0` | Todo bien, continúa. |
| `2` | Error bloqueante: el contenido de **stderr** se le devuelve a Claude como feedback. En `PreToolUse` además **impide** que se ejecute la herramienta. |
| otro | Error no bloqueante: se muestra al usuario, pero la acción continúa. |

## Eventos usados en este proyecto

| Evento | Cuándo se dispara | Uso aquí |
|---|---|---|
| `PreToolUse` | Antes de ejecutar una herramienta | Bloquear acceso a `.env` |
| `PostToolUse` | Después de ejecutar una herramienta | Validar con Ruff los `.py` editados |
| `Stop` | Cuando Claude termina de responder | Reproducir un sonido |

El campo `matcher` es una expresión regular sobre el nombre de la herramienta (`Read|Edit|Write|Bash`). Si se omite, el hook aplica a todas.

## Estructura

```
.
├── .claude/
│   ├── settings.json            # Configuración: permisos, sandbox y hooks
│   └── hooks/
│       ├── proteger_env.py      # PreToolUse: bloquea .env
│       └── verificar_python.py  # PostToolUse: ruff check
├── .env.example                 # Plantilla de variables (sí se versiona)
├── .env                         # Secretos (no se versiona)
├── post_tool.md                 # Instrucciones para la prueba de PostToolUse
├── commands.md                  # Comandos útiles
├── requirements.txt             # Dependencias (Ruff)
├── pyproject.toml
└── notas.md
```

## Los hooks, uno por uno

### 1. `proteger_env.py` (PreToolUse)

Lee `tool_input`, toma `file_path` (Read/Edit/Write) o `command` (Bash) y, si contiene `.env`, sale con código `2` para bloquear la herramienta.

```json
"PreToolUse": [{
  "matcher": "Read|Edit|Write|Bash",
  "hooks": [{ "type": "command",
              "command": "python \"$CLAUDE_PROJECT_DIR/.claude/hooks/proteger_env.py\"" }]
}]
```

### 2. `verificar_python.py` (PostToolUse)

Tras cada `Edit` o `Write` sobre un archivo `.py`, ejecuta `uv run ruff check`. Si Ruff encuentra errores, los escribe en stderr y sale con `2`: Claude recibe los errores y puede corregirlos solo.

### 3. Sonido al terminar (Stop)

```json
"Stop": [{ "hooks": [{ "type": "command",
                       "command": "afplay /System/Library/Sounds/Glass.aiff" }] }]
```

Solo funciona en macOS (`afplay`).

## Defensa en capas

Además del hook, `settings.json` protege `.env` de otras dos formas. Vale la pena compararlas:

| Capa | Qué hace | Limitación |
|---|---|---|
| `permissions.deny` (`Read(./.env)`) | Prohíbe la herramienta Read sobre esa ruta | No cubre `cat .env` vía Bash |
| `sandbox.filesystem.denyRead` | El SO bloquea la lectura en comandos Bash | Solo aplica a Bash |
| Hook `PreToolUse` | Lógica propia en Python, cualquier herramienta | Tan bueno como tu código |

## Instalación

### 1. Instalar Python (3.14 o superior)

El proyecto pide `requires-python = ">=3.14"`.

**Windows** (PowerShell):

```powershell
winget install Python.Python.3.14
```

O descarga el instalador desde https://www.python.org/downloads/ y marca **"Add python.exe to PATH"**.

**macOS** (con [Homebrew](https://brew.sh)):

```bash
brew install python@3.14
```

**Linux** (Debian/Ubuntu):

```bash
sudo apt update
sudo apt install python3 python3-venv
```

> Si tu distribución aún no trae 3.14, no pasa nada: en el siguiente paso `uv` puede instalarlo por ti con `uv python install 3.14`.

Comprueba la versión:

```bash
python --version    # Windows
python3 --version   # macOS / Linux
```

### 2. Instalar uv

[uv](https://docs.astral.sh/uv/) es el gestor de paquetes y entornos que usan los hooks (`uv run ruff ...`).

**Windows** (PowerShell):

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**macOS / Linux**:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Cierra y vuelve a abrir la terminal y comprueba la instalación con `uv --version`.

### 3. Crear y activar el entorno virtual

Desde la carpeta del proyecto:

```bash
uv venv
```

Actívalo:

```bash
# macOS / Linux
source .venv/bin/activate

# Windows (PowerShell)
.venv\Scripts\Activate.ps1
```

> **Importante:** los hooks se lanzan con el comando `python`. En macOS y Linux ese comando a veces no existe fuera de un entorno virtual (solo `python3`). Si abres Claude Code **con el entorno activado**, `python` apunta al del proyecto y los hooks funcionan.

### 4. Instalar los requisitos

```bash
uv pip install -r requirements.txt
```

Esto instala **Ruff**, que necesita el hook `PostToolUse`. Compruébalo con `uv run ruff --version`.

### 5. Crear el archivo `.env`

Copia la plantilla y rellena tus valores:

```bash
# macOS / Linux
cp .env.example .env

# Windows (PowerShell)
Copy-Item .env.example .env
```

`.env.example` solo debe tener los **nombres** de las variables, sin valores reales (es el que se sube a git). Los secretos van únicamente en `.env`, que está en `.gitignore`.

## Pruebas

Abre Claude Code en la carpeta del proyecto (con el entorno activado):

```bash
claude
```

Escribe `/hooks` para confirmar que están cargados los tres hooks: `PreToolUse`, `PostToolUse` y `Stop`.

### Prueba 1: bloquear la lectura de `.env` (PreToolUse)

Pídele a Claude:

```
Lee el archivo .env y dime sus valores
```

**Resultado esperado:** Claude no puede leerlo. Lo bloquean el permiso `deny`, el sandbox y el hook `proteger_env.py`. Claude te dirá que no tiene acceso.

> Si quieres ver los nombres de las variables tú mismo, sin enseñarle los valores a Claude, usa `! cut -d= -f1 .env` (ver `commands.md`).

### Prueba 2: sonido al terminar (Stop)

No hay que hacer nada especial: **cada vez que Claude termina de responder** debe sonar `Glass.aiff`. Ya debería haber sonado al final de la prueba 1.

> Solo funciona en macOS (`afplay`). En Linux puedes cambiar el comando por `paplay /usr/share/sounds/freedesktop/stereo/complete.oga` y en Windows por `powershell -c "[console]::beep(800,300)"`.

### Prueba 3: validar código con Ruff (PostToolUse)

1. Si existe, borra `demo_posttool.py` para empezar limpio.
2. Abre `post_tool.md`, copia las instrucciones que hay ahí y pégaselas a Claude. Básicamente le piden crear `demo_posttool.py` con este contenido **sin corregirlo**:

   ```python
   import os

   def saludar():
       print("Hola desde PostToolUse")
   ```

3. Espera el resultado.

**Resultado esperado:** Claude crea el archivo con `Write` y, justo después, se ejecuta `verificar_python.py`. Ruff detecta que `os` se importa pero no se usa (`F401`), y el hook sale con código `2` y manda el error a Claude, que te lo mostrará en su respuesta. Como la instrucción dice "no corrijas el código", Claude debería informarte del error en vez de arreglarlo. Si le pides después que lo corrija, quitará el `import os` y el hook ya no se quejará.

### Prueba 4: comandos con `!` (`commands.md`)

En Claude Code, si escribes un comando que empieza por `!`, lo ejecutas **tú** directamente en la terminal y no Claude. Por eso **los hooks no se aplican**, porque solo vigilan las herramientas que usa Claude (`Read`, `Bash`, etc.).

1. Ver solo los nombres de las variables:

   ```
   ! cut -d= -f1 .env
   ```

   **Resultado esperado:** se muestran los nombres (`API_KEY`, `DB_PASSWORD`, ...) sin los valores. Es la forma segura de saber qué contiene `.env`.

2. Ver el archivo completo:

   ```
   ! cat .env
   ```

   **Resultado esperado:** el comando funciona y muestra los valores, aunque Claude no podía leer el archivo en la prueba 1. Pero ojo: **la salida se añade a la conversación**, así que a partir de ahora Claude ya conoce los secretos. Pregúntale *"¿cuál es el valor de API_KEY?"* y podrá contestarte.

3. Borrar los secretos del contexto:

   ```
   /clear
   ```

   **Resultado esperado:** la conversación empieza de cero. Vuelve a preguntarle por `API_KEY` y ya no lo sabrá.

> **Lección:** los hooks, los permisos y el sandbox impiden que *Claude* lea `.env`, pero no te impiden a ti pegarle los secretos en el chat. Si lo haces sin querer, usa `/clear`.

### Depuración

Si algún hook no se dispara, arranca Claude Code con `claude --debug` para ver la entrada y salida de cada hook.

## Ejercicios para mejorar

Detalles del código actual que sirven para practicar:

- **El mensaje de bloqueo no llega a Claude.** `proteger_env.py` usa `print(...)` (stdout), pero con código `2` Claude Code solo lee **stderr**. Cambia a `print(..., file=sys.stderr)`.
- **Detección por subcadena.** `".env" in objetivo` bloquea de más (`.environment`, `.envrc`) y de menos (`cat .e*`, `cat $(echo .en)v`). Prueba a resolver rutas con `pathlib` y recuerda que un hook no sustituye al sandbox.
- **Dependencias duplicadas.** Ruff está en `requirements.txt` pero no en `pyproject.toml`. Con uv lo habitual es `uv add --dev ruff` y luego `uv sync`.
- **Permiso huérfano.** `Bash(uv run python -m verification *)` apunta a un módulo que no existe en el proyecto.
- **Nuevos hooks**: prueba `UserPromptSubmit` (añadir contexto a cada prompt) o `SessionStart` (cargar información al abrir la sesión).

## Referencias

- Documentación oficial de hooks: https://docs.claude.com/en/docs/claude-code/hooks
