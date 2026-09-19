"""Create the initial empty schema migration head."""



revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Establish the initial migration head before domain models exist."""


def downgrade() -> None:
    """Return to the pre-migration empty schema state."""
