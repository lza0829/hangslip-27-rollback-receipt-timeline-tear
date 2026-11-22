import { useEffect, useState } from "react";
import { api } from "../api";

export default function Gate() {
  const [today, setToday] = useState(null);
  const [rows, setRows] = useState([]);
  const [msg, setMsg] = useState("");

  async function load() {
    const [t, list] = await Promise.all([api.日闸今日(), api.日闸列表()]);
    setToday(t);
    setRows(list);
  }

  useEffect(() => {
    load().catch((e) => setMsg(e.message));
  }, []);

  async function seal() {
    setMsg("");
    try {
      const row = await api.结案({ note: "营业日结案" });
      setMsg(`已结案：${row.day}`);
      await load();
    } catch (e) {
      setMsg(e.message);
    }
  }

  return (
    <section className="panel">
      <h3>结案日闸</h3>
      <p className="msg">{msg}</p>
      <div className="row">
        <div className="metric">
          <b>{today?.day || "—"}</b>
          <span>今日</span>
        </div>
        <div className="metric">
          <b>{today?.状态 || "—"}</b>
          <span>日闸状态</span>
        </div>
        <button type="button" onClick={seal} disabled={today?.sealed}>
          今日结案
        </button>
      </div>
      <table>
        <thead>
          <tr>
            <th>日期</th>
            <th>状态</th>
            <th>结案时刻</th>
            <th>备注</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.day}>
              <td>{r.day}</td>
              <td>{r.状态}</td>
              <td>{r.sealed_at || "—"}</td>
              <td>{r.note || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
