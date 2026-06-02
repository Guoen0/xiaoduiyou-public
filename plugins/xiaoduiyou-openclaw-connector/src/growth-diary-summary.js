function valueLabel(value) {
  if (!value || typeof value !== "object") return value ?? "";
  if (typeof value.value === "string" || typeof value.value === "number") return value.value;
  if (typeof value.option_id === "string") return value.option_id;
  if (Array.isArray(value.option_ids)) return value.option_ids.join(",");
  if (Array.isArray(value.files)) return `${value.files.length} file(s)`;
  return "";
}

function summarizeGrowthDiaryRecord(record) {
  const values = record?.values && typeof record.values === "object" ? record.values : {};
  return {
    record_id: record?.record_id,
    source: record?.source,
    date: valueLabel(values.date),
    occurred_at: valueLabel(values.occurred_at),
    event_type: valueLabel(values.event_type),
    title: valueLabel(values.title),
    content: valueLabel(values.content),
    quantity: valueLabel(values.quantity),
    unit: valueLabel(values.unit),
    risk: valueLabel(values.risk),
    updated_at: record?.updated_at,
  };
}

export function summarizeGrowthDiaryPatchResult(payload, result) {
  const base = result?.base && typeof result.base === "object" ? result.base : {};
  const tables = Array.isArray(base.tables) ? base.tables : [];
  const updatedAt = typeof base.updated_at === "string" ? base.updated_at : "";
  const requestedRecords = Array.isArray(payload?.records) ? payload.records : [];
  const requestedUpdates = Array.isArray(payload?.updates) ? payload.updates : [];
  const requestedDeletions = Array.isArray(payload?.deletions) ? payload.deletions : [];
  const requestedFieldOptions = Array.isArray(payload?.field_options) ? payload.field_options : [];
  const requestedViews = Array.isArray(payload?.views) ? payload.views : [];

  const tableSummaries = tables.map((table) => ({
    table_id: table.table_id,
    record_count: Array.isArray(table.records) ? table.records.length : 0,
    updated_at: table.updated_at,
  }));

  const changedRecordIds = new Set([
    ...requestedUpdates.map((update) => update?.record_id).filter(Boolean),
    ...requestedDeletions.map((deletion) => deletion?.record_id).filter(Boolean),
  ]);
  const changed_records = [];
  const created_records = [];
  const deletion_results = requestedDeletions.map((deletion) => ({
    table_id: deletion?.table_id,
    record_id: deletion?.record_id,
    deleted: true,
  }));

  for (const table of tables) {
    const records = Array.isArray(table.records) ? table.records : [];
    for (const record of records) {
      if (changedRecordIds.has(record?.record_id)) changed_records.push(summarizeGrowthDiaryRecord(record));
      if (!changedRecordIds.has(record?.record_id) && record?.updated_at === updatedAt && requestedRecords.length > 0) {
        created_records.push(summarizeGrowthDiaryRecord(record));
      }
    }
    for (const deletionResult of deletion_results) {
      if (deletionResult.table_id !== table.table_id) continue;
      deletionResult.deleted = !records.some((record) => record?.record_id === deletionResult.record_id);
    }
  }

  return {
    ok: true,
    summary: {
      updated_at: updatedAt || undefined,
      tables: tableSummaries,
      requested: {
        records: requestedRecords.length,
        updates: requestedUpdates.length,
        deletions: requestedDeletions.length,
        field_options: requestedFieldOptions.length,
        views: requestedViews.length,
      },
      created_records: created_records.slice(0, Math.max(5, requestedRecords.length)),
      changed_records: changed_records.slice(0, Math.max(5, requestedUpdates.length)),
      deletion_results,
      note: "PATCH succeeded. This is a concise verification summary; the full Growth Diary base is intentionally omitted to avoid OpenClaw output truncation.",
    },
  };
}
