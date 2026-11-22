import { useEffect, useState } from "react";
import { api } from "../api";

export default function Quarantine() {
  const [ready, setReady] = useState([]);
  const [logs, setLogs] = useState([]);
  const [msg, setMsg] = useState("");

  async function load() {
    const [a, b] = await Promise.all([
      api.挂牌列表("?status=" + encodeURIComponent("待取")),
      api.隔离列表(),
    ]);
    setReady(a);
    setLogs(b);
  }

  useEffect(() => {
    load().catch((e) => setMsg(e.message));
  }, []);

  async function iso(ticket_no, kind) {
    setMsg("");
    try {
      await api.隔离(ticket_no, {
        kind,
        reason: kind === "超期隔离" ? "逾承诺日未取" : "店内申报丢失",
        operator: "店长",
      });
      setMsg(`${ticket_no} → ${kind}`);
      await load();
    } catch (e) {
      setMsg(e.message);
    }
  }

  return (
    <>
      <section className="panel">
        <h3>待取转隔离</h3>
        <p className="msg">{msg}</p>
        <table>
          <thead>
            <tr>
              <th>票号</th>
              <th>承诺日</th>
              <th>顾客</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {ready.map((r) => (
              <tr key={r.ticket_no}>
                <td>{r.ticket_no}</td>
                <td>{r.due_date}</td>
                <td>{r.customer_name}</td>
                <td>
                  <div className="row">
                    <button type="button" onClick={() => iso(r.ticket_no, "超期隔离")}>
                      超期隔离
                    </button>
                    <button
                      type="button"
                      className="ghost"
                      onClick={() => iso(r.ticket_no, "丢失隔离")}
                    >
                      丢失隔离
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <section className="panel">
        <h3>隔离流水</h3>
        <table>
          <thead>
            <tr>
              <th>票号</th>
              <th>种类</th>
              <th>原因</th>
              <th>时间</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((r) => (
              <tr key={r.id}>
                <td>{r.ticket_no}</td>
                <td>
                  <span className={`badge ${r.kind}`}>{r.kind}</span>
                </td>
                <td>{r.reason}</td>
                <td>{r.created_at}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </>
  );
}
