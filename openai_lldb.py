import lldb
import os
import json
import subprocess, sys

#####################################################
# Execute Python using the shell and extract the sys.path (for site-packages)
paths = subprocess.check_output('python -c "import os,sys;print(os.linesep.join(sys.path).strip())"', shell=True).decode("utf-8").split()

# Extend LLDB's Python search path
sys.path.extend(paths)
#####################################################

try:
  from openai import OpenAI
except ImportError:
  print("You must install the openai package: pip install openai")
  raise

class LLDBCmdContext:
  def __init__(self):
    self.history = []

def prompt_to_lldb_command(debugger, command, result, internal_dict):
  """
  LLDB command: prompt_to_lldb_command <natural language prompt>
  Example: prompt_to_lldb_command set a breakpoint at line 5 in main.cpp
  """
  client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")
  context = internal_dict.get('cmd_context', LLDBCmdContext())

  # Get command history for LLM context
  history_str = "\n".join([f"OUTPUT {i+1}:\n{item}" for i, item in enumerate(context.history[-3:])])

  # read system prompt from system_prompt.md
  with open('/Users/jravi/AgentGDB/system_prompt.md', 'r') as file:
    system_prompt = file.read()
  system_msg = f"""{system_prompt}
  Recent command outputs:{history_str}"""

  user_prompt = command.strip()

  # Query OpenAI
  response = client.chat.completions.create(
      model="model-identifier",
      messages=[
          {"role": "system", "content": system_msg},
          {"role": "user", "content": user_prompt},
      ],
      temperature=0.0
      # max_tokens=128,
  )
  llm_output = response.choices[0].message.content.strip()

  # Execute commands line by line
  interpreter = debugger.GetCommandInterpreter()
  cmd_return = lldb.SBCommandReturnObject()

  # Try to parse JSON response
  try:
    # Check if response is wrapped in markdown code blocks
    if llm_output.startswith("```") and "```" in llm_output[3:]:
      # Extract content between markdown code blocks
      content_start = llm_output.find("\n", 3) + 1
      content_end = llm_output.rfind("```")
      json_content = llm_output[content_start:content_end].strip()
      response_data = json.loads(json_content)
      
      # Display help output if available
      if "help_output" in response_data:
        for cmd, help_text in response_data["help_output"].items():
          result.AppendMessage(f"Help for '{cmd}':\n{help_text}")
          context.history.append(f"Command: help {cmd}\nOutput:\n{help_text}")
      
      # Get the actual LLDB command to execute
      lldb_command = None
      if "translated_command" in response_data and "lldb_command" in response_data["translated_command"]:
        lldb_command = response_data["translated_command"]["lldb_command"]
      
      # Display explanation if available
      if "explanation" in response_data:
        for key, explanation in response_data["explanation"].items():
          if isinstance(explanation, str):
            result.AppendMessage(f"Explanation: {explanation}")
      
      # Execute the extracted LLDB command
      if lldb_command:
        result.AppendMessage(f"Executing: {lldb_command}")
        interpreter.HandleCommand(lldb_command, cmd_return)
        output = cmd_return.GetOutput() or ""
        error = cmd_return.GetError() or ""
        
        # Store execution results
        context.history.append(f"Command: {lldb_command}\nOutput:\n{output}\nError:\n{error}")
        
        # Display results
        result.AppendMessage(output)
        if error:
          result.AppendMessage(f"Error: {error}")
      else:
        result.AppendMessage("No valid LLDB command found in the response.")
    
    else:
      # Not JSON, treat as regular LLDB command(s)
      for line in llm_output.split('\n'):
        if line.startswith("help "):
          # Capture help output
          interpreter.HandleCommand(line, cmd_return)
          help_output = cmd_return.GetOutput()
          context.history.append(f"Command: {line}\nOutput:\n{help_output}")
          result.AppendMessage(f"Help context captured:\n{help_output}")
        else:
          # Regular command
          interpreter.HandleCommand(line, cmd_return)
          output = cmd_return.GetOutput() or ""
          error = cmd_return.GetError() or ""
          
          # Store execution results
          context.history.append(f"Command: {line}\nOutput:\n{output}\nError:\n{error}")
          
          # Display results
          result.AppendMessage(f"Executed: {line}")
          result.AppendMessage(output)
          if error:
            result.AppendMessage(f"Error: {error}")
  
  except json.JSONDecodeError:
    # If JSON parsing fails, fall back to treating the output as direct commands
    result.AppendMessage("Failed to parse response as JSON, executing as direct commands.")
    for line in llm_output.split('\n'):
      if not line.strip():
        continue
        
      interpreter.HandleCommand(line, cmd_return)
      output = cmd_return.GetOutput() or ""
      error = cmd_return.GetError() or ""
      
      # Store execution results
      context.history.append(f"Command: {line}\nOutput:\n{output}\nError:\n{error}")
      
      # Display results
      result.AppendMessage(f"Executed: {line}")
      result.AppendMessage(output)
      if error:
        result.AppendMessage(f"Error: {error}")
  
  internal_dict['cmd_context'] = context

def __lldb_init_module(debugger, internal_dict):
  debugger.HandleCommand('command script add -f openai_lldb.prompt_to_lldb_command llm')
  print('"llm" command ready. Usage: (lldb) llm <natural-language-request>. Example:')
  print('  (lldb) llm set a breakpoint at line 5 in main.cpp')

