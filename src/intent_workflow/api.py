from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from intent_workflow.config import PROJECT_ROOT, load_workflow_config, save_workflow_config, validate_workflow_config
from intent_workflow.graph import build_workflow_graph


class WorkflowRequest(BaseModel):
    message: str


class WorkflowConfigRequest(BaseModel):
    config: dict[str, Any]


app = FastAPI(title="LangGraph Intent Workflow")
workflow_graph = build_workflow_graph()

app.mount("/apps", StaticFiles(directory=PROJECT_ROOT / "apps"), name="apps")
app.mount("/designer", StaticFiles(directory=PROJECT_ROOT / "designer"), name="designer")


@app.get("/")
def root() -> RedirectResponse:
    return RedirectResponse(url="/designer/index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/workflow")
def workflow() -> dict[str, Any]:
    return load_workflow_config()


@app.put("/workflow")
def update_workflow(request: WorkflowConfigRequest) -> dict[str, Any]:
    try:
        return save_workflow_config(request.config)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/workflow/validate")
def validate_workflow(request: WorkflowConfigRequest) -> dict[str, str]:
    try:
        validate_workflow_config(request.config)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"status": "valid"}


@app.get("/workflow/graph")
def workflow_graph_definition() -> dict[str, Any]:
    config = load_workflow_config()
    graph = {"nodes": [], "edges": []}
    for intent_id, intent in config["intents"].items():
        graph["nodes"].append(
            {
                "id": f"{intent_id}:classify",
                "label": intent["label"],
                "type": "intent",
            }
        )
        for stage_id, stage in intent["stages"].items():
            graph["nodes"].append(
                {
                    "id": f"{intent_id}:{stage_id}",
                    "label": stage["title"],
                    "type": stage["action"]["type"],
                }
            )
            for fork_id, fork in stage.get("forks", {}).items():
                graph["edges"].append(
                    {
                        "from": f"{intent_id}:{stage_id}",
                        "to": f"{intent_id}:{fork['next']}" if fork["next"] != "finalize" else f"{intent_id}:finalize",
                        "label": fork_id,
                        "action_type": fork.get("action", {}).get("type"),
                    }
                )
        graph["nodes"].append(
            {
                "id": f"{intent_id}:finalize",
                "label": "Finalize",
                "type": "finalize",
            }
        )
        graph["edges"].append(
            {
                "from": f"{intent_id}:classify",
                "to": f"{intent_id}:{intent['start_stage']}",
                "label": "start",
            }
        )
    return graph


@app.post("/invoke")
def invoke(request: WorkflowRequest) -> dict[str, Any]:
    result = workflow_graph.invoke({"user_input": request.message})
    return result["final_response"]
