# Extending JARVIS: Adding a New Skill Agent

This guide documents how to add a new skill agent to JARVIS **without modifying Orchestrator Core** (`orchestrator/core.py`).

JARVIS relies on a **data-driven architecture** where the Orchestrator Core coordinates abstract `TaskPlan` pipelines. All concrete execution is decoupled via the `AgentRegistry` and `AgentRouter`.

---

## The 3-Step Agent Addition Pattern

### Step 1: Create the Agent Implementation in `agents/`

Create a new file in `agents/` (for example, `agents/spotify_agent.py`):

```python
# agents/spotify_agent.py
from typing import Dict, Any

class SpotifyAgent:
    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Standardized execution interface required by AgentRouter."""
        action = inputs.get("action", "play")
        track = inputs.get("track", "Unknown Track")
        
        # Real skill logic here
        return {
            "success": True,
            "track": track,
            "status": "playback_started",
            "persona": inputs.get("active_persona", "Jarvis")
        }

spotify_agent = SpotifyAgent()
```

### Step 2: Declare the Agent in `config/agent_registry.yaml`

Add the declarative specification to `config/agent_registry.yaml`:

```yaml
agents:
  spotify_agent:
    name: "Spotify Music Agent"
    description: "Controls Spotify playback, search tracks, and queues playlists."
    capabilities:
      - "music_playback"
      - "playlist_control"
```

### Step 3: Register in `orchestrator/router.py`

In `orchestrator/router.py`, add your instance to `real_agent_map`:

```python
from agents.spotify_agent import spotify_agent

real_agent_map["spotify_agent"] = spotify_agent
```

---

## Why Orchestrator Core Remains Untouched

- **Decoupled Contracts**: `orchestrator/core.py` receives a `PerceptionEvent`, asks `task_planner` for a `TaskPlan`, checks `safety_guardrail`, and passes the plan to `execution_manager`.
- **Dynamic Lookup**: `execution_manager` calls `agent_router.route_and_execute(step.required_agent_type, step.inputs, persona)` which looks up the agent by string ID in the registry.
- **Safety Inheritance**: All agents automatically inherit Group 4 content filtering, rate limits, and verification without writing boilerplate code.
