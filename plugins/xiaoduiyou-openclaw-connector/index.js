import { defineChannelPluginEntry } from "openclaw/plugin-sdk/channel-core";
import { xiaoduiyouPlugin } from "./src/channel.js";
import { setXiaoduiyouRuntime } from "./src/runtime.js";
import { registerXiaoduiyouTools } from "./src/tools.js";

export default defineChannelPluginEntry({
  id: "xiaoduiyou",
  name: "Xiaoduiyou",
  description: "OpenClaw channel connector for Xiaoduiyou Agent turns.",
  plugin: xiaoduiyouPlugin,
  setRuntime: setXiaoduiyouRuntime,
  registerFull: registerXiaoduiyouTools,
});
