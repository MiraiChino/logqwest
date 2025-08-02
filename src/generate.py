import argparse
from pathlib import Path

from src.utils.commands import CommandHandler, CommandContext
from src.utils.config import ConfigManager
from src.utils.logger import Logger
from src.core.client import ClientFactory

def create_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Adventure Content Generator")
    # --client は自動判別に移行（後方互換のためオプション自体は削除）
    parser.add_argument(
        "--model",
        default=None,
        help="Model name for generation (uses client default if not specified)"
    )
    parser.add_argument(
        "--check-model",
        dest="check_model",
        default=None,
        help="Model name for checking (defaults to --model if not specified)"
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Run only check phase without generation"
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

    # クライアント自動判定
    model_input = args.model or "openrouter/openai:gpt-4o-mini"

    if model_input.startswith("gemini/"):
        client_type = "gemini"
        model = model_input.split("gemini/", 1)[1]
    elif model_input.startswith("models/"):
        client_type = "gemini"
        model = model_input
    elif model_input.startswith("openrouter/"):
        client_type = "openrouter"
        model = model_input.split("openrouter/", 1)[1]
    else:
        client_type = "openrouter"
        model = model_input

    client = ClientFactory.create_client(client_type, model)

    if args.check_model:
        check_input = args.check_model
        if check_input.startswith("gemini/"):
            check_client_type = "gemini"
            check_model = check_input.split("gemini/", 1)[1]
        elif check_input.startswith("models/"):
            check_client_type = "gemini"
            check_model = check_input
        elif check_input.startswith("openrouter/"):
            check_client_type = "openrouter"
            check_model = check_input.split("openrouter/", 1)[1]
        else:
            check_client_type = client_type
            check_model = check_input
        check_client = ClientFactory.create_client(check_client_type, check_model)
    else:
        check_client = client
        check_client_type = client_type
        check_model = model

    context = CommandContext(
        client=client,
        client_type=client_type,
        model_name=model,
        debug_mode=args.debug
    )
    check_context = CommandContext(
        client=check_client,
        client_type=check_client_type,
        model_name=check_model,
        debug_mode=args.debug
    )
    
    command_handler = CommandHandler(context, config, logger)
    check_handler = CommandHandler(check_context, config, logger)
    commands = {
        "area": lambda: command_handler.execute_area_command(),
        "locked_area": lambda: command_handler.execute_locked_area_command(),
        "adventure": lambda: command_handler.execute_adventure_command(args.result),
        "locked_adventure": lambda: command_handler.execute_locked_adventure_command(args.result),
        "log": command_handler.execute_log_command,
        "locked_log": command_handler.execute_locked_log_command,
        "location": command_handler.execute_location_command
    }
    check_commands = {
        "area": lambda: check_handler.check_area_only(),
        "locked_area": lambda: check_handler.check_area_only(),
        "adventure": lambda: check_handler.check_adventure_only(args.result),
        "locked_adventure": lambda: check_handler.check_locked_adventure_only(args.result),
        "log": check_handler.check_log_only,
        "locked_log": check_handler.check_locked_log_only,
        "location": check_handler.check_location_only
    }

    try:
        if args.check_only:
            check_commands[args.command]()
        else:
            commands[args.command]()
    except Exception as e:
        logger.error(str(e))
        raise

if __name__ == "__main__":
    main()
