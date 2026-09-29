const bridge = window.AstrBotPluginPage;

const typeSelect = document.getElementById("api-type");
const urlSelect = document.getElementById("api-url");
const testButton = document.getElementById("test-button");
const testAllButton = document.getElementById("test-all-button");
const refreshButton = document.getElementById("refresh-button");
const statusLine = document.getElementById("status-line");
const results = document.getElementById("results");

const state = {
  json_api_list: [],
  image_api_list: [],
  running: false,
};

function applyTheme(context) {
  document.documentElement.dataset.theme = context?.isDark ? "dark" : "light";
}

function currentApiType() {
  return typeSelect.value === "image" ? "image" : "json";
}

function currentEndpoints() {
  const key = currentApiType() === "json" ? "json_api_list" : "image_api_list";
  return state[key];
}

function setStatus(message, tone = "") {
  statusLine.textContent = message;
  statusLine.dataset.tone = tone;
}

function setRunning(running) {
  state.running = running;
  testButton.disabled = running || !urlSelect.value;
  testAllButton.disabled = running || currentEndpoints().length === 0;
  refreshButton.disabled = running;
  typeSelect.disabled = running;
  urlSelect.disabled = running;
}

function renderEndpointOptions() {
  const endpoints = currentEndpoints();
  urlSelect.replaceChildren();

  if (endpoints.length === 0) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "当前类型没有配置接口";
    urlSelect.append(option);
  } else {
    endpoints.forEach((url) => {
      const option = document.createElement("option");
      option.value = url;
      option.textContent = url;
      urlSelect.append(option);
    });
  }

  setRunning(false);
  renderEmptyState("尚未执行测试");
}

function renderEmptyState(message) {
  results.replaceChildren();
  const empty = document.createElement("div");
  empty.className = "empty-state";
  empty.textContent = message;
  results.append(empty);
}

function createMeta(label, value) {
  const wrapper = document.createElement("div");
  const term = document.createElement("dt");
  const detail = document.createElement("dd");

  term.textContent = label;
  detail.textContent = value ?? "-";
  wrapper.append(term, detail);
  return wrapper;
}

function renderResult(result) {
  const card = document.createElement("article");
  card.className = "result-card";

  const main = document.createElement("div");
  main.className = "result-main";

  const header = document.createElement("div");
  header.className = "result-header";

  const identity = document.createElement("div");
  const type = document.createElement("p");
  type.className = "result-type";
  type.textContent = result.api_type === "image" ? "图片 API" : "JSON API";

  const url = document.createElement("p");
  url.className = "result-url";
  url.textContent = result.api_url || "未返回接口地址";
  identity.append(type, url);

  const badge = document.createElement("span");
  badge.className = `badge ${
    result.success ? "badge-success" : "badge-error"
  }`;
  badge.textContent = result.success ? "成功" : "失败";
  header.append(identity, badge);

  const message = document.createElement("p");
  message.className = "result-message";
  message.textContent = result.message || (result.success ? "请求成功" : "请求失败");

  const metadata = document.createElement("dl");
  metadata.className = "metadata";
  metadata.append(
    createMeta("API 状态", result.api_status ?? result.status),
    createMeta("API 类型", result.api_content_type ?? result.content_type),
    createMeta("图片状态", result.image_status),
    createMeta("图片类型", result.image_content_type),
    createMeta(
      "图片大小",
      Number.isFinite(result.size) ? `${result.size} bytes` : "-",
    ),
    createMeta(
      "耗时",
      Number.isFinite(result.elapsed_ms) ? `${result.elapsed_ms} ms` : "-",
    ),
  );

  main.append(header, message, metadata);
  card.append(main);

  if (result.success && result.image_data_url) {
    const preview = document.createElement("div");
    preview.className = "image-preview";
    const image = document.createElement("img");
    image.src = result.image_data_url;
    image.alt = "接口返回图片预览";
    preview.append(image);
    card.append(preview);
  } else if (result.image_url) {
    const preview = document.createElement("div");
    preview.className = "image-preview";
    const unavailable = document.createElement("span");
    unavailable.className = "badge badge-warning";
    unavailable.textContent = "暂无图片预览";
    preview.append(unavailable);
    card.append(preview);
  }

  results.append(card);
}

async function loadEndpoints() {
  setRunning(true);
  setStatus("正在读取插件配置...");
  try {
    const payload = await bridge.apiGet("api-test/list");
    state.json_api_list = Array.isArray(payload.json_api_list)
      ? payload.json_api_list
      : [];
    state.image_api_list = Array.isArray(payload.image_api_list)
      ? payload.image_api_list
      : [];
    renderEndpointOptions();
    setStatus(
      `JSON API ${state.json_api_list.length} 个，图片 API ${state.image_api_list.length} 个`,
    );
  } catch (error) {
    state.json_api_list = [];
    state.image_api_list = [];
    renderEndpointOptions();
    setStatus(error?.message || "读取接口配置失败", "error");
  } finally {
    setRunning(false);
  }
}

async function runSingleTest(apiType, apiUrl) {
  const result = await bridge.apiPost("api-test/run", {
    api_type: apiType,
    api_url: apiUrl,
  });
  renderResult(result);
  return result;
}

async function testSelected() {
  const apiUrl = urlSelect.value;
  if (!apiUrl) {
    return;
  }

  const apiType = currentApiType();
  setRunning(true);
  renderEmptyState("正在测试并下载图片...");
  setStatus(`正在测试 ${apiUrl}`);

  try {
    const result = await runSingleTest(apiType, apiUrl);
    setStatus(result.success ? "接口测试成功" : "接口测试失败");
  } catch (error) {
    renderResult({
      success: false,
      message: error?.message || "测试请求失败",
      api_type: apiType,
      api_url: apiUrl,
    });
    setStatus("接口测试失败", "error");
  } finally {
    setRunning(false);
  }
}

async function testAll() {
  const apiType = currentApiType();
  const endpoints = [...currentEndpoints()];
  if (endpoints.length === 0) {
    return;
  }

  setRunning(true);
  results.replaceChildren();
  let successCount = 0;

  for (let index = 0; index < endpoints.length; index += 1) {
    const apiUrl = endpoints[index];
    setStatus(`正在测试 ${index + 1}/${endpoints.length}: ${apiUrl}`);
    try {
      const result = await runSingleTest(apiType, apiUrl);
      if (result.success) {
        successCount += 1;
      }
    } catch (error) {
      renderResult({
        success: false,
        message: error?.message || "测试请求失败",
        api_type: apiType,
        api_url: apiUrl,
      });
    }
  }

  setStatus(`测试完成：${successCount}/${endpoints.length} 个接口成功`);
  setRunning(false);
}

typeSelect.addEventListener("change", renderEndpointOptions);
urlSelect.addEventListener("change", () => setRunning(false));
testButton.addEventListener("click", testSelected);
testAllButton.addEventListener("click", testAll);
refreshButton.addEventListener("click", loadEndpoints);

const context = await bridge.ready();
applyTheme(context);
const removeContextListener = bridge.onContext(applyTheme);
window.addEventListener("beforeunload", removeContextListener);
await loadEndpoints();
