"""Module 4: matching requirements, shortlists and invitations

Revision ID: m4_0001_matching
Revises:
Create Date: 2026-11-03

Adds ONLY new tables (nothing existing is altered or dropped) plus the nullable
`events.ngo_id` column. Every step is guarded, so it is safe to run on a database
where the dev-mode `Base.metadata.create_all` already created these objects.
Requires the base tables (users, events, shifts, registrations, ngos) to exist.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "m4_0001_matching"
down_revision = None
branch_labels = None
depends_on = None


def _arr():
    return postgresql.ARRAY(sa.String(100))


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _has_column(table: str, column: str) -> bool:
    return column in {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if _has_table("events") and _has_table("ngos") and not _has_column("events", "ngo_id"):
        op.add_column("events", sa.Column("ngo_id", sa.String(36), nullable=True))
        op.create_foreign_key("fk_events_ngo_id", "events", "ngos", ["ngo_id"], ["id"], ondelete="SET NULL")
        op.create_index("ix_events_ngo_id", "events", ["ngo_id"])

    if not _has_table("shift_requirements"):
        op.create_table(
            "shift_requirements",
            sa.Column("shift_id", sa.String(36), sa.ForeignKey("shifts.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("required_skills", _arr(), nullable=False, server_default="{}"),
            sa.Column("optional_skills", _arr(), nullable=False, server_default="{}"),
            sa.Column("interest_tags", _arr(), nullable=False, server_default="{}"),
            sa.Column("skills_mandatory", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("required_city", sa.String(100), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )

    if not _has_table("event_matching_profiles"):
        op.create_table(
            "event_matching_profiles",
            sa.Column("event_id", sa.String(36), sa.ForeignKey("events.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("categories", _arr(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )

    if not _has_table("volunteer_shortlists"):
        op.create_table(
            "volunteer_shortlists",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("shift_id", sa.String(36), sa.ForeignKey("shifts.id", ondelete="CASCADE"), nullable=False),
            sa.Column("volunteer_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("shortlisted_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("match_score", sa.Float(), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("shift_id", "volunteer_id", name="uq_shortlist_shift_volunteer"),
        )
        op.create_index("ix_volunteer_shortlists_shift_id", "volunteer_shortlists", ["shift_id"])
        op.create_index("ix_shortlist_volunteer", "volunteer_shortlists", ["volunteer_id"])

    if not _has_table("volunteer_invitations"):
        op.create_table(
            "volunteer_invitations",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("shift_id", sa.String(36), sa.ForeignKey("shifts.id", ondelete="CASCADE"), nullable=False),
            sa.Column("volunteer_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("invited_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column("match_score", sa.Float(), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("registration_id", sa.String(36), sa.ForeignKey("registrations.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint(
                "status IN ('PENDING','ACCEPTED','DECLINED','EXPIRED','CANCELLED')",
                name="ck_invitation_status",
            ),
        )
        op.create_index(
            "uq_invitations_pending_shift_volunteer",
            "volunteer_invitations",
            ["shift_id", "volunteer_id"],
            unique=True,
            postgresql_where=sa.text("status = 'PENDING'"),
        )
        op.create_index("ix_invitations_volunteer_status", "volunteer_invitations", ["volunteer_id", "status"])
        op.create_index("ix_invitations_shift_status", "volunteer_invitations", ["shift_id", "status"])
        op.create_index(
            "ix_invitations_pending_expiry",
            "volunteer_invitations",
            ["expires_at"],
            postgresql_where=sa.text("status = 'PENDING'"),
        )


def downgrade() -> None:
    for table in ("volunteer_invitations", "volunteer_shortlists", "event_matching_profiles", "shift_requirements"):
        if _has_table(table):
            op.drop_table(table)
    if _has_table("events") and _has_column("events", "ngo_id"):
        op.drop_index("ix_events_ngo_id", table_name="events")
        op.drop_constraint("fk_events_ngo_id", "events", type_="foreignkey")
        op.drop_column("events", "ngo_id")
