"""SQLAlchemy 2.0 models. Importing this package registers every table on Base.metadata (Alembic needs that)."""
from app.models.apikey import ApiKey
from app.models.audit import AuditImmutable, AuditLog
from app.models.base import Base
from app.models.case import Case, CheckedMessage, Claim, Decision, Document, Job
from app.models.consent import Consent, ConsentEvent
from app.models.rule import Rule, RuleVersion
from app.models.user import Family, User

__all__ = ["ApiKey", "AuditImmutable", "AuditLog", "Base", "Case", "CheckedMessage", "Claim", "Consent", "ConsentEvent",
           "Decision", "Document", "Family", "Job", "Rule", "RuleVersion", "User"]
