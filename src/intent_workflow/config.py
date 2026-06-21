from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "workflow.yaml"
VALID_ACTION_TYPES = {"checklist", "html_app", "microservice"}
VALID_MICROSERVICE_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}


@lru_cache(maxsize=8)
def load_workflow_config(config_path: str | None = None) -> dict[str, Any]:
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    with path.open("r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)

    validate_workflow_config(config)

    return config


def validate_workflow_config(config: Any) -> None:
    if not isinstance(config, dict):
        raise ValueError("Workflow config must be an object.")

    workflow = config.get("workflow")
    if not isinstance(workflow, dict):
        raise ValueError("Workflow config must define a 'workflow' object.")

    intents = config.get("intents")
    if not isinstance(intents, dict) or not intents:
        raise ValueError("Workflow config must define at least one intent.")

    default_intent = workflow.get("default_intent")
    if default_intent and default_intent not in intents:
        raise ValueError("workflow.default_intent must match an intent id.")

    for intent_id, intent in intents.items():
        if not isinstance(intent, dict):
            raise ValueError(f"Intent '{intent_id}' must be an object.")

        stages = intent.get("stages")
        start_stage = intent.get("start_stage")
        if not isinstance(stages, dict) or not stages:
            raise ValueError(f"Intent '{intent_id}' must define at least one stage.")
        if start_stage not in stages:
            raise ValueError(f"Intent '{intent_id}' start_stage must match a stage id.")

        keywords = intent.get("keywords", [])
        if not isinstance(keywords, list):
            raise ValueError(f"Intent '{intent_id}' keywords must be a list.")

        for stage_id, stage in stages.items():
            if not isinstance(stage, dict):
                raise ValueError(f"Stage '{intent_id}.{stage_id}' must be an object.")

            validate_action(stage.get("action"), f"Stage '{intent_id}.{stage_id}'")

            forks = stage.get("forks", {})
            if not isinstance(forks, dict) or not forks:
                raise ValueError(f"Stage '{intent_id}.{stage_id}' must define at least one fork.")

            for fork_id, fork in forks.items():
                if not isinstance(fork, dict):
                    raise ValueError(f"Fork '{intent_id}.{stage_id}.{fork_id}' must be an object.")
                next_stage = fork.get("next")
                if next_stage == "finalize":
                    pass  # always valid
                elif isinstance(next_stage, str) and ":" in next_stage:
                    ref_intent_id, ref_stage_id = next_stage.split(":", 1)
                    if ref_intent_id not in intents:
                        raise ValueError(
                            f"Fork '{intent_id}.{stage_id}.{fork_id}' cross-intent target"
                            f" '{ref_intent_id}' is not a defined intent."
                        )
                    ref_stages = intents[ref_intent_id].get("stages", {})
                    if ref_stage_id not in ref_stages:
                        raise ValueError(
                            f"Fork '{intent_id}.{stage_id}.{fork_id}' cross-intent target"
                            f" '{ref_intent_id}:{ref_stage_id}' is not a stage in that intent."
                        )
                elif next_stage not in stages:
                    raise ValueError(
                        f"Fork '{intent_id}.{stage_id}.{fork_id}' must route to an existing stage,"
                        f" finalize, or a cross-intent reference (intent_id:stage_id)."
                    )
                if not fork.get("default") and not isinstance(fork.get("when_any"), list):
                    raise ValueError(
                        f"Fork '{intent_id}.{stage_id}.{fork_id}' must define when_any or default: true."
                    )
                if "action" in fork:
                    validate_action(fork.get("action"), f"Fork '{intent_id}.{stage_id}.{fork_id}'")


def validate_action(action: Any, location: str) -> None:
    if not isinstance(action, dict):
        raise ValueError(f"{location} must define an action object.")

    action_type = action.get("type")
    if action_type not in VALID_ACTION_TYPES:
        raise ValueError(f"{location} action.type must be one of: {', '.join(sorted(VALID_ACTION_TYPES))}.")

    if not action.get("instruction"):
        raise ValueError(f"{location} action.instruction is required.")

    if action_type == "html_app" and not action.get("app_url"):
        raise ValueError(f"{location} html_app action must define app_url.")

    if action_type == "microservice":
        if not action.get("url"):
            raise ValueError(f"{location} microservice action must define url.")
        method = action.get("method", "POST").upper()
        if method not in VALID_MICROSERVICE_METHODS:
            raise ValueError(
                f"{location} microservice method must be one of: {', '.join(sorted(VALID_MICROSERVICE_METHODS))}."
            )
        headers = action.get("headers", {})
        if headers is not None and not isinstance(headers, dict):
            raise ValueError(f"{location} microservice headers must be an object.")
        payload_template = action.get("payload_template", {})
        if payload_template is not None and not isinstance(payload_template, dict):
            raise ValueError(f"{location} microservice payload_template must be an object.")


def save_workflow_config(config: dict[str, Any], config_path: str | None = None) -> dict[str, Any]:
    validate_workflow_config(config)
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    with path.open("w", encoding="utf-8") as config_file:
        yaml.safe_dump(config, config_file, sort_keys=False, allow_unicode=False)

    load_workflow_config.cache_clear()
    return config
