#!/usr/bin/env python3
import typer

app = typer.Typer(name="myagent", help="Personal parallel task orchestrator")


@app.callback()
def main():
    pass


if __name__ == "__main__":
    app()