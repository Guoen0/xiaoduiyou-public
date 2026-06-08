import assert from "node:assert/strict";
import test from "node:test";

import {
  buildXiaoduiyouExecApprovalRequest,
  normalizeOpenClawExecApprovalPayload,
  openClawDecisionFromXiaoduiyouChoice,
} from "./approval.js";

test("normalizes OpenClaw exec approval payloads into Xiaoduiyou card data", () => {
  const expiresAtMs = Date.now() + 45_000;
  const approval = normalizeOpenClawExecApprovalPayload({
    channelData: {
      execApproval: {
        approvalId: "approval-123",
        approvalSlug: "abc123",
        command: "rm -rf build",
        cwd: "/repo",
        warningText: "destructive command",
        allowedDecisions: ["allow-once", "deny"],
        expiresAtMs,
      },
    },
  });

  assert.equal(approval.approvalId, "approval-123");
  assert.equal(approval.approvalSlug, "abc123");
  assert.equal(approval.command, "rm -rf build");
  assert.deepEqual(approval.actions, ["once", "deny"]);
  assert.equal(approval.cwd, "/repo");
  assert.equal(approval.warningText, "destructive command");
  assert.ok(approval.timeoutSeconds >= 15);
  assert.ok(approval.timeoutSeconds <= 45);
});

test("builds Xiaoduiyou interactive request payload for OpenClaw exec approval", () => {
  const approval = normalizeOpenClawExecApprovalPayload({
    details: {
      status: "approval-pending",
      approvalId: "approval-123",
      approvalSlug: "abc123",
      command: "pnpm deploy",
      cwd: "/repo",
      allowedDecisions: ["allow-once", "allow-always", "deny"],
    },
  });

  const request = buildXiaoduiyouExecApprovalRequest({
    approval,
    sessionId: "sess_1",
    turnId: "turn_1",
    sessionKey: "agent:main:xiaoduiyou:sess_1",
  });

  assert.equal(request.session_id, "sess_1");
  assert.equal(request.turn_id, "turn_1");
  assert.equal(request.kind, "exec_approval");
  assert.equal(request.command, "pnpm deploy");
  assert.deepEqual(request.actions, ["once", "always", "deny"]);
  assert.equal(request.session_key, "agent:main:xiaoduiyou:sess_1");
});

test("maps Xiaoduiyou choices to OpenClaw decisions", () => {
  assert.equal(openClawDecisionFromXiaoduiyouChoice("once"), "allow-once");
  assert.equal(openClawDecisionFromXiaoduiyouChoice("always"), "allow-always");
  assert.equal(openClawDecisionFromXiaoduiyouChoice("deny"), "deny");
  assert.equal(openClawDecisionFromXiaoduiyouChoice("cancel"), "deny");
  assert.equal(openClawDecisionFromXiaoduiyouChoice("session"), null);
});
