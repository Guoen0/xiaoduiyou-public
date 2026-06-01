import { resolveXiaoduiyouAccount } from "./accounts.js";
import { getXiaoduiyouGrowthDiary, patchXiaoduiyouGrowthDiary } from "./client.js";
import { queueXiaoduiyouDocumentAction } from "./tool-context.js";

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
    date: { type: "string", description: "Optional YYYY-MM-DD date to return only that day's records while preserving schema/options/views." },
    start_date: { type: "string", description: "Optional inclusive YYYY-MM-DD range start." },
    end_date: { type: "string", description: "Optional inclusive YYYY-MM-DD range end." },
    record_limit: { type: "integer", description: "Maximum records to return after filtering.", minimum: 1, maximum: 500 },
    account_id: { type: "string", description: "Optional OpenClaw Xiaoduiyou channel account id. Omit for the default/current connector account." },
  },
};

const GrowthDiaryPatchSchema = {
  type: "object",
  additionalProperties: false,
  properties: {
    payload: { type: "object", description: "Exact PATCH /api/growth-diary payload after reading the live schema first.", additionalProperties: true },
    account_id: { type: "string", description: "Optional OpenClaw Xiaoduiyou channel account id. Omit for the default/current connector account." },
  },
  required: ["payload"],
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
    document_id: { type: "string", description: "Optional document id. If omitted, Xiaoduiyou updates the current session document." },
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
    document_id: { type: "string", description: "Optional document id. If omitted, Xiaoduiyou deletes the current session document." },
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
  return jsonResult({ ok: true, queued: true, operation, document_action: action });
}

function createGrowthDiaryGetTool(config) {
  return {
    name: "xiaoduiyou_growth_diary_get",
    label: "Xiaoduiyou Growth Diary Get",
    description: "Read Xiaoduiyou Growth Diary schema and targeted records for the current connected Xiaoduiyou account. Use before any diary write.",
    parameters: GrowthDiaryGetSchema,
    execute: async (_toolCallId, rawParams = {}) => {
      const account = resolveToolAccount(config, rawParams);
      const result = await getXiaoduiyouGrowthDiary(account, {
        date: rawParams.date,
        start_date: rawParams.start_date,
        end_date: rawParams.end_date,
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
    description: "Create/update/delete Xiaoduiyou Growth Diary records/options/views for the current connected Xiaoduiyou account. Call xiaoduiyou_growth_diary_get first and pass only the PATCH payload.",
    parameters: GrowthDiaryPatchSchema,
    execute: async (_toolCallId, rawParams = {}) => {
      const account = resolveToolAccount(config, rawParams);
      const payload = rawParams.payload;
      if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
        throw new Error("payload must be a JSON object");
      }
      const result = await patchXiaoduiyouGrowthDiary(account, payload);
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
    description: "Update a Xiaoduiyou document only when the user explicitly asks to modify a document. Omit document_id to update the current session document.",
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
    description: "Delete a Xiaoduiyou document only when the user explicitly asks to delete a document. Omit document_id to delete the current session document.",
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
  api.registerTool(createDocumentCreateTool(), { name: "xiaoduiyou_documents_create" });
  api.registerTool(createDocumentUpdateTool(), { name: "xiaoduiyou_documents_update" });
  api.registerTool(createDocumentDeleteTool(), { name: "xiaoduiyou_documents_delete" });
}
