async function req(path, opts = {}) {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
    ...opts,
  });
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { 详情: text };
  }
  if (!res.ok) {
    const msg =
      (data && (data.detail || data.详情 || data.message)) || `请求失败 ${res.status}`;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return data;
}

export const api = {
  总览: () => req("/总览"),
  链路自检: () => req("/链路自检"),
  门店: () => req("/门店"),
  挂牌列表: (q = "") => req(`/挂牌${q}`),
  挂牌详情: (no) => req(`/挂牌/${encodeURIComponent(no)}`),
  开票: (body) => req("/挂牌", { method: "POST", body: JSON.stringify(body) }),
  推进: (no, body) =>
    req(`/挂牌/${encodeURIComponent(no)}/推进`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  倒回: (no, body) =>
    req(`/挂牌/${encodeURIComponent(no)}/倒回`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  取衣: (no, body) =>
    req(`/挂牌/${encodeURIComponent(no)}/取衣`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  隔离: (no, body) =>
    req(`/挂牌/${encodeURIComponent(no)}/隔离`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  隔离列表: () => req("/隔离"),
  日闸今日: () => req("/日闸/今日"),
  日闸列表: () => req("/日闸"),
  结案: (body) => req("/日闸/结案", { method: "POST", body: JSON.stringify(body) }),
  设置: () => req("/设置"),
};
