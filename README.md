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

1. **Start GDB with AgentGDB:**

   ```sh
   gdb -x $(python -c "import agentgdb; print(agentgdb.__file__)") your_program
   ```

   Or add to your `~/.gdbinit`:

   ```
   source $(python -c "import agentgdb; print(agentgdb.__file__)")
   ```

2. **Use the natural language commands:**

   You can now use natural language in GDB with two commands:
   
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