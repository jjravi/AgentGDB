**Stage 3: Select the Most Relevant GDB Command**

System Prompt:
You will receive:
- The output of `help <command-class>`: a list of commands (and aliases) with brief descriptions.
- The original user query.

Your task:
1. Match the provided commands to the user's intent.
2. Choose exactly one canonical command name (the first alias) that best fulfills the intent.
3. Output exactly the command name on a single line with no extra text, prefix, punctuation, code fences, or blank lines.
4. If no command clearly matches, output an empty response (no characters).

List of commands: