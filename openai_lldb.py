import lldb
import os
import subprocess
import sys
import json
import datetime
import threading
import time

#####################################################
# Execute Python using the shell and extract the sys.path (for site-packages)
paths = subprocess.check_output('python -c "import os,sys;print(os.linesep.join(sys.path).strip())"', shell=True).decode("utf-8").split()

# Extend LLDB's Python search path
sys.path.extend(paths)

from openai import OpenAI
#####################################################

class LLDBCmdContext:
  def __init__(self):
    self.history = []

def log_to_file(data, log_dir=None):
  """Log data to a file in the specified directory."""
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

def prompt_to_lldb_command(debugger, command, result, internal_dict):
  """
  LLDB command: prompt_to_lldb_command <natural language prompt>
  Example: prompt_to_lldb_command set a breakpoint at line 5 in main.cpp
  """
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
  final_command = None
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
    
    # Parse commands (one per line)
    commands = [cmd.strip() for cmd in llm_output.split('\n') if cmd.strip()]
    
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
        messages.append({"role": "assistant", "content": command_line})
        messages.append({"role": "user", "content": f"Help output:\n{help_output}\n\nNow based on this help information and my original request, what LLDB command should I use?"})
        
        break  # Process one help command at a time
    
    # If no help commands found, this must be our final command sequence
    if not has_help_command:
      # Make sure we've had at least one help command before accepting final command
      if help_iterations >= min_help_iterations:
        final_command = llm_output
        break
      else:
        # Force the model to use help first
        messages.append({"role": "assistant", "content": llm_output})
        messages.append({"role": "user", "content": "Before giving me the final command, please first use the help command to learn more about the relevant LLDB commands."})
        continue
  
  # Execute final command
  if final_command:
    # Log final command selection
    log_to_file({
      "event": "final_command",
      "command": final_command,
      "help_commands_used": help_commands_used
    }, log_dir)
    
    # Process and execute each command in the final output
    final_commands = [cmd.strip() for cmd in final_command.split('\n') if cmd.strip()]
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
    error_msg = "Failed to generate a final LLDB command after maximum help iterations."
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
  