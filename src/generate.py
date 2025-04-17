import argparse
from pathlib import Path

from src.utils.commands import CommandHandler, CommandContext
from src.utils.config import ConfigManager
from src.utils.logger import Logger
from src.core.client import ClientFactory

def create_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Adventure Content Generator")
    parser.add_argument(
        "--client",
        choices=["gemini", "groq"],
        default="gemini",
        help="Chat client to use (default: gemini)"
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model name (uses client default if not specified)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    
    subparsers.add_parser("area")
    subparsers.add_parser("locked_area")

    adventures_parser = subparsers.add_parser("adventure")
    adventures_parser.add_argument("result", nargs="?")
    locked_adventures_parser = subparsers.add_parser("locked_adventure")
    locked_adventures_parser.add_argument("result", nargs="?")
    
    subparsers.add_parser("log")
    subparsers.add_parser("locked_log")
    subparsers.add_parser("location")
    
    return parser

def main():
    parser = create_argument_parser()
    args = parser.parse_args()

    config = ConfigManager(Path("prompt/config.json"))
    logger = Logger(Path("logs/generator.log"))

    client = ClientFactory.create_client(args.client, args.model)
    context = CommandContext(
        client=client,
        client_type=args.client,
        model_name=args.model,
        debug_mode=args.debug
    )
    
    command_handler = CommandHandler(context, config, logger)
    commands = {
        "area": lambda: command_handler.execute_area_command(),
        "locked_area": lambda: command_handler.execute_locked_area_command(),
        "adventure": lambda: command_handler.execute_adventure_command(args.result),
        "locked_adventure": lambda: command_handler.execute_locked_adventure_command(args.result),
        "log": command_handler.execute_log_command,
        "locked_log": command_handler.execute_locked_log_command,
        "location": command_handler.execute_location_command
    }

    try:
        commands[args.command]()
    except Exception as e:
        logger.error(str(e))
        raise

if __name__ == "__main__":
    main()
