from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from intent_workflow.config import load_workflow_config


class WorkflowState(TypedDict, total=False):
    user_input: str
    intent: str
    current_stage: str
    step_count: int
    completed: bool
    workflow_config: dict[str, Any]
    history: list[dict[str, Any]]
    action_results: list[dict[str, Any]]
    final_response: dict[str, Any]


def build_workflow_graph(config_path: str | None = None):
    graph = StateGraph(WorkflowState)

    def format_action_result(
        *,
        intent: str,
        stage: str,
        title: str,
        action: dict[str, Any],
        source: str,
        fork: str | None = None,
    ) -> dict[str, Any]:
        result = {
            "intent": intent,
            "stage": stage,
            "title": title,
            "source": source,
            "action_type": action["type"],
            "instruction": action["instruction"],
        }

        if fork:
            result["fork"] = fork

        if action["type"] == "html_app":
            result["app_url"] = action["app_url"]
        elif action["type"] == "microservice":
            result["method"] = action.get("method", "POST").upper()
            result["url"] = action["url"]
            result["headers"] = action.get("headers", {})
            result["payload_template"] = action.get("payload_template", {})

        return result

    def load_config(state: WorkflowState) -> WorkflowState:
        return {
            **state,
            "workflow_config": load_workflow_config(config_path),
            "history": state.get("history", []),
            "action_results": state.get("action_results", []),
            "step_count": state.get("step_count", 0),
        }

    def classify_intent(state: WorkflowState) -> WorkflowState:
        config = state["workflow_config"]
        user_input = state.get("user_input", "").lower()
        default_intent = config.get("workflow", {}).get("default_intent")

        best_intent = default_intent
        best_score = -1
        for intent_name, intent_config in config["intents"].items():
            keywords = intent_config.get("keywords", [])
            score = sum(1 for keyword in keywords if keyword.lower() in user_input)
            if score > best_score:
                best_intent = intent_name
                best_score = score

        start_stage = config["intents"][best_intent]["start_stage"]
        return {**state, "intent": best_intent, "current_stage": start_stage}

    def execute_stage(state: WorkflowState) -> WorkflowState:
        intent_config = state["workflow_config"]["intents"][state["intent"]]
        stage_id = state["current_stage"]
        stage = intent_config["stages"][stage_id]
        action = stage["action"]

        result = format_action_result(
            intent=state["intent"],
            stage=stage_id,
            title=stage["title"],
            action=action,
            source="stage",
        )

        return {
            **state,
            "step_count": state.get("step_count", 0) + 1,
            "history": [*state.get("history", []), {"stage": stage_id, "title": stage["title"]}],
            "action_results": [*state.get("action_results", []), result],
        }

    def route_next_stage(state: WorkflowState) -> WorkflowState:
        intent_config = state["workflow_config"]["intents"][state["intent"]]
        stage = intent_config["stages"][state["current_stage"]]
        user_input = state.get("user_input", "").lower()

        def resolve_next(next_val: str) -> tuple[str, str]:
            """Return (intent_id, stage_id) for any next value."""
            if next_val != "finalize" and ":" in next_val:
                ref_intent, ref_stage = next_val.split(":", 1)
                return ref_intent, ref_stage
            return state["intent"], next_val

        def route_with_fork(fork_name: str, fork: dict[str, Any]) -> WorkflowState:
            next_intent, next_stage = resolve_next(fork["next"])
            history = [*state.get("history", []), {"fork": fork_name, "next": fork["next"]}]
            if next_intent != state["intent"]:
                history.append({"intent_switch": f"{state['intent']} → {next_intent}"})
            action_results = state.get("action_results", [])
            if fork_action := fork.get("action"):
                action_results = [
                    *action_results,
                    format_action_result(
                        intent=state["intent"],
                        stage=state["current_stage"],
                        title=f"Decision branch: {fork_name}",
                        action=fork_action,
                        source="fork",
                        fork=fork_name,
                    ),
                ]
                history.append({"fork_action": fork_name, "action_type": fork_action["type"]})

            return {
                **state,
                "intent": next_intent,
                "current_stage": next_stage,
                "history": history,
                "action_results": action_results,
            }

        default_next = "finalize"
        default_fork_name = "default"
        default_fork: dict[str, Any] = {"next": default_next}
        for fork_name, fork in stage.get("forks", {}).items():
            if fork.get("default"):
                default_next = fork["next"]
                default_fork_name = fork_name
                default_fork = fork
                continue

            matching_terms = fork.get("when_any", [])
            if any(term.lower() in user_input for term in matching_terms):
                return route_with_fork(fork_name, fork)

        return route_with_fork(default_fork_name, default_fork)

    def finalize(state: WorkflowState) -> WorkflowState:
        intent_config = state["workflow_config"]["intents"][state["intent"]]
        reached_step_limit = state.get("step_count", 0) >= 20 and state.get("current_stage") != "finalize"
        final_response = {
            "intent": state["intent"],
            "intent_label": intent_config["label"],
            "summary": (
                "Workflow stopped after reaching the max step limit. Check fork routing for a cycle."
                if reached_step_limit
                else f"Workflow prepared for {intent_config['label']}."
            ),
            "actions": state.get("action_results", []),
            "history": state.get("history", []),
        }
        return {**state, "completed": True, "final_response": final_response}

    def should_continue(state: WorkflowState) -> str:
        if state.get("step_count", 0) >= 20:
            return "finalize"
        return "finalize" if state["current_stage"] == "finalize" else "execute_stage"

    graph.add_node("load_config", load_config)
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("execute_stage", execute_stage)
    graph.add_node("route_next_stage", route_next_stage)
    graph.add_node("finalize", finalize)

    graph.set_entry_point("load_config")
    graph.add_edge("load_config", "classify_intent")
    graph.add_edge("classify_intent", "execute_stage")
    graph.add_edge("execute_stage", "route_next_stage")
    graph.add_conditional_edges(
        "route_next_stage",
        should_continue,
        {"execute_stage": "execute_stage", "finalize": "finalize"},
    )
    graph.add_edge("finalize", END)

    return graph.compile()
