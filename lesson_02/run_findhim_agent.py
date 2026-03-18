"""
run_findhim_agent.py
====================
Standalone runner for the S01E02 FindHim investigation agent.

Run from the project root:
    python lesson_02/run_findhim_agent.py

Or from inside the lesson_02/ directory:
    python run_findhim_agent.py
"""

import django
import os
import sys
import json

# Ensure the project root is on the path regardless of where this is executed from
_PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
os.chdir(os.path.abspath(_PROJECT_ROOT))
sys.path.insert(0, os.path.abspath(_PROJECT_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "operation_center.settings")
django.setup()

from lesson_02.services.findhim_agent_service import run_findhim_agent  # noqa: E402

result = run_findhim_agent()

print("=== FINAL OUTPUT ===")
print(result["output"])
print()
print(f"Steps taken: {len(result['steps'])}")
print(f"Answer saved to: {result['answer_path']}")

# Print the saved answer.json content
answer_path = result["answer_path"]
with open(answer_path, "r", encoding="utf-8") as f:
    print()
    print("=== answer.json content ===")
    print(f.read())
