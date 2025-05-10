import gdb
import os
import sys
import types
import importlib
import re

OpenAI = None
g_client = None

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
          #print(content, end="")
          collected_response += content
    #print("")

    return collected_response

    

def gdb_llm_prompt(x_prompt):
    global client

    # STAGE 1
    f = open("system_prompts/stage1.md","r")
    system_message = f.read()

    collected_response = query_llm(system_message, x_prompt)
    cmd_class = collected_response
    gdb_cmd = "help " + cmd_class.strip()

    print("RUNNING GDB CMD: " + gdb_cmd)
    gdb_cmd_class_help = gdb.execute(gdb_cmd, to_string=True)

    gdb_help_class_list = gdb_cmd_class_help.split("\n")

    gdb_output_list = []
    for line in gdb_help_class_list:
        if "set" not in line:
            gdb_output_list.append(line)

    gdb_cmd_class_help = "".join(gdb_output_list)
    gdb_cmd_class_help = gdb_cmd_class_help.strip()
    
    # STAGE 3
    f = open("system_prompts/stage3.md","r")
    system_message = f.read()
    system_message += "\n" + gdb_cmd_class_help
    collected_response = query_llm(system_message, x_prompt)
    print("STAGE 3 OUTPUT: " + str(collected_response))

    gdb_detailed_help = gdb.execute("help " + str(collected_response), to_string=True)

    # STAGE 4
    f = open("system_prompts/stage4.md","r")
    system_message = f.read()
    system_message += "\n" + gdb_detailed_help
    final_gdb_cmd = query_llm(system_message, x_prompt)
    print("STAGE 4 OUTPUT: " + str(final_gdb_cmd))

    gdb.execute(final_gdb_cmd)

    '''
    l_foundHelp = False
    l_helpCmd = ""
    for line in collected_response.split("\n"):
        if "help" in line:
            l_foundHelp = True
            l_helpCmd = line
            

    l_executeHelp = False
    gdb_output = ""
    if l_foundHelp:
        gdb_output = gdb.execute(l_helpCmd, to_string=True)
        l_executeHelp = True
    else:
        print("ERROR: could not find help!")
        exit()
            

    if l_executeHelp:
        system_message += "\n" + gdb_output

    # Store messages for ongoing conversation
    messages = [
      {"role": "system", "content": system_message},
      {"role": "user", "content": x_prompt}
    ]

    print("SYS MESSAGE LEN: " + str(len(system_message)))

    print(system_message)

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
      print(chunk)
      if hasattr(chunk.choices[0], 'delta') and hasattr(chunk.choices[0].delta, 'content'):
        content = chunk.choices[0].delta.content
        if content:
          # Immediately print each token
          print(content, end="")
          collected_response += content
    print("")

    l_saveLine = False
    gdb_cmds = []
    for line in collected_response.split("\n"):
        if "```" in line and "gdb" not in line:
            l_saveLine = False

        if l_saveLine and "help" not in line:
            gdb_cmds.append(line)
            
        if "```gdb" in line:
            l_saveLine = True
    print("GDB CMDS:")
    print(gdb_cmds)

    for cmd in gdb_cmds:
        gdb.execute(cmd)
    '''

        

class GdbCommand(gdb.Command):
    def __init__(self):
        super(GdbCommand, self).__init__("agent", gdb.COMMAND_USER)
    def invoke(self, x_arg, from_tty):
        gdb_llm_prompt(x_arg)

def setup_openai():
  """Setup OpenAI client - only called when needed."""
  global OpenAI
  if OpenAI is None:
    print("Setting up OpenAI client...")
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
    print("HELLO!")
    GdbCommand()
    setup_openai()

    g_client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")




    #gdb.execute('r')
