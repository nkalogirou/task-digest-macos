from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Literal, Optional

Priority = Literal["urgent", "high", "normal", "new"]
AgeBasis = Literal["assigned", "status"]
StatusSourceKind = Literal["custom_field", "section", "assignee_status"]
ActionState = Literal["action", "waiting"]
SourceKind = Literal["asana", "github"]
GitHubItemKind = Literal["review_request", "authored_pr", "assigned_issue", "mention"]
TaskEventSource = Literal["asana", "github", "local"]
TaskEventKind = Literal["assignment", "status", "comment", "dependency", "github", "due_date", "local", "system"]


@dataclass
class TaskEvent:
    id: str
    source: TaskEventSource
    kind: TaskEventKind
    title: str
    created_at: Optional[datetime] = None
    detail: Optional[str] = None
    actor: Optional[str] = None
    url: Optional[str] = None
    current: bool = False


@dataclass
class RelatedTask:
    gid: str
    title: str
    url: Optional[str] = None
    completed: bool = False


@dataclass(frozen=True)
class AsanaSectionOption:
    gid: str
    name: str
    scope: Literal["my_tasks", "project"]
    project_name: Optional[str] = None

    @property
    def label(self) -> str:
        if self.scope == "my_tasks":
            return f"My Tasks · {self.name}"
        if self.project_name:
            return f"{self.project_name} · {self.name}"
        return self.name


@dataclass(frozen=True)
class AsanaStatusOption:
    gid: str
    name: str


@dataclass
class TaskComment:
    gid: str
    author: str
    text: str
    created_at: datetime
    unread: bool = False


@dataclass
class GitHubCheckDetail:
    name: str
    state: str
    bucket: str = ""
    url: Optional[str] = None
    description: Optional[str] = None
    workflow: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    summary: Optional[str] = None


@dataclass
class GitHubReviewDetail:
    reviewer: str
    state: str
    submitted_at: Optional[datetime] = None
    body: Optional[str] = None
    url: Optional[str] = None
    requested: bool = False


@dataclass
class GitHubReviewThread:
    id: str
    author: str
    body: str
    path: str
    line: Optional[int] = None
    created_at: Optional[datetime] = None
    url: Optional[str] = None
    is_resolved: bool = False
    is_outdated: bool = False


@dataclass
class GitHubLink:
    owner: str
    repo: str
    number: int
    url: str
    kind: Literal["pull", "issue"] = "pull"
    title: Optional[str] = None
    is_draft: bool = False
    state: Optional[str] = None
    review_decision: Optional[str] = None
    action_reasons: List[str] = field(default_factory=list)
    failed_checks: List[str] = field(default_factory=list)
    pending_reviewers: List[str] = field(default_factory=list)
    approvals: int = 0
    checks_pending: bool = False
    mergeable: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    merged_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    merge_state_status: Optional[str] = None
    checks: List[GitHubCheckDetail] = field(default_factory=list)
    reviews: List[GitHubReviewDetail] = field(default_factory=list)
    unresolved_threads: List[GitHubReviewThread] = field(default_factory=list)
    changed_files: int = 0
    additions: int = 0
    deletions: int = 0
    commit_count: int = 0
    top_files: List[str] = field(default_factory=list)
    base_ref_name: Optional[str] = None
    head_ref_name: Optional[str] = None
    head_ref_oid: Optional[str] = None
    last_commit_at: Optional[datetime] = None
    last_review_at: Optional[datetime] = None

    @property
    def key(self) -> str:
        return f"{self.owner}/{self.repo}#{self.number}"

    @property
    def action_required(self) -> bool:
        return bool(self.action_reasons)


@dataclass
class StatusSource:
    kind: StatusSourceKind
    gid: Optional[str] = None
    name: Optional[str] = None
    value: Optional[str] = None


@dataclass
class TaskItem:
    key: str
    title: str
    url: Optional[str]
    source: SourceKind
    created_at: Optional[datetime] = None
    assigned_at: Optional[datetime] = None
    status_changed_at: Optional[datetime] = None
    due_on: Optional[date] = None
    status: Optional[str] = None
    status_source: Optional[StatusSource] = None
    project: Optional[str] = None
    section: Optional[str] = None
    github_links: List[GitHubLink] = field(default_factory=list)
    github_kind: Optional[GitHubItemKind] = None
    priority: Priority = "new"
    age_basis: AgeBasis = "assigned"
    age_working_days: int = 0
    notes: List[str] = field(default_factory=list)
    is_optional: bool = False
    action_state: ActionState = "action"
    stale_waiting: bool = False
    waiting_reason: Optional[str] = None
    dependencies: List[RelatedTask] = field(default_factory=list)
    dependents: List[RelatedTask] = field(default_factory=list)
    recent_comments: List[TaskComment] = field(default_factory=list)
    unread_updates: int = 0
    local_note: str = ""
    manual_priority: Optional[Priority] = None
    focus_rank: Optional[int] = None
    asana_sections: List[AsanaSectionOption] = field(default_factory=list)
    asana_status_options: List[AsanaStatusOption] = field(default_factory=list)
    timeline_events: List[TaskEvent] = field(default_factory=list)
    rule_matches: List[str] = field(default_factory=list)

    @property
    def is_focused(self) -> bool:
        return self.focus_rank is not None


@dataclass(frozen=True)
class SourceStatus:
    name: str
    ok: bool
    detail: str
