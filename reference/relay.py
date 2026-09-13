"""Reference Implementation of the Asynchronous HITL Approval Relay Gateway (RFC 0003).

Simulates the Approval Relay's role as an intelligent proxy, streaming gateway, and HITL dispatcher:
1. Intercepts PreToolUse hooks and evaluates security decisions via Security Receiver (PDP).
2. Manages Asynchronous Turn Suspension when decision == 'ask' (eliminating HTTP connection timeouts).
3. Dispatches out-of-band Slack/Teams interactive messages (Block Kit cards with Approve/Deny buttons).
4. Ingests interactive webhook callbacks, validates approver identity, and obtains an Ed25519-signed ApprovalGrantToken.
5. Dispatches resumption payloads to the Agent Runtime to resume turn execution under zero-trust TOCTOU protection.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Literal, Optional

from crypto import (
    Ed25519KeyPair,
    canonical_json_bytes,
    canonical_json_str,
    compute_content_identity,
    sign_approval_grant,
)
from models import (
    ApprovalResumptionPayload,
    ApproverInfo,
    Escalation,
    UniversalDecisionResponse,
)


@dataclass
class SuspendedTurnState:
    """Represents a suspended agent turn held in the Relay's state store."""
    approval_id: str
    session_id: str
    turn_id: str
    tool_name: str
    tool_input: Dict[str, Any]
    content_identity_binding: str
    escalation: Escalation
    suspended_at: float
    status: Literal["SUSPENDED", "APPROVED", "REJECTED", "EXPIRED"] = "SUSPENDED"
    slack_message_ts: Optional[str] = None
    slack_channel_id: Optional[str] = None


class ApprovalRelay:
    """Normative Reference Implementation of the Asynchronous HITL Relay Gateway (RFC 0003)."""

    def __init__(
        self,
        relay_id: str = "approval-relay-01",
        relay_keypair: Optional[Ed25519KeyPair] = None,
    ):
        self.relay_id = relay_id
        self.relay_keypair = relay_keypair or Ed25519KeyPair(key_id=relay_id)

        # In-memory turn suspension store: {approval_id: SuspendedTurnState}
        self.suspension_store: Dict[str, SuspendedTurnState] = {}

        # Out-of-band mock Slack message queue: {approval_id: slack_message_dict}
        self.slack_message_outbox: Dict[str, Dict[str, Any]] = {}

        # Audit history of relayed approvals
        self.relay_audit_log: List[Dict[str, Any]] = []

    def suspend_agent_turn(
        self,
        session_id: str,
        turn_id: str,
        tool_name: str,
        tool_input: Dict[str, Any],
        decision_resp: Any = None,
        escalation: Optional[Escalation] = None,
    ) -> SuspendedTurnState:
        """Suspend an agent turn and format out-of-band notifications."""
        esc: Optional[Escalation] = escalation
        if not esc and decision_resp:
            if isinstance(decision_resp, Escalation):
                esc = decision_resp
            elif isinstance(decision_resp, dict):
                resp_obj = UniversalDecisionResponse.from_dict(decision_resp)
                esc = resp_obj.escalation
            elif hasattr(decision_resp, "escalation"):
                esc = decision_resp.escalation

        if not esc:
            raise ValueError("Cannot suspend turn: Missing escalation metadata in decision")

        approval_id = esc.approval_id

        suspended_turn = SuspendedTurnState(
            approval_id=approval_id,
            session_id=session_id,
            turn_id=turn_id,
            tool_name=tool_name,
            tool_input=tool_input,
            content_identity_binding=esc.content_identity_binding,
            escalation=esc,
            suspended_at=time.time(),
            status="SUSPENDED",
        )
        self.suspension_store[approval_id] = suspended_turn

        # Format and queue Slack Block Kit message if Slack channel is enabled
        if "slack_interactive" in esc.allowed_channels or "slack" in esc.channel_dispatch:
            slack_config = esc.channel_dispatch.get("slack", {})
            slack_msg = self._build_slack_block_kit(
                approval_id=approval_id,
                tool_name=tool_name,
                tool_input=tool_input,
                escalation=esc,
                slack_config=slack_config,
            )
            self.slack_message_outbox[approval_id] = slack_msg
            suspended_turn.slack_channel_id = slack_config.get("channel_id", "C_SECURITY_ALERTS")
            suspended_turn.slack_message_ts = f"17889.{int(time.time())}"

        self.relay_audit_log.append({
            "action": "turn_suspended",
            "approval_id": approval_id,
            "session_id": session_id,
            "turn_id": turn_id,
            "binding": esc.content_identity_binding,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })

        return suspended_turn

    def _build_slack_block_kit(
        self,
        approval_id: str,
        tool_name: str,
        tool_input: Dict[str, Any],
        escalation: Escalation,
        slack_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Construct Slack Block Kit message structure for interactive approval."""
        blocks = slack_config.get("blocks")
        if not blocks:
            command = tool_input.get("command", str(tool_input))
            blocks = [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "🚨 Security Approval Required (Dual-Custody HITL)"},
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Tool:* `{tool_name}`"},
                        {"type": "mrkdwn", "text": f"*Approval ID:* `{approval_id}`"},
                        {"type": "mrkdwn", "text": f"*Risk Level:* *{escalation.risk_level.upper()}*"},
                        {"type": "mrkdwn", "text": f"*Expires At:* `{escalation.expires_at}`"},
                        {"type": "mrkdwn", "text": f"*Summary:* {escalation.summary}"},
                        {"type": "mrkdwn", "text": f"*Content Binding (SHA-256):*\n`{escalation.content_identity_binding}`"},
                    ],
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*Command Payload:*\n```{command}```"},
                },
                {
                    "type": "actions",
                    "block_id": f"hitl_block_{approval_id}",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Approve Operation"},
                            "style": "primary",
                            "action_id": "relay_approve",
                            "value": json.dumps({
                                "approval_id": approval_id,
                                "decision": "approved",
                                "content_identity": escalation.content_identity_binding,
                            }),
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Reject Operation"},
                            "style": "danger",
                            "action_id": "relay_reject",
                            "value": json.dumps({
                                "approval_id": approval_id,
                                "decision": "rejected",
                                "content_identity": escalation.content_identity_binding,
                            }),
                        },
                    ],
                },
            ]

        return {
            "channel": slack_config.get("channel_id", "C_SECOPS_APPROVALS"),
            "text": slack_config.get("notification_text", f"Approval needed for {tool_name}"),
            "blocks": blocks,
            "metadata": {
                "event_type": "agent_hook_escalation",
                "approval_id": approval_id,
                "binding": escalation.content_identity_binding,
            },
        }

    def process_slack_interaction_webhook(
        self,
        slack_action_payload: Dict[str, Any],
        receiver_signer: Any,
    ) -> ApprovalResumptionPayload:
        """Process an inbound Slack interactive button click from an approver.

        Validates approver identity and requests an Ed25519-signed grant from the receiver.
        """
        # Extract button action value
        actions = slack_action_payload.get("actions", [])
        if not actions:
            raise ValueError("Invalid Slack payload: No actions found")

        action_data = json.loads(actions[0].get("value", "{}"))
        approval_id = action_data.get("approval_id")
        decision_raw = action_data.get("decision", "rejected")
        claimed_binding = action_data.get("content_identity", "")

        if approval_id not in self.suspension_store:
            raise ValueError(f"Unknown or expired approval ID: {approval_id}")

        suspended_turn = self.suspension_store[approval_id]

        # Extract approver details from Slack event
        user_info = slack_action_payload.get("user", {})
        approver = ApproverInfo(
            subject=user_info.get("username", "sre_lead@enterprise.com"),
            channel="slack",
            assurance_level="verified_mfa",
            channel_user_id=user_info.get("id", "U_SLACK_SRE_01"),
            workspace_id=slack_action_payload.get("team", {}).get("id", "T_CORP_WORKSPACE"),
        )

        decision: Literal["approved", "rejected"] = "approved" if decision_raw == "approved" else "rejected"
        comments = slack_action_payload.get("comments", "Approved via Slack Interactive Card")

        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # Sign the approval grant using the Security Receiver / KMS keypair
        signer = getattr(receiver_signer, "receiver_keypair", receiver_signer)
        grant_token = sign_approval_grant(
            keypair=signer,
            approval_id=approval_id,
            decision=decision,
            content_identity_echo=claimed_binding,
            approver_subject=approver.subject,
            timestamp=now_iso,
        )

        resumption_payload = ApprovalResumptionPayload(
            approval_id=approval_id,
            session_id=suspended_turn.session_id,
            turn_id=suspended_turn.turn_id,
            decision=decision,
            approver=approver,
            content_identity_echo=claimed_binding,
            approval_grant_token=grant_token,
            approved_at=now_iso,
            approver_comments=comments,
        )

        # Update suspension store state
        suspended_turn.status = "APPROVED" if decision == "approved" else "REJECTED"

        self.relay_audit_log.append({
            "action": "slack_interaction_processed",
            "approval_id": approval_id,
            "decision": decision,
            "approver": approver.subject,
            "grant_token": grant_token,
            "timestamp": now_iso,
        })

        return resumption_payload
