"""Entry point: python -m agent"""

import typer

from agent.loop import main

typer.run(main)
