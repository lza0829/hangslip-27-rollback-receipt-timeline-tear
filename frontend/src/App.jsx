import { NavLink, Route, Routes } from "react-router-dom";
import Home from "./pages/Home.jsx";
import Intake from "./pages/Intake.jsx";
import Process from "./pages/Process.jsx";
import Ready from "./pages/Ready.jsx";
import Quarantine from "./pages/Quarantine.jsx";
import Stores from "./pages/Stores.jsx";
import Gate from "./pages/Gate.jsx";
import Settings from "./pages/Settings.jsx";

const links = [
  ["/", "总览", true],
  ["/收衣", "收衣开票"],
  ["/工序", "工序轨"],
  ["/待取", "待取核销"],
  ["/隔离", "超期隔离"],
  ["/门店", "门店衣架"],
  ["/日闸", "结案日闸"],
  ["/设置", "设置"],
];

export default function App() {
  return (
    <div className="layout">
      <aside className="rail">
        <div className="brand-block">
          <h1 className="brand">衣票墙</h1>
          <p className="brand-sub">收衣贴号，沿工序到待取；凭暗码取衣关账，超期进隔离。</p>
        </div>
        <nav>
          {links.map(([to, label, end]) => (
            <NavLink key={to} to={to} end={!!end}>
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="stage">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/收衣" element={<Intake />} />
          <Route path="/工序" element={<Process />} />
          <Route path="/待取" element={<Ready />} />
          <Route path="/隔离" element={<Quarantine />} />
          <Route path="/门店" element={<Stores />} />
          <Route path="/日闸" element={<Gate />} />
          <Route path="/设置" element={<Settings />} />
        </Routes>
      </main>
    </div>
  );
}
