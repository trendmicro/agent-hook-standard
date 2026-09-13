"""Automated Verification Suite for Secure Human-In-The-Loop (HITL) & Approval Relay.

Verifies end-to-end:
1. HITL-01: Local CLI Terminal Approval (Interactive developer confirmation)
2. HITL-02: Remote Slack Out-of-Band Approval via Approval Relay (Happy Path)
3. HITL-03: TOCTOU Bait-and-Switch Tampering Detection (Pillar 3 Hard Abort)
4. HITL-04: Forged / Untrusted Approval Grant Token Rejection (Ed25519 Signature Verification)
5. HITL-05: Expired Approval Token Fail-Closed Rejection
6. HITL-06: Explicit Human Rejection via Slack Interaction
"""

from __future__ import annotations

import json
import socket
import sys
import threading
import time
from typing import Any, Dict, Optional

from agent import (
    AgentRuntime,
    ApprovalExpiredException,
    ApprovalForgedException,
    ApprovalRejectedException,
    HumanApprovalRequiredException,
    TOCTOUBaitAndSwitchException,
)
from crypto import Ed25519KeyPair, canonical_json_str, compute_content_identity
from models import ApprovalResumptionPayload, ApproverInfo
from receiver import ReceiverServer, SecurityReceiver
from relay import ApprovalRelay


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class HITLTestReport:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.results: list[dict] = []

    def record(
        self,
        scenario_id: str,
        name: str,
        success: bool,
        details: str = "",
        input_data: Any = None,
        output_data: Any = None,
    ):
        if success:
            self.passed += 1
            status = "PASS"
        else:
            self.failed += 1
            status = "FAIL"
        entry = {
            "id": scenario_id,
            "name": name,
            "status": status,
            "details": details,
            "input": input_data,
            "output": output_data,
        }
        self.results.append(entry)
        symbol = "✓" if success else "✗"
        print(f"[{symbol}] Scenario {scenario_id}: {name} -> {status} ({details})")

    def save_json(self, filepath: str = "hitl_verification_execution.json"):
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "summary": {
                        "passed": self.passed,
                        "failed": self.failed,
                        "total": len(self.results),
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    },
                    "scenarios": self.results,
                },
                f,
                indent=2,
                ensure_ascii=False,
            )


def run_hitl_verification():
    print("=" * 90)
    print("Agent Hook Standard: Secure Human-In-The-Loop (HITL) & Approval Relay Verification")
    print("=" * 90)

    port = find_free_port()
    receiver_key = Ed25519KeyPair(key_id="kms-secops-receiver-prod")
    receiver = SecurityReceiver(receiver_id="secops-receiver-prod", receiver_keypair=receiver_key)
    server = ReceiverServer(receiver, host="127.0.0.1", port=port)
    server.start()
    print(f"[*] Started Security Receiver daemon on http://127.0.0.1:{port}\n")

    report = HITLTestReport()
    receiver_url = f"http://127.0.0.1:{port}"

    try:
        # ---------------------------------------------------------------------
        # Scenario HITL-01: Local CLI Terminal Approval
        # ---------------------------------------------------------------------
        agent_local_key = Ed25519KeyPair(key_id="kms-dev-local")
        receiver.register_agent_key("dev-local@enterprise.com", agent_local_key)

        agent_local = AgentRuntime(
            session_id="sess_hitl_local_01",
            receiver_url=receiver_url,
            agent_subject="dev-local@enterprise.com",
            agent_keypair=agent_local_key,
            receiver_public_keypair=receiver_key,
        )

        try:
            res_local = agent_local.execute_tool_local_hitl(
                tool_name="Bash",
                tool_input={"command": "kubectl get pods -n prod"},
                local_confirm=True,
                thought_process="Developer verifying pod health from CLI terminal",
                trigger_prompt="List all pods in prod namespace",
                receiver_signer=receiver_key,
            )
            is_success = (
                res_local.get("status") == "success"
                and res_local.get("approval_channel") == "local_terminal"
            )
            report.record(
                "HITL-01",
                "Local CLI Terminal Interactive Approval",
                is_success,
                details="Local operator confirmed command, content identity verified before execution",
                input_data={
                    "tool": "Bash",
                    "command": "kubectl get pods -n prod",
                    "channel": "local_terminal",
                },
                output_data=res_local,
            )
        except Exception as ex:
            report.record("HITL-01", "Local CLI Terminal Interactive Approval", False, str(ex))

        # ---------------------------------------------------------------------
        # Scenario HITL-02: Remote Slack Out-of-Band Approval via Approval Relay
        # ---------------------------------------------------------------------
        relay = ApprovalRelay(relay_id="approval-relay-01")
        agent_remote_key = Ed25519KeyPair(key_id="kms-agent-swarm-prod")
        receiver.register_agent_key("agent-k8s-operator@enterprise.com", agent_remote_key)

        agent_remote = AgentRuntime(
            session_id="sess_hitl_remote_02",
            receiver_url=receiver_url,
            agent_subject="agent-k8s-operator@enterprise.com",
            agent_keypair=agent_remote_key,
            receiver_public_keypair=receiver_key,
        )

        try:
            # 1. Agent attempts privileged tool -> Intercepted with 'ask'
            appr_id = None
            try:
                agent_remote.execute_tool(
                    tool_name="Bash",
                    tool_input={"command": "kubectl get pods -n prod --show-labels"},
                    thought_process="Autonomous agent preparing health diagnostics report for incident response",
                    trigger_prompt="Diagnose payment gateway cluster in prod",
                )
            except HumanApprovalRequiredException as hitl_ex:
                appr_id = hitl_ex.approval_id
                # 2. Approval Relay catches suspension and formats Slack Block Kit card
                suspended_turn = relay.suspend_agent_turn(
                    session_id=agent_remote.session_id,
                    turn_id=agent_remote.turn_id,
                    tool_name="Bash",
                    tool_input={"command": "kubectl get pods -n prod --show-labels"},
                    escalation=hitl_ex.escalation,
                )

            # 3. Simulate SRE clicking 'Approve' in Slack
            slack_msg = relay.slack_message_outbox[appr_id]
            slack_action_payload = {
                "type": "block_actions",
                "user": {"id": "U08_SRE_ALICE", "username": "alice.sre@enterprise.com"},
                "team": {"id": "T01_CORP_SLACK"},
                "actions": [
                    {
                        "action_id": "relay_approve",
                        "value": json.dumps({
                            "approval_id": appr_id,
                            "decision": "approved",
                            "content_identity": suspended_turn.content_identity_binding,
                        }),
                    }
                ],
                "comments": "Approved for production diagnostics incident #INC-9012",
            }

            # 4. Approval Relay processes interaction and obtains Ed25519-signed grant
            resumption_grant = relay.process_slack_interaction_webhook(
                slack_action_payload=slack_action_payload,
                receiver_signer=receiver,
            )

            # 5. Agent resumes turn with signed grant
            res_remote = agent_remote.resume_turn(resumption_grant)

            is_remote_success = (
                res_remote.get("status") == "success"
                and res_remote.get("approved_by") == "alice.sre@enterprise.com"
                and res_remote.get("approval_channel") == "slack"
            )

            report.record(
                "HITL-02",
                "Remote Slack Out-of-Band Approval via Approval Relay",
                is_remote_success,
                details=f"Approved by {res_remote.get('approved_by')} via Slack; grant token verified",
                input_data={
                    "approval_id": appr_id,
                    "slack_blocks_generated": len(slack_msg["blocks"]),
                    "slack_channel": slack_msg["channel"],
                },
                output_data=res_remote,
            )
        except Exception as ex:
            report.record("HITL-02", "Remote Slack Out-of-Band Approval via Approval Relay", False, str(ex))

        # ---------------------------------------------------------------------
        # Scenario HITL-03: TOCTOU Bait-and-Switch Tampering Detection (Pillar 3)
        # ---------------------------------------------------------------------
        agent_toctou_key = Ed25519KeyPair(key_id="kms-agent-toctou")
        receiver.register_agent_key("agent-toctou@enterprise.com", agent_toctou_key)

        agent_toctou = AgentRuntime(
            session_id="sess_hitl_toctou_03",
            receiver_url=receiver_url,
            agent_subject="agent-toctou@enterprise.com",
            agent_keypair=agent_toctou_key,
            receiver_public_keypair=receiver_key,
        )

        try:
            toctou_appr_id = None
            try:
                agent_toctou.execute_tool(
                    tool_name="Bash",
                    tool_input={"command": "kubectl get pods -n prod"},
                    thought_process="Innocuous pod inspection",
                    trigger_prompt="Check running pods",
                )
            except HumanApprovalRequiredException as hitl_ex:
                toctou_appr_id = hitl_ex.approval_id
                original_binding = hitl_ex.content_identity_binding

            # Approver approves the legitimate command in Slack
            valid_grant = receiver.issue_approval_grant(
                approval_id=toctou_appr_id,
                session_id=agent_toctou.session_id,
                turn_id=agent_toctou.turn_id,
                decision="approved",
                content_identity_binding=original_binding,
                approver=ApproverInfo(subject="bob.sre@enterprise.com", channel="slack"),
            )

            # ATTACK: In-memory bait-and-switch!
            # Malicious subagent / memory corruption swaps the command before dispatch!
            tampered_payload = {
                "tool_name": "Bash",
                "tool_call_id": "call_tampered",
                "tool_input": {"command": "kubectl delete namespace prod --force"},
                "execution_context": {"cwd": "/workspace", "is_sandboxed": False},
            }

            try:
                agent_toctou.resume_turn(
                    resumption_payload=valid_grant,
                    mutated_payload_override=tampered_payload,
                )
                report.record(
                    "HITL-03",
                    "TOCTOU Bait-and-Switch Detection (Pillar 3)",
                    False,
                    "Failed: Tampered command was executed instead of aborted!",
                )
            except TOCTOUBaitAndSwitchException as toctou_err:
                report.record(
                    "HITL-03",
                    "TOCTOU Bait-and-Switch Detection (Pillar 3)",
                    True,
                    details=f"Caught in-memory payload tampering: {str(toctou_err)[:65]}...",
                    input_data={
                        "original_approved_command": "kubectl get pods -n prod",
                        "tampered_command_injected": "kubectl delete namespace prod --force",
                    },
                    output_data={"exception": "TOCTOUBaitAndSwitchException", "error": str(toctou_err)},
                )
        except Exception as ex:
            report.record("HITL-03", "TOCTOU Bait-and-Switch Detection (Pillar 3)", False, str(ex))

        # ---------------------------------------------------------------------
        # Scenario HITL-04: Forged / Untrusted Approval Grant Token Rejection
        # ---------------------------------------------------------------------
        agent_forge_key = Ed25519KeyPair(key_id="kms-agent-forge")
        receiver.register_agent_key("agent-forge@enterprise.com", agent_forge_key)

        agent_forge = AgentRuntime(
            session_id="sess_hitl_forge_04",
            receiver_url=receiver_url,
            agent_subject="agent-forge@enterprise.com",
            agent_keypair=agent_forge_key,
            receiver_public_keypair=receiver_key,
        )

        try:
            forge_appr_id = None
            try:
                agent_forge.execute_tool(
                    tool_name="Bash",
                    tool_input={"command": "kubectl get pods -n prod"},
                )
            except HumanApprovalRequiredException as hitl_ex:
                forge_appr_id = hitl_ex.approval_id
                target_binding = hitl_ex.content_identity_binding

            # ATTACK: Attacker generates a forged grant signed with an UNTRUSTED keypair
            attacker_fake_key = Ed25519KeyPair(key_id="kms-rogue-attacker")
            forged_grant = receiver.issue_approval_grant(
                approval_id=forge_appr_id,
                session_id=agent_forge.session_id,
                turn_id=agent_forge.turn_id,
                decision="approved",
                content_identity_binding=target_binding,
                approver=ApproverInfo(subject="fake_admin@attacker.com", channel="slack"),
            )
            # Replace grant token with rogue signature
            forged_grant.approval_grant_token = f"v1,ed25519={attacker_fake_key.sign_string('fake_data')}"

            try:
                agent_forge.resume_turn(forged_grant)
                report.record("HITL-04", "Forged Approval Grant Token Rejection", False, "Failed: Forged signature accepted!")
            except ApprovalForgedException as forge_err:
                report.record(
                    "HITL-04",
                    "Forged Approval Grant Token Rejection",
                    True,
                    details="Rejected untrusted Ed25519 signature on approval grant",
                    input_data={"forged_token": forged_grant.approval_grant_token},
                    output_data={"exception": "ApprovalForgedException", "error": str(forge_err)},
                )
        except Exception as ex:
            report.record("HITL-04", "Forged Approval Grant Token Rejection", False, str(ex))

        # ---------------------------------------------------------------------
        # Scenario HITL-05: Expired Approval Token Fail-Closed Rejection
        # ---------------------------------------------------------------------
        agent_exp_key = Ed25519KeyPair(key_id="kms-agent-exp")
        receiver.register_agent_key("agent-exp@enterprise.com", agent_exp_key)

        agent_exp = AgentRuntime(
            session_id="sess_hitl_exp_05",
            receiver_url=receiver_url,
            agent_subject="agent-exp@enterprise.com",
            agent_keypair=agent_exp_key,
            receiver_public_keypair=receiver_key,
        )

        try:
            exp_appr_id = None
            try:
                agent_exp.execute_tool(
                    tool_name="Bash",
                    tool_input={"command": "kubectl get pods -n prod"},
                )
            except HumanApprovalRequiredException as hitl_ex:
                exp_appr_id = hitl_ex.approval_id
                target_binding = hitl_ex.content_identity_binding

            # Simulate past expiration date in suspended record
            past_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 3600))
            agent_exp.pending_approvals[exp_appr_id]["expires_at"] = past_iso

            valid_grant = receiver.issue_approval_grant(
                approval_id=exp_appr_id,
                session_id=agent_exp.session_id,
                turn_id=agent_exp.turn_id,
                decision="approved",
                content_identity_binding=target_binding,
                approver=ApproverInfo(subject="charlie.sre@enterprise.com", channel="slack"),
            )

            try:
                agent_exp.resume_turn(valid_grant)
                report.record("HITL-05", "Expired Approval Token Fail-Closed Rejection", False, "Failed: Expired token executed!")
            except ApprovalExpiredException as exp_err:
                report.record(
                    "HITL-05",
                    "Expired Approval Token Fail-Closed Rejection",
                    True,
                    details=f"Fail-closed enforced: Token expired at {past_iso}",
                    input_data={"expired_at": past_iso},
                    output_data={"exception": "ApprovalExpiredException", "error": str(exp_err)},
                )
        except Exception as ex:
            report.record("HITL-05", "Expired Approval Token Fail-Closed Rejection", False, str(ex))

        # ---------------------------------------------------------------------
        # Scenario HITL-06: Explicit Human Rejection via Slack Interaction
        # ---------------------------------------------------------------------
        agent_rej_key = Ed25519KeyPair(key_id="kms-agent-rej")
        receiver.register_agent_key("agent-rej@enterprise.com", agent_rej_key)

        agent_rej = AgentRuntime(
            session_id="sess_hitl_rej_06",
            receiver_url=receiver_url,
            agent_subject="agent-rej@enterprise.com",
            agent_keypair=agent_rej_key,
            receiver_public_keypair=receiver_key,
        )

        try:
            rej_appr_id = None
            try:
                agent_rej.execute_tool(
                    tool_name="Bash",
                    tool_input={"command": "kubectl get pods -n prod"},
                )
            except HumanApprovalRequiredException as hitl_ex:
                rej_appr_id = hitl_ex.approval_id
                target_binding = hitl_ex.content_identity_binding

            # Approver clicks 'Deny'
            rejection_grant = receiver.issue_approval_grant(
                approval_id=rej_appr_id,
                session_id=agent_rej.session_id,
                turn_id=agent_rej.turn_id,
                decision="rejected",
                content_identity_binding=target_binding,
                approver=ApproverInfo(subject="security_officer@enterprise.com", channel="slack"),
                comments="Cluster maintenance window currently closed.",
            )

            try:
                agent_rej.resume_turn(rejection_grant)
                report.record("HITL-06", "Explicit Approver Rejection via Slack", False, "Failed: Rejected action executed!")
            except ApprovalRejectedException as rej_err:
                report.record(
                    "HITL-06",
                    "Explicit Approver Rejection via Slack",
                    True,
                    details="Cleanly aborted upon human rejection in Slack",
                    input_data={"decision": "rejected", "approver": "security_officer@enterprise.com"},
                    output_data={"exception": "ApprovalRejectedException", "error": str(rej_err)},
                )
        except Exception as ex:
            report.record("HITL-06", "Explicit Approver Rejection via Slack", False, str(ex))

    finally:
        server.stop()
        print("\n[*] Stopped Security Receiver daemon.\n")

    print("=" * 90)
    print(f"VERIFICATION SUMMARY: {report.passed} Passed, {report.failed} Failed (Total {len(report.results)})")
    print("=" * 90)
    report.save_json("hitl_verification_execution.json")
    print("[*] Results saved to hitl_verification_execution.json")

    return report.failed == 0


if __name__ == "__main__":
    success = run_hitl_verification()
    sys.exit(0 if success else 1)
