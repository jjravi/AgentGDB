import gdb
import os
import sys
import types
import importlib
import re

OpenAI = None
g_client = None

def format_light_text(text):
  """Format text as 'light' for terminal display."""
  # Using ANSI escape code for dim text (not available in all terminals)
  return f"\033[2m{text}\033[0m"

def print_light(text):
  """Print text in light formatting, immediately flushing output."""
  sys.stdout.write(format_light_text(text))
  sys.stdout.flush()

def query_llm(x_systemMessage, x_prompt):
  # Store messages for ongoing conversation
  messages = [
    {"role": "system", "content": x_systemMessage},
    {"role": "user", "content": x_prompt}
  ]

  # Query OpenAI with streaming enabled
  stream = g_client.chat.completions.create(
    model="model-identifier",
    messages=messages,
    temperature=0.0,
    stream=True
  )

  # Process stream with immediate output
  collected_response = ""
  for chunk in stream:
    if hasattr(chunk.choices[0], 'delta') and hasattr(chunk.choices[0].delta, 'content'):
      content = chunk.choices[0].delta.content
      if content:
        # Immediately print each token
        print_light(content)
        collected_response += content
  print("") # Add newline after all tokens
  return collected_response

def gdb_llm_prompt(x_prompt, x_ask=False):
  global client

  # STAGE 1: Classify the user's intent
  f = open("system_prompts/stage1.md","r")
  system_message = f.read()

  collected_response = query_llm(system_message, x_prompt)

  # Extract the command class from the response
  # expect two lines of output:
  # <summary>
  # <command class>
  cmd_class = collected_response.split("\n")[1].strip()
  gdb_cmd = "help " + cmd_class.strip()

  # STAGE 2: Get the help for the command class
  print("(gdb) " + gdb_cmd)
  gdb_cmd_class_help = gdb.execute(gdb_cmd, to_string=True)

  ## STAGE 2.1: FILTER
  # delete everything before "List of commands:"
  gdb_cmd_class_help = gdb_cmd_class_help.split("List of commands:")[1]
  # delete everything that starts with "set "
  gdb_cmd_class_help = "\n".join([line for line in gdb_cmd_class_help.split("\n") if not line.startswith("set ")])
  # delete any whitespace
  gdb_cmd_class_help = gdb_cmd_class_help.strip()

  # STAGE 3: Select the most relevant command from the available commands in the class
  f = open("system_prompts/stage3.md","r")
  system_message = f.read()
  system_message += "\nList of commands:\n" + gdb_cmd_class_help
  collected_response = query_llm(system_message, x_prompt)

  if collected_response == "":
    print_light("No command found. Please try again.")
    return

  # STAGE 4: Get the detailed help for the command
  gdb_cmd = "help " + str(collected_response).strip()
  print("(gdb) " + gdb_cmd)
  gdb_detailed_help = gdb.execute(gdb_cmd, to_string=True)

  # STAGE 5: Generate the final command
  f = open("system_prompts/stage5.md","r")
  system_message = f.read()
  system_message += "\nHelp Query:\n" + gdb_detailed_help
  final_gdb_cmd = query_llm(system_message, x_prompt)

  if final_gdb_cmd == "# No valid command":
    print_light("No valid command found. Please try again.")
    return

  print_light("Suggested command: " + str(final_gdb_cmd))

  if not x_ask:
    gdb.execute(final_gdb_cmd)


class AIGdbCommand(gdb.Command):
  def __init__(self):
    super(AIGdbCommand, self).__init__("agent", gdb.COMMAND_USER)
  def invoke(self, x_arg, from_tty):
    gdb_llm_prompt(x_arg)

class AskAIGdbCommand(gdb.Command):
  def __init__(self):
    super(AskAIGdbCommand, self).__init__("ask", gdb.COMMAND_USER)
  def invoke(self, x_arg, from_tty):
    gdb_llm_prompt(x_arg, True)

def setup_openai():
  """Setup OpenAI client - only called when needed."""
  global OpenAI
  if OpenAI is None:
    print_light("Setting up OpenAI client...")
    print("")
    # Extend Python search path for site-packages only when needed
    if not hasattr(setup_openai, 'path_extended'):
      import subprocess
      paths = subprocess.check_output('python -c "import os,sys;print(os.linesep.join(sys.path).strip())"', shell=True).decode("utf-8").split()
      sys.path.extend(paths)
      setup_openai.path_extended = True
    
    try:
      from openai import OpenAI as OpenAIClient
      OpenAI = OpenAIClient
    except ImportError:
      print("Error: OpenAI package not found. Please install it using: pip install openai")
      raise

if __name__ == "__main__":
  AIGdbCommand()
  AskAIGdbCommand()
  setup_openai()

  # g_client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")
  g_client = OpenAI(base_url="http://10.0.0.208:1234/v1", api_key="lm-studio")
