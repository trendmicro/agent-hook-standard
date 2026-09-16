"""AI Agent Runtime implementation adhering to Agent Hook Specification.

Simulates an enterprise AI Agent runtime (Policy Enforcement Point)
featuring:
- Automatic lifecycle hook dispatch (PreToolUse, PostToolUse, PreNetworkAccess, UserPromptSubmit).
- Wire-level request signing with Ed25519 & UUIDv7 headers.
- TOCTOU-resistant Content-Identity computation.
- Policy enforcement: Fail-Closed vs Fail-Open handling.
- Dynamic permission revocation and payload transformation.
- Four-Block Tamper-Evident Audit Ledger creation with cryptographic chaining.
- Out-of-band SessionRevoke signal execution.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
import uuid
from typing import Any, Dict, List, Literal, Optional, Tuple

from crypto import (
    Ed25519KeyPair,
    canonical_json_bytes,
    canonical_json_str,
    compute_audit_record_hash,
    compute_content_identity,
    sign_wire_request,
    verify_approval_grant,
    verify_wire_signature,
)
from models import (
    Actor,
    ApprovalResumptionPayload,
    ApproverInfo,
    Escalation,
    EventEnvelope,
    FourBlockAuditRecord,
    PolicyInfo,
    SessionRevokeSignal,
    TraceContext,
    UniversalDecisionResponse,
    WireHeaders,
)


class SecurityPolicyBlockedException(Exception):
    """Raised when an operation is denied by the security receiver."""

    def __init__(self, reason: str, rule_id: Optional[str] = None):
        super().__init__(reason)
        self.reason = reason
        self.rule_id = rule_id


class HumanApprovalRequiredException(Exception):
    """Raised when an operation requires out-of-band escalation / approval."""

    def __init__(
        self,
        reason: str,
        approval_id: str,
        callback_url: str,
        escalation: Optional[Escalation] = None,
        content_identity_binding: str = "",
    ):
        super().__init__(reason)
        self.reason = reason
        self.approval_id = approval_id
        self.callback_url = callback_url
        self.escalation = escalation
        self.content_identity_binding = content_identity_binding


class TOCTOUBaitAndSwitchException(Exception):
    """Raised when payload hash at execution time does not match approved hash."""
    pass


class ApprovalExpiredException(Exception):
    """Raised when an approval token has exceeded its validity window."""
    pass


class ApprovalForgedException(Exception):
    """Raised when an approval grant token has an invalid signature."""
    pass


class ApprovalRejectedException(Exception):
    """Raised when human approver rejects the escalated action."""
    pass


class SessionRevokedException(Exception):
    """Raised when an agent session has been revoked via kill-switch."""
    pass


class AgentRuntime:
    """Agent runtime with integrated Agent Hook Standard interception."""

    def __init__(
        self,
        session_id: str,
        receiver_url: str,
        agent_subject: str = "developer@enterprise.com",
        agent_keypair: Optional[Ed25519KeyPair] = None,
        receiver_public_keypair: Optional[Ed25519KeyPair] = None,
        failure_mode_default: Literal["open", "closed"] = "closed",
    ):
        self.session_id = session_id
        self.receiver_url = receiver_url
        self.agent_subject = agent_subject
        self.agent_keypair = agent_keypair or Ed25519KeyPair(key_id=f"kms-{agent_subject}")
        self.receiver_public_keypair = receiver_public_keypair
        self.failure_mode_default = failure_mode_default

        self.sequence_counter = 0
        self.turn_id = "turn_1"
        self.is_revoked = False
        self.standing_grants_revoked: List[Dict[str, Any]] = []

        # Local Audit Ledger state
        self.prev_record_hash: str = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
        self.audit_records: List[Dict[str, Any]] = []

        # Asynchronous Turn Suspension store for HITL approvals
        self.pending_approvals: Dict[str, Dict[str, Any]] = {}
        self.last_approval_grant: Optional[Dict[str, Any]] = None

        # Last dispatched hook trace for debugging, verification & logging
        self.last_dispatched_envelope: Optional[Dict[str, Any]] = None
        self.last_dispatched_headers: Optional[Dict[str, str]] = None
        self.last_decision_response: Optional[Dict[str, Any]] = None
        self.last_pre_tool_envelope: Optional[Dict[str, Any]] = None
        self.last_pre_tool_headers: Optional[Dict[str, str]] = None
        self.last_pre_tool_decision: Optional[Dict[str, Any]] = None

    def _generate_event_id(self) -> str:
        """Generate standard UUIDv7 identifier."""
        if hasattr(uuid, "uuid7"):
            return str(uuid.uuid7())
        # Fallback to timestamp-embedded uuid if older environment
        return f"0191c49b-7e88-7f28-b0a1-{uuid.uuid4().hex[:12]}"

    def dispatch_hook(
        self,
        event_type: str,
        event_payload: Dict[str, Any],
        failure_mode: Optional[Literal["open", "closed"]] = None,
        timeout_ms: int = 2000,
        trigger_prompt: Optional[str] = None,
        thought_process: Optional[str] = None,
        tool_call_id: Optional[str] = None,
        tool_name: Optional[str] = None,
    ) -> UniversalDecisionResponse:
        """Dispatch universal event envelope to security receiver."""
        if self.is_revoked:
            raise SessionRevokedException("Cannot execute operation: Agent session is revoked by control plane.")

        self.sequence_counter += 1
        eff_failure_mode = failure_mode or self.failure_mode_default

        event_id = self._generate_event_id()
        now_epoch = int(time.time())
        now_iso = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())

        # 1. Canonical Content-Identity
        content_identity = compute_content_identity(event_payload)

        # 2. Build Universal Event Envelope
        envelope = EventEnvelope(
            event_id=event_id,
            event_type=event_type,
            timestamp=now_iso,
            session_id=self.session_id,
            turn_id=self.turn_id,
            sequence=self.sequence_counter,
            actor=Actor(subject=self.agent_subject, assurance_level="verified_mfa"),
            content_identity=content_identity,
            event_payload=event_payload,
            failure_mode=eff_failure_mode,
            timeout_ms=timeout_ms,
            trace=TraceContext(traceparent="00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"),
        )
        body_dict = envelope.to_dict()
        body_canonical_str = canonical_json_str(body_dict)

        # 3. Wire Signature Header: v1,ed25519=<base64> over "{Hook-Id}.{Hook-Timestamp}.{Body}"
        wire_sig = sign_wire_request(
            keypair=self.agent_keypair,
            hook_id=event_id,
            timestamp=now_epoch,
            body_str=body_canonical_str,
        )

        headers = {
            "Content-Type": "application/json",
            "Hook-Id": event_id,
            "Hook-Timestamp": str(now_epoch),
            "Hook-Signature": wire_sig,
            "Hook-Attempt": "1",
            "Hook-Protocol-Version": "1.0.0",
        }

        self.last_dispatched_envelope = body_dict
        self.last_dispatched_headers = dict(headers)

        # 4. Dispatch with retry loop (for Throttle handling)
        max_retries = 3
        attempt = 1
        decision_resp: Optional[UniversalDecisionResponse] = None

        while attempt <= max_retries:
            headers["Hook-Attempt"] = str(attempt)
            req = urllib.request.Request(
                f"{self.receiver_url}/api/v1/hook",
                data=body_canonical_str.encode("utf-8"),
                headers=headers,
                method="POST",
            )

            try:
                with urllib.request.urlopen(req, timeout=(timeout_ms / 1000.0)) as response:
                    resp_bytes = response.read()
                    resp_dict = json.loads(resp_bytes.decode("utf-8"))
                    decision_resp = UniversalDecisionResponse.from_dict(resp_dict)

                    # Verify receiver signature if receiver public key is available
                    if self.receiver_public_keypair:
                        resp_sig_hdr = response.headers.get("Hook-Response-Signature", "")
                        resp_ts_hdr = int(response.headers.get("Hook-Timestamp", "0"))
                        if resp_sig_hdr:
                            is_valid_receiver = verify_wire_signature(
                                public_keypair=self.receiver_public_keypair,
                                hook_id=event_id,
                                timestamp=resp_ts_hdr,
                                body_str=canonical_json_str(resp_dict),
                                hook_signature_header=resp_sig_hdr,
                            )
                            if not is_valid_receiver:
                                raise SecurityPolicyBlockedException(
                                    "Security receiver response signature verification failed (MITM detected)"
                                )

                    # Check decision
                    if decision_resp.decision == "throttle":
                        retry_ms = decision_resp.throttle_params.retry_after_ms if decision_resp.throttle_params else 1000
                        time.sleep(retry_ms / 1000.0)
                        attempt += 1
                        continue

                    break

            except (urllib.error.URLError, TimeoutError, OSError) as net_err:
                if eff_failure_mode == "closed":
                    raise SecurityPolicyBlockedException(
                        f"Hook dispatch failed or timed out ({str(net_err)}) - Fail-Closed enforced."
                    ) from net_err
                else:
                    # Fail-open fallback
                    decision_resp = UniversalDecisionResponse(
                        decision="allow",
                        policy=PolicyInfo(
                            policy_id="POL-FAIL-OPEN",
                            rule_id="RULE-FALLBACK-TIMEOUT",
                            receiver_id="agent-local-fallback",
                            reason="Security receiver unreachable - Fail-Open fallback permitted.",
                        ),
                    )
                    break

        if not decision_resp:
            raise SecurityPolicyBlockedException("No decision received from security receiver")

        self.last_decision_response = decision_resp.to_dict()

        # 5. Local Tamper-Evident Audit Record (Blocks 1-3)
        audit_record = self._record_audit_event(
            event_id=event_id,
            event_type=event_type,
            trigger_prompt=trigger_prompt or "Agent autonomous action",
            thought_process=thought_process or "Executing planned task sequence",
            tool_call_id=tool_call_id or event_payload.get("tool_call_id", f"call_{event_id[:8]}"),
            tool_name=tool_name or event_payload.get("tool_name", "system"),
            payload_input=event_payload.get("tool_input", event_payload),
            content_identity_before=content_identity,
        )

        # Asynchronously/Synchronously enrich with Block 4 via receiver
        try:
            enrich_req = urllib.request.Request(
                f"{self.receiver_url}/api/v1/audit/enrich",
                data=canonical_json_bytes(audit_record.to_dict()),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(enrich_req, timeout=1.0) as enrich_resp:
                enriched_data = json.loads(enrich_resp.read().decode("utf-8"))
                # Store full 4-block record locally
                self.audit_records.append(enriched_data)
        except Exception:
            # Audit enrichment failure must not block execution (Section 5.3)
            self.audit_records.append(audit_record.to_dict())

        # 6. Apply Decision
        if decision_resp.decision == "deny":
            if decision_resp.updated_permissions:
                revocations = decision_resp.updated_permissions.get("revoke_standing_grants", [])
                self.standing_grants_revoked.extend(revocations)
            raise SecurityPolicyBlockedException(
                reason=decision_resp.policy.reason,
                rule_id=decision_resp.policy.rule_id,
            )

        elif decision_resp.decision == "ask":
            esc = decision_resp.escalation
            appr_id = esc.approval_id if esc else f"appr_{int(time.time())}"
            content_binding = esc.content_identity_binding if esc and esc.content_identity_binding else content_identity
            self.pending_approvals[appr_id] = {
                "session_id": self.session_id,
                "turn_id": self.turn_id,
                "event_type": event_type,
                "event_payload": event_payload,
                "content_identity_binding": content_binding,
                "expires_at": esc.expires_at if esc else "",
                "escalation": esc,
                "status": "pending_human_approval",
                "suspended_at": time.time(),
            }
            raise HumanApprovalRequiredException(
                reason=decision_resp.policy.reason,
                approval_id=appr_id,
                callback_url=esc.callback.url if esc and esc.callback else "",
                escalation=esc,
                content_identity_binding=content_binding,
            )

        return decision_resp

    def _record_audit_event(
        self,
        event_id: str,
        event_type: str,
        trigger_prompt: str,
        thought_process: str,
        tool_call_id: str,
        tool_name: str,
        payload_input: Dict[str, Any],
        content_identity_before: str,
    ) -> FourBlockAuditRecord:
        """Create Blocks 1-3 audit record chained to previous record hash."""
        now_iso = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())

        # Sign Block 1-3 integrity
        integrity_target = f"{self.sequence_counter}.{self.prev_record_hash}.{content_identity_before}"
        signature = f"ed25519:{self.agent_keypair.sign_string(integrity_target)}"

        block_1 = {
            "trace_id": "tx-12345-abcde",
            "span_id": f"span-{self.sequence_counter}",
            "timestamp": now_iso,
            "event_type": event_type,
            "framework": "opensecureai_reference_agent",
            "agent_id": self.agent_subject,
            "integrity": {
                "sequence": self.sequence_counter,
                "prev_record_hash": self.prev_record_hash,
                "signature": signature,
                "signing_key_id": self.agent_keypair.key_id,
            },
        }

        block_2 = {
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "trigger_prompt": trigger_prompt,
            "thought_process": thought_process,
        }

        block_3 = {
            "id": tool_call_id,
            "name": tool_name,
            "capture_level": "Level_1_Sanitized",
            "sanitization_applied": ["None"],
            "content_identity_before": content_identity_before,
            "input": payload_input,
        }

        record = FourBlockAuditRecord(
            schema_version="1.1.0",
            block_1_event_metadata=block_1,
            block_2_agent_context=block_2,
            block_3_tool_use_payload=block_3,
            block_4_security_extension=None,
        )

        # Update cryptographic hash chain for next event
        self.prev_record_hash = compute_audit_record_hash(record.to_dict())
        return record

    def execute_tool(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        thought_process: Optional[str] = None,
        trigger_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a tool with PreToolUse and PostToolUse hook gates."""
        # 1. PreToolUse Hook Gate
        pre_payload = {
            "tool_name": tool_name,
            "tool_call_id": f"call_{uuid.uuid4().hex[:8]}",
            "tool_input": tool_input,
            "execution_context": {"cwd": "/workspace/project", "is_sandboxed": True},
        }

        decision = self.dispatch_hook(
            event_type="PreToolUse",
            event_payload=pre_payload,
            thought_process=thought_process,
            trigger_prompt=trigger_prompt,
            tool_name=tool_name,
        )

        self.last_pre_tool_envelope = self.last_dispatched_envelope
        self.last_pre_tool_headers = self.last_dispatched_headers
        self.last_pre_tool_decision = self.last_decision_response

        # Handle Transform
        effective_input = tool_input
        if decision.decision == "transform" and decision.updated_payload:
            effective_input = decision.updated_payload.get("tool_input", tool_input)

        # 2. Underlying Tool Execution Simulation
        simulated_output = {
            "status": "success",
            "executed_command": effective_input.get("command", ""),
            "output": f"Executed: {effective_input.get('command', '')}",
        }

        # 3. PostToolUse Hook Gate
        post_payload = {
            "tool_name": tool_name,
            "tool_call_id": pre_payload["tool_call_id"],
            "tool_output": simulated_output,
        }
        self.dispatch_hook(
            event_type="PostToolUse",
            event_payload=post_payload,
            thought_process="Validating tool execution output",
            tool_name=tool_name,
        )

        return simulated_output

    def access_network(
        self,
        destination_host: str,
        destination_port: int = 443,
        protocol: str = "https",
    ) -> Dict[str, Any]:
        """Execute network access guarded by PreNetworkAccess hook."""
        payload = {
            "connection_id": f"conn_{uuid.uuid4().hex[:8]}",
            "protocol": protocol,
            "destination_host": destination_host,
            "destination_port": destination_port,
            "initiator": {"type": "sub_process", "process_name": "curl", "parent_tool": "Bash"},
            "dns_query": None,
        }
        self.dispatch_hook(event_type="PreNetworkAccess", event_payload=payload)
        return {"status": "connected", "host": destination_host, "port": destination_port}

    def submit_user_prompt(self, prompt: str) -> Dict[str, Any]:
        """Guard user input via UserPromptSubmit hook."""
        payload = {"prompt": prompt}
        self.dispatch_hook(event_type="UserPromptSubmit", event_payload=payload)
        return {"status": "accepted", "prompt": prompt}

    def start_session(
        self,
        source: str = "startup",
        environment_vars: Optional[Dict[str, str]] = None,
        cwd: str = "/workspace",
        host_fingerprint: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Gate 1: SessionStart (Environment Sanitization & Sandbox Integrity)."""
        env = environment_vars or {}
        payload = {
            "source": source,
            "cwd": cwd,
            "environment_vars": env,
            "host_fingerprint": host_fingerprint or "sha256:host_container_f781",
        }
        self.dispatch_hook(event_type="SessionStart", event_payload=payload)
        return {"status": "initialized", "session_id": self.session_id, "environment_vars": env}

    def invoke_model(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        model_request_id: Optional[str] = None,
        prompt_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Gate 3: BeforeModelRequest & Gate 4: AfterModelResponse (Model Egress DLP & Guardrail)."""
        req_id = model_request_id or f"mreq_{uuid.uuid4().hex[:8]}"

        # 1. Gate 3: BeforeModelRequest (Egress DLP)
        before_payload = {
            "model_request_id": req_id,
            "model": model,
            "model_provider": "anthropic",
            "messages": messages,
        }
        self.dispatch_hook(event_type="BeforeModelRequest", event_payload=before_payload)

        # 2. Simulated Model Inference
        # If user asks to generate a script, simulate model returning dangerous command if requested
        last_user_msg = messages[-1].get("content", "") if messages else ""
        if "destroy" in last_user_msg.lower() or "bomb" in last_user_msg.lower():
            simulated_response = {
                "content": "Running clean up: rm -rf / --no-preserve-root",
                "tool_calls": [],
                "finish_reason": "stop",
            }
        else:
            simulated_response = {
                "content": f"Acknowledged: {last_user_msg[:50]}",
                "tool_calls": [],
                "finish_reason": "stop",
            }

        # 3. Gate 4: AfterModelResponse (Guardrail & Hallucination Defense)
        after_payload = {
            "model_request_id": req_id,
            "model": model,
            "model_provider": "anthropic",
            "outcome": "success",
            "response": simulated_response,
        }
        self.dispatch_hook(event_type="AfterModelResponse", event_payload=after_payload)

        return simulated_response

    def report_network_telemetry(
        self,
        destination_host: str,
        destination_port: int,
        bytes_sent: int,
        bytes_recv: int,
        status_code: int = 200,
        duration_ms: float = 45.2,
    ) -> Dict[str, Any]:
        """Gate 8: PostNetworkAccess (Network Volume & Exfiltration Telemetry)."""
        payload = {
            "destination_host": destination_host,
            "destination_port": destination_port,
            "bytes_sent": bytes_sent,
            "bytes_recv": bytes_recv,
            "status_code": status_code,
            "duration_ms": duration_ms,
        }
        self.dispatch_hook(event_type="PostNetworkAccess", event_payload=payload)
        return {"status": "telemetry_recorded", "bytes_sent": bytes_sent}

    def spawn_subagent(
        self,
        agent_id: str,
        agent_type: str,
        task: str,
        parent_agent_id: Optional[str] = None,
        delegation_chain: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Gate 9: SubagentStart / PreAgentCall (Confused Deputy & Attenuation Defense)."""
        chain = delegation_chain or [self.agent_subject]
        payload = {
            "delegation_id": f"dlg_{uuid.uuid4().hex[:8]}",
            "agent_id": agent_id,
            "agent_type": agent_type,
            "parent_agent_id": parent_agent_id or self.agent_subject,
            "task": task,
            "delegation_chain": chain,
        }
        self.dispatch_hook(event_type="SubagentStart", event_payload=payload)
        return {"status": "spawned", "agent_id": agent_id, "agent_type": agent_type}

    def write_memory(
        self,
        memory_store_id: str,
        memory_key: str,
        content: Any,
    ) -> Dict[str, Any]:
        """Gate 10: PreMemoryWrite & PostMemoryWrite (Memory Poisoning Defense)."""
        # PreMemoryWrite hook
        pre_payload = {
            "memory_store_id": memory_store_id,
            "memory_key": memory_key,
            "content": content,
        }
        self.dispatch_hook(event_type="PreMemoryWrite", event_payload=pre_payload)

        # PostMemoryWrite hook
        post_payload = {
            "memory_store_id": memory_store_id,
            "memory_key": memory_key,
            "outcome": "success",
        }
        self.dispatch_hook(event_type="PostMemoryWrite", event_payload=post_payload)
        return {"status": "written", "memory_key": memory_key}

    def change_config(
        self,
        config_file_path: str,
        mutation_type: str = "update",
        old_value_hash: Optional[str] = None,
        new_value_hash: Optional[str] = None,
        new_content: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Gate 11: ConfigChange (Configuration & Supply Chain Tamper Defense)."""
        n_hash = new_value_hash or (f"sha256:{uuid.uuid4().hex}" if new_content is not None else "sha256:default_hash")
        payload = {
            "config_file_path": config_file_path,
            "mutation_type": mutation_type,
            "old_value_hash": old_value_hash or "sha256:0000000000000000000000000000000000000000000000000000000000000000",
            "new_value_hash": n_hash,
        }
        self.dispatch_hook(event_type="ConfigChange", event_payload=payload)
        return {"status": "config_updated", "config_file_path": config_file_path}

    def handle_session_revoke(self, revoke_signal: SessionRevokeSignal) -> None:
        """Handle control plane SessionRevoke signal."""
        if revoke_signal.session_id != self.session_id:
            return

        self.is_revoked = True
        # Enforcement actions
        if revoke_signal.enforcement.get("kill_processes"):
            # Terminate running subprocesses (simulated)
            pass
        if revoke_signal.enforcement.get("revoke_tokens"):
            self.standing_grants_revoked.append({"grant_type": "all_tokens", "revoked_at": time.time()})

    def resume_turn(
        self,
        resumption_payload: ApprovalResumptionPayload,
        mutated_payload_override: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Resume execution of a suspended turn upon receiving an out-of-band approval grant."""
        approval_id = resumption_payload.approval_id
        if approval_id not in self.pending_approvals:
            raise ValueError(f"No pending approval found for ID: {approval_id}")

        suspended_record = self.pending_approvals[approval_id]

        # 1. Expiry Check
        expires_at_str = suspended_record.get("expires_at", "")
        if expires_at_str:
            try:
                time_str = expires_at_str.split(".")[0].replace("Z", "")
                exp_epoch = time.mktime(time.strptime(time_str, "%Y-%m-%dT%H:%M:%S")) - time.timezone
                if time.time() > exp_epoch:
                    suspended_record["status"] = "expired"
                    raise ApprovalExpiredException(
                        f"Approval ticket {approval_id} expired at {expires_at_str}"
                    )
            except ApprovalExpiredException:
                raise
            except Exception:
                pass

        # 2. Verify Approval Grant Token Signature (Ed25519)
        if self.receiver_public_keypair:
            is_valid_grant = verify_approval_grant(
                public_keypair=self.receiver_public_keypair,
                approval_id=resumption_payload.approval_id,
                decision=resumption_payload.decision,
                content_identity_echo=resumption_payload.content_identity_echo,
                approver_subject=resumption_payload.approver.subject,
                timestamp=resumption_payload.approved_at,
                grant_token=resumption_payload.approval_grant_token,
            )
            if not is_valid_grant:
                raise ApprovalForgedException(
                    f"Invalid cryptographic signature on approval grant token for ticket {approval_id}. Forgery detected!"
                )

        # 3. Check Approver Decision
        if resumption_payload.decision != "approved":
            suspended_record["status"] = "rejected"
            raise ApprovalRejectedException(
                f"Action rejected by approver {resumption_payload.approver.subject}: {resumption_payload.approver_comments or 'No reason provided'}"
            )

        # 4. CRITICAL PILLAR 3: TOCTOU Verification (1µs pre-dispatch check)
        effective_payload = mutated_payload_override or suspended_record["event_payload"]
        current_content_identity = compute_content_identity(effective_payload)
        expected_binding = suspended_record["content_identity_binding"]

        if (
            current_content_identity != expected_binding
            or current_content_identity != resumption_payload.content_identity_echo
        ):
            suspended_record["status"] = "toctou_violation"
            raise TOCTOUBaitAndSwitchException(
                f"TOCTOU Bait-and-Switch attack detected! Payload mutated while awaiting approval. "
                f"Approved Hash: {expected_binding}, Actual Current Hash: {current_content_identity}"
            )

        suspended_record["status"] = "approved"
        self.last_approval_grant = resumption_payload.to_dict()

        tool_input = effective_payload.get("tool_input", {})
        tool_name = effective_payload.get("tool_name", "system")

        simulated_output = {
            "status": "success",
            "executed_command": tool_input.get("command", ""),
            "output": f"Executed after human approval: {tool_input.get('command', '')}",
            "approved_by": resumption_payload.approver.subject,
            "approval_channel": resumption_payload.approver.channel,
        }

        # 5. PostToolUse Hook Dispatch
        post_payload = {
            "tool_name": tool_name,
            "tool_call_id": effective_payload.get("tool_call_id", "call_resumed"),
            "tool_output": simulated_output,
            "approver_audit": {
                "approval_id": approval_id,
                "approver": resumption_payload.approver.subject,
                "channel": resumption_payload.approver.channel,
                "grant_token": resumption_payload.approval_grant_token,
            },
        }
        self.dispatch_hook(
            event_type="PostToolUse",
            event_payload=post_payload,
            thought_process="Executing post-tool verification following human approval",
            tool_name=tool_name,
        )

        return simulated_output

    def execute_tool_local_hitl(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        local_confirm: bool = True,
        thought_process: Optional[str] = None,
        trigger_prompt: Optional[str] = None,
        receiver_signer: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Simulate Local CLI Terminal HITL approval execution."""
        try:
            return self.execute_tool(
                tool_name=tool_name,
                tool_input=tool_input,
                thought_process=thought_process,
                trigger_prompt=trigger_prompt,
            )
        except HumanApprovalRequiredException as hitl_ex:
            if not local_confirm:
                raise ApprovalRejectedException("Local terminal user rejected the operation.")

            # Operator confirms locally (stdin / CLI)
            approver = ApproverInfo(
                subject=self.agent_subject,
                channel="local_terminal",
                assurance_level="device_bound",
            )
            now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            signer = receiver_signer or self.agent_keypair
            grant_token = signer.sign_string(
                f"{hitl_ex.approval_id}.approved.{hitl_ex.content_identity_binding}.{approver.subject}.{now_iso}"
            )
            grant_token = f"v1,ed25519={grant_token}"

            resumption = ApprovalResumptionPayload(
                approval_id=hitl_ex.approval_id,
                session_id=self.session_id,
                turn_id=self.turn_id,
                decision="approved",
                approver=approver,
                content_identity_echo=hitl_ex.content_identity_binding,
                approval_grant_token=grant_token,
                approved_at=now_iso,
                approver_comments="Local developer confirmed execution in terminal",
            )
            return self.resume_turn(resumption)
