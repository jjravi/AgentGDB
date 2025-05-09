import lldb
import os
import sys
import types
import importlib
import re

#####################################################
# LazyLoader implementation for improved startup time
class LazyLoader(types.ModuleType):
    """
    Lazily import a module only when its attributes are accessed.
    """
    def __init__(self, local_name, parent_module_globals, name, module_path=None):
        self._local_name = local_name
        self._parent_module_globals = parent_module_globals
        self._module_path = module_path or name
        
        super(LazyLoader, self).__init__(name)
        
    def _load(self):
        module = importlib.import_module(self._module_path)
        self._parent_module_globals[self._local_name] = module
        self.__dict__.update(module.__dict__)
        return module
        
    def __getattr__(self, item):
        module = self._load()
        return getattr(module, item)

# Lazily load dependencies
subprocess = LazyLoader('subprocess', globals(), 'subprocess')
json = LazyLoader('json', globals(), 'json')
datetime = LazyLoader('datetime', globals(), 'datetime')
threading = LazyLoader('threading', globals(), 'threading')
time = LazyLoader('time', globals(), 'time')

# OpenAI will be loaded only when needed
OpenAI = None
#####################################################

class LLDBCmdContext:
  def __init__(self):
    self.history = []

def log_to_file(data, log_dir=None):
  """Log data to a file in the specified directory."""
  # Import json and datetime only when this function is called
  import json
  import datetime
  import os
  
  if log_dir is None:
    log_dir = os.path.join(os.getcwd(), "llm_logs")
  
  # Create log directory if it doesn't exist
  if not os.path.exists(log_dir):
    os.makedirs(log_dir)
    
  # Create a timestamped log file for this session
  timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
  log_file = os.path.join(log_dir, f"llm_debug_{timestamp}.log")
  
  # Append the log entry with timestamp
  with open(log_file, "a") as f:
    log_entry = {
      "timestamp": datetime.datetime.now().isoformat(),
      "data": data
    }
    f.write(json.dumps(log_entry, indent=2) + "\n")
  
  return log_file

def format_light_text(text):
  """Format text as 'light' for terminal display."""
  # Using ANSI escape code for dim text (not available in all terminals)
  return f"\033[2m{text}\033[0m"

def print_light(text):
  """Print text in light formatting, immediately flushing output."""
  sys.stdout.write(format_light_text(text))
  sys.stdout.flush()

def extract_lldb_commands(markdown_text):
  """
  Extract LLDB commands from markdown code blocks.
  
  Looks for code blocks that start with ```lldb and end with ```.
  Returns a list of commands and the remaining text (non-command text).
  """
  # Pattern to find ```lldb ... ``` blocks
  pattern = r"```lldb\s*([\s\S]*?)\s*```"
  
  # Find all command blocks
  command_blocks = re.findall(pattern, markdown_text)
  
  # Get all commands from the blocks
  all_commands = []
  for block in command_blocks:
    commands = [cmd.strip() for cmd in block.split('\n') if cmd.strip()]
    all_commands.extend(commands)
  
  # Replace command blocks with empty strings to get non-command text
  non_command_text = re.sub(pattern, "", markdown_text)
  
  return all_commands, non_command_text

def setup_openai():
  """Setup OpenAI client - only called when needed."""
  global OpenAI
  if OpenAI is None:
    print_light("Setting up OpenAI client...")
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

def prompt_to_lldb_command(debugger, command, result, internal_dict):
  """
  LLDB command: prompt_to_lldb_command <natural language prompt>
  Example: prompt_to_lldb_command set a breakpoint at line 5 in main.cpp
  """
  # Setup OpenAI only when this command is used
  setup_openai()
  
  # Initialize log file
  log_dir = os.path.join(os.getcwd(), "llm_logs")
  log_file = None
  
  # Log the initial command
  log_file = log_to_file({
    "event": "command",
    "command": command
  }, log_dir)
  
  client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")
  
  # Ensure we have a persistent context
  if 'cmd_context' not in internal_dict:
    internal_dict['cmd_context'] = LLDBCmdContext()
  context = internal_dict['cmd_context']
  
  interpreter = debugger.GetCommandInterpreter()
  
  # Get command history for LLM context
  history_str = "\n".join([f"OUTPUT {i+1}:\n{item}" for i, item in enumerate(context.history[-3:])])

  # read system prompt from system_prompt.md
  with open('/Users/jravi/AgentGDB/system_prompt3.md', 'r') as file:
    system_prompt = file.read()
  
  # Initial user prompt
  user_prompt = command.strip()
  
  # Prepare system message
  system_message = system_prompt
  if history_str:
    system_message += f"\nRecent command outputs:\n{history_str}"
  
  # Store messages for ongoing conversation
  messages = [
    {"role": "system", "content": system_message},
    {"role": "user", "content": user_prompt}
  ]
  
  # Log initial messages
  log_to_file({
    "event": "initial_messages",
    "messages": [
      {"role": "system", "content": system_message},
      {"role": "user", "content": user_prompt}
    ]
  }, log_dir)
  
  # Conversation loop
  final_commands = None
  help_iterations = 0
  min_help_iterations = 1  # Require at least one help command
  max_help_iterations = 5  # Safety limit to prevent infinite loops
  help_commands_used = []
  
  while help_iterations < max_help_iterations:
    print_light("Thinking about your request...\n")
    
    # Query OpenAI with streaming enabled
    stream = client.chat.completions.create(
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
    
    print("\n")  # Add newline after all tokens
    llm_output = collected_response.strip()
    
    # Log the LLM response
    log_to_file({
      "event": "llm_response",
      "iteration": help_iterations,
      "messages": messages,
      "response": llm_output
    }, log_dir)
    
    # Extract LLDB commands from markdown blocks
    commands, text_output = extract_lldb_commands(llm_output)
    
    # If there are no commands but there's text content, it might be thinking aloud
    if not commands and text_output.strip():
      # Assume it's thinking/explaining, continue conversation
      messages.append({"role": "assistant", "content": llm_output})
      messages.append({"role": "user", "content": "Please provide LLDB commands in ```lldb code blocks to execute commands."})
      continue
    
    # Track if any help commands were found in this response
    has_help_command = False
    
    # Process each command
    for command_line in commands:
      # Check if it's a help command
      if command_line.startswith("help "):
        has_help_command = True
        help_iterations += 1
        help_commands_used.append(command_line)
        
        # Show the help command
        print_light(f"Exploring: {command_line}\n")
        
        # Execute help command and get output
        cmd_return = lldb.SBCommandReturnObject()
        interpreter.HandleCommand(command_line, cmd_return)
        help_output = cmd_return.GetOutput() or ""
        
        # Display help output immediately, line by line
        for line in help_output.split('\n'):
          if line.strip():
            print_light(line + "\n")
        
        # Log the help command execution
        log_to_file({
          "event": "help_command",
          "command": command_line,
          "output": help_output
        }, log_dir)
        
        # Add to conversation
        messages.append({"role": "assistant", "content": f"I'm exploring the `{command_line}` command to understand how to help you better.\n\n```\n{help_output}\n```"})
        messages.append({"role": "user", "content": "Based on this help information and my original request, what LLDB command should I use? Please put the LLDB commands within ```lldb code blocks."})
        
        break  # Process one help command at a time
    
    # If no help commands found, check if we can proceed to final commands
    if not has_help_command:
      # Make sure we've had at least one help command before accepting final command
      if help_iterations >= min_help_iterations:
        final_commands = commands
        break
      else:
        # Force the model to use help first
        messages.append({"role": "assistant", "content": llm_output})
        messages.append({"role": "user", "content": "Before giving me the final command, please first use the help command to learn more about the relevant LLDB commands. Place your help command inside ```lldb code blocks."})
        continue
  
  # Execute final commands
  if final_commands:
    # Log final command selection
    log_to_file({
      "event": "final_command",
      "commands": final_commands,
      "help_commands_used": help_commands_used
    }, log_dir)
    
    execution_results = []
    
    for cmd in final_commands:
      # Skip any help commands in the final output
      if cmd.startswith("help "):
        continue
        
      # Show executing message
      result.AppendMessage(f"Executed: {cmd}")
      
      # Execute command
      cmd_return = lldb.SBCommandReturnObject()
      interpreter.HandleCommand(cmd, cmd_return)
      output = cmd_return.GetOutput() or ""
      error = cmd_return.GetError() or ""
      
      # Log command execution
      log_to_file({
        "event": "command_execution",
        "command": cmd,
        "output": output,
        "error": error
      }, log_dir)
      
      execution_results.append(f"Command: {cmd}\nOutput:\n{output}\nError:\n{error}")
      
      # Show command output
      if output:
        result.AppendMessage(output)
      if error:
        result.AppendMessage(f"Error: {error}")
    
    # Store execution results in context
    context.history.append("\n".join(execution_results))
    internal_dict['cmd_context'] = context
    
    # Log completion and show log file location
    log_to_file({
      "event": "completion",
      "success": True
    }, log_dir)
    
    result.AppendMessage(f"Debug log saved to: {log_file}")
  else:
    error_msg = "Failed to generate valid LLDB commands after maximum help iterations."
    result.AppendMessage(error_msg)
    
    # Log failure
    log_to_file({
      "event": "completion",
      "success": False,
      "error": error_msg
    }, log_dir)
    
    result.AppendMessage(f"Debug log saved to: {log_file}")

def __lldb_init_module(debugger, internal_dict):
  debugger.HandleCommand('command script add -f openai_lldb.prompt_to_lldb_command llm')
  print("The 'llm' command has been installed. Use: llm <your instruction>")
  