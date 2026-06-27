"""
Migration helper script.
Usage:
  python migrate.py init       # First time setup — stamp current DB as head
  python migrate.py generate   # Generate migration from model changes
  python migrate.py upgrade    # Apply pending migrations
  python migrate.py history    # Show migration history
  python migrate.py current    # Show current revision
"""
import sys
import subprocess


def run(cmd: str):
    print(f"Running: {cmd}")
    result = subprocess.run(cmd.split(), capture_output=False)
    return result.returncode


commands = {
    "init":     "alembic stamp head",
    "generate": "alembic revision --autogenerate -m",
    "upgrade":  "alembic upgrade head",
    "downgrade":"alembic downgrade -1",
    "history":  "alembic history",
    "current":  "alembic current",
}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python migrate.py [init|generate|upgrade|downgrade|history|current]")
        print("\nCommon workflow:")
        print("  1. Make model changes")
        print("  2. python migrate.py generate 'describe_your_change'")
        print("  3. python migrate.py upgrade")
        sys.exit(1)

    action = sys.argv[1]

    if action == "generate":
        msg = sys.argv[2] if len(sys.argv) > 2 else "auto_migration"
        run(f"alembic revision --autogenerate -m {msg}")
    elif action in commands:
        run(commands[action])
    else:
        print(f"Unknown command: {action}")
        print(f"Available: {list(commands.keys())}")