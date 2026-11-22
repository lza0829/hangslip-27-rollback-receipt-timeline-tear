import { useEffect, useState } from "react";
import { api } from "../api";

export default function Ready() {
  const [rows, setRows] = useState([]);
  const [codes, setCodes] = useState({});
  const [msg, setMsg] = useState("");

  async function load() {
    setRows(await api.挂牌列表("?status=" + encodeURIComponent("待取")));
  }

  useEffect(() => {
    load().catch((e) => setMsg(e.message));
  }, []);

  async function pick(ticket_no) {
    setMsg("");
    try {
      await api.取衣(ticket_no, {
        pickup_code: codes[ticket_no] || "",
        operator: "柜员",
      });
      setMsg(`${ticket_no} 已取衣核销`);
      await load();
    } catch (e) {
      setMsg(e.message);
    }
  }

  return (
    <section className="panel">
      <h3>待取核销</h3>
      <p className={`msg ${msg.includes("已取") ? "ok" : ""}`}>{msg}</p>
      <table>
        <thead>
          <tr>
            <th>票号</th>
            <th>顾客</th>
            <th>承诺日</th>
            <th>暗码</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.ticket_no}>
              <td>{r.ticket_no}</td>
              <td>{r.customer_name}</td>
              <td>{r.due_date}</td>
              <td>
                <input
                  placeholder="输入暗码"
                  value={codes[r.ticket_no] || ""}
                  onChange={(e) =>
                    setCodes({ ...codes, [r.ticket_no]: e.target.value })
                  }
                />
              </td>
              <td>
                <button type="button" onClick={() => pick(r.ticket_no)}>
                  核销取衣
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
