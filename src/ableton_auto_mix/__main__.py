"""Entry point: MCP server by default, CLI when a subcommand is given.

python -m ableton_auto_mix               -> run the MCP stdio server
python -m ableton_auto_mix styles        -> run the CLI
python -m ableton_auto_mix mcp           -> force the MCP server
"""

from __future__ import annotations

import sys

from .logging_utils import setup_logging

CLI_COMMANDS = {
    "styles",
    "style",
    "analyze",
    "suggest",
    "mix",
    "preview",
    "conflicts",
    "release",
}


def main() -> None:
    setup_logging()
    argv = sys.argv[1:]
    if argv and argv[0] not in ("mcp",) and argv[0] not in CLI_COMMANDS:
        # Unknown first arg -> let the CLI show its help/usage.
        from .cli import main as cli_main

        cli_main(argv)
        return

    if argv and argv[0] in CLI_COMMANDS:
        from .cli import main as cli_main

        cli_main(argv)
        return

    from .server import main as server_main

    server_main()


if __name__ == "__main__":
    main()
