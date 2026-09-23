"""Capability 39: Personal Productivity Provider.

Generalized, provider-neutral task, note, routine, and focus management:
- Explicit lifecycle: CREATED -> READY -> IN_PROGRESS -> BLOCKED -> COMPLETED / CANCELLED / ARCHIVED
- Strict dependency graph: Tasks are BLOCKED until all dependencies are COMPLETED;
  completing a dependency automatically unblocks dependents to READY.
- Distinct separation: Task != Calendar Event != Reminder.
- Zero domain-specific hardcoding: Task names, project tags, and priorities are pure data.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
import threading
import time
from typing import Any, Dict, List, Optional
import uuid

from capabilities.base import ActionResult, BaseCapabilityProvider, ProviderMetadata
from capabilities.contracts.schema import SafetyClassification

logger = logging.getLogger("JARVIS.Capabilities.Providers.Productivity")


class TaskStatus(str, Enum):
    CREATED = "CREATED"
    READY = "READY"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    ARCHIVED = "ARCHIVED"


@dataclass
class ProductivityConfig:
    """Runtime configuration for Personal Productivity Provider."""
    default_priority: str = "medium"
    auto_schedule_reminders: bool = False
    max_tasks: int = 1000
    enforce_dependencies: bool = True


@dataclass
class ProductivityItem:
    """Canonical provider-neutral productivity task representation."""
    id: str
    type: str  # "task", "todo", "routine", "focus_session"
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.CREATED
    priority: str = "medium"
    created_at: str = ""
    updated_at: str = ""
    due_at: Optional[str] = None
    timezone: str = "UTC"
    dependencies: List[str] = field(default_factory=list)
    parent_id: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    source: str = "user"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "due_at": self.due_at,
            "timezone": self.timezone,
            "dependencies": list(self.dependencies),
            "parent_id": self.parent_id,
            "tags": list(self.tags),
            "context": dict(self.context),
            "source": self.source,
            "metadata": dict(self.metadata),
        }


class PersonalProductivityProvider(BaseCapabilityProvider):
    """Authoritative provider for Capability 39: Personal Productivity."""

    def __init__(self, config: Optional[ProductivityConfig] = None):
        metadata = ProviderMetadata(
            provider_id="provider.productivity.local_task",
            name="Personal Productivity Provider",
            description="Manages personal tasks, dependencies, notes, focus routines, and deadline tracking.",
            version="1.0.0",
            supported_capabilities=[
                "productivity.create_task",
                "productivity.add_task",
                "productivity.get_tasks",
                "productivity.list_tasks",
                "productivity.update_task",
                "productivity.complete_task",
                "productivity.cancel_task",
                "productivity.delete_task",
                "productivity.check_dependencies",
                "productivity.start_focus_session",
                "productivity.create_note",
                "productivity.get_notes",
                "productivity.triage_notifications",
            ],
            safety_level="modifying",
            priority=10,
            estimated_latency_ms=10.0,
        )
        super().__init__(metadata)
        self.config = config or ProductivityConfig()
        self._lock = threading.RLock()
        self._items: Dict[str, ProductivityItem] = {}
        self._notes: Dict[str, Dict[str, Any]] = {}
        self._active_focus_session: Optional[Dict[str, Any]] = None

    def is_available(self) -> bool:
        return True

    def execute(
        self,
        capability: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> ActionResult:
        operation = capability
        t0 = time.perf_counter()
        try:
            if operation in ("productivity.create_task", "productivity.add_task"):
                return self._create_task(parameters, t0)
            elif operation in ("productivity.get_tasks", "productivity.list_tasks"):
                return self._get_tasks(parameters, t0)
            elif operation == "productivity.update_task":
                return self._update_task(parameters, t0)
            elif operation == "productivity.complete_task":
                return self._complete_task(parameters, t0)
            elif operation == "productivity.cancel_task":
                return self._cancel_task(parameters, t0)
            elif operation == "productivity.delete_task":
                return self._delete_task(parameters, t0)
            elif operation == "productivity.check_dependencies":
                return self._check_dependencies(parameters, t0)
            elif operation == "productivity.start_focus_session":
                return self._start_focus_session(parameters, t0)
            elif operation == "productivity.create_note":
                return self._create_note(parameters, t0)
            elif operation == "productivity.get_notes":
                return self._get_notes(parameters, t0)
            elif operation == "productivity.triage_notifications":
                return self._triage_notifications(parameters, t0)
            else:
                return ActionResult(
                    status="FAILED",
                    action=operation,
                    provider_id="provider.productivity.local_task",
                    output={"error": f"Unsupported operation '{operation}'"},
                    message=f"Unsupported operation '{operation}'",
                    execution_time_ms=(time.perf_counter() - t0) * 1000,
                )
        except Exception as e:
            logger.exception("[PersonalProductivityProvider] Execution failed: %s", e)
            return ActionResult(
                status="FAILED",
                action=operation,
                provider_id="provider.productivity.local_task",
                output={"error": str(e)},
                message=f"Productivity operation error: {str(e)}",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

    def _create_task(self, params: Dict[str, Any], t0: float) -> ActionResult:
        title = params.get("title", "").strip()
        if not title:
            return ActionResult(
                status="FAILED",
                action="productivity.create_task",
                provider_id="provider.productivity.local_task",
                output={"error": "Missing required field 'title'"},
                message="Task creation failed: 'title' is required.",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

        task_id = params.get("id") or f"task_{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(timezone.utc).isoformat()
        dependencies = list(params.get("dependencies", []))

        with self._lock:
            if len(self._items) >= self.config.max_tasks:
                return ActionResult(
                    status="FAILED",
                    action="productivity.create_task",
                    provider_id="provider.productivity.local_task",
                    output={"error": f"Task limit ({self.config.max_tasks}) exceeded."},
                    message="Task limit reached.",
                    execution_time_ms=(time.perf_counter() - t0) * 1000,
                )

            # Dependency Evaluation
            initial_status = TaskStatus.READY
            if self.config.enforce_dependencies and dependencies:
                unmet = [dep_id for dep_id in dependencies if dep_id not in self._items or self._items[dep_id].status != TaskStatus.COMPLETED]
                if unmet:
                    initial_status = TaskStatus.BLOCKED

            # User specified status override if explicit and valid
            if "status" in params:
                try:
                    initial_status = TaskStatus(params["status"])
                except ValueError:
                    pass

            item = ProductivityItem(
                id=task_id,
                type=params.get("type", "task"),
                title=title,
                description=params.get("description", ""),
                status=initial_status,
                priority=params.get("priority", self.config.default_priority),
                created_at=now_iso,
                updated_at=now_iso,
                due_at=params.get("due_at"),
                timezone=params.get("timezone", "UTC"),
                dependencies=dependencies,
                parent_id=params.get("parent_id"),
                tags=params.get("tags", []),
                context=params.get("context", {}),
                source=params.get("source", "user"),
                metadata=params.get("metadata", {}),
            )

            self._items[task_id] = item

            # Optional Calendar / Scheduler Integration (keeping artifacts distinct)
            calendar_link = None
            if params.get("create_calendar_event") and item.due_at:
                calendar_link = self._link_to_calendar(item)
                if calendar_link:
                    item.metadata["calendar_event_id"] = calendar_link

            reminder_link = None
            if (params.get("create_reminder") or self.config.auto_schedule_reminders) and item.due_at:
                reminder_link = self._link_to_scheduler(item)
                if reminder_link:
                    item.metadata["scheduler_reminder_id"] = reminder_link

            return ActionResult(
                status="SUCCESS",
                action="productivity.create_task",
                provider_id="provider.productivity.local_task",
                output={
                    "task": item.to_dict(),
                    "is_blocked": item.status == TaskStatus.BLOCKED,
                    "calendar_event_id": calendar_link,
                    "scheduler_reminder_id": reminder_link,
                },
                message=f"Task '{item.title}' created with status {item.status.value}.",
                evidence=f"Task {item.id} registered (status={item.status.value}, priority={item.priority}).",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

    def _get_tasks(self, params: Dict[str, Any], t0: float) -> ActionResult:
        status_filter = params.get("status")
        tag_filter = params.get("tag")
        priority_filter = params.get("priority")
        parent_filter = params.get("parent_id")
        query = params.get("query", "").strip().lower()

        with self._lock:
            matched: List[Dict[str, Any]] = []
            for item in self._items.values():
                if status_filter and item.status.value != status_filter:
                    continue
                if tag_filter and tag_filter not in item.tags:
                    continue
                if priority_filter and item.priority != priority_filter:
                    continue
                if parent_filter is not None and item.parent_id != parent_filter:
                    continue
                if query and query not in item.title.lower() and query not in item.description.lower():
                    continue
                matched.append(item.to_dict())

            return ActionResult(
                status="SUCCESS",
                action="productivity.get_tasks",
                provider_id="provider.productivity.local_task",
                output={"tasks": matched, "count": len(matched)},
                message=f"Retrieved {len(matched)} productivity tasks.",
                evidence=f"Matched {len(matched)} tasks from memory store.",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

    def _update_task(self, params: Dict[str, Any], t0: float) -> ActionResult:
        task_id = params.get("id") or params.get("task_id")
        if not task_id:
            return ActionResult(
                status="FAILED",
                action="productivity.update_task",
                provider_id="provider.productivity.local_task",
                output={"error": "Missing 'id'"},
                message="Task update failed: missing task ID.",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

        with self._lock:
            if task_id not in self._items:
                return ActionResult(
                    status="NOT_FOUND",
                    action="productivity.update_task",
                    provider_id="provider.productivity.local_task",
                    output={"error": f"Task '{task_id}' not found"},
                    message=f"Task '{task_id}' not found.",
                    execution_time_ms=(time.perf_counter() - t0) * 1000,
                )

            item = self._items[task_id]
            if "title" in params:
                item.title = params["title"]
            if "description" in params:
                item.description = params["description"]
            if "priority" in params:
                item.priority = params["priority"]
            if "due_at" in params:
                item.due_at = params["due_at"]
            if "timezone" in params:
                item.timezone = params["timezone"]
            if "tags" in params:
                item.tags = params["tags"]
            if "dependencies" in params:
                item.dependencies = list(params["dependencies"])
            if "status" in params:
                try:
                    item.status = TaskStatus(params["status"])
                except ValueError:
                    pass

            item.updated_at = datetime.now(timezone.utc).isoformat()

            # Re-evaluate dependency state if not already completed/cancelled
            if self.config.enforce_dependencies and item.status not in (TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.ARCHIVED):
                unmet = [dep_id for dep_id in item.dependencies if dep_id not in self._items or self._items[dep_id].status != TaskStatus.COMPLETED]
                if unmet and item.status != TaskStatus.BLOCKED:
                    item.status = TaskStatus.BLOCKED
                elif not unmet and item.status == TaskStatus.BLOCKED:
                    item.status = TaskStatus.READY

            return ActionResult(
                status="SUCCESS",
                action="productivity.update_task",
                provider_id="provider.productivity.local_task",
                output={"task": item.to_dict()},
                message=f"Task '{item.id}' updated successfully.",
                evidence=f"Updated task {item.id} (status={item.status.value}).",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

    def _complete_task(self, params: Dict[str, Any], t0: float) -> ActionResult:
        task_id = params.get("id") or params.get("task_id")
        if not task_id:
            return ActionResult(
                status="FAILED",
                action="productivity.complete_task",
                provider_id="provider.productivity.local_task",
                output={"error": "Missing 'id'"},
                message="Task completion failed: missing task ID.",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

        with self._lock:
            if task_id not in self._items:
                return ActionResult(
                    status="NOT_FOUND",
                    action="productivity.complete_task",
                    provider_id="provider.productivity.local_task",
                    output={"error": f"Task '{task_id}' not found"},
                    message=f"Task '{task_id}' not found.",
                    execution_time_ms=(time.perf_counter() - t0) * 1000,
                )

            item = self._items[task_id]
            item.status = TaskStatus.COMPLETED
            item.updated_at = datetime.now(timezone.utc).isoformat()

            # CASCADE UNBLOCKING: Check all tasks that depend on this task
            unblocked_tasks: List[str] = []
            if self.config.enforce_dependencies:
                for other in self._items.values():
                    if other.status == TaskStatus.BLOCKED and task_id in other.dependencies:
                        # Check if all other's dependencies are now completed
                        remaining_unmet = [
                            d for d in other.dependencies
                            if d not in self._items or self._items[d].status != TaskStatus.COMPLETED
                        ]
                        if not remaining_unmet:
                            other.status = TaskStatus.READY
                            other.updated_at = datetime.now(timezone.utc).isoformat()
                            unblocked_tasks.append(other.id)

            return ActionResult(
                status="SUCCESS",
                action="productivity.complete_task",
                provider_id="provider.productivity.local_task",
                output={
                    "task": item.to_dict(),
                    "unblocked_tasks": unblocked_tasks,
                },
                message=f"Task '{item.id}' marked COMPLETED. Unblocked {len(unblocked_tasks)} dependent task(s).",
                evidence=f"Task {item.id} completed. Cascade unblocked: {unblocked_tasks}.",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

    def _cancel_task(self, params: Dict[str, Any], t0: float) -> ActionResult:
        task_id = params.get("id") or params.get("task_id")
        with self._lock:
            if not task_id or task_id not in self._items:
                return ActionResult(
                    status="NOT_FOUND" if task_id else "FAILED",
                    action="productivity.cancel_task",
                    provider_id="provider.productivity.local_task",
                    output={"error": f"Task '{task_id}' not found"},
                    message=f"Task '{task_id}' not found.",
                    execution_time_ms=(time.perf_counter() - t0) * 1000,
                )
            item = self._items[task_id]
            item.status = TaskStatus.CANCELLED
            item.updated_at = datetime.now(timezone.utc).isoformat()

            return ActionResult(
                status="SUCCESS",
                action="productivity.cancel_task",
                provider_id="provider.productivity.local_task",
                output={"task": item.to_dict()},
                message=f"Task '{item.id}' cancelled.",
                evidence=f"Task {item.id} cancelled.",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

    def _delete_task(self, params: Dict[str, Any], t0: float) -> ActionResult:
        task_id = params.get("id") or params.get("task_id")
        with self._lock:
            if not task_id or task_id not in self._items:
                return ActionResult(
                    status="NOT_FOUND" if task_id else "FAILED",
                    action="productivity.delete_task",
                    provider_id="provider.productivity.local_task",
                    output={"error": f"Task '{task_id}' not found"},
                    message=f"Task '{task_id}' not found.",
                    execution_time_ms=(time.perf_counter() - t0) * 1000,
                )
            deleted = self._items.pop(task_id)
            return ActionResult(
                status="SUCCESS",
                action="productivity.delete_task",
                provider_id="provider.productivity.local_task",
                output={"deleted_id": task_id, "title": deleted.title},
                message=f"Task '{task_id}' removed from store.",
                evidence=f"Task {task_id} successfully deleted.",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

    def _check_dependencies(self, params: Dict[str, Any], t0: float) -> ActionResult:
        task_id = params.get("id") or params.get("task_id")
        with self._lock:
            if task_id:
                if task_id not in self._items:
                    return ActionResult(
                        status="NOT_FOUND",
                        action="productivity.check_dependencies",
                        provider_id="provider.productivity.local_task",
                        output={"error": f"Task '{task_id}' not found"},
                        message=f"Task '{task_id}' not found.",
                        execution_time_ms=(time.perf_counter() - t0) * 1000,
                    )
                target = self._items[task_id]
                dep_details = []
                for d in target.dependencies:
                    dep_item = self._items.get(d)
                    dep_details.append({
                        "dependency_id": d,
                        "exists": dep_item is not None,
                        "status": dep_item.status.value if dep_item else "UNKNOWN",
                        "is_completed": dep_item.status == TaskStatus.COMPLETED if dep_item else False,
                    })
                all_met = all(d["is_completed"] for d in dep_details)
                return ActionResult(
                    status="SUCCESS",
                    action="productivity.check_dependencies",
                    provider_id="provider.productivity.local_task",
                    output={
                        "task_id": task_id,
                        "is_blocked": not all_met,
                        "dependencies": dep_details,
                    },
                    message=f"Task '{task_id}' dependencies evaluated: {'BLOCKED' if not all_met else 'SATISFIED'}.",
                    evidence=f"Task {task_id} has {len(dep_details)} dependencies (all_met={all_met}).",
                    execution_time_ms=(time.perf_counter() - t0) * 1000,
                )
            else:
                # Summary across all tasks
                blocked_count = sum(1 for t in self._items.values() if t.status == TaskStatus.BLOCKED)
                ready_count = sum(1 for t in self._items.values() if t.status == TaskStatus.READY)
                return ActionResult(
                    status="SUCCESS",
                    action="productivity.check_dependencies",
                    provider_id="provider.productivity.local_task",
                    output={
                        "total_tasks": len(self._items),
                        "blocked_tasks": blocked_count,
                        "ready_tasks": ready_count,
                    },
                    message=f"Dependency graph: {ready_count} READY, {blocked_count} BLOCKED.",
                    evidence=f"Total tasks: {len(self._items)}, blocked: {blocked_count}.",
                    execution_time_ms=(time.perf_counter() - t0) * 1000,
                )

    def _start_focus_session(self, params: Dict[str, Any], t0: float) -> ActionResult:
        task_id = params.get("task_id")
        duration_min = int(params.get("duration_minutes", 25))
        now_iso = datetime.now(timezone.utc).isoformat()

        with self._lock:
            task_title = "General Focus"
            if task_id and task_id in self._items:
                self._items[task_id].status = TaskStatus.IN_PROGRESS
                task_title = self._items[task_id].title

            session_id = f"focus_{uuid.uuid4().hex[:8]}"
            self._active_focus_session = {
                "session_id": session_id,
                "task_id": task_id,
                "task_title": task_title,
                "duration_minutes": duration_min,
                "started_at": now_iso,
                "is_active": True,
            }

            return ActionResult(
                status="SUCCESS",
                action="productivity.start_focus_session",
                provider_id="provider.productivity.local_task",
                output=dict(self._active_focus_session),
                message=f"Focus session started for '{task_title}' ({duration_min} min).",
                evidence=f"Focus session {session_id} active.",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

    def _create_note(self, params: Dict[str, Any], t0: float) -> ActionResult:
        title = params.get("title", "Untitled Note")
        content = params.get("content", "")
        note_id = params.get("id") or f"note_{uuid.uuid4().hex[:8]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        with self._lock:
            note = {
                "id": note_id,
                "title": title,
                "content": content,
                "tags": params.get("tags", []),
                "task_id": params.get("task_id"),
                "created_at": now_iso,
            }
            self._notes[note_id] = note

            return ActionResult(
                status="SUCCESS",
                action="productivity.create_note",
                provider_id="provider.productivity.local_task",
                output={"note": note},
                message=f"Note '{title}' saved successfully.",
                evidence=f"Note {note_id} stored.",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

    def _get_notes(self, params: Dict[str, Any], t0: float) -> ActionResult:
        tag = params.get("tag")
        task_id = params.get("task_id")
        with self._lock:
            matched = []
            for n in self._notes.values():
                if tag and tag not in n.get("tags", []):
                    continue
                if task_id and n.get("task_id") != task_id:
                    continue
                matched.append(n)
            return ActionResult(
                status="SUCCESS",
                action="productivity.get_notes",
                provider_id="provider.productivity.local_task",
                output={"notes": matched, "count": len(matched)},
                message=f"Retrieved {len(matched)} notes.",
                evidence=f"Matched {len(matched)} notes.",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

    def _triage_notifications(self, params: Dict[str, Any], t0: float) -> ActionResult:
        """Evaluates pending tasks or alerts by priority and deadline closeness."""
        with self._lock:
            urgent_tasks = []
            now = datetime.now(timezone.utc)
            for item in self._items.values():
                if item.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.ARCHIVED):
                    continue
                score = 0
                if item.priority in ("urgent", "critical", "highest"):
                    score += 50
                elif item.priority == "high":
                    score += 30

                if item.due_at:
                    try:
                        due_dt = datetime.fromisoformat(item.due_at.replace("Z", "+00:00"))
                        delta_hours = (due_dt - now).total_seconds() / 3600.0
                        if delta_hours < 24:
                            score += 40
                        elif delta_hours < 72:
                            score += 20
                    except Exception:
                        pass

                if score >= 50:
                    urgent_tasks.append({"task_id": item.id, "title": item.title, "urgency_score": score})

            return ActionResult(
                status="SUCCESS",
                action="productivity.triage_notifications",
                provider_id="provider.productivity.local_task",
                output={"high_priority_items": urgent_tasks, "count": len(urgent_tasks)},
                message=f"Triaged {len(urgent_tasks)} high-priority task items.",
                evidence=f"{len(urgent_tasks)} items scored as high priority.",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

    def _link_to_calendar(self, item: ProductivityItem) -> Optional[str]:
        """Optionally creates a distinct calendar event for deadline."""
        try:
            from capabilities.intelligence import capability_intelligence
            cal_prov = capability_intelligence.select_provider("calendar.create_event")
            if cal_prov:
                cal_res = cal_prov.execute("calendar.create_event", {
                    "title": f"Deadline: {item.title}",
                    "start": item.due_at,
                    "timezone": item.timezone,
                    "allow_conflicts": True,
                    "reminders": [30],
                })
                if cal_res.status == "SUCCESS" and cal_res.output:
                    return cal_res.output.get("event_id") or cal_res.output.get("event", {}).get("event_id") or cal_res.output.get("event", {}).get("id")
        except Exception as e:
            logger.debug("[PersonalProductivityProvider] Calendar link skipped: %s", e)
        return None

    def _link_to_scheduler(self, item: ProductivityItem) -> Optional[str]:
        """Optionally creates a distinct scheduler reminder."""
        try:
            from capabilities.intelligence import capability_intelligence
            sched_prov = capability_intelligence.select_provider("scheduler.reminder")
            if sched_prov:
                rem_res = sched_prov.execute("scheduler.reminder", {
                    "time": item.due_at,
                    "message": f"Task Due: {item.title}",
                })
                if rem_res.status == "SUCCESS":
                    return rem_res.output.get("job_id") or rem_res.output.get("reminder_id")
        except Exception as e:
            logger.debug("[PersonalProductivityProvider] Scheduler link skipped: %s", e)
        return None


productivity_provider = PersonalProductivityProvider()
