import { useEffect, useState } from "react";
import { api } from "../api";

export default function Settings() {
  const [rows, setRows] = useState({});
  const [msg, setMsg] = useState("");

  useEffect(() => {
    api
      .设置()
      .then(setRows)
      .catch((e) => setMsg(e.message));
  }, []);

  return (
    <section className="panel">
      <h3>设置</h3>
      <p className="msg">{msg}</p>
      <table>
        <thead>
          <tr>
            <th>键</th>
            <th>值</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(rows).map(([k, v]) => (
            <tr key={k}>
              <td>{k}</td>
              <td>{v}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
