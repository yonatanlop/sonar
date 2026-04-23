from __future__ import annotations

from enum import Enum


class UserRole(str, Enum):
    admin = "admin"
    analyst = "analyst"
    viewer = "viewer"


class SentimentLabel(str, Enum):
    positive = "positive"
    neutral = "neutral"
    negative = "negative"


class AlertSeverity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class AlertAction(str, Enum):
    reported_platform = "reported_platform"
    escalated_mira = "escalated_mira"
    escalated_church = "escalated_church"
    opportunity = "opportunity"
    dismissed = "dismissed"


class LegalCaseLevel(str, Enum):
    platform = "platform"
    mira_legal = "mira_legal"
    church_legal = "church_legal"


class LegalCaseStatus(str, Enum):
    open = "open"
    in_progress = "in_progress"
    closed = "closed"
    escalated = "escalated"


class MonitoringType(str, Enum):
    reputation = "reputation"
    campaign = "campaign"
    legal = "legal"


class ActorType(str, Enum):
    politician = "politician"
    organization = "organization"
    media = "media"
    influencer = "influencer"


class RelationType(str, Enum):
    ally = "ally"
    opponent = "opponent"
    financed_by = "financed_by"
    member_of = "member_of"
