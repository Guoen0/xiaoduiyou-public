import assert from "node:assert/strict";
import test from "node:test";

import { isOpenClawLifecycleProgress, textFromPayload, xiaoduiyouDispatchDeliveryKind } from "./dispatch.js";

test("OpenClaw compaction status is lifecycle progress, not a final reply", () => {
  assert.equal(isOpenClawLifecycleProgress("🧹 Auto-compaction complete (count 2).", { kind: "final" }), true);
  assert.equal(isOpenClawLifecycleProgress("📦 Preflight compression…", { kind: "status" }), true);
  assert.equal(xiaoduiyouDispatchDeliveryKind("🧹 Auto-compaction complete (count 2).", { kind: "final" }), "tool_progress");
  assert.equal(xiaoduiyouDispatchDeliveryKind("真正的最终回复", { kind: "final" }), "final");
});

test("payload text extraction handles OpenClaw text/content shapes", () => {
  assert.equal(textFromPayload({ text: "done" }), "done");
  assert.equal(textFromPayload({ content: "done" }), "done");
  assert.equal(textFromPayload({ content: [{ text: "a" }, { text: "b" }] }), "a\nb");
});

test("normal final assistant text is not treated as lifecycle progress", () => {
  assert.equal(isOpenClawLifecycleProgress("抱歉，我刚才已经回复了。", { kind: "final" }), false);
});
