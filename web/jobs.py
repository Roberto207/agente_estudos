"""JobManager em memória para operações longas (geração, busca de fontes).

threading.Thread + dict por job_id, sem fila externa (Celery/Redis) — proporcional
a um processo único de uso pessoal, sem necessidade real de distribuição. Jobs são
perdidos se o processo reiniciar (aceitável: é o mesmo custo de fechar um terminal
com uma run de CLI em andamento).
"""
from __future__ import annotations
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Job:
    id: str
    kind: str
    status: str = "running"  # running | done | error
    events: list[dict] = field(default_factory=list)
    result: dict | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def start(self, kind: str, target: Callable, *args, **kwargs) -> str:
        job_id = uuid.uuid4().hex
        job = Job(id=job_id, kind=kind)
        with self._lock:
            self._jobs[job_id] = job

        def _on_event(event_type: str, payload: dict) -> None:
            with self._lock:
                job.events.append({"type": event_type, "payload": payload, "ts": time.time()})

        def _runner() -> None:
            try:
                result = target(*args, on_event=_on_event, **kwargs)
                with self._lock:
                    job.status = "done"
                    job.result = result if isinstance(result, dict) else {"value": result}
            except Exception as exc:
                with self._lock:
                    job.status = "error"
                    job.error = f"{exc}\n{traceback.format_exc(limit=3)}"

        threading.Thread(target=_runner, daemon=True).start()
        return job_id

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)


job_manager = JobManager()
