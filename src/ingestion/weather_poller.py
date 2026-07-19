import logging
from datetime import datetime, timezone
 
from src.ingestion.tfl_client import get_line_status
from src.storage.log_store import append_jsonl
 
logger = logging.getLogger(__name__)
 
LOG_PATH = "data/logs/tube_status.jsonl"
 
 
def poll_and_store(mode: str = "tube") -> int:
    """Fetch current line status and append it to the log. Returns rows written."""
    lines = get_line_status(mode=mode)
    polled_at = datetime.now(timezone.utc).isoformat()
 
    count = 0
    for line in lines:
        # A line can technically have >1 active status; TfL returns them
        # all in lineStatuses. We log each as its own record rather than
        # picking "the worst one", so no information is thrown away.
        for status in line.get("lineStatuses", []):
            append_jsonl(
                LOG_PATH,
                {
                    "line_id": line["id"],
                    "line_name": line["name"],
                    "status_severity": status["statusSeverity"],
                    "status_description": status["statusSeverityDescription"],
                    "reason": status.get("reason"),
                    "polled_at": polled_at,
                },
            )
            count += 1
 
    logger.info("Appended %d line status record(s) to %s", count, LOG_PATH)
    return count
 