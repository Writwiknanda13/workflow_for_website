from __future__ import annotations

import argparse
import json

from intent_workflow.graph import build_workflow_graph


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the intent-driven LangGraph workflow.")
    parser.add_argument("message", help="User request to classify and route.")
    args = parser.parse_args()

    graph = build_workflow_graph()
    result = graph.invoke({"user_input": args.message})
    print(json.dumps(result["final_response"], indent=2))


if __name__ == "__main__":
    main()
