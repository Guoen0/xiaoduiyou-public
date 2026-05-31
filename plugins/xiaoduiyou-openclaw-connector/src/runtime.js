let runtime;

export function setXiaoduiyouRuntime(nextRuntime) {
  runtime = nextRuntime;
}

export function getXiaoduiyouRuntime() {
  if (!runtime) throw new Error("Xiaoduiyou OpenClaw runtime has not been initialized");
  return runtime;
}
