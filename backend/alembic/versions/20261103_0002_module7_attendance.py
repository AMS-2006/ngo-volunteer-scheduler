"""Module 7: Attendance & Volunteer History

Revision ID: m7_0002_attendance
Revises: m4_0001_matching
Create Date: 2026-11-03
"""

import sqlalchemy as sa
from alembic import op

revision = "m7_0002_attendance"
down_revision = "m4_0001_matching"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _has_table("attendance_records"):
        status_enum = sa.Enum("present", "absent", "late", name="attendance_status_enum")
        op.create_table(
            "attendance_records",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "event_id",
                sa.String(36),
                sa.ForeignKey("events.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "shift_id",
                sa.String(36),
                sa.ForeignKey("shifts.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "registration_id",
                sa.String(36),
                sa.ForeignKey("registrations.id", ondelete="CASCADE"),
                nullable=False,
                unique=True,
                index=True,
            ),
            sa.Column(
                "volunteer_id",
                sa.String(36),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column("status", status_enum, nullable=False, server_default="present"),
            sa.Column("check_in_time", sa.DateTime(timezone=True), nullable=True),
            sa.Column("check_out_time", sa.DateTime(timezone=True), nullable=True),
            sa.Column("hours_awarded", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column(
                "recorded_by",
                sa.String(36),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.UniqueConstraint("shift_id", "volunteer_id", name="uq_attendance_shift_volunteer"),
            sa.CheckConstraint("hours_awarded >= 0.0", name="ck_attendance_hours_non_negative"),
        )


def downgrade() -> None:
    if _has_table("attendance_records"):
        op.drop_table("attendance_records")
        sa.Enum(name="attendance_status_enum").drop(op.get_bind(), checkfirst=True)
