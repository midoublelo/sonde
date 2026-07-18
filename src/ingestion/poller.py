import logging

from src.ingestion.tfl_client import get_line_status
from src.storage.db import get_session
from src.storage.models import LineStatusSnapshot

logger = logging.getLogger(__name__)

def poll_and_store(mode: str = "tube") -> int:
    lines = get_line_status(mode=mode)

    rows = []
    for line in lines:
        # A line can technically have >1 active status; TfL returns them
        # all in lineStatuses. We store each as its own row rather than
        # picking "the worst one", so no information is thrown away.
        for status in line.get("lineStatuses", []):
            rows.append(
                LineStatusSnapshot(
                    line_id=line["id"],
                    line_name=line["name"],
                    status_severity=status["statusSeverity"],
                    status_description=status["statusSeverityDescription"],
                    reason=status.get("reason"),
                )
            )

    with get_session() as session:
        session.add_all(rows)

    logger.info("Stored %d line status rows", len(rows))
    return len(rows)
