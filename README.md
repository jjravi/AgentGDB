# AgentGDB

Supercharge your GDB/LLDB debugging with the power of LLMs!

AgentGDB is a tool that brings natural language understanding to the GDB/LLDB debugger. Describe what you want to do in plain English, and AgentGDB will translate your request into the appropriate GDB/LLDB commands—optionally explaining its reasoning and leveraging help commands to ensure accuracy. Focus on solving bugs, not memorizing debugger syntax!

![AgentGDB Screenshot](TODO)

## Contents

1. [Installation](#installation)
2. [Updating](#updating)
3. [Usage](#usage)
4. [Features](#features)
5. [Contributing](#contributing)
6. [Staying Updated](#staying-updated)

---

## Installation

First, ensure you have Python 3.7+ and [pip](https://pip.pypa.io/en/stable/installation/) installed.

Clone the repository and set up a virtual environment:

```sh
git clone https://github.com/jjravi/AgentGDB.git
cd AgentGDB
python -m venv openai-env
source openai-env/bin/activate
pip install openai
```

You’ll also need to have LLDB installed (comes with Xcode on macOS, or via your package manager on Linux).

## Updating

To update AgentGDB, simply pull the latest changes and re-install dependencies:

```sh
git pull origin main
pip install -U openai
```

## Usage

1. **Import the AgentGDB script in LLDB:**

   Add the following to your `~/.lldbinit`:

   ```sh
   command script import /full/path/to/AgentGDB/openai_lldb.py
   ```

2. **Start LLDB as usual:**

   ```sh
   lldb your_program
   ```

3. **Use the `llm` command:**

   You can now use natural language in LLDB:

   ```
   (lldb) llm set a breakpoint at line 42 in main.cpp
   ```

   AgentGDB will:
   - Query the LLM for the correct LLDB command(s)
   - Use `help` commands to verify and learn about LLDB features
   - Show you the reasoning and the commands before executing them

4. **Example:**

   ```
   (lldb) llm print the value of variable foo
   ```

   The LLM might respond with:

   ```
   To print the value of `foo`, use the following command:
   ```lldb
   print foo
   ```
   ```

   Only the command inside the code block will be executed.

## Features

- **Natural Language to LLDB:** Describe your intent, and AgentGDB figures out the command.
- **LLDB Help Integration:** The agent uses `help` commands to learn and verify before acting.
- **Markdown Command Parsing:** Only executes commands inside ```lldb code blocks for safety.
- **Streaming Output:** See the LLM’s thought process and command generation in real time.
- **Session Logging:** All interactions are logged for review and reproducibility.

## Contributing

Contributions are welcome! Please open issues or pull requests on [GitHub](https://github.com/jjravi/AgentGDB).

---

**Note:** AgentGDB is under active development. Feedback and suggestions are highly appreciated!

## GDB
gdb_test.py implements this for gdb. You still need to have the openai Python package installed. It is recommmended to use a virtual environment like instructed above. Pass the Python script to gdb with the -x argument.

```
gdb -x ./gdb_test.py <path to binary>
```