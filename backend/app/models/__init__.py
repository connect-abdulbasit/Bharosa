"""SQLAlchemy models. TODO(Basit): implement the tables below, one file each, with Alembic migrations.

Tables:
  users            id, username, password_hash, role, display_name, language
  families         id, helper_id, head_name            (Helper Mode)
  cases            id, citizen_id, status, claim_type, amount_claimed_pkr, risk_score, confidence, assigned_to, ...
  case_notes       id, case_id, author, text, created_at
  claims           id, case_id, transcript, draft_json, document_id
  documents        id, owner_id, blur_score, fields_json, confidence
  decisions        id, case_id, action, confidence, trace_json, rule_version, model_version
  pipeline_steps   id, claim_id, step, status, detail_json   (resume after failure)
  rules            id, name
  rule_versions    id, rule_id, version, thresholds_json, logic_json, created_by, created_at (immutable)
  consents         id, user_id, scope, granted, granted_at, withdrawn_at, shared_with
  audit_log        id, timestamp, actor, actor_type, action, target, before_json, after_json (append-only)
  api_keys         id, name, key_hash, prefix, scopes, revoked
  webhooks         id, url, events          (with services/webhooks)
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
