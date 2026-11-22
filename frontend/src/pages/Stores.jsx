import { useEffect, useState } from "react";
import { api } from "../api";

export default function Stores() {
  const [rows, setRows] = useState([]);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    api
      .门店()
      .then(setRows)
      .catch((e) => setMsg(e.message));
  }, []);

  return (
    <section className="panel">
      <h3>门店衣架</h3>
      <p className="msg">{msg}</p>
      <table>
        <thead>
          <tr>
            <th>代号</th>
            <th>名称</th>
            <th>衣架轨数</th>
            <th>状态</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.code}>
              <td>{r.code}</td>
              <td>{r.name}</td>
              <td>{r.rack_count}</td>
              <td>{r.active ? "在用" : "停用"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
