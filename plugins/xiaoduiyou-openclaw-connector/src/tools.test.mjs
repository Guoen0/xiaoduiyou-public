import assert from "node:assert/strict";
import test from "node:test";

import { summarizeGrowthDiaryPatchResult } from "./growth-diary-summary.js";

test("growth diary patch result is summarized without the full base", () => {
  const payload = {
    records: [{ table_id: "tbl_growth_events", source: "agent", values: { title: "喝奶 150ml" } }],
    updates: [{ table_id: "tbl_growth_events", record_id: "rec_existing", field_id: "risk", value: "normal" }],
    deletions: [{ table_id: "tbl_growth_events", record_id: "rec_deleted" }],
  };
  const result = {
    base: {
      updated_at: "2026-06-02T13:45:03.000Z",
      tables: [{
        table_id: "tbl_growth_events",
        updated_at: "2026-06-02T13:45:03.000Z",
        records: [
          {
            record_id: "rec_existing",
            source: "manual",
            updated_at: "2026-06-02T13:45:03.000Z",
            values: { title: { type: "text", value: "旧记录" }, risk: { type: "single_select", option_id: "normal" } },
          },
          {
            record_id: "agent_mpvh0ciy_oafdh4",
            source: "agent",
            updated_at: "2026-06-02T13:45:03.000Z",
            values: {
              title: { type: "text", value: "喝奶 150ml" },
              event_type: { type: "single_select", option_id: "milk" },
              quantity: { type: "number", value: 150 },
              unit: { type: "single_select", option_id: "ml" },
            },
          },
        ],
      }],
    },
  };

  const summary = summarizeGrowthDiaryPatchResult(payload, result);

  assert.equal(summary.ok, true);
  assert.equal(summary.base, undefined);
  assert.deepEqual(summary.summary.requested, {
    records: 1,
    updates: 1,
    deletions: 1,
    field_options: 0,
    views: 0,
  });
  assert.equal(summary.summary.created_records[0].title, "喝奶 150ml");
  assert.equal(summary.summary.created_records[0].quantity, 150);
  assert.equal(summary.summary.changed_records[0].record_id, "rec_existing");
  assert.deepEqual(summary.summary.deletion_results, [{
    table_id: "tbl_growth_events",
    record_id: "rec_deleted",
    deleted: true,
  }]);
});
