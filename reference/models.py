"""Data models for Agent Hook Specification 0.1.

Aligned with:
spec/0.1/ (core.md, events.md, security.md, hitl.md, audit-ledger.md)
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Literal, Optional


@dataclass
class WireHeaders:
    """Wire-level cryptographic headers defined in Section 4.1."""
    hook_id: str
    hook_timestamp: int
    hook_signature: str
    hook_attempt: int = 1
    hook_protocol_version: str = "1.0.0"

    def to_http_headers(self) -> Dict[str, str]:
        return {
            "Hook-Id": self.hook_id,
            "Hook-Timestamp": str(self.hook_timestamp),
            "Hook-Signature": self.hook_signature,
            "Hook-Attempt": str(self.hook_attempt),
            "Hook-Protocol-Version": self.hook_protocol_version,
        }

    @classmethod
    def from_http_headers(cls, headers: Dict[str, str]) -> WireHeaders:
        normalized = {k.lower(): v for k, v in headers.items()}
        return cls(
            hook_id=normalized.get("hook-id", ""),
            hook_timestamp=int(normalized.get("hook-timestamp", "0")),
            hook_signature=normalized.get("hook-signature", ""),
            hook_attempt=int(normalized.get("hook-attempt", "1")),
            hook_protocol_version=normalized.get("hook-protocol-version", "1.0.0"),
        )


@dataclass
class Actor:
    subject: str
    assurance_level: Literal["self_asserted", "device_bound", "verified_mfa"] = "verified_mfa"


@dataclass
class TraceContext:
    traceparent: str
    tracestate: Optional[str] = None


@dataclass
class EventEnvelope:
    """Universal Event Envelope Schema defined in Section 4.2."""
    event_id: str
    event_type: str
    timestamp: str
    session_id: str
    turn_id: str
    sequence: int
    actor: Actor
    content_identity: str
    event_payload: Dict[str, Any]
    failure_mode: Literal["open", "closed"] = "closed"
    timeout_ms: int = 2000
    trace: Optional[TraceContext] = None
    hook_ext: Dict[str, Any] = field(default_factory=dict)
    protocol_version: str = "1.0.0"
    schema_url: str = "https://opensecureai.org/schemas/agent-hook/v1/envelope.json"

    @property
    def hook_event_name(self) -> str:
        return self.event_type

    @property
    def prompt_id(self) -> str:
        return self.turn_id

    @property
    def tool_name(self) -> Optional[str]:
        return self.event_payload.get("tool_name")

    @property
    def tool_input(self) -> Optional[Dict[str, Any]]:
        return self.event_payload.get("tool_input")

    @property
    def tool_use_id(self) -> Optional[str]:
        return self.event_payload.get("tool_use_id")

    @property
    def destination_host(self) -> Optional[str]:
        return self.event_payload.get("destination_host")

    @property
    def destination_port(self) -> Optional[int]:
        return self.event_payload.get("destination_port")

    @property
    def content(self) -> Optional[Any]:
        return self.event_payload.get("content")

    @property
    def memory_key(self) -> Optional[str]:
        return self.event_payload.get("memory_key")

    @property
    def memory_store_id(self) -> Optional[str]:
        return self.event_payload.get("memory_store_id")

    @property
    def config_file_path(self) -> Optional[str]:
        return self.event_payload.get("config_file_path")

    @property
    def revoke_reason(self) -> Optional[str]:
        return self.event_payload.get("revoke_reason")

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "$schema": self.schema_url,
            "protocol_version": self.protocol_version,
            "spec": "agent-hooks/0.1",
            "event_id": self.event_id,
            "hook_event_name": self.event_type,
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "trace": {
                "traceparent": self.trace.traceparent if self.trace else "",
                "tracestate": self.trace.tracestate if self.trace else None,
            },
            "session_id": self.session_id,
            "prompt_id": self.turn_id,
            "turn_id": self.turn_id,
            "sequence": self.sequence,
            "actor": asdict(self.actor),
            "content_identity": self.content_identity,
            "failure_mode": self.failure_mode,
            "timeout_ms": self.timeout_ms,
            "hook_ext": self.hook_ext,
            "event_payload": self.event_payload,
        }
        # In hybrid mode, mirror event_payload fields to top-level for convenience
        for k, v in self.event_payload.items():
            if k not in d:
                d[k] = v
        return d

    def to_flat_dict(self) -> Dict[str, Any]:
        """Output strictly compliant with Agent Hook 0.1 flat schema."""
        d = {
            "spec": "agent-hooks/0.1",
            "event_id": self.event_id,
            "hook_event_name": self.event_type,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "sequence": self.sequence,
            "prompt_id": self.turn_id,
            "actor": asdict(self.actor),
            "content_identity": self.content_identity,
        }
        if self.trace:
            d["trace"] = {
                "traceparent": self.trace.traceparent,
                "span_id": self.trace.traceparent.split("-")[2] if "-" in self.trace.traceparent else "0" * 16,
            }
        for k, v in self.event_payload.items():
            d[k] = v
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EventEnvelope:
        actor_data = data.get("actor", {})
        actor = Actor(
            subject=actor_data.get("subject", "anonymous"),
            assurance_level=actor_data.get("assurance_level", "self_asserted"),
        )
        trace_data = data.get("trace")
        trace = TraceContext(
            traceparent=trace_data.get("traceparent", "") if trace_data else "",
            tracestate=trace_data.get("tracestate") if trace_data else None,
        ) if trace_data else None

        event_name = data.get("hook_event_name") or data.get("event_type", "PreToolUse")
        turn_id = data.get("prompt_id") or data.get("turn_id", "turn-0")

        # Resolve payload from nested event_payload or top-level flat fields
        payload = dict(data.get("event_payload", {}))
        for key in [
            "tool_name", "tool_input", "tool_use_id", "tool_response", "prompt", "model",
            "messages", "destination_host", "destination_port", "protocol", "bytes_sent",
            "bytes_recv", "memory_store_id", "memory_key", "content", "config_file_path",
            "mutation_type", "new_value_hash", "revoke_reason", "revoked_by", "thought_process",
            "trigger_prompt", "execution_risk_tier"
        ]:
            if key in data and key not in payload:
                payload[key] = data[key]

        return cls(
            schema_url=data.get("$schema", "https://opensecureai.org/schemas/agent-hook/v1/envelope.json"),
            protocol_version=data.get("protocol_version", "1.0.0"),
            event_id=data["event_id"],
            event_type=event_name,
            timestamp=data["timestamp"],
            trace=trace,
            session_id=data["session_id"],
            turn_id=turn_id,
            sequence=int(data.get("sequence", 0)),
            actor=actor,
            content_identity=data.get("content_identity", ""),
            failure_mode=data.get("failure_mode", "closed"),
            timeout_ms=int(data.get("timeout_ms", 2000)),
            hook_ext=data.get("hook_ext", {}),
            event_payload=payload,
        )


@dataclass
class TelemetryMetadata:
    latency_ms: Optional[float] = None
    audit_record_id: Optional[str] = None
    receiver_id: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PolicyInfo:
    policy_id: str
    rule_id: str
    receiver_id: str
    reason: str
    triggered_rules: List[str] = field(default_factory=list)


@dataclass
class ThrottleParams:
    retry_after_ms: int
    max_requests_per_minute: int = 60


@dataclass
class EscalationCallback:
    type: str
    url: str


@dataclass
class Escalation:
    approval_id: str
    risk_level: str
    summary: str
    callback: EscalationCallback
    expires_at: str
    on_expiry: str = "deny"
    content_identity_binding: str = ""
    urgency: str = "medium"
    suspension_mode: str = "ephemeral"
    on_timeout: str = "abort"
    remind_interval_seconds: Optional[int] = None
    max_total_timeout_seconds: Optional[int] = None
    allowed_channels: List[str] = field(default_factory=lambda: ["local_terminal", "slack_interactive"])
    channel_dispatch: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ApproverInfo:
    """Identity and assurance level of human approver."""
    subject: str
    channel: Literal["slack", "local_terminal", "itsm", "cli"]
    assurance_level: Literal["self_asserted", "device_bound", "verified_mfa"] = "verified_mfa"
    channel_user_id: Optional[str] = None
    workspace_id: Optional[str] = None


@dataclass
class ApprovalResumptionPayload:
    """Out-of-band resumption payload sent to Agent Runtime / Approval Relay Gateway."""
    approval_id: str
    session_id: str
    turn_id: str
    decision: Literal["approved", "rejected"]
    approver: ApproverInfo
    content_identity_echo: str
    approval_grant_token: str
    approved_at: str
    protocol_version: str = "1.0.0"
    event_type: str = "TurnResumeApproval"
    approver_comments: Optional[str] = None
    schema_url: str = "https://opensecureai.org/schemas/agent-hook/v1/resumption.json"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "$schema": self.schema_url,
            "protocol_version": self.protocol_version,
            "event_type": self.event_type,
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "approval_id": self.approval_id,
            "decision": self.decision,
            "approver": asdict(self.approver),
            "content_identity_echo": self.content_identity_echo,
            "approved_at": self.approved_at,
            "approver_comments": self.approver_comments,
            "approval_grant_token": self.approval_grant_token,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ApprovalResumptionPayload:
        app_data = data["approver"]
        approver = ApproverInfo(
            subject=app_data.get("subject", "anonymous"),
            channel=app_data.get("channel", "local_terminal"),
            assurance_level=app_data.get("assurance_level", "verified_mfa"),
            channel_user_id=app_data.get("channel_user_id"),
            workspace_id=app_data.get("workspace_id"),
        )
        return cls(
            schema_url=data.get("$schema", "https://opensecureai.org/schemas/agent-hook/v1/resumption.json"),
            protocol_version=data.get("protocol_version", "1.0.0"),
            event_type=data.get("event_type", "TurnResumeApproval"),
            session_id=data["session_id"],
            turn_id=data["turn_id"],
            approval_id=data["approval_id"],
            decision=data["decision"],
            approver=approver,
            content_identity_echo=data["content_identity_echo"],
            approval_grant_token=data["approval_grant_token"],
            approved_at=data["approved_at"],
            approver_comments=data.get("approver_comments"),
        )


@dataclass
class UniversalDecisionResponse:
    """Universal Decision Response Schema defined in Section 4.3."""
    decision: Literal["allow", "deny", "transform", "ask", "defer", "throttle"]
    policy: Optional[PolicyInfo] = None
    telemetry: Optional[TelemetryMetadata] = None
    protocol_version: str = "1.0.0"
    updated_payload: Optional[Dict[str, Any]] = None
    throttle_params: Optional[ThrottleParams] = None
    escalation: Optional[Escalation] = None
    updated_permissions: Optional[Dict[str, Any]] = None
    content_classification: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {
            "protocol_version": self.protocol_version,
            "decision": self.decision,
            "policy": asdict(self.policy) if self.policy else None,
            "telemetry": asdict(self.telemetry) if self.telemetry else None,
            "updated_payload": self.updated_payload,
            "throttle_params": asdict(self.throttle_params) if self.throttle_params else None,
            "escalation": asdict(self.escalation) if self.escalation else None,
            "updated_permissions": self.updated_permissions,
            "content_classification": self.content_classification,
        }
        return res

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> UniversalDecisionResponse:
        p_raw = data.get("policy")
        pm = None
        if p_raw:
            pm = PolicyInfo(
                policy_id=p_raw.get("policy_id", ""),
                rule_id=p_raw.get("rule_id", ""),
                receiver_id=p_raw.get("receiver_id", ""),
                reason=p_raw.get("reason", ""),
                triggered_rules=p_raw.get("triggered_rules", []),
            )
        t_raw = data.get("telemetry")
        tm = None
        if t_raw:
            tm = TelemetryMetadata(
                latency_ms=t_raw.get("latency_ms"),
                audit_record_id=t_raw.get("audit_record_id"),
                receiver_id=t_raw.get("receiver_id"),
                extra=t_raw.get("extra", {}),
            )
        tp = None
        if data.get("throttle_params"):
            tp = ThrottleParams(**data["throttle_params"])

        esc = None
        if data.get("escalation"):
            esc_data = data["escalation"]
            cb = EscalationCallback(**esc_data["callback"]) if "callback" in esc_data else None
            esc = Escalation(
                approval_id=esc_data["approval_id"],
                risk_level=esc_data["risk_level"],
                summary=esc_data["summary"],
                callback=cb,
                expires_at=esc_data["expires_at"],
                on_expiry=esc_data.get("on_expiry", "deny"),
                content_identity_binding=esc_data.get("content_identity_binding", ""),
                allowed_channels=esc_data.get("allowed_channels", ["local_terminal", "slack_interactive"]),
                channel_dispatch=esc_data.get("channel_dispatch", {}),
            )

        return cls(
            protocol_version=data.get("protocol_version", "1.0.0"),
            decision=data["decision"],
            policy=pm,
            telemetry=tm,
            updated_payload=data.get("updated_payload"),
            throttle_params=tp,
            escalation=esc,
            updated_permissions=data.get("updated_permissions"),
            content_classification=data.get("content_classification"),
        )


@dataclass
class SessionRevokeSignal:
    """Control Signal Schema defined in Section 4.4 Spec 4."""
    control_action: str = "SessionRevoke"
    timestamp: str = ""
    session_id: str = ""
    target_actor: str = ""
    enforcement: Dict[str, bool] = field(default_factory=lambda: {
        "kill_processes": True,
        "quarantine_sandbox": True,
        "revoke_tokens": True,
    })
    audit_metadata: Dict[str, str] = field(default_factory=dict)
    signature: str = ""
    schema_url: str = "https://opensecureai.org/schemas/agent-hook/v1/control.json"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "$schema": self.schema_url,
            "control_action": self.control_action,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "target_actor": self.target_actor,
            "enforcement": self.enforcement,
            "audit_metadata": self.audit_metadata,
            "signature": self.signature,
        }


@dataclass
class FourBlockAuditRecord:
    """Four-Block Standard Audit Record Schema defined in Section 5.2."""
    schema_version: str = "1.1.0"
    block_1_event_metadata: Dict[str, Any] = field(default_factory=dict)
    block_2_agent_context: Dict[str, Any] = field(default_factory=dict)
    block_3_tool_use_payload: Dict[str, Any] = field(default_factory=dict)
    block_4_security_extension: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "1_event_metadata": self.block_1_event_metadata,
            "2_agent_context": self.block_2_agent_context,
            "3_tool_use_payload": self.block_3_tool_use_payload,
            "4_security_extension": self.block_4_security_extension,
        }
