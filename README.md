# LangGraph Intent Workflow

This workspace contains an intent-driven LangGraph workflow.

## Visual Workflow Designer

Run the local app:

```powershell
python -m pip install -e .
python -m uvicorn intent_workflow.api:app --reload
```

Open:

```text
http://127.0.0.1:8000/designer/index.html
```

The designer lets you manually add or change:

- intents
- stages
- fork decisions
- decision alternatives
- action type and instructions
- HTML app URLs
- branch-level HTML app and microservice hooks

Click **Save YAML** in the designer to update:

```text
config/workflow.yaml
```

The LangGraph workflow loads that YAML as its source of truth.

## Manual Flow Maintenance

Edit the flow in:

```text
config/workflow.yaml
```

Use this file to manually add or alter:

- intents
- keywords used for intent matching
- stages
- forks and decision conditions
- next-step routing
- HTML app action links
- microservice action hooks

## Current Intents

- Data Migration
- System Configuration
- Incident Management
- Business Process Improvement

## HTML App Actions

For a stage that should open an HTML app, set:

```yaml
action:
  type: html_app
  app_url: apps/example.html
  instruction: Open the supporting app for this workflow step.
```

For a standard workflow action, set:

```yaml
action:
  type: checklist
  instruction: Describe the manual or agent-assisted step here.
```

## Decision Branch Actions

Forks can also define their own optional action. This action runs when that branch is selected, before the workflow routes to the next stage.

HTML branch action:

```yaml
forks:
  critical:
    when_any:
      - critical
      - sev1
    next: command_center
    action:
      type: html_app
      app_url: apps/incident_management.html
      instruction: Open the incident command center for this branch.
```

Microservice branch action:

```yaml
forks:
  automation_candidate:
    when_any:
      - automation
      - repetitive
    next: automation_canvas
    action:
      type: microservice
      method: POST
      url: http://localhost:9000/automation-score
      instruction: Send this branch context to the scoring service.
      headers:
        Content-Type: application/json
      payload_template:
        intent: business_process_improvement
        branch: automation_candidate
        selected_stage: opportunity
```
