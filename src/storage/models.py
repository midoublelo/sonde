from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class LineStatusSnapshot(Base):
    __tablename__ = "line_status_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # TfL's internal line id, e.g. "victoria", "central"
    line_id: Mapped[str] = mapped_column(String(64), index=True)
    line_name: Mapped[str] = mapped_column(String(128))

    # TfL severity is an integer (10 = Good Service, lower = worse).
    # Keeping both the code and the description means you don't have to
    # hardcode TfL's severity table anywhere else in the project.
    status_severity: Mapped[int] = mapped_column(Integer)
    status_description: Mapped[str] = mapped_column(String(256))

    # Free-text reason, present only when there's a disruption. Nullable.
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    polled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )

    def __repr__(self) -> str:
        return (
            f"<LineStatusSnapshot {self.line_name} "
            f"sev={self.status_severity} at={self.polled_at.isoformat()}>"
        )