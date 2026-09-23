"""JARVIS Cognitive Kernel.

Integrates the 5 Cognitive Stages:
1. Understanding Engine
2. World Model
3. Reasoning Engine
4. Goal Engine
5. Planning Engine

Implements Dual-Process Cognitive Routing (System 1 Fast Path vs System 2 Deep Deliberative Path).
"""

import logging
import time
from typing import Any, Dict, Optional
from cognitive.understanding import understanding_engine, CognitiveIntent
from cognitive.world_model import world_model
from cognitive.reasoning import reasoning_engine
from cognitive.goal_engine import goal_engine, GoalTree
from cognitive.planning_engine import planning_engine, CognitivePlan

logger = logging.getLogger("JARVIS.Cognitive.Kernel")


class CognitiveKernel:
    """The central intelligence kernel orchestrating all cognition."""

    def __init__(self):
        self.understanding = understanding_engine
        self.world_model = world_model
        self.reasoning = reasoning_engine
        self.goal_engine = goal_engine
        self.planning_engine = planning_engine

    def process(self, utterance: str, session_id: str = "default") -> Dict[str, Any]:
        """Main ingress for natural language processing."""
        t_start = time.perf_counter()

        # 1. Sample World Model reality JIT
        context = self.world_model.get_context_snapshot()

        # 2. Perception -> Emotion & Social Context Integration (Capability 19)
        social_context = None
        try:
            from capabilities.intelligence import capability_intelligence
            sentiment_provider = capability_intelligence.select_provider("emotion.analyze_sentiment")
            if sentiment_provider:
                res_sentiment = sentiment_provider.execute("emotion.analyze_sentiment", {"text": utterance})
                if res_sentiment.status == "SUCCESS" and res_sentiment.output:
                    conf = res_sentiment.output.get("confidence", 0.0)
                    # Do not force emotion interpretation when confidence is low; preserve uncertainty
                    if conf >= 0.60:
                        urgency_provider = capability_intelligence.select_provider("emotion.detect_urgency")
                        urgency_res = urgency_provider.execute("emotion.detect_urgency", {"text": utterance}) if urgency_provider else None
                        is_urgent = urgency_res.output.get("is_urgent", False) if (urgency_res and urgency_res.status == "SUCCESS") else False

                        social_context = {
                            "sentiment": res_sentiment.output.get("sentiment_category", "neutral"),
                            "confidence": conf,
                            "recommended_tone": res_sentiment.output.get("recommended_tone", "efficient_courteous"),
                            "is_urgent": is_urgent,
                            "uncertainty_preserved": False,
                        }
                    else:
                        social_context = {
                            "sentiment": "neutral",
                            "confidence": conf,
                            "recommended_tone": "balanced",
                            "is_urgent": False,
                            "uncertainty_preserved": True,
                            "disclaimer": "Low confidence emotion cues preserved without forced categorization",
                        }
        except Exception as e:
            logger.debug("[CognitiveKernel] Emotion analysis bypassed: %s", e)

        # Inject social_context into context and World Model without overriding explicit user intent
        if social_context:
            context["social_context"] = social_context
            self.world_model.update_social_context(social_context)

        # 3. Understand Meaning & Disambiguate Intent
        intent: CognitiveIntent = self.understanding.understand(utterance, context)
        logger.info(
            "[CognitiveKernel] Understood intent: domain='%s', action='%s', fast_path=%s (conf=%.2f)",
            intent.domain,
            intent.action,
            intent.is_system_1_fast_path,
            intent.confidence,
        )

        # 4. Dual-Process Routing: System 1 vs System 2
        if intent.is_system_1_fast_path and intent.domain != "chat":
            # System 1: Direct Atomic Goal & Fast Plan Generation (<10ms)
            goal_tree = self.goal_engine.create_atomic_goal(
                goal_text=utterance,
                domain=intent.domain,
                action=intent.action,
                params=intent.parameters,
            )
            plan: CognitivePlan = self.planning_engine.generate_plan(goal_tree, is_fast_path=True, context=context)
            elapsed_ms = (time.perf_counter() - t_start) * 1000

            return {
                "system_path": "System_1_Fast_Path",
                "intent": intent,
                "goal_tree": goal_tree,
                "plan": plan,
                "social_context": social_context,
                "direct_response": None,
                "elapsed_ms": elapsed_ms,
            }
        else:
            # System 2: Deep Deliberative Cognition (Reasoning & Complex Goals)
            # If domain is chat, invoke Reasoning Engine directly
            if intent.domain == "chat" and intent.action != "session_summary":
                direct_resp = self.reasoning.reason(utterance, context)
                elapsed_ms = (time.perf_counter() - t_start) * 1000
                return {
                    "system_path": "System_2_Reasoning",
                    "intent": intent,
                    "goal_tree": None,
                    "plan": None,
                    "social_context": social_context,
                    "direct_response": direct_resp,
                    "elapsed_ms": elapsed_ms,
                }
            else:
                goal_tree = self.goal_engine.decompose(utterance)
                plan = self.planning_engine.generate_plan(goal_tree, is_fast_path=False, context=context)
                elapsed_ms = (time.perf_counter() - t_start) * 1000
                return {
                    "system_path": "System_2_Deliberative",
                    "intent": intent,
                    "goal_tree": goal_tree,
                    "plan": plan,
                    "social_context": social_context,
                    "direct_response": None,
                    "elapsed_ms": elapsed_ms,
                }


    async def execute_plan(self, plan: CognitivePlan, request_id: str = "") -> Dict[str, Any]:
        """Executes a CognitivePlan through the ExecutionKernel with Policy, Verification, and Memory."""
        from execution.runtime import execution_kernel
        from verification.verifier import system_verifier
        from memory.system import memory_system
        from observability.tracer import cognitive_tracer

        req_id = request_id or f"req_{int(time.time()*1000)}"
        t_start = time.perf_counter()

        # Build execution workflow steps
        job_steps = []
        for s in plan.steps:
            job_steps.append({
                "capability": s.required_capability,
                "parameters": s.parameters,
                "timeout_sec": s.timeout_sec,
            })

        job = execution_kernel.create_job(request_id=req_id, goal=plan.root_goal, steps=job_steps)
        exec_summary = await execution_kernel.run_job(job)

        results = []
        verifications = []
        final_response = ""

        for step in job.steps:
            output = step.result.output if step.result else None
            msg = step.result.message if step.result else ""

            # Verification
            ver_res = system_verifier.verify(
                capability=step.capability,
                expected={"action": step.capability},
                actual=output if isinstance(output, dict) else {"result": output, "message": msg},
            )
            verifications.append(ver_res)

            # Record in 7-Tier Episodic Memory
            success = (step.state.value == "completed") and ver_res.is_verified
            step_domain = step.capability.split(".")[0] if "." in step.capability else "system"
            step_status = "completed" if success else "failed"
            step_summary = msg or str(output)
            memory_system.record_episodic_action(
                request_id=req_id,
                persona="Jarvis",
                domain=step_domain,
                action=step.capability,
                target=str(step.parameters.get("target") or step.parameters.get("query") or step.parameters.get("url") or step.parameters.get("path") or ""),
                status=step_status,
                summary=step_summary,
            )

            # Record Observability trace span
            cognitive_tracer.record_span(
                request_id=req_id,
                stage="execution",
                inputs=step.parameters,
                outputs={"output": output, "message": msg, "verified": ver_res.is_verified},
            )

            if msg and not final_response:
                final_response = msg

            results.append({
                "step_id": step.step_id,
                "capability": step.capability,
                "status": step.state.value,
                "verified": ver_res.is_verified,
                "result": output,
                "message": msg,
            })

        elapsed_ms = (time.perf_counter() - t_start) * 1000

        return {
            "status": exec_summary.get("status", "completed"),
            "request_id": req_id,
            "response": final_response or "Action executed and verified successfully.",
            "results": results,
            "verifications": verifications,
            "elapsed_ms": elapsed_ms,
        }

    process_utterance = process



cognitive_kernel = CognitiveKernel()

