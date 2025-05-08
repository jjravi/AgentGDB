import lldb
import os

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

def prompt_to_lldb_command(debugger, command, result, internal_dict):
    """
    LLDB command: prompt_to_lldb_command <natural language prompt>
    Example: prompt_to_lldb_command set a breakpoint at line 5 in main.cpp
    """
    print("prompt_to_lldb_command")
    # Prepare OpenAI API client
    client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")
    user_prompt = command.strip()

    # Construct a prompt for the LLM
    system_message = (
        "You are an assistant that translates natural language debugging instructions "
        "into LLDB commands. Only output the LLDB command, nothing else. Do not include lldb prompt in your response."
    )

    # Query OpenAI
    response = client.chat.completions.create(
        model="model-identifier",
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=64,
        temperature=0.0
    )
    lldb_command = response.choices[0].message.content.strip()

    # Print and execute the command in LLDB
    print(f"LLDB command: {lldb_command}")
    debugger.HandleCommand(lldb_command)

def __lldb_init_module(debugger, internal_dict):
    debugger.HandleCommand(
        'command script add -f openai_lldb.prompt_to_lldb_command prompt_to_lldb'
    )
    print('The "prompt_to_lldb" command is ready for use. Example:')
    print('  (lldb) prompt_to_lldb set a breakpoint at line 5 in main.cpp')

