import { resolveXiaoduiyouAccount } from "./accounts.js";
import { getXiaoduiyouDocument, getXiaoduiyouGrowthDiary, patchXiaoduiyouGrowthDiary } from "./client.js";
import { summarizeGrowthDiaryPatchResult } from "./growth-diary-summary.js";
import { activeXiaoduiyouToolContext, queueXiaoduiyouDocumentAction } from "./tool-context.js";

function jsonResult(value) {
  return JSON.stringify(value, null, 2);
}

function resolveToolAccount(config, rawParams) {
  const accountId = typeof rawParams?.account_id === "string" ? rawParams.account_id.trim() : undefined;
  const account = resolveXiaoduiyouAccount(config, accountId || undefined);
  if (!account.configured) throw new Error("Xiaoduiyou connector requires baseUrl and connectionToken");
  return account;
}

const GrowthDiaryGetSchema = {
  type: "object",
  additionalProperties: false,
  properties: {
    view: { type: "string", enum: ["full", "records"], description: "Use records to return a concise record_id-friendly list. Omit for full legacy base only when schema/options/views are needed." },
    date: { type: "string", description: "Optional YYYY-MM-DD date. When present, the connector defaults to view=records." },
    start_date: { type: "string", description: "Optional inclusive YYYY-MM-DD range start." },
    end_date: { type: "string", description: "Optional inclusive YYYY-MM-DD range end." },
    event_type: { type: "string", description: "Optional event type option id such as milk, poop, food, height, weight, note." },
    query: { type: "string", description: "Optional text query matched against title/content/original_message/recorder. Use this to find a record_id before deletion." },
    quantity: { type: "number", description: "Optional numeric quantity filter, such as 150." },
    unit: { type: "string", description: "Optional unit option id such as ml, times, kg, cm." },
    record_limit: { type: "integer", description: "Maximum records to return after filtering.", minimum: 1, maximum: 500 },
    account_id: { type: "string", description: "Optional OpenClaw Xiaoduiyou channel account id. Omit for the default/current connector account." },
  },
};

const GrowthDiaryPatchSchema = {
  type: "object",
  additionalProperties: false,
  properties: {
    payload: {
      type: "object",
      description: "Exact PATCH /api/growth-diary payload after reading the live schema first and using skill xiaoduiyou-growth-diary. Use records only to add records; each record must have table_id/source at the record root and field values under values, e.g. { records: [{ table_id: 'tbl_growth_events', source: 'agent', values: { occurred_at, event_type, title, content, quantity, unit, risk } }] }. Use updates for existing cells, deletions for deletes, and never send values:null.",
      additionalProperties: true,
    },
    account_id: { type: "string", description: "Optional OpenClaw Xiaoduiyou channel account id. Omit for the default/current connector account." },
  },
  required: ["payload"],
};

const DocumentGetSchema = {
  type: "object",
  additionalProperties: false,
  properties: {
    document_id: { type: "string", description: "Optional document id. Use when known." },
    session_id: { type: "string", description: "Optional Xiaoduiyou session id. Omit to read the current Xiaoduiyou turn's attached document." },
    view: { type: "string", enum: ["summary", "field", "blocks", "full"], description: "Default summary is concise. Use field for one metadata field, blocks for paged block_json, and full only when the user explicitly needs the entire document." },
    field: { type: "string", description: "Required for view=field. Dot path under fields, e.g. publish_notes.xiaohongshu or source_markdown." },
    start: { type: "integer", description: "For view=blocks: zero-based block offset.", minimum: 0 },
    block_limit: { type: "integer", description: "For summary/blocks: max blocks/previews returned.", minimum: 1, maximum: 100 },
    char_limit: { type: "integer", description: "For view=field: max string/JSON preview chars.", minimum: 200, maximum: 20000 },
    account_id: { type: "string", description: "Optional OpenClaw Xiaoduiyou channel account id. Omit for the current connector account." },
  },
};

const DocumentCreateSchema = {
  type: "object",
  additionalProperties: false,
  properties: {
    title: { type: "string", description: "Document title." },
    body: { type: "string", description: "Plain text or Markdown body. One paragraph per line is OK." },
    block_json: { type: "object", description: "Optional Xiaoduiyou Block JSON: {schema:'xdy.block_json.v1', blocks:[...]}", additionalProperties: true },
    ui_templates: {
      type: "array",
      description: "Content-package UI templates to render. Currently supported: xiaohongshu and moments. Also written to fields.ui_templates.",
      items: { type: "string", enum: ["xiaohongshu", "moments"] },
    },
    fields: { type: "object", description: "Optional metadata fields.", additionalProperties: true },
    attach_to_session: { type: "boolean", description: "Attach as the current session document. Defaults true." },
  },
  required: ["title"],
};

const DocumentUpdateSchema = {
  type: "object",
  additionalProperties: false,
  properties: {
    document_id: { type: "string", description: "Optional document id. If omitted, Xiaoduiyou updates the current screen document/content package, then falls back to the current session document." },
    command: { type: "string", enum: ["overwrite", "append_blocks", "patch_fields"], description: "Update mode. Defaults overwrite." },
    title: { type: "string", description: "New title for overwrite or patch_fields." },
    body: { type: "string", description: "New/append body text." },
    block_json: { type: "object", description: "Optional full Block JSON for overwrite.", additionalProperties: true },
    ui_templates: {
      type: "array",
      description: "Replace the content-package UI templates for this document. Currently supported: xiaohongshu and moments. Also written to fields.ui_templates.",
      items: { type: "string", enum: ["xiaohongshu", "moments"] },
    },
    blocks: {
      type: "array",
      description: "Blocks for append_blocks.",
      items: { type: "object", additionalProperties: true },
    },
    fields: { type: "object", description: "Metadata fields for patch_fields/overwrite.", additionalProperties: true },
  },
};

const DocumentDeleteSchema = {
  type: "object",
  additionalProperties: false,
  properties: {
    document_id: { type: "string", description: "Optional document id. If omitted, Xiaoduiyou deletes the current screen document/content package, then falls back to the current session document." },
  },
};

function textBlock(text, type = "paragraph", props = undefined) {
  return {
    type,
    ...(props ? { props } : {}),
    content: [{ type: "text", text: String(text ?? ""), styles: {} }],
  };
}

function blockJsonFromText(title, body) {
  const blocks = [];
  const cleanTitle = String(title ?? "").trim();
  if (cleanTitle) blocks.push(textBlock(cleanTitle, "heading", { level: 2 }));
  for (const line of String(body ?? "").split(/\r?\n/)) {
    const text = line.trim();
    if (text) blocks.push(textBlock(text));
  }
  return { schema: "xdy.block_json.v1", blocks };
}

function normalizeBlockJson(blockJson, { title = "", body = "" } = {}) {
  if (blockJson && typeof blockJson === "object" && !Array.isArray(blockJson) && Array.isArray(blockJson.blocks)) {
    return {
      schema: String(blockJson.schema ?? "xdy.block_json.v1"),
      blocks: blockJson.blocks,
    };
  }
  return blockJsonFromText(title, body);
}

function mergeUiTemplatesIntoFields(rawParams, fields) {
  const next = { ...(fields && typeof fields === "object" && !Array.isArray(fields) ? fields : {}) };
  if (Array.isArray(rawParams.ui_templates)) {
    next.ui_templates = rawParams.ui_templates.filter((template) => template === "xiaohongshu" || template === "moments");
  }
  return next;
}

function queuedResult(operation, action) {
  const target = action.document_id ? { document_id: action.document_id } : { current_session_document: true };
  return jsonResult({
    ok: true,
    queued: true,
    operation,
    ...target,
    attach_to_session: action.operation === "create" ? Boolean(action.attach_to_session ?? true) : undefined,
    will_apply_on: "final_callback",
    next_step: "Continue the answer normally. Do not repeat this tool call just to verify; use xiaoduiyou_documents_get after the final callback or in a later turn.",
  });
}

function growthDiaryPatchFailureResult(error) {
  return {
    ok: false,
    error: {
      message: String(error?.message ?? error ?? "PATCH_FAILED"),
      code: error?.code,
      status: error?.status,
    },
    skill: "xiaoduiyou-growth-diary",
    hint: "Read/use skill xiaoduiyou-growth-diary, then retry with payload.records[].table_id and source at the record root, and field values inside records[].values. Example: { records: [{ table_id: \"tbl_growth_events\", source: \"agent\", values: { title: \"喝奶 150ml\", event_type: \"milk\", quantity: 150, unit: \"ml\" } }] }. Use updates for existing cells and deletions for deletes.",
  };
}

function createGrowthDiaryGetTool(config) {
  return {
    name: "xiaoduiyou_growth_diary_get",
    label: "Xiaoduiyou Growth Diary Get",
    description: "Read Xiaoduiyou Growth Diary data for the current connected account. Use skill xiaoduiyou-growth-diary. To find a record_id before update/delete, pass date/event_type/query/quantity/unit; filtered calls default to view=records and return concise records instead of the full base.",
    parameters: GrowthDiaryGetSchema,
    execute: async (_toolCallId, rawParams = {}) => {
      const account = resolveToolAccount(config, rawParams);
      const hasRecordFilter = Boolean(rawParams.date || rawParams.start_date || rawParams.end_date || rawParams.event_type || rawParams.query || rawParams.quantity !== undefined || rawParams.unit || rawParams.record_limit);
      const view = rawParams.view === "records" || (rawParams.view !== "full" && hasRecordFilter) ? "records" : undefined;
      const result = await getXiaoduiyouGrowthDiary(account, {
        view,
        date: rawParams.date,
        start_date: rawParams.start_date,
        end_date: rawParams.end_date,
        event_type: rawParams.event_type,
        query: rawParams.query,
        quantity: rawParams.quantity,
        unit: rawParams.unit,
        record_limit: rawParams.record_limit,
      });
      return jsonResult(result);
    },
  };
}

function createGrowthDiaryPatchTool(config) {
  return {
    name: "xiaoduiyou_growth_diary_patch",
    label: "Xiaoduiyou Growth Diary Patch",
    description: "Create/update/delete Xiaoduiyou Growth Diary records/options/views for the current connected Xiaoduiyou account. Use skill xiaoduiyou-growth-diary, then call xiaoduiyou_growth_diary_get first. For new records, records items must look like { table_id, source, values }; put title/event_type/quantity/unit/date/occurred_at/risk inside values, not at the record root. Use updates for existing cells, deletions for deletes, and never send values:null. The result is a concise verification summary, not the full base.",
    parameters: GrowthDiaryPatchSchema,
    execute: async (_toolCallId, rawParams = {}) => {
      const account = resolveToolAccount(config, rawParams);
      const payload = rawParams.payload;
      if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
        throw new Error("payload must be a JSON object");
      }
      try {
        const result = await patchXiaoduiyouGrowthDiary(account, payload);
        return jsonResult(summarizeGrowthDiaryPatchResult(payload, result));
      } catch (error) {
        return jsonResult(growthDiaryPatchFailureResult(error));
      }
    },
  };
}

function createDocumentGetTool(config) {
  return {
    name: "xiaoduiyou_documents_get",
    label: "Xiaoduiyou Documents Get",
    description: "Read the current Xiaoduiyou content-package document without loading everything by default. Omit document_id/session_id inside an active Xiaoduiyou turn to read the current session document. Default view=summary. Use view=field for one field such as publish_notes.xiaohongshu/source_markdown, view=blocks for paged blocks, and view=full only when explicitly necessary.",
    parameters: DocumentGetSchema,
    execute: async (_toolCallId, rawParams = {}) => {
      const context = activeXiaoduiyouToolContext();
      const account = resolveToolAccount(config, { ...rawParams, account_id: rawParams.account_id || context.accountId });
      const result = await getXiaoduiyouDocument(account, {
        document_id: rawParams.document_id,
        session_id: rawParams.session_id || context.sessionId,
        view: rawParams.view || "summary",
        field: rawParams.field,
        start: rawParams.start,
        block_limit: rawParams.block_limit,
        char_limit: rawParams.char_limit,
      });
      return jsonResult(result);
    },
  };
}

function createDocumentCreateTool() {
  return {
    name: "xiaoduiyou_documents_create",
    label: "Xiaoduiyou Documents Create",
    description: "Create a Xiaoduiyou document only when the user explicitly asks for a document artifact.",
    parameters: DocumentCreateSchema,
    execute: async (_toolCallId, rawParams = {}) => {
      const title = String(rawParams.title ?? "Untitled").trim() || "Untitled";
      const body = String(rawParams.body ?? rawParams.markdown ?? "");
      const input = {
        title,
        block_json: normalizeBlockJson(rawParams.block_json, { title, body }),
        created_by: "agent",
      };
      const fields = mergeUiTemplatesIntoFields(rawParams, rawParams.fields);
      if (Object.keys(fields).length > 0) input.fields = fields;
      const action = {
        operation: "create",
        attach_to_session: Boolean(rawParams.attach_to_session ?? true),
        input,
      };
      queueXiaoduiyouDocumentAction(action);
      return queuedResult("create", action);
    },
  };
}

function createDocumentUpdateTool() {
  return {
    name: "xiaoduiyou_documents_update",
    label: "Xiaoduiyou Documents Update",
    description: "Update a Xiaoduiyou document only when the user explicitly asks to modify a document. Omit document_id to target the current screen document/content package; Xiaoduiyou falls back to the current session document.",
    parameters: DocumentUpdateSchema,
    execute: async (_toolCallId, rawParams = {}) => {
      const command = String(rawParams.command ?? "overwrite").trim();
      let input;
      if (command === "append_blocks") {
        const blocks = Array.isArray(rawParams.blocks)
          ? rawParams.blocks
          : blockJsonFromText("", String(rawParams.body ?? rawParams.markdown ?? "")).blocks;
        input = { command: "append_blocks", blocks, updated_by: "agent" };
      } else if (command === "patch_fields") {
        input = { command: "patch_fields", updated_by: "agent" };
        if (rawParams.title) input.title = String(rawParams.title);
        const fields = mergeUiTemplatesIntoFields(rawParams, rawParams.fields);
        if (Object.keys(fields).length > 0) input.fields = fields;
      } else {
        const title = String(rawParams.title ?? "").trim();
        const body = String(rawParams.body ?? rawParams.markdown ?? "");
        input = {
          command: "overwrite",
          block_json: normalizeBlockJson(rawParams.block_json, { title, body }),
          updated_by: "agent",
        };
        if (title) input.title = title;
        const fields = mergeUiTemplatesIntoFields(rawParams, rawParams.fields);
        if (Object.keys(fields).length > 0) input.fields = fields;
      }
      const documentId = String(rawParams.document_id ?? "").trim();
      const action = { operation: "update", input };
      if (documentId) action.document_id = documentId;
      queueXiaoduiyouDocumentAction(action);
      return queuedResult("update", action);
    },
  };
}

function createDocumentDeleteTool() {
  return {
    name: "xiaoduiyou_documents_delete",
    label: "Xiaoduiyou Documents Delete",
    description: "Delete a Xiaoduiyou document only when the user explicitly asks to delete a document. Omit document_id to target the current screen document/content package; Xiaoduiyou falls back to the current session document.",
    parameters: DocumentDeleteSchema,
    execute: async (_toolCallId, rawParams = {}) => {
      const documentId = String(rawParams.document_id ?? "").trim();
      const action = { operation: "delete" };
      if (documentId) action.document_id = documentId;
      queueXiaoduiyouDocumentAction(action);
      return queuedResult("delete", action);
    },
  };
}

export function registerXiaoduiyouTools(api) {
  api.registerTool(createGrowthDiaryGetTool(api.config), { name: "xiaoduiyou_growth_diary_get" });
  api.registerTool(createGrowthDiaryPatchTool(api.config), { name: "xiaoduiyou_growth_diary_patch" });
  api.registerTool(createDocumentGetTool(api.config), { name: "xiaoduiyou_documents_get" });
  api.registerTool(createDocumentCreateTool(), { name: "xiaoduiyou_documents_create" });
  api.registerTool(createDocumentUpdateTool(), { name: "xiaoduiyou_documents_update" });
  api.registerTool(createDocumentDeleteTool(), { name: "xiaoduiyou_documents_delete" });
}
