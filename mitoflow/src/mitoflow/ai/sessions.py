"""Local JSONL session storage for MitoFlow AI."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from .models import AIMessage, RuntimeEvent

T = TypeVar("T", bound=BaseModel)


class LocalSessionStore:
    """Persist chat messages and runtime events under a local directory."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def create_session(self) -> str:
        """Create a session directory and return its id."""
        session_id = str(uuid.uuid4())
        self._session_dir(session_id).mkdir(parents=True, exist_ok=False)
        (self._session_dir(session_id) / "artifacts").mkdir(parents=True, exist_ok=True)
        return session_id

    def session_exists(self, session_id: str) -> bool:
        """Return whether a session exists."""
        return self._session_dir(session_id).exists()

    def artifact_dir(self, session_id: str) -> Path:
        """Return the artifact directory for a session."""
        path = self._session_dir(session_id) / "artifacts"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def append_message(self, session_id: str, message: AIMessage) -> None:
        """Append one message to a session."""
        self._append_model(self._messages_path(session_id), message)

    def load_messages(self, session_id: str) -> list[AIMessage]:
        """Load all messages for a session."""
        return self._load_models(self._messages_path(session_id), AIMessage)

    def append_event(self, session_id: str, event: RuntimeEvent) -> None:
        """Append one runtime event to a session."""
        self._append_model(self._events_path(session_id), event)

    def load_events(self, session_id: str) -> list[RuntimeEvent]:
        """Load all runtime events for a session."""
        return self._load_models(self._events_path(session_id), RuntimeEvent)

    def _session_dir(self, session_id: str) -> Path:
        return self.root / session_id

    def _messages_path(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "messages.jsonl"

    def _events_path(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "events.jsonl"

    def _append_model(self, path: Path, value: BaseModel) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(value.model_dump(mode="json"), ensure_ascii=True) + "\n")

    def _load_models(self, path: Path, model_type: type[T]) -> list[T]:
        if not path.exists():
            return []
        values: list[T] = []
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    values.append(model_type.model_validate(json.loads(line)))
        return values
