import gdb
import os
import sys
import types
import importlib
import re

# --- Constants ---
VERBOSE = False
OPENAI_API_KEY = "lm-studio"
OPENAI_BASE_URL = "http://10.0.0.208:1234/v1" # Or "http://localhost:1234/v1"
LLM_MODEL_IDENTIFIER = "model-identifier" # Replace with your actual model
NO_VALID_COMMAND_MARKER = "# No valid command"

PROMPT_FILES_DIR = "system_prompts"
STAGE1_PROMPT_FILE = os.path.join(PROMPT_FILES_DIR, "stage1.md")
STAGE3_PROMPT_FILE = os.path.join(PROMPT_FILES_DIR, "stage3.md")
STAGE5_PROMPT_FILE = os.path.join(PROMPT_FILES_DIR, "stage5.md")

# --- Global Variables ---
g_openai_client = None
g_system_prompts = {
    "stage1": None,
    "stage3": None,
    "stage5": None,
}

def format_light_text(text):
  """Format text as 'light' for terminal display."""
  # Using ANSI escape code for dim text (not available in all terminals)
  return f"\033[2m{text}\033[0m"

def print_light(text):
  """Print text in light formatting, immediately flushing output."""
  sys.stdout.write(format_light_text(text))
  sys.stdout.flush()

def print_debug(text):
  """Print text in debug formatting, immediately flushing output."""
  if VERBOSE:
    sys.stdout.write(format_light_text(text))
    sys.stdout.flush()

def load_system_prompts():
  """Loads all system prompts from their files."""
  global g_system_prompts
  prompt_map = {
    "stage1": STAGE1_PROMPT_FILE,
    "stage3": STAGE3_PROMPT_FILE,
    "stage5": STAGE5_PROMPT_FILE,
  }
  for stage, filepath in prompt_map.items():
    try:
      with open(filepath, "r") as f:
        g_system_prompts[stage] = f.read()
    except FileNotFoundError:
      print(f"Error: System prompt file not found: {filepath}")
      # Potentially raise an exception or handle this more gracefully
      return False
    except IOError as e:
      print(f"Error reading system prompt file {filepath}: {e}")
      return False
  return True

def ensure_openai_client_ready():
  """
  Initializes the OpenAI client and loads system prompts if not already done.
  Returns True if successful, False otherwise.
  """
  global g_openai_client
  if g_openai_client is None:
    print_debug("Setting up OpenAI client...")
    # Extend Python search path for site-packages only when needed
    if not hasattr(ensure_openai_client_ready, 'path_extended'):
      try:
        import subprocess
        # Use sys.executable to ensure we're using the same python interpreter
        paths_str = subprocess.check_output(
            ["python", '-c', "import os,sys;print(os.linesep.join(sys.path).strip())"]
        ).decode("utf-8")
        paths = paths_str.split(os.linesep)
        for p in paths:
            if p not in sys.path: # Avoid duplicates
                sys.path.append(p)
        ensure_openai_client_ready.path_extended = True
      except subprocess.CalledProcessError as e:
        print(f"Error extending Python path: {e}")
        return False
      except Exception as e:
        print(f"An unexpected error occurred while extending Python path: {e}")
        return False
    
    try:
      from openai import OpenAI as OpenAIClient
    except ImportError:
      print("Error: OpenAI package not found. Please install it using: pip install openai")
      raise

    try:
      # OpenAIClient is already imported at the top
      g_openai_client = OpenAIClient(base_url=OPENAI_BASE_URL, api_key=OPENAI_API_KEY)
      print_debug("Success.")
      print_debug("\n")
    except Exception as e: # Catching a broader exception for client initialization
      print(f"Error: Failed to initialize OpenAI client: {e}")
      print("Please ensure your OpenAI server is running and accessible.")
      print(f"Attempted to connect to: {OPENAI_BASE_URL}")
      return False

  # Load prompts if not already loaded
  if any(p is None for p in g_system_prompts.values()):
    print_debug("Loading system prompts...")
    if not load_system_prompts():
      print("Failed to load system prompts. Aborting.")
      return False
    print_debug("Success.")
    print_debug("\n")
  return True

def query_llm(x_system_message, x_prompt):
  """Queries the LLM and returns the collected response."""
  global g_openai_client
  if not g_openai_client:
    print("OpenAI client not available.")
    return "" # Or raise an exception

  messages = [
    {"role": "system", "content": x_system_message},
    {"role": "user", "content": x_prompt}
  ]

  try:
    stream = g_openai_client.chat.completions.create(
      model=LLM_MODEL_IDENTIFIER,
      messages=messages,
      temperature=0.0,
      stream=True
    )
    collected_response = ""
    for chunk in stream:
      if hasattr(chunk.choices[0], 'delta') and hasattr(chunk.choices[0].delta, 'content'):
        content = chunk.choices[0].delta.content
        if content:
          print_light(content)
          collected_response += content
    print("") # Add newline after all tokens
    return collected_response.strip()
  except Exception as e: # Catching a broader exception for API calls
    print(f"Error querying LLM: {e}")
    return ""

def execute_gdb_command(gdb_cmd_str, to_string=True):
    """Executes a GDB command and handles potential errors."""
    try:
        print("(gdb) " + gdb_cmd_str)
        output = gdb.execute(gdb_cmd_str, to_string=to_string)
        return output
    except gdb.error as e:
        print(f"Error executing GDB command '{gdb_cmd_str}': {e}")
        return None # Indicate failure
    except Exception as e: # Catch other potential errors
        print(f"An unexpected error occurred while executing GDB command '{gdb_cmd_str}': {e}")
        return None

def gdb_llm_prompt(x_prompt, x_ask=False):
  global g_system_prompts

  if not ensure_openai_client_ready():
    return # Client or prompts failed to initialize

  # STAGE 1: Classify the user's intent
  system_message_stage1 = g_system_prompts.get("stage1")
  if not system_message_stage1:
    print("Error: Stage 1 system prompt not loaded. Aborting.\n")
    return

  print_debug("Stage 1: Classifying command...\n")
  collected_response_stage1 = query_llm(system_message_stage1, x_prompt)
  if not collected_response_stage1:
    print("Stage 1: Failed to get command class from LLM. Please try again.\n")
    return

  response_lines = collected_response_stage1.split("\n")
  if len(response_lines) < 2:
    print(f"Stage 1: Unexpected LLM response format for command class: '{collected_response_stage1}'. Expected summary and command class on separate lines.\n")
    return
  cmd_class = response_lines[1].strip()
  if not cmd_class:
    print("Stage 1: LLM did not provide a command class. Please try again.\n")
    return
  
  gdb_cmd_stage2 = "help " + cmd_class

  # STAGE 2: Get the help for the command class
  print_debug(f"Stage 2: Getting help for command class '{cmd_class}'...\n")
  gdb_cmd_class_help = execute_gdb_command(gdb_cmd_stage2, to_string=True)
  if gdb_cmd_class_help is None: # Error handled in execute_gdb_command
    return

  ## STAGE 2.1: FILTER
  # Robustly find "List of commands:"
  list_of_commands_marker = "List of commands:"
  marker_pos = gdb_cmd_class_help.find(list_of_commands_marker)
  if marker_pos == -1:
      print(f"Stage 2.1: Could not find '{list_of_commands_marker}' in help output for '{cmd_class}'. The help format might have changed or the class is incorrect.\n")
      # print_light(f"Full help output received:\\n{gdb_cmd_class_help}") # Optional: for debugging
      return
  
  gdb_cmd_class_help_filtered = gdb_cmd_class_help[marker_pos + len(list_of_commands_marker):]
  gdb_cmd_class_help_filtered = "\n".join([line for line in gdb_cmd_class_help_filtered.split("\n") if not line.strip().startswith("set ")])
  gdb_cmd_class_help_filtered = gdb_cmd_class_help_filtered.strip()

  if not gdb_cmd_class_help_filtered:
      print(f"Stage 2.1: No commands found for class '{cmd_class}' after filtering. Or all commands started with 'set '.\n")
      return

  # STAGE 3: Select the most relevant command
  system_message_stage3 = g_system_prompts.get("stage3")
  if not system_message_stage3:
    print("Error: Stage 3 system prompt not loaded. Aborting.\n")
    return
  
  prompt_stage3 = system_message_stage3 + "\nList of commands:\n" + gdb_cmd_class_help_filtered
  print_debug("Stage 3: Selecting specific command...\n")
  selected_command = query_llm(prompt_stage3, x_prompt)

  if not selected_command:
    print("Stage 3: LLM failed to select a command. Please try again.\n")
    return
  if selected_command == NO_VALID_COMMAND_MARKER: # Assuming LLM might return this for clarity
      print("Stage 3: LLM indicated no specific command found for your query.\n")
      return

  # STAGE 4: Get the detailed help for the selected command
  gdb_cmd_stage4 = "help " + selected_command.strip()
  print_debug(f"Stage 4: Getting detailed help for command '{selected_command}'...\n")
  gdb_detailed_help = execute_gdb_command(gdb_cmd_stage4, to_string=True)
  if gdb_detailed_help is None:
    return

  # STAGE 5: Generate the final command
  system_message_stage5 = g_system_prompts.get("stage5")
  if not system_message_stage5:
    print("Error: Stage 5 system prompt not loaded. Aborting.\n")
    return

  prompt_stage5 = system_message_stage5 + "\nHelp Query:\n" + gdb_detailed_help
  print_debug("Stage 5: Generating final GDB command...\n")
  final_gdb_cmd = query_llm(prompt_stage5, x_prompt)

  if not final_gdb_cmd:
    print("Stage 5: LLM failed to generate the final command. Please try again.\n")
    return
  if final_gdb_cmd == NO_VALID_COMMAND_MARKER:
    print("Stage 5: LLM indicated no valid command could be generated based on the help provided. Please try again or rephrase your query.\n")
    return

  if x_ask:
    print_light("Suggested command: " + final_gdb_cmd + "\n")
    # Optionally, ask for confirmation here before executing
    confirmation = input("Execute this command? (y/N): ")
    if confirmation.lower() == 'y':
      execute_gdb_command(final_gdb_cmd, to_string=False)
  else:
    execute_gdb_command(final_gdb_cmd, to_string=True)

class AgentGdbCommand(gdb.Command):
  def __init__(self):
    super(AgentGdbCommand, self).__init__("agent", gdb.COMMAND_USER)
  def invoke(self, x_arg, from_tty):
    if not x_arg:
        print_light("Usage: agent <natural language query>")
        return
    gdb_llm_prompt(x_arg)

class AskGdbCommand(gdb.Command):
  def __init__(self):
    super(AskGdbCommand, self).__init__("ask", gdb.COMMAND_USER)
  def invoke(self, x_arg, from_tty):
    if not x_arg:
        print_light("Usage: ask <natural language query>")
        return
    gdb_llm_prompt(x_arg, True)

if __name__ == "__main__":
  if not ensure_openai_client_ready():
    print("Failed to initialize AI GDB agent during startup. Some features might not work.")
    print("Please check your OpenAI client configuration and prompt files.")
  else:
    print_light("(gdb) GDB AI Agent installed. Type 'agent' or 'ask' followed by your query to use.\n")
  AgentGdbCommand()
  AskGdbCommand()
