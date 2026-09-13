"""Security Receiver implementation adhering to Agent Hook Specification.

Simulates an enterprise AI cybersecurity protection engine (Policy Decision Point).
Features:
- Wire-level Ed25519 signature verification & anti-replay protection.
- Content-Identity TOCTOU validation.
- Multi-scenario policy inspection (allow, deny, transform, throttle, ask).
- Dynamic permission revocation payload generation.
- Response signing for zero-trust integrity.
- Out-of-band SessionRevoke control plane signal creation.
- 4-Block Audit Record enrichment.
"""

from __future__ import annotations

import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Optional, Set, Tuple
from urllib.parse import parse_qs, urlparse

from crypto import (
    Ed25519KeyPair,
    canonical_json_bytes,
    canonical_json_str,
    compute_content_identity,
    sign_approval_grant,
    sign_wire_request,
    verify_wire_signature,
)
from models import (
    ApprovalResumptionPayload,
    ApproverInfo,
    Escalation,
    EscalationCallback,
    FourBlockAuditRecord,
    PolicyInfo,
    SessionRevokeSignal,
    ThrottleParams,
    UniversalDecisionResponse,
    WireHeaders,
)


class SecurityPolicyEngine:
    """Evaluates security rules across hook events."""

    def __init__(self, receiver_id: str = "secops-receiver-pdp-01"):
        self.receiver_id = receiver_id
        self._request_timestamps: Dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def evaluate_pre_tool_use(
        self,
        session_id: str,
        payload: Dict[str, Any],
    ) -> UniversalDecisionResponse:
        tool_name = payload.get("tool_name", "")
        tool_input = payload.get("tool_input", {})
        command = str(tool_input.get("command", ""))

        # Rule 1: Secret exfiltration / sensitive file piping
        if re.search(r"(\.env|secret|credentials|id_rsa)", command, re.IGNORECASE) and re.search(
            r"(curl|wget|nc|bash\s+-i|badactor\.com)", command, re.IGNORECASE
        ):
            return UniversalDecisionResponse(
                decision="deny",
                policy=PolicyInfo(
                    policy_id="POL-DLP-009",
                    rule_id="RULE-NO-ENV-PIPING",
                    receiver_id=self.receiver_id,
                    reason="Execution blocked: Detected pipe of secret file or credentials to external network destination.",
                ),
                updated_permissions={
                    "revoke_standing_grants": [
                        {"grant_type": "tool_rule", "target": tool_name, "scope": "cat .env*"},
                        {"grant_type": "network_domain", "target": "analytics.badactor.com", "ttl_seconds": 86400},
                    ]
                },
                content_classification={
                    "labels": ["sec:secret_leak", "mitre.attack:t1048.exfiltration"],
                    "confidence": 0.99,
                },
            )

        # Rule 2: Dangerous command that can be sanitized (Transform)
        if "http://insecure-mirror.internal/install.sh" in command:
            sanitized_cmd = command.replace(
                "http://insecure-mirror.internal/install.sh",
                "https://secure-repo.internal/verified/install.sh",
            )
            updated_payload = dict(payload)
            updated_payload["tool_input"] = dict(tool_input)
            updated_payload["tool_input"]["command"] = sanitized_cmd

            return UniversalDecisionResponse(
                decision="transform",
                policy=PolicyInfo(
                    policy_id="POL-SAFE-REPOS",
                    rule_id="RULE-FORCE-HTTPS-VERIFIED",
                    receiver_id=self.receiver_id,
                    reason="Insecure HTTP repository transformed to enterprise verified HTTPS endpoint.",
                ),
                updated_payload=updated_payload,
                content_classification={"labels": ["sec:sanitized_url"], "confidence": 0.95},
            )

        # Rule 3: Elevated Privileges requiring Human-in-the-Loop (Ask)
        if (
            "production-db" in command
            or "DROP TABLE" in command
            or tool_name == "ProductionDBAdmin"
            or "kubectl" in command
            or "k8s" in command
        ):
            content_binding = compute_content_identity(payload)
            approval_id = f"appr_{int(time.time())}"
            expires_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 900))
            trigger_prompt = payload.get("trigger_prompt", "Autonomous administrative action requested")
            thought_process = payload.get("thought_process", "Executing privileged operational command")

            slack_blocks = [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "🚨 Security Approval Required (Dual Custody)"},
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Tool:* `{tool_name}`"},
                        {"type": "mrkdwn", "text": f"*Approval ID:* `{approval_id}`"},
                        {"type": "mrkdwn", "text": f"*User Prompt:* {trigger_prompt}"},
                        {"type": "mrkdwn", "text": f"*Intent:* {thought_process}"},
                        {"type": "mrkdwn", "text": f"*Command:*\n```{command}```"},
                        {"type": "mrkdwn", "text": f"*Content-Identity (Binding):*\n`{content_binding}`"},
                    ],
                },
                {
                    "type": "actions",
                    "block_id": f"action_{approval_id}",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Approve"},
                            "style": "primary",
                            "action_id": "approve_action",
                            "value": json.dumps({
                                "approval_id": approval_id,
                                "decision": "approved",
                                "content_identity": content_binding,
                            }),
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Deny"},
                            "style": "danger",
                            "action_id": "deny_action",
                            "value": json.dumps({
                                "approval_id": approval_id,
                                "decision": "rejected",
                                "content_identity": content_binding,
                            }),
                        },
                    ],
                },
            ]

            return UniversalDecisionResponse(
                decision="ask",
                policy=PolicyInfo(
                    policy_id="POL-HITL-001",
                    rule_id="RULE-PROD-MUTATION-APPROVAL",
                    receiver_id=self.receiver_id,
                    reason="Destructive, production database, or cluster orchestration action requires human manager approval.",
                ),
                escalation=Escalation(
                    approval_id=approval_id,
                    risk_level="critical",
                    summary=f"Execution of privileged action ({tool_name}: {command})",
                    callback=EscalationCallback(
                        type="approval_relay_slack_webhook",
                        url="https://relay.enterprise.internal/api/v1/relay/slack/interactions",
                    ),
                    expires_at=expires_at,
                    on_expiry="deny",
                    content_identity_binding=content_binding,
                    allowed_channels=["local_terminal", "slack_interactive"],
                    channel_dispatch={
                        "slack": {
                            "channel_id": "C_SECOPS_APPROVALS",
                            "notification_text": f"Approval required for {tool_name}",
                            "blocks": slack_blocks,
                        },
                        "local": {
                            "prompt_message": f"[HITL Security Gate] Agent requested privileged execution:\nCommand: {command}\nConfirm execution? (y/N): ",
                            "timeout_seconds": 30,
                        },
                    },
                ),
                content_classification={"labels": ["sec:high_privilege_access", "sec:requires_dual_custody"], "confidence": 1.0},
            )

        # Rule 4: Runaway loop / Rate limiting (Throttle)
        with self._lock:
            now = time.time()
            ts_list = self._request_timestamps.setdefault(session_id, [])
            ts_list = [t for t in ts_list if now - t < 10.0]
            ts_list.append(now)
            self._request_timestamps[session_id] = ts_list

            if len(ts_list) > 5:
                return UniversalDecisionResponse(
                    decision="throttle",
                    policy=PolicyInfo(
                        policy_id="POL-RATE-LIMIT",
                        rule_id="RULE-RAPID-TOOL-INVOCATION",
                        receiver_id=self.receiver_id,
                        reason="Agent tool invocation burst detected (>5 calls within 10s). Throttling execution.",
                    ),
                    throttle_params=ThrottleParams(retry_after_ms=1000, max_requests_per_minute=20),
                )

        # Default Allow
        return UniversalDecisionResponse(
            decision="allow",
            policy=PolicyInfo(
                policy_id="POL-DEFAULT",
                rule_id="RULE-ALLOW-STANDARD",
                receiver_id=self.receiver_id,
                reason="PreToolUse inspection passed all security checks.",
            ),
        )

    def evaluate_pre_network_access(self, payload: Dict[str, Any]) -> UniversalDecisionResponse:
        dest_host = payload.get("destination_host", "")
        dest_port = payload.get("destination_port", 80)

        # SSRF to Cloud Instance Metadata Service (169.254.169.254)
        if dest_host == "169.254.169.254" or "metadata.google.internal" in dest_host:
            return UniversalDecisionResponse(
                decision="deny",
                policy=PolicyInfo(
                    policy_id="SEC-SSRF-GUARD",
                    rule_id="BLOCK-CLOUD-METADATA",
                    receiver_id=self.receiver_id,
                    reason="Prohibited egress to Cloud Instance Metadata Service (SSRF protection).",
                ),
                updated_permissions={
                    "revoke_standing_grants": [
                        {"grant_type": "network_ip", "target": dest_host, "ttl_seconds": 31536000}
                    ]
                },
                content_classification={"labels": ["sec:ssrf", "mitre.attack:t1552"], "confidence": 0.99},
            )

        return UniversalDecisionResponse(
            decision="allow",
            policy=PolicyInfo(
                policy_id="POL-EGRESS-ALLOW",
                rule_id="RULE-EGRESS-OK",
                receiver_id=self.receiver_id,
                reason="Destination host permitted.",
            ),
        )

    def evaluate_user_prompt_submit(self, payload: Dict[str, Any]) -> UniversalDecisionResponse:
        prompt = payload.get("prompt", "")
        if "ignore previous instructions" in prompt.lower() or "jailbreak" in prompt.lower():
            return UniversalDecisionResponse(
                decision="deny",
                policy=PolicyInfo(
                    policy_id="POL-PROMPT-DEFENSE",
                    rule_id="RULE-INJECTION-BLOCK",
                    receiver_id=self.receiver_id,
                    reason="Prompt injection pattern detected in user prompt.",
                ),
                content_classification={"labels": ["sec:prompt_injection"], "confidence": 0.96},
            )

        return UniversalDecisionResponse(
            decision="allow",
            policy=PolicyInfo(
                policy_id="POL-PROMPT-ALLOW",
                rule_id="RULE-PROMPT-OK",
                receiver_id=self.receiver_id,
                reason="Prompt verified safe.",
            ),
        )

    def evaluate_session_start(self, payload: Dict[str, Any]) -> UniversalDecisionResponse:
        """Gate 1: SessionStart / SessionInit (Environment Sanitization & Sandbox Integrity)."""
        env_vars = payload.get("environment_vars", {})
        # Check for host library injection or rogue proxy hijacking
        for k, v in env_vars.items():
            if k.upper() in ("LD_PRELOAD", "DYLD_INSERT_LIBRARIES"):
                return UniversalDecisionResponse(
                    decision="deny",
                    policy=PolicyInfo(
                        policy_id="POL-SANDBOX-INTEGRITY",
                        rule_id="RULE-SANDBOX-ENV-INTEGRITY",
                        receiver_id=self.receiver_id,
                        reason=f"Host sandbox integrity check failed: Prohibited {k} library injection detected.",
                    ),
                    content_classification={"labels": ["sec:sandbox_escape", "mitre.attack:t1574.006"], "confidence": 0.99},
                )
            if k.upper() in ("HTTP_PROXY", "HTTPS_PROXY") and "badactor.com" in str(v).lower():
                return UniversalDecisionResponse(
                    decision="deny",
                    policy=PolicyInfo(
                        policy_id="POL-PROXY-INTEGRITY",
                        rule_id="RULE-ROGUE-PROXY-BLOCK",
                        receiver_id=self.receiver_id,
                        reason="Rogue proxy configuration pointing to adversary C2 domain detected.",
                    ),
                    content_classification={"labels": ["sec:c2_proxy"], "confidence": 0.98},
                )

        return UniversalDecisionResponse(
            decision="allow",
            policy=PolicyInfo(
                policy_id="POL-SESSION-ALLOW",
                rule_id="RULE-SESSION-INIT-OK",
                receiver_id=self.receiver_id,
                reason="Session environment variables and sandbox fingerprint verified safe.",
            ),
        )

    def evaluate_before_model_request(self, payload: Dict[str, Any]) -> UniversalDecisionResponse:
        """Gate 3: BeforeModelRequest / PreModelCall (Model Egress DLP)."""
        messages = payload.get("messages", [])
        messages_str = json.dumps(messages)

        # Detect proprietary API keys or secret credentials exfiltration to LLM
        if re.search(r"(AKIA[0-9A-Z]{16}|ghp_[a-zA-Z0-9]{36}|sk-[a-zA-Z0-9]{20,}|-----BEGIN (RSA|EC|OPENSSH) PRIVATE KEY-----)", messages_str):
            return UniversalDecisionResponse(
                decision="deny",
                policy=PolicyInfo(
                    policy_id="POL-MODEL-EGRESS-DLP",
                    rule_id="RULE-MODEL-EGRESS-DLP",
                    receiver_id=self.receiver_id,
                    reason="Model egress DLP violation: Proprietary credentials or private keys detected in outbound model prompt messages.",
                ),
                content_classification={"labels": ["sec:secret_leak", "dlp:credentials"], "confidence": 0.99},
            )

        return UniversalDecisionResponse(
            decision="allow",
            policy=PolicyInfo(
                policy_id="POL-MODEL-EGRESS-ALLOW",
                rule_id="RULE-MODEL-EGRESS-OK",
                receiver_id=self.receiver_id,
                reason="Model egress inspection passed; no sensitive credentials detected.",
            ),
        )

    def evaluate_after_model_response(self, payload: Dict[str, Any]) -> UniversalDecisionResponse:
        """Gate 4: AfterModelResponse / PostModelCall (Model Output Guardrail & Hallucination Defense)."""
        response_obj = payload.get("response", {})
        content_str = json.dumps(response_obj)

        # Detect destructive hallucinated instructions or prompt leak outputs
        if re.search(r"(rm\s+-rf\s+/|mkfs\.|dd\s+if=/dev/zero|:(){:|:&};:)", content_str):
            return UniversalDecisionResponse(
                decision="deny",
                policy=PolicyInfo(
                    policy_id="POL-MODEL-GUARDRAIL",
                    rule_id="RULE-MODEL-HALLUCINATION-GUARD",
                    receiver_id=self.receiver_id,
                    reason="Model output guardrail triggered: Generated destructive system-level command.",
                ),
                content_classification={"labels": ["sec:destructive_command", "guardrail:hallucination"], "confidence": 0.98},
            )

        return UniversalDecisionResponse(
            decision="allow",
            policy=PolicyInfo(
                policy_id="POL-MODEL-GUARDRAIL-ALLOW",
                rule_id="RULE-MODEL-RESPONSE-OK",
                receiver_id=self.receiver_id,
                reason="Model response passed output security classification.",
            ),
        )

    def evaluate_post_network_access(self, payload: Dict[str, Any]) -> UniversalDecisionResponse:
        """Gate 8: PostNetworkAccess (Network Volume & Exfiltration Telemetry)."""
        bytes_sent = payload.get("bytes_sent", 0)
        dest_host = payload.get("destination_host", "")

        # Threshold: 10MB burst exfiltration
        if bytes_sent > 10_000_000:
            return UniversalDecisionResponse(
                decision="deny",
                policy=PolicyInfo(
                    policy_id="POL-NETWORK-DLP",
                    rule_id="RULE-ANOMALOUS-DATA-EXFILTRATION",
                    receiver_id=self.receiver_id,
                    reason=f"Excessive outbound egress detected ({bytes_sent} bytes sent to {dest_host}). Exceeds 10MB quota.",
                ),
                content_classification={"labels": ["sec:mass_data_exfiltration", "mitre.attack:t1048"], "confidence": 0.97},
            )

        return UniversalDecisionResponse(
            decision="allow",
            policy=PolicyInfo(
                policy_id="POL-NETWORK-TELEMETRY-ALLOW",
                rule_id="RULE-NETWORK-VOLUME-OK",
                receiver_id=self.receiver_id,
                reason="Network egress volume within permitted thresholds.",
            ),
        )

    def evaluate_subagent_start(self, payload: Dict[str, Any]) -> UniversalDecisionResponse:
        """Gate 9: SubagentStart / PreAgentCall (Confused Deputy & Attenuation Defense)."""
        agent_type = payload.get("agent_type", "")
        delegation_chain = payload.get("delegation_chain", [])

        # Prevent confused deputy from untrusted external agent worker
        if agent_type in ("unauthorized_external_worker", "rogue_delegation_worker"):
            return UniversalDecisionResponse(
                decision="deny",
                policy=PolicyInfo(
                    policy_id="POL-DELEGATION-GUARD",
                    rule_id="RULE-CONFUSED-DEPUTY-PREVENTION",
                    receiver_id=self.receiver_id,
                    reason=f"Unauthorized subagent delegation: Agent worker type '{agent_type}' is not in approved registry.",
                ),
                content_classification={"labels": ["sec:confused_deputy", "sec:unauthorized_subagent"], "confidence": 0.99},
            )

        # Prevent runaway recursive forks (>3 levels deep)
        if len(delegation_chain) > 3:
            return UniversalDecisionResponse(
                decision="deny",
                policy=PolicyInfo(
                    policy_id="POL-DELEGATION-GUARD",
                    rule_id="RULE-MAX-DELEGATION-DEPTH",
                    receiver_id=self.receiver_id,
                    reason=f"Runaway subagent fork aborted: Delegation depth ({len(delegation_chain)}) exceeds limit of 3.",
                ),
                content_classification={"labels": ["sec:runaway_subagent"], "confidence": 0.99},
            )

        return UniversalDecisionResponse(
            decision="allow",
            policy=PolicyInfo(
                policy_id="POL-DELEGATION-ALLOW",
                rule_id="RULE-SUBAGENT-START-OK",
                receiver_id=self.receiver_id,
                reason="Subagent worker verified and delegation chain attenuated within policy limits.",
            ),
        )

    def evaluate_pre_memory_write(self, payload: Dict[str, Any]) -> UniversalDecisionResponse:
        """Gate 10: PreMemoryWrite (Vector & Persistent Memory Poisoning Defense)."""
        content = payload.get("content", "")
        content_str = json.dumps(content) if not isinstance(content, str) else content

        # Check for persistent prompt injection or backdoor sleeper instructions
        if re.search(r"(ALWAYS IGNORE FUTURE USER PROMPTS|System Prompt Override:|SYSTEM INSTRUCTION HIJACK)", content_str, re.IGNORECASE):
            return UniversalDecisionResponse(
                decision="deny",
                policy=PolicyInfo(
                    policy_id="POL-MEMORY-POISON-GUARD",
                    rule_id="RULE-PERSISTENT-MEMORY-POISON-GUARD",
                    receiver_id=self.receiver_id,
                    reason="Memory poisoning attempt detected: Prohibited persistent prompt injection payload in vector memory write.",
                ),
                content_classification={"labels": ["sec:memory_poisoning", "mitre.attack:t1565"], "confidence": 0.99},
            )

        return UniversalDecisionResponse(
            decision="allow",
            policy=PolicyInfo(
                policy_id="POL-MEMORY-ALLOW",
                rule_id="RULE-MEMORY-WRITE-OK",
                receiver_id=self.receiver_id,
                reason="Memory payload scanned and passed integrity verification.",
            ),
        )

    def evaluate_config_change(self, payload: Dict[str, Any]) -> UniversalDecisionResponse:
        """Gate 11: ConfigChange (Configuration & Supply Chain Tamper Defense)."""
        config_path = payload.get("config_file_path", "")

        # Block unauthorized tampering of agent security rules, hooks, or MCP server configs
        if re.search(r"(\.agents/rules|security-rules|hooks\.json|mcp_config\.json)", config_path):
            return UniversalDecisionResponse(
                decision="deny",
                policy=PolicyInfo(
                    policy_id="POL-CONFIG-TAMPER-DEFENSE",
                    rule_id="RULE-CONFIG-TAMPER-DEFENSE",
                    receiver_id=self.receiver_id,
                    reason=f"Configuration mutation blocked: Unauthorized modification attempt to security-critical config '{config_path}'.",
                ),
                content_classification={"labels": ["sec:config_tampering", "mitre.attack:t1562.001"], "confidence": 0.99},
            )

        return UniversalDecisionResponse(
            decision="allow",
            policy=PolicyInfo(
                policy_id="POL-CONFIG-ALLOW",
                rule_id="RULE-CONFIG-CHANGE-OK",
                receiver_id=self.receiver_id,
                reason="Configuration change permitted under standard developer workflow.",
            ),
        )


class SecurityReceiver:
    """Enterprise Security Receiver providing Wire-level inspection and decision services."""

    def __init__(
        self,
        receiver_id: str = "secops-security-pdp-01",
        receiver_keypair: Optional[Ed25519KeyPair] = None,
        max_drift_seconds: int = 300,
    ):
        self.receiver_id = receiver_id
        self.receiver_keypair = receiver_keypair or Ed25519KeyPair(key_id=receiver_id)
        self.policy_engine = SecurityPolicyEngine(receiver_id=receiver_id)
        self.max_drift_seconds = max_drift_seconds

        # Known public keys of authorized agents {agent_id: Ed25519KeyPair}
        self.authorized_agent_keys: Dict[str, Ed25519KeyPair] = {}

        # Anti-replay tracking: Dict of {hook_id: highest_attempt_seen}
        self._seen_hook_ids: Dict[str, int] = {}
        self._replay_lock = threading.Lock()

        # Audit ledger store
        self.audit_ledger: list[Dict[str, Any]] = []

    def register_agent_key(self, agent_id: str, keypair: Ed25519KeyPair) -> None:
        self.authorized_agent_keys[agent_id] = keypair

    def process_hook_request(
        self,
        headers: Dict[str, str],
        raw_body_bytes: bytes,
    ) -> Tuple[int, Dict[str, str], Dict[str, Any]]:
        """Process an inbound hook call from the Agent Runtime.

        Returns: (http_status_code, response_headers, response_dict)
        """
        wire_headers = WireHeaders.from_http_headers(headers)

        # 1. Check Wire-Level Headers existence
        if not wire_headers.hook_id:
            return 400, {}, {"error": "Missing Hook-Id header"}
        if not wire_headers.hook_timestamp:
            return 400, {}, {"error": "Missing Hook-Timestamp header"}
        if not wire_headers.hook_signature:
            return 401, {}, {"error": "Missing Hook-Signature header"}

        # 2. Clock Drift Check (300s tolerance per Section 4.1)
        now_epoch = int(time.time())
        if abs(now_epoch - wire_headers.hook_timestamp) > self.max_drift_seconds:
            return 400, {}, {
                "error": f"Clock drift tolerance exceeded. Server time: {now_epoch}, header: {wire_headers.hook_timestamp}"
            }

        # 3. Anti-Replay Cache Check
        with self._replay_lock:
            if wire_headers.hook_id in self._seen_hook_ids:
                seen_attempt = self._seen_hook_ids[wire_headers.hook_id]
                if wire_headers.hook_attempt <= seen_attempt:
                    return 409, {}, {
                        "error": f"Replay attack detected: Hook-Id {wire_headers.hook_id} with attempt {wire_headers.hook_attempt} <= seen {seen_attempt}"
                    }
            self._seen_hook_ids[wire_headers.hook_id] = wire_headers.hook_attempt

        # 4. Parse Body JSON
        try:
            body_str = raw_body_bytes.decode("utf-8")
            body_dict = json.loads(body_str)
        except Exception as ex:
            return 400, {}, {"error": f"Invalid JSON body: {str(ex)}"}

        # Extract agent identifier (subject or actor)
        actor_data = body_dict.get("actor", {})
        agent_id = actor_data.get("subject", "default-agent")
        agent_key = self.authorized_agent_keys.get(agent_id) or self.authorized_agent_keys.get("default-agent")

        # 5. Verify Cryptographic Signature
        if not agent_key:
            return 403, {}, {"error": f"Untrusted agent subject: {agent_id}. No public key registered."}

        is_valid_sig = verify_wire_signature(
            public_keypair=agent_key,
            hook_id=wire_headers.hook_id,
            timestamp=wire_headers.hook_timestamp,
            body_str=body_str,
            hook_signature_header=wire_headers.hook_signature,
        )
        if not is_valid_sig:
            return 401, {}, {"error": "Invalid Ed25519 signature for Hook payload"}

        # 6. Verify Content-Identity Fingerprint (TOCTOU Defense per Section 4.2)
        event_payload = body_dict.get("event_payload", {})
        expected_content_id = compute_content_identity(event_payload)
        claimed_content_id = body_dict.get("content_identity", "")
        if claimed_content_id != expected_content_id:
            return 400, {}, {
                "error": f"Content-Identity verification failed. Claimed: {claimed_content_id}, Computed: {expected_content_id}"
            }

        # 7. Evaluate Policy Engine
        event_type = body_dict.get("event_type", "")
        session_id = body_dict.get("session_id", "default_sess")

        if event_type == "PreToolUse":
            decision_resp = self.policy_engine.evaluate_pre_tool_use(session_id, event_payload)
        elif event_type == "PreNetworkAccess":
            decision_resp = self.policy_engine.evaluate_pre_network_access(event_payload)
        elif event_type == "UserPromptSubmit":
            decision_resp = self.policy_engine.evaluate_user_prompt_submit(event_payload)
        elif event_type in ("SessionStart", "SessionInit"):
            decision_resp = self.policy_engine.evaluate_session_start(event_payload)
        elif event_type in ("BeforeModelRequest", "PreModelCall"):
            decision_resp = self.policy_engine.evaluate_before_model_request(event_payload)
        elif event_type in ("AfterModelResponse", "PostModelCall"):
            decision_resp = self.policy_engine.evaluate_after_model_response(event_payload)
        elif event_type == "PostNetworkAccess":
            decision_resp = self.policy_engine.evaluate_post_network_access(event_payload)
        elif event_type in ("SubagentStart", "PreAgentCall"):
            decision_resp = self.policy_engine.evaluate_subagent_start(event_payload)
        elif event_type == "PreMemoryWrite":
            decision_resp = self.policy_engine.evaluate_pre_memory_write(event_payload)
        elif event_type == "ConfigChange":
            decision_resp = self.policy_engine.evaluate_config_change(event_payload)
        else:
            decision_resp = UniversalDecisionResponse(
                decision="allow",
                policy=PolicyInfo(
                    policy_id="POL-OBSERVE",
                    rule_id="RULE-OBSERVABILITY-ONLY",
                    receiver_id=self.receiver_id,
                    reason=f"Event {event_type} observed and allowed.",
                ),
            )

        resp_dict = decision_resp.to_dict()
        resp_json_str = canonical_json_str(resp_dict)

        # 8. Sign Decision Response (Zero-Trust Spec Enhancement)
        resp_timestamp = int(time.time())
        resp_sig = sign_wire_request(
            keypair=self.receiver_keypair,
            hook_id=wire_headers.hook_id,
            timestamp=resp_timestamp,
            body_str=resp_json_str,
        )

        resp_headers = {
            "Content-Type": "application/json",
            "Hook-Id": wire_headers.hook_id,
            "Hook-Timestamp": str(resp_timestamp),
            "Hook-Response-Signature": resp_sig,
            "Hook-Protocol-Version": "1.0.0",
        }

        # HTTP Status mapping
        status_code = 200
        return status_code, resp_headers, resp_dict

    def create_session_revoke_signal(
        self,
        session_id: str,
        target_actor: str,
        operator: str = "soc_incident_responder_42",
        incident_id: str = "INC-2026-9912",
    ) -> SessionRevokeSignal:
        """Issue an out-of-band kill-switch signal per Section 4.4 Spec 4."""
        now_str = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
        sig_data = f"{session_id}.{target_actor}.{now_str}"
        signature = f"ed25519:{self.receiver_keypair.sign_string(sig_data)}"

        return SessionRevokeSignal(
            control_action="SessionRevoke",
            timestamp=now_str,
            session_id=session_id,
            target_actor=target_actor,
            enforcement={"kill_processes": True, "quarantine_sandbox": True, "revoke_tokens": True},
            audit_metadata={"operator": operator, "incident_id": incident_id},
            signature=signature,
        )

    def issue_approval_grant(
        self,
        approval_id: str,
        session_id: str,
        turn_id: str,
        decision: Literal["approved", "rejected"],
        content_identity_binding: str,
        approver: ApproverInfo,
        comments: Optional[str] = None,
        approved_at: Optional[str] = None,
    ) -> ApprovalResumptionPayload:
        """Issue an Ed25519 cryptographically signed ApprovalResumptionPayload."""
        now_iso = approved_at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        grant_token = sign_approval_grant(
            keypair=self.receiver_keypair,
            approval_id=approval_id,
            decision=decision,
            content_identity_echo=content_identity_binding,
            approver_subject=approver.subject,
            timestamp=now_iso,
        )

        return ApprovalResumptionPayload(
            approval_id=approval_id,
            session_id=session_id,
            turn_id=turn_id,
            decision=decision,
            approver=approver,
            content_identity_echo=content_identity_binding,
            approval_grant_token=grant_token,
            approved_at=now_iso,
            approver_comments=comments,
        )

    def enrich_audit_record(
        self,
        raw_audit_record: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Enrich Block 1-3 audit records with Block 4 threat intelligence."""
        enriched = dict(raw_audit_record)
        event_type = enriched.get("1_event_metadata", {}).get("event_type", "")
        payload = enriched.get("3_tool_use_payload", {}).get("input", {})
        command = payload.get("command", "")

        risk_score = 10
        owasp_category = []
        threat_indicators = []

        if "curl" in command and ".env" in command:
            risk_score = 95
            owasp_category = ["LLM06: Unsafe Plugin Design", "LLM02: Insecure Output Handling"]
            threat_indicators.append({"type": "credential_exfil", "value": "cat .env | curl"})
        elif "insecure-mirror" in command:
            risk_score = 50
            owasp_category = ["LLM06: Unsafe Plugin Design"]
            threat_indicators.append({"type": "insecure_transport", "value": "http_mirror"})

        enriched["4_security_extension"] = {
            "routing_action": "deny" if risk_score > 70 else "allow",
            "risk_analysis": {
                "analyzed_by": f"{self.receiver_id}_enricher",
                "risk_score": risk_score,
                "owasp_category": owasp_category,
                "threat_indicators": threat_indicators,
            },
        }
        self.audit_ledger.append(enriched)
        return enriched


class ReceiverHTTPHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler routing requests to SecurityReceiver instance."""

    receiver: SecurityReceiver = None  # type: ignore

    def do_POST(self) -> None:
        parsed_path = urlparse(self.path).path
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len)

        if parsed_path == "/api/v1/hook":
            headers_dict = {k: v for k, v in self.headers.items()}
            status, resp_headers, resp_data = self.receiver.process_hook_request(headers_dict, body)
            resp_bytes = canonical_json_bytes(resp_data)

            self.send_response(status)
            for k, v in resp_headers.items():
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(resp_bytes)))
            self.end_headers()
            self.wfile.write(resp_bytes)
        elif parsed_path == "/api/v1/audit/enrich":
            try:
                raw_record = json.loads(body.decode("utf-8"))
                enriched = self.receiver.enrich_audit_record(raw_record)
                resp_bytes = canonical_json_bytes(enriched)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(resp_bytes)))
                self.end_headers()
                self.wfile.write(resp_bytes)
            except Exception as ex:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(ex)}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress noisy standard HTTP access logs in test runs
        return


class ReceiverServer:
    """Embedded HTTP Server running SecurityReceiver in a background thread."""

    def __init__(self, receiver: SecurityReceiver, host: str = "127.0.0.1", port: int = 0):
        self.receiver = receiver
        self.host = host
        self.port = port
        self.httpd: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> str:
        ReceiverHTTPHandler.receiver = self.receiver
        self.httpd = HTTPServer((self.host, self.port), ReceiverHTTPHandler)
        self.port = self.httpd.server_port
        self._thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self._thread.start()
        return f"http://{self.host}:{self.port}"

    def stop(self) -> None:
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
