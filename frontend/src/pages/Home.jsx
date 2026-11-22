import { useEffect, useState } from "react";
import { api } from "../api";

export default function Home() {
  const [d, setD] = useState(null);
  const [check, setCheck] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    Promise.all([api.总览(), api.链路自检()])
      .then(([overview, chain]) => {
        setD(overview);
        setCheck(chain);
      })
      .catch((e) => setErr(e.message));
  }, []);

  const cells = d
    ? [
        ["在途水位", d.surface_ok ? (d.在途水位 ?? d.在途 ?? "—") : d.在途水位],
        ["待取", d.待取],
        ["超期隔离", d.超期隔离],
        ["今日已取", d.已取],
        ["水洗中", d.水洗],
        ["日闸", d.日闸],
      ]
    : [];

  return (
    <>
      <div className="hero-strip">
        <section className="ticket-hero">
          <h2>今日挂衣</h2>
          <p>
            票墙左侧是工位入口。先开票贴号，再沿工序推到待取，顾客凭暗码核销；逾承诺日可进超期隔离，与现行票态互证。
          </p>
        </section>
        <div className="metrics">
          {cells.map(([k, v], i) => (
            <div className="metric" key={k} style={{ animationDelay: `${i * 0.05}s` }}>
              <b>{v ?? "—"}</b>
              <span>{k}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="msg">{err}</div>
      {check && (
        <section className="panel chain-check">
          <h3>事件链联动自检</h3>
          <div className="row">
            <span className={`badge ${check.一致 ? "kind-推进" : "kind-倒回"}`}>
              {check.一致 ? "重放与现行态一致" : "口径分裂，需排查"}
            </span>
            <span className="muted-text">
              水位 watermarks={check.水位.watermarks} / 重放={check.水位.重放}
            </span>
            <span className="muted-text">
              分裂票 {check.分裂票.length} · 非法事件 {check.非法事件.length}
            </span>
          </div>
          {!check.一致 && (
            <pre className="check-detail">
              {JSON.stringify(
                { 分裂票: check.分裂票, 非法事件: check.非法事件 },
                null,
                2
              )}
            </pre>
          )}
        </section>
      )}
      {d && (
        <section className="panel">
          <h3>工序分布</h3>
          <table>
            <thead>
              <tr>
                <th>状态</th>
                <th>票数</th>
              </tr>
            </thead>
            <tbody>
              {["已收", "水洗", "烘干", "熨烫", "待取", "已取", "超期隔离", "丢失隔离"].map(
                (s) => (
                  <tr key={s}>
                    <td>
                      <span className={`badge ${s}`}>{s}</span>
                    </td>
                    <td>{d[s]}</td>
                  </tr>
                )
              )}
            </tbody>
          </table>
        </section>
      )}
    </>
  );
}
