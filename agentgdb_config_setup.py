import argparse
import configparser
import os

CONFIG_FILE_PATH = os.path.expanduser("~/.agentgdb_config.ini")
CREDENTIALS_SECTION = "Credentials"
DEBUG_SECTION = "Debug"

def main():
    parser = argparse.ArgumentParser(description="Configure AgentGDB settings.")
    parser.add_argument(
        "--api-key",
        metavar="KEY",
        type=str,
        help="Your OpenAI API key."
    )
    parser.add_argument(
        "--base-url",
        metavar="URL",
        type=str,
        help="The base URL for the OpenAI API (e.g., http://localhost:1234/v1)."
    )
    parser.add_argument(
        "--model-id",
        metavar="ID",
        type=str,
        help="The model identifier for the LLM."
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose debug output."
    )
    parser.add_argument(
        "--no-verbose",
        action="store_true",
        help="Disable verbose debug output."
    )

    args = parser.parse_args()

    config = configparser.ConfigParser()

    # Read existing config file if it exists
    if os.path.exists(CONFIG_FILE_PATH):
        try:
            config.read(CONFIG_FILE_PATH)
        except configparser.Error as e:
            print(f"Warning: Could not parse existing config file at {CONFIG_FILE_PATH}: {e}")
            print("A new configuration will be created or will overwrite the existing one if possible.")
            # Initialize config object freshly if reading failed
            config = configparser.ConfigParser()


    if not config.has_section(CREDENTIALS_SECTION):
        config.add_section(CREDENTIALS_SECTION)
    
    if not config.has_section(DEBUG_SECTION):
        config.add_section(DEBUG_SECTION)

    updated_any = False
    current_settings = {}

    # Get current settings to display later if not overwritten
    for key in ['api_key', 'base_url', 'model_identifier']:
        current_settings[key] = config.get(CREDENTIALS_SECTION, key, fallback=None)
    
    # Get current verbose setting
    current_settings["verbose"] = config.getboolean(DEBUG_SECTION, "verbose", fallback=False)

    if args.api_key is not None:
        config.set(CREDENTIALS_SECTION, "api_key", args.api_key)
        current_settings["api_key"] = args.api_key
        updated_any = True
        print(f"API Key set to: {args.api_key}")
    elif current_settings["api_key"]:
        print(f"API Key retained: {current_settings['api_key']}")
    else:
        print("API Key: Not set. Use --api-key to set it.")


    if args.base_url is not None:
        config.set(CREDENTIALS_SECTION, "base_url", args.base_url)
        current_settings["base_url"] = args.base_url
        updated_any = True
        print(f"Base URL set to: {args.base_url}")
    elif current_settings["base_url"]:
        print(f"Base URL retained: {current_settings['base_url']}")
    else:
        print("Base URL: Not set. Use --base-url to set it.")

    if args.model_id is not None:
        config.set(CREDENTIALS_SECTION, "model_identifier", args.model_id)
        current_settings["model_identifier"] = args.model_id
        updated_any = True
        print(f"Model Identifier set to: {args.model_id}")
    elif current_settings["model_identifier"]:
        print(f"Model Identifier retained: {current_settings['model_identifier']}")
    else:
        print("Model Identifier: Not set. Use --model-id to set it.")

    # Handle verbose flag - prioritize explicit flags
    if args.verbose and args.no_verbose:
        print("Warning: Both --verbose and --no-verbose specified. Using --verbose.")
        config.set(DEBUG_SECTION, "verbose", "true")
        current_settings["verbose"] = True
        updated_any = True
        print("Verbose mode enabled.")
    elif args.verbose:
        config.set(DEBUG_SECTION, "verbose", "true")
        current_settings["verbose"] = True
        updated_any = True
        print("Verbose mode enabled.")
    elif args.no_verbose:
        config.set(DEBUG_SECTION, "verbose", "false")
        current_settings["verbose"] = False
        updated_any = True
        print("Verbose mode disabled.")
    elif "verbose" in current_settings:
        print(f"Verbose mode retained: {'enabled' if current_settings['verbose'] else 'disabled'}")
    else:
        print("Verbose mode: Not set (defaults to disabled).")

    if not updated_any and not all(current_settings.values()):
        print("\nNo new settings provided and no existing complete configuration found.")
        print(f"Please provide at least one setting or ensure {CONFIG_FILE_PATH} is configured.")
        parser.print_help()
        return

    try:
        with open(CONFIG_FILE_PATH, "w") as configfile:
            config.write(configfile)
        print(f"\nConfiguration saved to {CONFIG_FILE_PATH}")
    except IOError as e:
        print(f"Error: Could not write configuration to {CONFIG_FILE_PATH}: {e}")

if __name__ == "__main__":
    main() 