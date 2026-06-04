import { ChevronLeft, ChevronRight } from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

const navItems = [
  { to: "/", label: "首页", code: "01" },
  { to: "/quick-evaluation", label: "端到端评测", code: "02" },
  { to: "/evaluation", label: "分阶段评测", code: "03" },
  { to: "/calibration", label: "评测样本库", code: "04" },
  { to: "/history", label: "历史评测", code: "05" }
];

export function AppLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();
  const activeItem =
    navItems.find((item) =>
      item.to === "/"
        ? location.pathname === "/"
        : location.pathname.startsWith(item.to)
    ) || navItems[0];

  return (
    <div className={collapsed ? "app-shell sidebar-collapsed" : "app-shell"}>
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">美</div>
          <div>
            <div className="brand-title">美团履约评测</div>
            <div className="brand-subtitle">复杂指令下的多轮对话自动评估</div>
          </div>
        </div>
        <div className="run-status" aria-label="当前页面">
          <span className="status-dot idle" />
          {activeItem.label}
        </div>
        <div className="context-pill">评测记录按项目隔离保存</div>
      </header>

      <div className="workspace">
        <aside className="global-nav light-nav">
          <button
            className="nav-toggle"
            type="button"
            aria-label={collapsed ? "展开导航" : "收起导航"}
            onClick={() => setCollapsed((value) => !value)}
          >
            {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
          </button>
          <div className="nav-product">
            <strong>履约评测平台</strong>
            <span>复杂指令、多轮对话、证据链报告</span>
          </div>
          <div className="nav-section-label">工作台</div>
          <nav aria-label="主导航">
          {navItems.map((item) => {
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                className={({ isActive }) =>
                  isActive ? "global-nav-item active" : "global-nav-item"
                }
              >
                <span className="global-nav-icon">{item.code}</span>
                <span className="global-nav-label">{item.label}</span>
              </NavLink>
            );
          })}
          </nav>
          <p className="nav-note">
            首页启动快速评测；分阶段评测用于逐步校准；评测样本库用于验证评测可靠性。
          </p>
        </aside>
        <main className="main-workspace">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
