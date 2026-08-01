import { useState, type ComponentType } from "react";
import {
  Blocks,
  Bot,
  ChevronDown,
  CircleGauge,
  FileClock,
  Gamepad2,
  LayoutDashboard,
  RadioTower,
  ScanLine,
  Settings,
  Waypoints,
} from "lucide-react";
import RobotViewport from "./components/RobotViewport";
import TerminalPanel from "./components/TerminalPanel";

type ViewMode = "model" | "rgb" | "depth";

type NavigationItem = {
  id: string;
  label: string;
  icon: ComponentType<{ size?: number; strokeWidth?: number }>;
};

const navigation: NavigationItem[] = [
  { id: "overview", label: "总览", icon: LayoutDashboard },
  { id: "control", label: "控制", icon: Gamepad2 },
  { id: "vision", label: "感知", icon: ScanLine },
  { id: "tasks", label: "任务", icon: Waypoints },
  { id: "records", label: "记录", icon: FileClock },
];

const viewModes: Array<{ id: ViewMode; label: string }> = [
  { id: "model", label: "模型" },
  { id: "rgb", label: "RGB" },
  { id: "depth", label: "深度" },
];

function Menu({ label, children }: { label: string; children: string[] }) {
  return (
    <details className="menu-item">
      <summary>
        {label}
        <ChevronDown size={13} />
      </summary>
      <div className="menu-popover">
        {children.map((child) => (
          <button key={child} type="button">
            {child}
          </button>
        ))}
      </div>
    </details>
  );
}

function EmptyCameraView({ mode }: { mode: Exclude<ViewMode, "model"> }) {
  const isDepth = mode === "depth";
  return (
    <div className={`camera-placeholder ${isDepth ? "is-depth" : "is-rgb"}`}>
      <div className="camera-reticle" aria-hidden="true" />
      <RadioTower size={24} strokeWidth={1.5} />
      <strong>{isDepth ? "深度视图" : "RGB 视图"}</strong>
      <span>等待相机数据</span>
    </div>
  );
}

export default function App() {
  const [activeNavigation, setActiveNavigation] = useState(navigation[0]);
  const [viewMode, setViewMode] = useState<ViewMode>("model");

  return (
    <div className="app-shell">
      <header className="top-bar">
        <div className="brand-block">
          <div className="brand-mark">
            <Bot size={21} strokeWidth={1.8} />
          </div>
          <div>
            <strong>A1Z</strong>
            <span>CONSOLE</span>
          </div>
        </div>

        <nav className="menu-bar" aria-label="应用菜单">
          <Menu label="文件" children={["新建工作区", "打开布局", "保存布局"]} />
          <Menu label="视图" children={["重置布局", "全屏", "显示面板"]} />
          <Menu label="工具" children={["终端", "模型检查器", "诊断"]} />
          <Menu label="设置" children={["通用", "连接", "外观"]} />
          <Menu label="帮助" children={["快捷键", "关于 A1Z Console"]} />
        </nav>

        <div className="frame-status">
          <span className="status-dot" />
          FRAMEWORK
        </div>
      </header>

      <div className="app-body">
        <aside className="side-navigation" aria-label="功能列表">
          <div className="side-caption">功能</div>
          {navigation.map((item) => {
            const Icon = item.icon;
            const active = activeNavigation.id === item.id;
            return (
              <button
                className={`navigation-button ${active ? "is-active" : ""}`}
                key={item.id}
                onClick={() => setActiveNavigation(item)}
                type="button"
                aria-current={active ? "page" : undefined}
              >
                <Icon size={20} strokeWidth={1.7} />
                <span>{item.label}</span>
              </button>
            );
          })}
          <button className="navigation-button settings-button" type="button">
            <Settings size={20} strokeWidth={1.7} />
            <span>设置</span>
          </button>
        </aside>

        <main className="workspace-grid">
          <section className="panel primary-workspace">
            <div className="panel-header workspace-header">
              <div>
                <span className="eyebrow">WORKSPACE</span>
                <h1>{activeNavigation.label}</h1>
              </div>
              <div className="placeholder-chip">
                <Blocks size={14} />
                主界面
              </div>
            </div>
            <div className="workspace-canvas">
              <div className="canvas-origin">
                <CircleGauge size={22} strokeWidth={1.3} />
                <span>{activeNavigation.label}</span>
              </div>
            </div>
          </section>

          <TerminalPanel />

          <section className="panel viewport-panel">
            <div className="panel-header viewport-header">
              <div>
                <span className="eyebrow">VIEWPORT</span>
                <h2>{viewMode === "model" ? "A1Z G1Z" : viewMode.toUpperCase()}</h2>
              </div>
              <div className="segmented-control" role="tablist" aria-label="视窗内容">
                {viewModes.map((mode) => (
                  <button
                    className={viewMode === mode.id ? "is-active" : ""}
                    key={mode.id}
                    onClick={() => setViewMode(mode.id)}
                    role="tab"
                    aria-selected={viewMode === mode.id}
                    type="button"
                  >
                    {mode.label}
                  </button>
                ))}
              </div>
            </div>
            <div className="viewport-content">
              {viewMode === "model" ? <RobotViewport /> : <EmptyCameraView mode={viewMode} />}
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}
