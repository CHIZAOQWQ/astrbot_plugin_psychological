const bridge = window.AstrBotPluginPage;

const typeSelect = document.getElementById("api-type");
const urlSelect = document.getElementById("api-url");
const testButton = document.getElementById("test-button");
const testAllButton = document.getElementById("test-all-button");
const refreshButton = document.getElementById("refresh-button");
const manageTypeSelect = document.getElementById("manage-api-type");
const manageUrlInput = document.getElementById("manage-api-url");
const addApiButton = document.getElementById("add-api-button");
const cancelEditButton = document.getElementById("cancel-edit-button");
const saveApiButton = document.getElementById("save-api-button");
const discardApiButton = document.getElementById("discard-api-button");
const managementList = document.getElementById("management-list");
const managementStatus = document.getElementById("management-status");
const statusLine = document.getElementById("status-line");
const results = document.getElementById("results");

const state = {
  json_api_list: [],
  image_api_list: [],
  running: false,
  dirty: false,
  editing: null,
  revision: null,
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

function currentManagementKey() {
  return manageTypeSelect.value === "image" ? "image_api_list" : "json_api_list";
}

function setStatus(message, tone = "") {
  statusLine.textContent = message;
  statusLine.dataset.tone = tone;
}

function setManagementStatus(message, tone = "") {
  managementStatus.textContent = message;
  managementStatus.dataset.tone = tone;
}

function setRunning(running) {
  state.running = running;
  const unavailable = running || state.revision === null;
  testButton.disabled = unavailable || state.dirty || !urlSelect.value;
  testAllButton.disabled = unavailable || state.dirty || currentEndpoints().length === 0;
  refreshButton.disabled = running || state.dirty;
  typeSelect.disabled = unavailable || state.dirty;
  urlSelect.disabled = unavailable || state.dirty;
  manageTypeSelect.disabled = unavailable;
  manageUrlInput.disabled = unavailable;
  addApiButton.disabled = unavailable;
  cancelEditButton.disabled = unavailable;
  saveApiButton.disabled = unavailable || !state.dirty;
  discardApiButton.disabled = unavailable || !state.dirty;
  managementList.querySelectorAll("button").forEach((button) => {
    button.disabled = unavailable;
  });
}

function renderManagementList() {
  managementList.replaceChildren();
  const apiTypes = [
    { key: "json_api_list", label: "JSON API" },
    { key: "image_api_list", label: "图片 API" },
  ];

  apiTypes.forEach(({ key, label }) => {
    const heading = document.createElement("li");
    heading.className = "management-list-heading";
    heading.textContent = `${label}（${state[key].length}）`;
    managementList.append(heading);

    if (state[key].length === 0) {
      const empty = document.createElement("li");
      empty.className = "management-empty";
      empty.textContent = "暂无地址";
      managementList.append(empty);
      return;
    }

    state[key].forEach((url, index) => {
      const item = document.createElement("li");
      item.className = "management-item";
      const urlText = document.createElement("span");
      urlText.className = "management-item-url";
      urlText.textContent = url;

      const actions = document.createElement("div");
      actions.className = "management-item-actions";
      const editButton = document.createElement("button");
      editButton.type = "button";
      editButton.className = "button button-secondary";
      editButton.textContent = "编辑";
      editButton.addEventListener("click", () => startEdit(key, index));
      const deleteButton = document.createElement("button");
      deleteButton.type = "button";
      deleteButton.className = "button button-danger";
      deleteButton.textContent = "删除";
      deleteButton.addEventListener("click", () => removeEndpoint(key, index));
      actions.append(editButton, deleteButton);
      item.append(urlText, actions);
      managementList.append(item);
    });
  });

  setRunning(state.running);
}

function renderDraft(message) {
  state.dirty = true;
  renderManagementList();
  renderEndpointOptions();
  setManagementStatus(message);
}

function clearEdit() {
  state.editing = null;
  manageUrlInput.value = "";
  addApiButton.textContent = "添加地址";
  cancelEditButton.hidden = true;
}

function startEdit(key, index) {
  state.editing = { key, index };
  manageTypeSelect.value = key === "image_api_list" ? "image" : "json";
  manageUrlInput.value = state[key][index];
  addApiButton.textContent = "应用编辑";
  cancelEditButton.hidden = false;
  manageUrlInput.focus();
}

function normalizeApiUrl(value) {
  const url = value.trim();
  if (!/^https?:\/\/[^/\s?#]/.test(url) || /[\s\x00-\x1f\x7f\\]/.test(url)) {
    throw new Error("请输入有效的 HTTP/HTTPS 地址");
  }
  try {
    const parsed = new URL(url);
    if (!parsed.hostname || parsed.port === "0") throw new Error();
  } catch {
    throw new Error("请输入有效的 HTTP/HTTPS 地址");
  }
  return url;
}

function addOrEditEndpoint() {
  try {
    const url = normalizeApiUrl(manageUrlInput.value);
    const key = currentManagementKey();
    if (state.editing) {
      const { key: oldKey, index } = state.editing;
      const conflict = state[key].some((item, itemIndex) =>
        item === url && !(key === oldKey && itemIndex === index),
      );
      if (conflict) throw new Error("该类型中已存在此地址");
      if (key === oldKey) {
        state[key][index] = url;
      } else {
        state[oldKey].splice(index, 1);
        state[key].push(url);
      }
      clearEdit();
    } else {
      if (state[key].includes(url)) throw new Error("该类型中已存在此地址");
      state[key].push(url);
      manageUrlInput.value = "";
    }
    renderDraft("地址已更新，尚未保存");
  } catch (error) {
    setManagementStatus(error?.message || "地址格式无效", "error");
  }
}

function removeEndpoint(key, index) {
  state[key].splice(index, 1);
  if (state.editing?.key === key && state.editing.index === index) {
    clearEdit();
  } else if (state.editing?.key === key && state.editing.index > index) {
    state.editing.index -= 1;
  }
  renderDraft("地址已移除，尚未保存");
}

function applySnapshot(payload) {
  if (
    !Array.isArray(payload?.json_api_list) ||
    !Array.isArray(payload?.image_api_list) ||
    typeof payload?.revision !== "string"
  ) {
    throw new Error("服务器未返回有效的接口配置，请确认已重载新版插件");
  }
  state.json_api_list = payload.json_api_list;
  state.image_api_list = payload.image_api_list;
  state.revision = payload.revision;
  state.dirty = false;
  clearEdit();
  renderManagementList();
  renderEndpointOptions();
  setStatus(`JSON API ${state.json_api_list.length} 个，图片 API ${state.image_api_list.length} 个`);
}

async function saveEndpoints() {
  if (state.running || !state.dirty) return;
  if (state.editing || manageUrlInput.value.trim()) {
    setManagementStatus("请先应用或取消当前编辑，或添加输入框中的地址", "error");
    return;
  }
  setRunning(true);
  setManagementStatus("正在保存 API 地址...");
  try {
    const payload = await bridge.apiPost("api-config/save", {
      json_api_list: state.json_api_list,
      image_api_list: state.image_api_list,
      revision: state.revision,
    });
    applySnapshot(payload);
    setManagementStatus("API 地址已保存并立即生效", "success");
  } catch (error) {
    setManagementStatus(error?.message || "保存 API 地址失败", "error");
  } finally {
    setRunning(false);
  }
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

  setRunning(state.running);
  renderEmptyState(state.dirty ? "请先保存或放弃更改再测试" : "尚未执行测试");
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
  if (state.running) return;
  setRunning(true);
  setManagementStatus("正在读取插件配置...");
  try {
    applySnapshot(await bridge.apiGet("api-test/list"));
    setManagementStatus("");
  } catch (error) {
    setManagementStatus(error?.message || "读取接口配置失败，请刷新重试", "error");
  } finally {
    setRunning(false);
  }
}

async function runSingleTest(apiType, apiUrl) {
  const result = await bridge.apiPost("api-test/run", {
    api_type: apiType,
    api_url: apiUrl,
  });
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
    results.replaceChildren();
    renderResult(result);
    setStatus(result.success ? "接口测试成功" : "接口测试失败", result.success ? "success" : "error");
  } catch (error) {
    results.replaceChildren();
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
      renderResult(result);
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
urlSelect.addEventListener("change", () => setRunning(state.running));
testButton.addEventListener("click", testSelected);
testAllButton.addEventListener("click", testAll);
refreshButton.addEventListener("click", loadEndpoints);
discardApiButton.addEventListener("click", loadEndpoints);
addApiButton.addEventListener("click", addOrEditEndpoint);
cancelEditButton.addEventListener("click", clearEdit);
saveApiButton.addEventListener("click", saveEndpoints);
manageUrlInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.isComposing) {
    addOrEditEndpoint();
  }
});

const context = await bridge.ready();
applyTheme(context);
const removeContextListener = bridge.onContext(applyTheme);
window.addEventListener("beforeunload", removeContextListener);
await loadEndpoints();
