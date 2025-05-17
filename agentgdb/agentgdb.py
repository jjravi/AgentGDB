import gdb
import os
import sys
import types
import importlib
import re
import configparser

# --- Constants ---

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Controls whether debug messages are displayed
# This will be overwritten by config file if present
VERBOSE = False

# Default values for OpenAI configuration
DEFAULT_OPENAI_API_KEY = "lm-studio"
DEFAULT_OPENAI_BASE_URL = "http://localhost:1234/v1"
DEFAULT_LLM_MODEL_IDENTIFIER = "model-identifier"

NO_VALID_COMMAND_MARKER = "# No valid command"

PROMPT_FILES_DIR = os.path.join(_BASE_DIR, "system_prompts")
STAGE1_PROMPT_FILE = os.path.join(PROMPT_FILES_DIR, "stage1.md")
STAGE3_PROMPT_FILE = os.path.join(PROMPT_FILES_DIR, "stage3.md")
STAGE5_PROMPT_FILE = os.path.join(PROMPT_FILES_DIR, "stage5.md")

CONFIG_FILE_PATH = os.path.expanduser("~/.agentgdb_config.ini")
CREDENTIALS_SECTION = "Credentials"
DEBUG_SECTION = "Debug"

# --- Global Variables ---
g_openai_client = None
g_openai_api_key = None
g_openai_base_url = None
g_llm_model_identifier = None

g_system_prompts = {
    "stage1": None,
    "stage3": None,
    "stage5": None,
}

def format_llm_text(text):
    """Format text as 'light' for LLM output display."""
    return f"\033[2m{text}\033[0m"

def print_llm(text):
    """Print LLM output in light formatting, immediately flushing output."""
    sys.stdout.write(format_llm_text(text))
    sys.stdout.flush()

def format_error_text(text):
    """Format text as 'error' for terminal display."""
    if text.startswith("[AgentGDB] "):
        return f"\033[91m{text}\033[0m"
    return f"\033[91m[AgentGDB] {text}\033[0m"

def print_error(text):
    """Print text in error formatting, immediately flushing output."""
    sys.stderr.write(format_error_text(text))
    sys.stderr.write("\n")
    sys.stderr.flush()

def print_verbose(text):
    """Print verbose debug information, only if VERBOSE is True."""
    if VERBOSE:
        sys.stdout.write(text)
        sys.stdout.write("\n")
        sys.stdout.flush()

def set_verbose(value):
    """Set the VERBOSE flag to control debug output."""
    global VERBOSE
    VERBOSE = value 

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
      print_error(f"Error: System prompt file not found: {filepath}")
      # Potentially raise an exception or handle this more gracefully
      return False
    except IOError as e:
      print_error(f"Error reading system prompt file {filepath}: {e}")
      return False
  return True

def load_plugin_configuration():
  """Loads API key, base URL, model ID, and verbose setting from the config file, using defaults if not found."""
  global g_openai_api_key, g_openai_base_url, g_llm_model_identifier, VERBOSE

  # Initialize with default values
  g_openai_api_key = DEFAULT_OPENAI_API_KEY
  g_openai_base_url = DEFAULT_OPENAI_BASE_URL
  g_llm_model_identifier = DEFAULT_LLM_MODEL_IDENTIFIER
  # VERBOSE is already initialized at the module level

  config = configparser.ConfigParser()
  loaded_from_config = {key: False for key in ["api_key", "base_url", "model_identifier", "verbose"]}

  if not os.path.exists(CONFIG_FILE_PATH):
    print(f"[AgentGDB] Info: Configuration file not found: {CONFIG_FILE_PATH}.")
    print(f"[AgentGDB] Using default settings: API Key='{DEFAULT_OPENAI_API_KEY}', Base URL='{DEFAULT_OPENAI_BASE_URL}', Model='{DEFAULT_LLM_MODEL_IDENTIFIER}', Verbose=False.")
    print(f"[AgentGDB] You can create a configuration file at {CONFIG_FILE_PATH} or use 'agentgdb_config_setup.py' to set these values.")
    return True # Defaults are set

  try:
    config.read(CONFIG_FILE_PATH)
    if CREDENTIALS_SECTION in config:
        # Attempt to load each key, retaining default if key is not in config
        temp_api_key = config.get(CREDENTIALS_SECTION, 'api_key', fallback=None)
        if temp_api_key is not None:
            g_openai_api_key = temp_api_key
            loaded_from_config["api_key"] = True

        temp_base_url = config.get(CREDENTIALS_SECTION, 'base_url', fallback=None)
        if temp_base_url is not None:
            g_openai_base_url = temp_base_url
            loaded_from_config["base_url"] = True

        temp_model_id = config.get(CREDENTIALS_SECTION, 'model_identifier', fallback=None)
        if temp_model_id is not None:
            g_llm_model_identifier = temp_model_id
            loaded_from_config["model_identifier"] = True
        
        print(f"[AgentGDB] Info: Loaded configuration from {CONFIG_FILE_PATH}.")
        if not loaded_from_config["api_key"]:
            print(f"[AgentGDB] Info: API Key not found in config, using default: '{DEFAULT_OPENAI_API_KEY}'.")
        if not loaded_from_config["base_url"]:
            print(f"[AgentGDB] Info: Base URL not found in config, using default: '{DEFAULT_OPENAI_BASE_URL}'.")
        if not loaded_from_config["model_identifier"]:
            print(f"[AgentGDB] Info: Model Identifier not found in config, using default: '{DEFAULT_LLM_MODEL_IDENTIFIER}'.")
    else:
        print(f"[AgentGDB] Info: '[{CREDENTIALS_SECTION}]' section not found in {CONFIG_FILE_PATH}. Using default settings.")
        # Defaults are already set, so no further action needed here

    # Load verbose setting from DEBUG_SECTION
    if DEBUG_SECTION in config:
        temp_verbose = config.getboolean(DEBUG_SECTION, 'verbose', fallback=None)
        if temp_verbose is not None:
            set_verbose(temp_verbose)
            loaded_from_config["verbose"] = True
            print(f"[AgentGDB] Info: Verbose mode {'enabled' if temp_verbose else 'disabled'} from config.")
    else:
        print(f"[AgentGDB] Info: '[{DEBUG_SECTION}]' section not found in {CONFIG_FILE_PATH}. Verbose mode disabled.")

    # Final check to ensure that values (either default or loaded) are not empty if they are critical
    # For now, we assume defaults are valid and non-empty. If defaults could be empty, add checks here.
    if not g_openai_api_key or not g_openai_base_url or not g_llm_model_identifier:
        print_error("Error: Critical configuration (API Key, Base URL, or Model ID) is missing or empty after loading defaults and config.")
        print_error(f"  API Key: '{g_openai_api_key}'")
        print_error(f"  Base URL: '{g_openai_base_url}'")
        print_error(f"  Model ID: '{g_llm_model_identifier}'")
        print_error(f"Please ensure these are set either in {CONFIG_FILE_PATH} or as valid defaults in the script.")
        return False
        
    return True
  except configparser.Error as e:
    print_error(f"Error reading configuration file {CONFIG_FILE_PATH}: {e}. Using default settings.")
    # Defaults are already set, but indicate that config reading failed.
    return True # Proceed with defaults despite error in config file
  except Exception as e:
    print_error(f"An unexpected error occurred while loading configuration: {e}. Using default settings.")
    return True # Proceed with defaults

def ensure_openai_client_ready():
  """
  Initializes the OpenAI client and loads system prompts if not already done.
  Returns True if successful, False otherwise.
  """
  global g_openai_client, g_openai_api_key, g_openai_base_url, g_llm_model_identifier

  # Check if we need to load configuration
  if not (g_openai_api_key and g_openai_base_url and g_llm_model_identifier):
      print_verbose("Loading plugin configuration...")
      if not load_plugin_configuration():
          print_error("Failed to load plugin configuration. Aborting OpenAI client setup.")
          return False
      print_verbose("Plugin configuration processed (defaults or loaded).")

  if g_openai_client is None:
    print_verbose("Setting up OpenAI client...")
    # Extend Python search path for site-packages only when needed
    if not hasattr(ensure_openai_client_ready, 'path_extended'):
      try:
        import subprocess
        # Use sys.executable to ensure we're using the same python interpreter
        paths_str = subprocess.check_output(["python", '-c', "import os,sys;print(os.linesep.join(sys.path).strip())"]).decode("utf-8")
        paths = paths_str.split(os.linesep)
        for p in paths:
            if p not in sys.path: # Avoid duplicates
                sys.path.append(p)
        ensure_openai_client_ready.path_extended = True
      except subprocess.CalledProcessError as e:
        print_error(f"Error extending Python path: {e}")
        return False
      except Exception as e:
        print_error(f"An unexpected error occurred while extending Python path: {e}")
        return False
    try:
      from openai import OpenAI as OpenAIClient
    except ImportError:
      print_error("Error: OpenAI package not found. Please install it using: pip install openai")
      raise

    try:
      # OpenAIClient is already imported at the top
      g_openai_client = OpenAIClient(base_url=g_openai_base_url, api_key=g_openai_api_key)
      print_verbose("Success.")
      print_verbose("\n")
    except Exception as e: # Catching a broader exception for client initialization
      print_error(f"Error: Failed to initialize OpenAI client: {e}")
      print_error("Please ensure your OpenAI server is running and accessible, and your configuration is correct.")
      print_error(f"Attempted to connect to: {g_openai_base_url} with the provided API key.")
      return False

  # Load prompts if not already loaded
  if any(p is None for p in g_system_prompts.values()):
    print_verbose("Loading system prompts...")
    if not load_system_prompts():
      print_error("Failed to load system prompts. Aborting.")
      return False
    print_verbose("Success.")
    print_verbose("\n")
  return True

def query_llm(x_system_message, x_prompt):
  """Queries the LLM and returns the collected response."""
  global g_openai_client, g_llm_model_identifier
  if not g_openai_client:
    print_error("OpenAI client not available.")
    return "" # Or raise an exception

  messages = [
    {"role": "system", "content": x_system_message},
    {"role": "user", "content": x_prompt}
  ]

  try:
    stream = g_openai_client.chat.completions.create(
      model=g_llm_model_identifier,
      messages=messages,
      temperature=0.0,
      stream=True
    )
    collected_response = ""
    for chunk in stream:
      if hasattr(chunk.choices[0], 'delta') and hasattr(chunk.choices[0].delta, 'content'):
        content = chunk.choices[0].delta.content
        if content:
          print_llm(content)
          collected_response += content
    print("") # Add newline after all tokens
    return collected_response.strip()
  except Exception as e: # Catching a broader exception for API calls
    print_error(f"Error querying LLM: {e}")
    return ""

def execute_gdb_command(gdb_cmd_str, to_string=True):
  """Executes a GDB command and handles potential errors."""
  try:
    print("(gdb) " + gdb_cmd_str)
    output = gdb.execute(gdb_cmd_str, to_string=to_string)
    return output
  except gdb.error as e:
    print_error(f"Error executing GDB command '{gdb_cmd_str}': {e}")
    return None # Indicate failure
  except Exception as e: # Catch other potential errors
    print_error(f"An unexpected error occurred while executing GDB command '{gdb_cmd_str}': {e}")
    return None

def gdb_llm_prompt(x_prompt, x_ask=False):
  global g_system_prompts

  if not ensure_openai_client_ready():
    return # Client or prompts failed to initialize

  # STAGE 1: Classify the user's intent
  system_message_stage1 = g_system_prompts.get("stage1")
  if not system_message_stage1:
    print_error("Error: Stage 1 system prompt not loaded. Aborting.\n")
    return

  print_verbose("[AgentGDB] Stage 1: Classifying command...\n")
  collected_response_stage1 = query_llm(system_message_stage1, x_prompt)
  if not collected_response_stage1:
    print_error("Stage 1: Failed to get command class from LLM. Please try again.\n")
    return

  response_lines = [line for line in collected_response_stage1.split("\n") if line.strip()] # Remove empty lines
  if len(response_lines) < 2:
    print_error(f"Stage 1: Unexpected LLM response format for command class: '{collected_response_stage1}'. Expected summary and command class on separate lines.\n")
    return
  
  # The summary is the second to last line, and the command class is the last line.
  # This handles potential <think> blocks or other multi-line preamble from the LLM.
  summary_line = response_lines[-2].strip() # Optional: use if needed
  cmd_class = response_lines[-1].strip()

  if not cmd_class:
    print_error("Stage 1: LLM did not provide a command class. Please try again.\n")
    return
  
  # Sanity check: Validate the command class is one of the 12 supported classes
  supported_command_classes = [
    "breakpoints", "data", "files", "internals", "obscure", "running", 
    "stack", "status", "support", "text-user-interface", "tracepoints", "user-defined"
  ]
  
  if cmd_class not in supported_command_classes:
    print_error(f"Stage 1: LLM provided an invalid command class: '{cmd_class}'. Expected one of: {', '.join(supported_command_classes)}.\n")
    return
  
  gdb_cmd_stage2 = "help " + cmd_class

  # STAGE 2: Get the help for the command class
  print_verbose(f"Stage 2: Getting help for command class '{cmd_class}'...\n")
  gdb_cmd_class_help = execute_gdb_command(gdb_cmd_stage2, to_string=True)
  if gdb_cmd_class_help is None: # Error handled in execute_gdb_command
    return

  ## STAGE 2.1: FILTER
  # Robustly find "List of commands:"
  list_of_commands_marker = "List of commands:"
  marker_pos = gdb_cmd_class_help.find(list_of_commands_marker)
  if marker_pos == -1:
      print_error(f"Stage 2.1: Could not find '{list_of_commands_marker}' in help output for '{cmd_class}'. The help format might have changed or the class is incorrect.\n")
      # print_verbose(f"Full help output received:\\n{gdb_cmd_class_help}") # Optional: for debugging
      return
  
  gdb_cmd_class_help_filtered = gdb_cmd_class_help[marker_pos + len(list_of_commands_marker):]
  gdb_cmd_class_help_filtered = "\n".join([line for line in gdb_cmd_class_help_filtered.split("\n") if not line.strip().startswith("set ")])
  gdb_cmd_class_help_filtered = gdb_cmd_class_help_filtered.strip()

  if not gdb_cmd_class_help_filtered:
      print_error(f"Stage 2.1: No commands found for class '{cmd_class}' after filtering. Or all commands started with 'set '.\n")
      return

  # STAGE 3: Select the most relevant command
  system_message_stage3 = g_system_prompts.get("stage3")
  if not system_message_stage3:
    print_error("Error: Stage 3 system prompt not loaded. Aborting.\n")
    return
  
  prompt_stage3 = system_message_stage3 + "\n" + gdb_cmd_class_help_filtered
  prompt_stage3 = prompt_stage3 + "\nUser Query: "
  print_verbose("Stage 3: Selecting specific command...\n")
  selected_command_raw = query_llm(prompt_stage3, x_prompt)

  if not selected_command_raw:
    print_error("Stage 3: LLM failed to select a command. Please try again.\n")
    return

  # Handle potential <think> blocks or other multi-line preamble from the LLM.
  # The actual selected command is expected to be the last non-empty line.
  selected_command_lines = [line for line in selected_command_raw.split("\n") if line.strip()]
  if not selected_command_lines:
      print_error("Stage 3: LLM returned an empty response after filtering. Please try again.\n")
      return
  selected_command = selected_command_lines[-1].strip()

  if selected_command == NO_VALID_COMMAND_MARKER: # Assuming LLM might return this for clarity
      print_error("Stage 3: LLM indicated no specific command found for your query.\n")
      return
  if not selected_command: # Added check in case the last line was empty after strip or if NO_VALID_COMMAND_MARKER was the only content
    print_error("Stage 3: LLM failed to select a command after processing the response. Please try again.\n")
    return

  # STAGE 4: Get the detailed help for the selected command
  gdb_cmd_stage4 = "help " + selected_command # .strip() is already done
  print_verbose(f"Stage 4: Getting detailed help for command '{selected_command}'...\n")
  gdb_detailed_help = execute_gdb_command(gdb_cmd_stage4, to_string=True)
  if gdb_detailed_help is None:
    return

  # STAGE 5: Generate the final command
  system_message_stage5 = g_system_prompts.get("stage5")
  if not system_message_stage5:
    print_error("Error: Stage 5 system prompt not loaded. Aborting.\n")
    return

  prompt_stage5 = system_message_stage5 + "\n" + gdb_detailed_help
  prompt_stage5 = prompt_stage5 + "\nUser Query: "
  print_verbose("Stage 5: Generating final GDB command...\n")
  final_gdb_cmd_raw = query_llm(prompt_stage5, x_prompt)

  if not final_gdb_cmd_raw.strip():
    print_error("Stage 5: LLM returned an empty or whitespace-only response. Please try again.\n")
    return

  # Assume the actual command block is the last "paragraph" (separated by blank lines).
  # This handles potential <think> blocks if they are followed by a blank line before the command(s).
  paragraphs = re.split(r'\n\s*\n', final_gdb_cmd_raw.strip())
  final_gdb_cmd = paragraphs[-1].strip() # Get the last paragraph and strip it.

  if not final_gdb_cmd:
    print_error("Stage 5: LLM failed to generate the final command (extracted block is empty). Please try again.\n")
    return
  
  if final_gdb_cmd == NO_VALID_COMMAND_MARKER:
    print_error("Stage 5: LLM indicated no valid command could be generated based on the help provided. Please try again or rephrase your query.\n")
    return

  if x_ask:
    print("[AgentGDB] Suggested command: " + final_gdb_cmd)
    # Optionally, ask for confirmation here before executing
    confirmation = input("[AgentGDB] Execute this command? (y/N): ")
    if confirmation.lower() == 'y':
      execute_gdb_command(final_gdb_cmd, to_string=False)
  else:
    execute_gdb_command(final_gdb_cmd, to_string=True)

class AgentGdbCommand(gdb.Command):
  def __init__(self):
    super(AgentGdbCommand, self).__init__("agent", gdb.COMMAND_USER)
  def invoke(self, x_arg, from_tty):
    if not x_arg:
        print("[AgentGDB] Usage: agent <natural language query>")
        return
    gdb_llm_prompt(x_arg)

class AskGdbCommand(gdb.Command):
  def __init__(self):
    super(AskGdbCommand, self).__init__("ask", gdb.COMMAND_USER)
  def invoke(self, x_arg, from_tty):
    if not x_arg:
        print("[AgentGDB] Usage: ask <natural language query>")
        return
    gdb_llm_prompt(x_arg, True)

if __name__ == "__main__": 
  # Load configuration first to ensure VERBOSE flag is set correctly
  if not load_plugin_configuration():
    print_error("Failed to load configuration during startup. Some features might not work.")
    print_error("Please check your configuration file at ~/.agentgdb_config.ini")
  
  # Now initialize the OpenAI client
  if not ensure_openai_client_ready():
    print_error("Failed to initialize AI GDB agent during startup. Some features might not work.")
    print_error("Please check your OpenAI client configuration (e.g., API key, base URL, model ID in ~/.agentgdb_config.ini) and system prompt files.")
  else:
    print("[AgentGDB] GDB AI Agent installed. Type 'agent' or 'ask' followed by your query to use.")
  AgentGdbCommand()
  AskGdbCommand() 
