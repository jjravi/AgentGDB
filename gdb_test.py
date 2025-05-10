import gdb
import os
import sys
import types
import importlib
import re

OpenAI = None
g_client = None

def gdb_llm_prompt(x_prompt):
    global client

    f = open("system_prompt4.md","r")
    system_message = f.read()

    print("SYSTEM MESSAGE:\n " + system_message)
    print("PROMPT:\n " + x_prompt)

    # Store messages for ongoing conversation
    messages = [
      {"role": "system", "content": system_message},
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
          print(content, end="")
          collected_response += content
    print("")

    print("RESPONSE: ")
    collected_response = collected_response.replace("<think>","")
    collected_response = collected_response.replace("</think>","")
    collected_response = collected_response.strip()
    print(collected_response.split("\n"))

    for cmd in collected_response.split("\n"):
        gdb.execute(cmd)
        

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
