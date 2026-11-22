import { Fragment, useEffect, useState } from "react";
import { api } from "../api";

const NEXT = {
  已收: ["水洗", "烘干", "熨烫", "待取"],
  水洗: ["烘干", "熨烫", "待取"],
  烘干: ["熨烫", "待取"],
  熨烫: ["待取"],
};

// 相邻上一档：与后端 PROCESS_CHAIN/PREV 同口径；已收无键即不显示倒回
const PREV = {
  水洗: "已收",
  烘干: "水洗",
  熨烫: "烘干",
  待取: "熨烫",
};

const EVENT_BADGE = {
  收衣: "收衣",
  推进: "推进",
  倒回: "倒回",
  取衣: "取衣",
  隔离: "隔离",
};

export default function Process() {
  const [rows, setRows] = useState([]);
  const [msg, setMsg] = useState("");
  const [openNo, setOpenNo] = useState(null);
  const [chains, setChains] = useState({});

  async function load() {
    const all = await api.挂牌列表();
    setRows(all.filter((r) => !["已取", "超期隔离", "丢失隔离"].includes(r.status)));
  }

  useEffect(() => {
    load().catch((e) => setMsg(e.message));
  }, []);

  async function go(ticket_no, to_status) {
    setMsg("");
    try {
      await api.推进(ticket_no, { to_status, operator: "工序员" });
      setMsg(`${ticket_no} → ${to_status}`);
      await load();
      if (openNo === ticket_no) await loadChain(ticket_no);
    } catch (e) {
      setMsg(e.message);
    }
  }

  async function back(ticket_no) {
    setMsg("");
    const target = PREV[rows.find((r) => r.ticket_no === ticket_no)?.status];
    if (!target) return;
    try {
      await api.倒回(ticket_no, { operator: "工序员", note: "推错回上一工位" });
      setMsg(`${ticket_no} 倒回 → ${target}`);
      await load();
      if (openNo === ticket_no) await loadChain(ticket_no);
    } catch (e) {
      setMsg(e.message);
    }
  }

  async function loadChain(ticket_no) {
    const detail = await api.挂牌详情(ticket_no);
    setChains((m) => ({ ...m, [ticket_no]: detail.events || [] }));
  }

  async function toggleChain(ticket_no) {
    if (openNo === ticket_no) {
      setOpenNo(null);
      return;
    }
    setOpenNo(ticket_no);
    if (!chains[ticket_no]) await loadChain(ticket_no).catch((e) => setMsg(e.message));
  }

  return (
    <section className="panel">
      <h3>工序轨（可倒回相邻上一档；已取/隔离为硬边界）</h3>
      <p className={`msg ${msg.includes("→") ? "ok" : ""}`}>{msg}</p>
      <table>
        <thead>
          <tr>
            <th>票号</th>
            <th>门店</th>
            <th>顾客</th>
            <th>现行</th>
            <th>承诺日</th>
            <th>推进</th>
            <th>倒回</th>
            <th>时间线</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <Fragment key={r.ticket_no}>
              <tr>
                <td>{r.ticket_no}</td>
                <td>{r.store_code}</td>
                <td>{r.customer_name}</td>
                <td>
                  <span className={`badge ${r.status}`}>{r.status}</span>
                </td>
                <td>{r.due_date}</td>
                <td>
                  <div className="row">
                    {(NEXT[r.status] || []).map((s) => (
                      <button key={s} type="button" className="ghost" onClick={() => go(r.ticket_no, s)}>
                        {s}
                      </button>
                    ))}
                  </div>
                </td>
                <td>
                  {PREV[r.status] ? (
                    <button
                      type="button"
                      className="ghost rollback"
                      onClick={() => back(r.ticket_no)}
                      title={`倒回到相邻上一档：${PREV[r.status]}`}
                    >
                      ↩ {PREV[r.status]}
                    </button>
                  ) : (
                    <span className="muted-text">首档不可倒回</span>
                  )}
                </td>
                <td>
                  <button type="button" className="ghost" onClick={() => toggleChain(r.ticket_no)}>
                    {openNo === r.ticket_no ? "收起" : "事件链"}
                  </button>
                </td>
              </tr>
              {openNo === r.ticket_no && (
                <tr className="chain-row">
                  <td colSpan={8}>
                    <table className="chain-table">
                      <thead>
                        <tr>
                          <th>事件</th>
                          <th>自</th>
                          <th>至</th>
                          <th>操作员</th>
                          <th>时刻</th>
                          <th>附注</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(chains[r.ticket_no] || []).map((e) => (
                          <tr key={e.id}>
                            <td>
                              <span className={`badge kind-${e.kind}`}>
                                {EVENT_BADGE[e.kind] || e.kind}
                              </span>
                            </td>
                            <td>{e.from_status ?? "—"}</td>
                            <td>{e.to_status}</td>
                            <td>{e.operator}</td>
                            <td>{e.occurred_at}</td>
                            <td>{e.note || "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </td>
                </tr>
              )}
            </Fragment>
          ))}
        </tbody>
      </table>
    </section>
  );
}
