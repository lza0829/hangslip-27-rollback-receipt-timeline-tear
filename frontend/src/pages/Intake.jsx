import { useEffect, useState } from "react";
import { api } from "../api";

export default function Intake() {
  const [stores, setStores] = useState([]);
  const [msg, setMsg] = useState("");
  const [form, setForm] = useState({
    ticket_no: "",
    store_code: "",
    pickup_code: "",
    customer_name: "",
    due_date: "",
    note: "",
    garment: "衬衣",
    qty: 1,
  });

  useEffect(() => {
    api.门店().then((rows) => {
      setStores(rows.filter((s) => s.active));
      if (rows[0]) setForm((f) => ({ ...f, store_code: rows[0].code }));
    });
  }, []);

  async function submit(e) {
    e.preventDefault();
    setMsg("");
    try {
      const row = await api.开票({
        ticket_no: form.ticket_no,
        store_code: form.store_code,
        pickup_code: form.pickup_code,
        customer_name: form.customer_name,
        due_date: form.due_date,
        note: form.note,
        items: [{ garment: form.garment, qty: Number(form.qty), remark: "" }],
      });
      setMsg(`已开票 ${row.ticket_no}，状态 ${row.status}`);
      setForm((f) => ({ ...f, ticket_no: "", pickup_code: "", customer_name: "", note: "" }));
    } catch (err) {
      setMsg(err.message);
    }
  }

  return (
    <section className="panel">
      <h3>收衣开票</h3>
      <p className="msg">{msg}</p>
      <form onSubmit={submit}>
        <div className="row">
          <input
            placeholder="票号"
            value={form.ticket_no}
            onChange={(e) => setForm({ ...form, ticket_no: e.target.value })}
            required
          />
          <select
            value={form.store_code}
            onChange={(e) => setForm({ ...form, store_code: e.target.value })}
          >
            {stores.map((s) => (
              <option key={s.code} value={s.code}>
                {s.name}
              </option>
            ))}
          </select>
          <input
            placeholder="取衣暗码"
            value={form.pickup_code}
            onChange={(e) => setForm({ ...form, pickup_code: e.target.value })}
            required
          />
          <input
            placeholder="顾客称呼"
            value={form.customer_name}
            onChange={(e) => setForm({ ...form, customer_name: e.target.value })}
            required
          />
        </div>
        <div className="row">
          <input
            type="date"
            value={form.due_date}
            onChange={(e) => setForm({ ...form, due_date: e.target.value })}
          />
          <input
            placeholder="衣物"
            value={form.garment}
            onChange={(e) => setForm({ ...form, garment: e.target.value })}
          />
          <input
            type="number"
            min="1"
            value={form.qty}
            onChange={(e) => setForm({ ...form, qty: e.target.value })}
          />
          <input
            placeholder="备注"
            value={form.note}
            onChange={(e) => setForm({ ...form, note: e.target.value })}
          />
          <button type="submit">开票贴号</button>
        </div>
      </form>
    </section>
  );
}
