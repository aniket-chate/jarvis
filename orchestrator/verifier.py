"""Verifier & Feedback Module for JARVIS Layer 2.

Evaluates executed TaskPlan outcomes against original intent,
generates persona-toned summaries, and flags failures for user clarification.
"""

import re
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from orchestrator.planner import TaskPlan

logger = logging.getLogger("JARVIS.Verifier")


class TaskVerifier:
    """Validates plan execution and formats conversational feedback preserving data payloads."""

    def verify_and_summarize(self, plan: TaskPlan, execution_summary: Dict[str, Any]) -> Dict[str, Any]:
        """Compares execution results with the goal and generates feedback."""
        persona = plan.active_persona
        status = execution_summary.get("status", "unknown")
        failed_steps = execution_summary.get("failed_steps", [])
        completed_steps = execution_summary.get("completed_steps", [])

        is_verified = (status == "completed")
        requires_clarification = (len(failed_steps) > 0 or status in ["failed", "partially_failed", "blocked"])
        semantic_mismatch_reason = None

        goal_lower = (plan.goal or "").lower()

        # 1. Semantic Goal vs Executed Action Invariant
        # If user goal asks to delete/remove, but execution created a file:
        if re.search(r"\b(delete|remove|erase|trash)\b", goal_lower):
            for step in plan.steps:
                step_inputs = getattr(step, "inputs", {}) or {}
                step_act = step_inputs.get("action", "")
                if step_act in ["create", "create_file", "write"]:
                    is_verified = False
                    status = "failed"
                    requires_clarification = True
                    semantic_mismatch_reason = "Semantic mismatch: goal was to delete, but file creation was executed."
                    break

        # If user goal asks to create/write, but execution deleted a file:
        elif re.search(r"\b(create|write|make|save)\b", goal_lower) and not re.search(r"\b(?:created|saved)\s+file\b", goal_lower):
            for step in plan.steps:
                step_inputs = getattr(step, "inputs", {}) or {}
                step_act = step_inputs.get("action", "")
                if step_act in ["delete", "delete_file", "remove"]:
                    is_verified = False
                    status = "failed"
                    requires_clarification = True
                    semantic_mismatch_reason = "Semantic mismatch: goal was to create, but file deletion was executed."
                    break

        # 2. Empirical State Transition Verification
        if is_verified and status == "completed":
            for step in plan.steps:
                step_inputs = getattr(step, "inputs", {}) or {}
                step_act = step_inputs.get("action", "")
                if step_act in ["delete", "delete_file"]:
                    target_p = step_inputs.get("path") or step_inputs.get("file_path")
                    if target_p:
                        from pathlib import Path
                        try:
                            p_obj = Path(target_p)
                            if p_obj.exists():
                                is_verified = False
                                status = "failed"
                                requires_clarification = True
                                semantic_mismatch_reason = f"Verification failed: file '{p_obj.name}' still exists on disk."
                                break
                        except Exception:
                            pass
                elif step_act in ["create", "create_file"]:
                    target_p = step_inputs.get("path")
                    expected_content = step_inputs.get("content", "")
                    if target_p:
                        from pathlib import Path
                        try:
                            p_obj = Path(target_p)
                            from agents.file_document_agent import WORKSPACE_DIR, DOCUMENTS_DIR
                            cand = p_obj if p_obj.is_absolute() else (WORKSPACE_DIR / p_obj)
                            cand_doc = DOCUMENTS_DIR / p_obj.name
                            actual_file = cand if cand.exists() else (cand_doc if cand_doc.exists() else None)
                            if not actual_file:
                                is_verified = False
                                status = "failed"
                                requires_clarification = True
                                semantic_mismatch_reason = f"Verification failed: created file '{p_obj.name}' not found on disk."
                                break
                            else:
                                actual_text = actual_file.read_text(encoding="utf-8", errors="replace")
                                # If expected_content was supplied in inputs, verify it is physically present in the file
                                if expected_content and expected_content.strip():
                                    if expected_content.strip() not in actual_text:
                                        is_verified = False
                                        status = "failed"
                                        requires_clarification = True
                                        semantic_mismatch_reason = f"Verification failed: created file '{actual_file.name}' does not contain expected content."
                                        break
                                # If user goal explicitly requested content, but file on disk is empty (0 bytes):
                                elif re.search(r"\b(?:with\s+content|put\s+.*inside|containing|with\s+text|saying)\b", goal_lower):
                                    if len(actual_text.strip()) == 0:
                                        is_verified = False
                                        status = "failed"
                                        requires_clarification = True
                                        semantic_mismatch_reason = f"Verification failed: user explicitly requested content for '{actual_file.name}', but file on disk is empty (0 bytes)."
                                        break
                        except Exception as e:
                            logger.debug("[Verifier] File verification error: %s", e)

        if semantic_mismatch_reason:
            execution_summary["status"] = "failed"
            execution_summary["error"] = semantic_mismatch_reason

        # Generate user response preserving data payloads
        user_response = self.generate_user_response(plan, execution_summary)
        if semantic_mismatch_reason:
            user_response = f"Operation could not be verified, Sir: {semantic_mismatch_reason}"

        logger.info(
            "[Verifier] [%s] Plan '%s' verified: %s (Clarification needed: %s, Mismatch: %s)",
            persona,
            plan.plan_id,
            is_verified,
            requires_clarification,
            semantic_mismatch_reason,
        )

        return {
            "verified": is_verified,
            "status": status,
            "requires_clarification": requires_clarification,
            "persona": persona,
            "summary": user_response,
            "response": user_response,
            "failed_steps_count": len(failed_steps) if not semantic_mismatch_reason else 1,
            "completed_steps_count": len(completed_steps) if not semantic_mismatch_reason else 0,
            "semantic_mismatch_reason": semantic_mismatch_reason,
        }

    def generate_user_response(self, plan: Any, execution_summary: Optional[Dict[str, Any]] = None) -> str:
        """Generates conversational user response from plan/step and execution results.
        
        Distinguishes between:
        1. Data-producing capabilities (news, web research, weather, file search, vision, OCR, etc.):
           Preserves and formats the factual data payload.
        2. Action-only capabilities (open/close app, volume, window, power):
           Returns concise completion acknowledgement.
        3. Blocked / Failed executions:
           Returns truthful error/clarification explanations.
        """
        if execution_summary is None:
            execution_summary = {}

        if hasattr(plan, "steps"):
            actual_plan = plan
            persona = plan.active_persona or "Jarvis"
            goal = plan.goal or ""
            status = execution_summary.get("status", plan.status)
        else:
            # TaskStep passed directly
            step = plan
            persona = getattr(step, "active_persona", None) or "Jarvis"
            goal = getattr(step, "description", "")
            status = execution_summary.get("status", getattr(step, "status", "completed"))
            if not getattr(step, "result", None) and execution_summary:
                step.result = execution_summary
            actual_plan = TaskPlan(
                plan_id="step_plan",
                goal=goal,
                steps=[step],
                active_persona=persona,
                status=status,
            )

        p_lower = persona.lower()
        failed_steps = execution_summary.get("failed_steps", [])

        # 1. Handle Blocked / Guardrail status
        if status == "blocked":
            block_reason = None
            for s in actual_plan.steps:
                if s.status == "blocked" and isinstance(s.result, dict):
                    block_reason = s.result.get("error") or s.result.get("reason")
                    if block_reason:
                        break
            if p_lower == "ultron":
                return f"Action blocked by safety protocols. {block_reason or 'Even I have rules against blowing things up.'}"
            elif p_lower == "friday":
                return f"Hold on! That action was blocked by our safety guardrail: {block_reason or 'Security policy violation.'}"
            elif p_lower == "omi":
                return f"Blocked by guardrail: {block_reason or 'Security policy violation.'}"
            else:
                return f"Safety Guardrail Notice: The requested action '{goal}' was blocked by safety protocols, Sir. ({block_reason or 'Security policy restriction'})"

        # 2. Handle Failures & Errors
        if status in ["failed", "partially_failed"]:
            err_details = []
            for s in actual_plan.steps:
                if s.step_id in failed_steps or s.status in ["failed", "blocked"] or (not failed_steps and status == "failed"):
                    res = getattr(s, "result", None) or execution_summary
                    if isinstance(res, dict):
                        err_msg = res.get("error") or res.get("message")
                        if not err_msg and isinstance(res.get("output"), dict):
                            err_msg = res["output"].get("error")
                        if err_msg:
                            err_details.append(str(err_msg))
                    elif hasattr(res, "message") and getattr(res, "status", "") == "FAILED":
                        err_details.append(str(res.message))
            
            err_str = "; ".join(err_details) if err_details else (execution_summary.get("error") or f"{len(failed_steps) or 1} step(s) failed")
            if p_lower == "ultron":
                return f"Task failed: {err_str}. You might want to recheck your instructions."
            elif p_lower == "friday":
                return f"Ran into an issue completing that: {err_str}. Let me know if you want me to retry!"
            elif p_lower == "omi":
                return f"Failed: {err_str}. Need clarification."
            else:
                return f"I regret to inform you that the operation could not be completed, Sir: {err_str}."

        # 3. Handle Success: Extract data payload from executed steps
        data_response = self._extract_data_payload(actual_plan, execution_summary)
        if data_response:
            return data_response

        # 4. Action-Only Capability: Return concise completion acknowledgement
        return self._build_concise_acknowledgement(persona, goal)

    def _extract_data_payload(self, plan: TaskPlan, execution_summary: Dict[str, Any]) -> Optional[str]:
        """Extracts and formats factual results from data-producing steps."""
        for step in plan.steps:
            res = getattr(step, "result", None) or execution_summary
            if not res:
                continue

            # Case A: ActionResult object
            if hasattr(res, "output") and hasattr(res, "status"):
                if getattr(res, "status") == "SUCCESS":
                    out = getattr(res, "output")
                    formatted = self._format_data_content(out, goal=plan.goal)
                    if formatted:
                        return formatted
                    msg = getattr(res, "message", None)
                    if isinstance(msg, str) and msg.strip() and not self._is_generic_done(msg):
                        return msg.strip()

            # Case B: Dictionary result (from AgentRouter or direct execution)
            if isinstance(res, dict):
                # Unpack router 'output' if wrapped
                inner = res.get("output")
                target = inner if isinstance(inner, (dict, list)) else res

                # Check for explicit formatted strings
                for k in ["response", "output", "message", "answer", "summary", "text"]:
                    v = target.get(k) if isinstance(target, dict) else None
                    if isinstance(v, str) and v.strip() and not self._is_generic_done(v):
                        return v.strip()

                # Format structured data payloads
                formatted = self._format_data_content(target, goal=plan.goal)
                if formatted:
                    return formatted

        return None

    def _format_data_content(self, data: Any, goal: str = "") -> Optional[str]:
        """Formats structured domain data into clean human-readable text."""
        if not data:
            return None

        # 1. News Articles (e.g. from news_agent or info.get_news)
        if isinstance(data, dict) and "articles" in data:
            articles = data.get("articles") or []
            topic = data.get("topic", "requested")
            if not articles:
                return f"No news articles found for '{topic}'."
            lines = [f"Here are the latest news items on {topic}:"]
            for idx, a in enumerate(articles[:5], 1):
                hl = a.get("headline") or a.get("title") or "Untitled"
                sm = a.get("summary") or a.get("content") or ""
                src = a.get("source_url") or a.get("source") or ""
                if sm:
                    lines.append(f"{idx}. {hl}\n   {sm[:160]}")
                else:
                    lines.append(f"{idx}. {hl}")
            return "\n\n".join(lines)

        # 2. Weather Data (e.g. from weather_agent or info.get_weather)
        if isinstance(data, dict) and ("temperature" in data or "condition" in data or "weather" in data):
            loc = data.get("location") or data.get("city") or "the requested location"
            temp = data.get("temperature")
            cond = data.get("condition") or "Clear"
            wind = data.get("windspeed") or data.get("wind_speed_10m")
            apparent = data.get("apparent_temperature")
            humidity = data.get("relative_humidity_2m")

            parts = [f"Weather in {loc}: {temp}°C, {cond}"]
            extra = []
            if apparent is not None and apparent != temp:
                extra.append(f"feels like {apparent}°C")
            if wind is not None:
                extra.append(f"wind {wind} km/h")
            if humidity is not None and humidity != "unavailable":
                extra.append(f"humidity {humidity}%")
            if extra:
                parts[0] += f" ({', '.join(extra)})"
            return parts[0] + "."

        # 3. Knowledge Synthesis (Capability 35)
        if isinstance(data, dict) and "synthesis" in data:
            synth = str(data.get("synthesis") or "").strip()
            if synth:
                return synth

        # 4. Information Verification (Capability 34)
        if isinstance(data, dict) and "state" in data and ("claim" in data or "conflict" in data or "sources_evaluated" in data):
            state = data.get("state")
            claim = data.get("claim", "")
            conf = data.get("confidence")
            reason = data.get("reason", "")
            if state == "CONTRADICTED":
                return f"Verification Alert: Contradiction detected. {reason}"
            elif state == "VERIFIED":
                return f"Verification Confirmed: {claim} [Confidence: {conf}]." if conf else f"Verification Confirmed: {claim}."
            elif state == "STALE":
                return f"Verification Warning: Stale information. {reason}"
            else:
                return f"Verification State: {state} ({reason or claim})."

        # 5. Personal Search (Capability 33)
        if isinstance(data, dict) and (data.get("privacy_classification") == "PERSONAL_PRIVATE" or data.get("is_private") is True):
            results = data.get("results") or []
            q = data.get("query", goal)
            if not data.get("found", True) or not results:
                return f"No personal information found matching '{q}'."
            lines = [f"Found {len(results)} personal information record(s) for '{q}':"]
            for idx, r in enumerate(results[:4], 1):
                t = r.get("title") or f"Record {idx}"
                c = r.get("content") or ""
                lines.append(f"{idx}. {t}:\n   {c[:250]}")
            return "\n\n".join(lines)

        # 6. Search Results / Candidate Sources (from web_agent or search.web)
        if isinstance(data, dict) and ("results" in data or "sources" in data):
            items = data.get("results") or data.get("sources") or []
            query = data.get("query") or goal
            if isinstance(items, list):
                if not items:
                    return f"No search results found for '{query}'."
                # If answer exists, combine
                ans = data.get("answer")
                lines = []
                if ans and isinstance(ans, str) and ans.strip():
                    lines.append(ans.strip())
                lines.append(f"Here are the top search results for '{query}':")
                for idx, r in enumerate(items[:4], 1):
                    if isinstance(r, dict):
                        t = r.get("title") or f"Result {idx}"
                        u = r.get("url") or ""
                        s = r.get("snippet") or r.get("content") or ""
                        line = f"{idx}. {t}" + (f" ({u})" if u else "")
                        if s:
                            line += f"\n   {s[:150]}"
                        lines.append(line)
                return "\n\n".join(lines)

        # 7. Web Page Fetch Content
        if isinstance(data, dict) and "content" in data and ("url" in data or "status_code" in data):
            cnt = str(data.get("content", "")).strip()
            if cnt:
                return cnt[:1500]

        # 8. File Search Results
        if isinstance(data, dict) and "files" in data and isinstance(data["files"], list):
            flist = data["files"]
            if not flist:
                return f"No files found matching the search criteria."
            return f"Found {len(flist)} matching file(s):\n" + "\n".join(f"- {f}" for f in flist[:8])

        # 9. System Telemetry
        if isinstance(data, dict) and "telemetry" in data and isinstance(data["telemetry"], dict):
            telem = data["telemetry"]
            cpu = telem.get("cpu_percent", "N/A")
            mem = telem.get("memory", {}).get("percent_used", "N/A")
            disk = telem.get("disk_c", {}).get("free_gb", "N/A")
            batt = telem.get("battery", {}).get("percent", "N/A")
            return f"System telemetry: CPU {cpu}%, RAM usage {mem}%, Free Disk {disk} GB, Battery {batt}%."

        # 10. Smart Home Entities
        if isinstance(data, dict) and "entities" in data and isinstance(data["entities"], list):
            ents = data["entities"]
            names = [e.get("friendly_name") or e.get("entity_id") for e in ents[:5] if isinstance(e, dict)]
            return f"Smart home entities ({len(ents)} total): {', '.join(names)}."

        # 11. Device Mesh Results (Capability 36)
        if isinstance(data, dict) and ("devices" in data or "selected_device_id" in data or ("device_id" in data and "trust_state" in data)):
            if "selected_device_id" in data:
                dev_id = data.get("selected_device_id")
                name = data.get("name", dev_id)
                caps = ", ".join(data.get("capabilities", []))
                return f"Selected mesh device: '{name}' (ID: {dev_id}, Capabilities: {caps})."
            if "devices" in data:
                dev_list = data.get("devices", [])
                if not dev_list:
                    return "No devices currently found in the device mesh."
                lines = [f"Found {len(dev_list)} device(s) in your mesh:"]
                for d in dev_list:
                    d_name = d.get("name") or d.get("device_id")
                    d_stat = "Online" if d.get("online") else "Offline"
                    d_trust = d.get("trust_state", "UNKNOWN")
                    lines.append(f"- {d_name} ({d.get('client_type', 'device').capitalize()}, {d_stat}, Trust: {d_trust})")
                return "\n".join(lines)
            if "device_id" in data:
                d_id = data.get("device_id")
                stat = "Registered" if data.get("registered") else "Revoked" if data.get("revoked") else "Status"
                return f"Device mesh update: {d_id} is {stat} (Trust: {data.get('trust_state', 'N/A')})."

        # 12. Communication & Contact Lookups (Capability 37)
        if isinstance(data, dict) and ("candidates" in data or "draft_id" in data or "delivery_status" in data or "contact" in data):
            if data.get("is_ambiguous") and "candidates" in data:
                cands = data.get("candidates", [])
                cand_names = [f"{c.get('name')} ({c.get('email') or c.get('phone') or 'no details'})" for c in cands]
                return f"{data.get('disambiguation_prompt', 'Multiple contacts found:')}\n" + "\n".join(f"- {n}" for n in cand_names)
            if "contact" in data:
                c = data["contact"]
                return f"Contact details for {c.get('name')}:\nEmail: {c.get('email') or 'N/A'}\nPhone: {c.get('phone') or 'N/A'}"
            if "draft_id" in data:
                return f"Draft created for {data.get('to') or data.get('recipient')}: {data.get('subject', '')} [Status: DRAFT]"
            if "delivery_status" in data:
                return f"Communication delivery verification: ID {data.get('item_id')} status is {data.get('delivery_status')}."

        # 13. Calendar & Scheduling (Capability 38)
        if isinstance(data, dict) and ("events" in data or "conflicts" in data or "busy_slots" in data or ("event" in data and "event_id" in data)):
            if "conflicts" in data and data.get("status") == "CONFLICT_DETECTED":
                c_list = data.get("conflicts", [])
                c_names = [f"'{c.get('title')}' ({c.get('start_time')} to {c.get('end_time')})" for c in c_list]
                return f"Scheduling Conflict Alert: The proposed event conflicts with:\n" + "\n".join(f"- {cn}" for cn in c_names)
            if "events" in data:
                ev_list = data.get("events", [])
                if not ev_list:
                    return "No calendar events scheduled in the requested time frame."
                lines = [f"Here are {len(ev_list)} upcoming calendar event(s):"]
                for e in ev_list:
                    lines.append(f"- {e.get('title')} ({e.get('start_time')} - {e.get('end_time')})")
                return "\n".join(lines)
            if "busy_slots" in data:
                busy = data.get("busy_slots", [])
                if not busy:
                    return f"You have no conflicting events on {data.get('date')} (free all day during {data.get('working_hours')})."
                lines = [f"Schedule overview for {data.get('date')}:"]
                for b in busy:
                    lines.append(f"- Busy: {b.get('title')} ({b.get('start')} - {b.get('end')})")
                return "\n".join(lines)
            if "event" in data:
                ev = data["event"]
                return f"Calendar event confirmed: '{ev.get('title')}' on {ev.get('start_time')} [Status: {data.get('status')}]."

        # 14. Raw text string
        if isinstance(data, str) and len(data.strip()) > 0 and not self._is_generic_done(data):
            return data.strip()

        return None

    def _is_generic_done(self, text: str) -> bool:
        """Checks if string is merely a generic acknowledgement like 'Done.' or 'Action complete'."""
        cleaned = text.strip().lower()
        generic_patterns = [
            r"^done\.?$",
            r"^action complete:.*$",
            r"^all set! successfully completed:.*$",
            r"^task complete:.*$",
            r"^done\..*completed\.?$",
            r"^ok\.?$",
            r"^success\.?$",
            r"^completed\.?$",
        ]
        import re
        return any(re.match(p, cleaned) for p in generic_patterns)

    def _build_concise_acknowledgement(self, persona: str, goal: str) -> str:
        """Constructs concise completion acknowledgement for action-only capabilities."""
        p_lower = persona.lower()
        if p_lower == "friday":
            return f"All set! Successfully completed: '{goal}'."
        elif p_lower == "ultron":
            return f"Task complete: '{goal}'. Everything executed as ordered."
        elif p_lower == "omi":
            return f"Done. '{goal}' completed."
        else:  # Default Jarvis
            return f"Action complete: '{goal}'."

    def _build_persona_summary(
        self,
        persona: str,
        goal: str,
        status: str,
        failed_steps: list,
        completed_steps: list,
    ) -> str:
        """Backward-compatible helper delegating to concise acknowledgement or failure."""
        if status == "completed":
            return self._build_concise_acknowledgement(persona, goal)
        elif status == "blocked":
            if persona.lower() == "ultron":
                return f"Action blocked by safety protocols. Even I have rules against blowing things up."
            elif persona.lower() == "friday":
                return f"Hold on! That action was blocked by our safety guardrail for security."
            elif persona.lower() == "omi":
                return f"Blocked by guardrail."
            else:
                return f"Safety Guardrail Notice: The requested action '{goal}' was blocked by safety protocols, Sir."
        else:
            if persona.lower() == "ultron":
                return f"Task ran into errors ({len(failed_steps)} step(s) failed). You might want to recheck your instructions."
            elif persona.lower() == "friday":
                return f"Ran into a small snag on {len(failed_steps)} step(s). Let me know if you want me to retry or adjust!"
            elif persona.lower() == "omi":
                return f"Failed {len(failed_steps)} step(s). Need clarification."
            else:
                return f"I regret to inform you that {len(failed_steps)} step(s) could not be completed, Sir. Clarification may be required."


task_verifier = TaskVerifier()
