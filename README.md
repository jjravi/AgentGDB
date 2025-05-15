# AgentGDB

Supercharge your GDB debugging with the power of LLMs!

AgentGDB is a tool that brings natural language understanding to the GDB debugger. Describe what you want to do in plain English, and AgentGDB will translate your request into the appropriate GDB commands. Focus on solving bugs, not memorizing debugger syntax!

![AgentGDB Screenshot](TODO)

## Contents

1. [Installation](#installation)
2. [Updating](#updating)
3. [Usage](#usage)
4. [Features](#features)
5. [Contributing](#contributing)

---

## Installation

You can install AgentGDB using pip:

```sh
pip install agentgdb
```

Alternatively, you can install from source:

```sh
git clone https://github.com/jjravi/AgentGDB.git
cd AgentGDB
python -m venv openai-env
source openai-env/bin/activate
pip install -e .
```

You'll need to have GDB installed on your system.

## Updating

To update AgentGDB, simply run:

```sh
pip install -U agentgdb
```

Or if installed from source:

```sh
git pull origin main
pip install -e .
```

## Usage

To use AgentGDB, you need to configure GDB to find the AgentGDB package and its dependencies. The recommended way is to add the following to your `~/.gdbinit` file:

```python
# In ~/.gdbinit
python
import sys
import subprocess
import os

try:
    env_python = "python3"  # Or "python", or e.g., "/path/to/venv/bin/python"

    paths_str = subprocess.check_output(
        [env_python, "-c", "import sys, os; print(os.linesep.join(sys.path))"],
        stderr=subprocess.PIPE
    ).decode("utf-8")

    for p in paths_str.split(os.linesep):
        if p and os.path.isdir(p) and p not in sys.path:
            sys.path.append(p)

    import agentgdb
    gdb.execute(f"source {agentgdb.MAIN_SCRIPT_PATH}") # load config and register GDB commands.

except FileNotFoundError:
    print(f"[AgentGDB] Error: Python executable '{env_python}' not found. Please check the path in your .gdbinit.")
except subprocess.CalledProcessError as e:
    error_message = e.stderr.decode().strip() if e.stderr else str(e)
    print(f"[AgentGDB] Error getting sys.path from '{env_python}': {error_message}")
    print(f"[AgentGDB] Ensure '{env_python}' is a valid Python interpreter and has the 'agentgdb' package and its dependencies (like 'openai') installed.")
except ImportError:
    print("[AgentGDB] Error: Could not import 'agentgdb' package after setting sys.path.")
    print(f"[AgentGDB] This usually means 'agentgdb' is not installed in the Python environment targeted by '{env_python}'.")
except Exception as e:
    print(f"[AgentGDB] An unexpected error occurred during AgentGDB setup: {e}")

end
```

Once your `~/.gdbinit` is configured, start GDB as usual:

```sh
gdb your_program
```

Then, you can use the natural language commands:

- `agent`: Executes the command directly
- `ask`: Shows the suggested command and asks for confirmation before execution

Examples:
```
(gdb) agent show all breakpoints
(gdb) ask print the value of variable x
```

## Features

- **Natural Language to GDB:** Describe your intent, and AgentGDB figures out the command.
- **Multi-stage Processing:** 
  1. Classifies your query into GDB command categories
  2. Gets help for relevant command class
  3. Selects the most appropriate command
  4. Gets detailed help for the selected command
  5. Generates the exact GDB command to accomplish your intent
- **Two Interaction Modes:** Direct execution with `agent` or confirmation-based with `ask`
- **Streaming Output:** See the LLM's thought process and command generation in real time.

## Contributing

Contributions are welcome! Please open issues or pull requests on [GitHub](https://github.com/jjravi/AgentGDB).

---

**Note:** AgentGDB is under active development. Feedback and suggestions are highly appreciated!