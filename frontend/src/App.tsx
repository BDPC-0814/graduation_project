import { useState } from "react";

import { AlertCenterPage } from "./pages/AlertCenterPage";
import { ControlConsolePage } from "./pages/ControlConsolePage";
import { DashboardPage } from "./pages/DashboardPage";

type ViewKey = "dashboard" | "alerts" | "control";

const viewItems: Array<{ key: ViewKey; label: string }> = [
  { key: "dashboard", label: "监控总览" },
  { key: "alerts", label: "告警中心" },
  { key: "control", label: "系统控制台" },
];

export default function App() {
  const [activeView, setActiveView] = useState<ViewKey>("dashboard");

  return (
    <>
      <div className="app-view-switcher" role="tablist" aria-label="页面切换">
        {viewItems.map((item) => (
          <button
            key={item.key}
            type="button"
            className={`app-view-button ${item.key === activeView ? "active" : ""}`}
            onClick={() => setActiveView(item.key)}
          >
            {item.label}
          </button>
        ))}
      </div>

      {activeView === "dashboard" ? <DashboardPage /> : null}
      {activeView === "alerts" ? <AlertCenterPage /> : null}
      {activeView === "control" ? <ControlConsolePage /> : null}
    </>
  );
}
