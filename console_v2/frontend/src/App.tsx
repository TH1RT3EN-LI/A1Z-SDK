import { useEffect, useRef, useState, type ComponentType } from "react";
import {
  Check,
  ChevronDown,
  ExternalLink,
  Gamepad2,
  Minus,
  Square,
  X,
} from "lucide-react";
import JointReadback from "./components/JointReadback";
import RobotViewport from "./components/RobotViewport";
import StartupAssistant from "./components/StartupAssistant";
import TerminalPanel from "./components/TerminalPanel";
import {
  readDeploymentMode,
  storeDeploymentMode,
  type DeploymentMode,
} from "./deployment";
import { readThemeMode, storeThemeMode, type ThemeMode } from "./theme";
import {
  readStartupParameters,
  storeStartupParameters,
  type StartupParameters,
} from "./startup";
import { useRobotTelemetry } from "./robot-telemetry";

type NavigationItem = {
  id: string;
  label: string;
  icon: ComponentType<{ size?: number; strokeWidth?: number }>;
};

type MenuEntry = {
  label: string;
  selected?: boolean;
  onSelect?: () => void;
};

const navigation: NavigationItem[] = [
  { id: "control", label: "控制", icon: Gamepad2 },
];

const developmentMode =
  window.a1zDesktop?.developmentMode ??
  import.meta.env.VITE_A1Z_DEVELOPMENT_MODE === "1";

const relatedRepositories = [
  {
    name: "A1Z-SDK",
    url: "https://github.com/TH1RT3EN-LI/A1Z-SDK",
    current: true,
  },
  {
    name: "GALAXEA-A1Z",
    url: "https://github.com/userguide-galaxea/GALAXEA-A1Z",
  },
  {
    name: "SAM 2",
    url: "https://github.com/facebookresearch/sam2",
  },
  {
    name: "AnyGrasp SDK",
    url: "https://github.com/graspnet/anygrasp_sdk",
  },
] as const;

function Menu({
  label,
  entries,
  open,
  onToggle,
  onSelect,
}: {
  label: string;
  entries: MenuEntry[];
  open: boolean;
  onToggle: () => void;
  onSelect: () => void;
}) {
  return (
    <div className={`menu-item ${open ? "is-open" : ""}`}>
      <button
        className="menu-trigger"
        type="button"
        aria-expanded={open}
        aria-haspopup="menu"
        onClick={onToggle}
      >
        {label}
        <ChevronDown size={13} />
      </button>
      {open ? (
        <div className="menu-popover" role="menu">
          {entries.map((entry) => {
            const selectable = typeof entry.selected === "boolean";
            return (
              <button
                key={entry.label}
                type="button"
                role={selectable ? "menuitemradio" : "menuitem"}
                aria-checked={selectable ? entry.selected : undefined}
                onClick={() => {
                  entry.onSelect?.();
                  onSelect();
                }}
              >
                <span>{entry.label}</span>
                {selectable && entry.selected ? (
                  <Check size={13} strokeWidth={2} aria-hidden="true" />
                ) : null}
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

function DeploymentSettingsDialog({
  mode,
  onModeChange,
  onClose,
}: {
  mode: DeploymentMode;
  onModeChange: (mode: DeploymentMode) => void;
  onClose: () => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const modes: Array<{ value: DeploymentMode; label: string }> = [
    { value: "host", label: "宿主机" },
    { value: "docker", label: "Docker" },
  ];

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    dialog.showModal();
    return () => {
      if (dialog.open) dialog.close();
    };
  }, []);

  return (
    <dialog
      className="deployment-dialog"
      ref={dialogRef}
      aria-labelledby="deployment-dialog-title"
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
    >
      <div className="deployment-dialog-content">
        <h2 id="deployment-dialog-title">部署方式</h2>
        <div className="deployment-options" role="radiogroup" aria-label="部署方式">
          {modes.map((option) => {
            const selected = mode === option.value;
            return (
              <button
                className={`deployment-option ${selected ? "is-selected" : ""}`}
                key={option.value}
                type="button"
                role="radio"
                aria-checked={selected}
                onClick={() => onModeChange(option.value)}
              >
                <span>{option.label}</span>
                {selected ? <Check size={16} strokeWidth={2} aria-hidden="true" /> : null}
              </button>
            );
          })}
        </div>
        <div className="deployment-dialog-footer">
          <button className="deployment-dialog-done" type="button" onClick={onClose}>
            完成
          </button>
        </div>
      </div>
    </dialog>
  );
}

function AboutDialog({ onClose }: { onClose: () => void }) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const titleRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    dialog.showModal();
    titleRef.current?.focus();
    return () => {
      if (dialog.open) dialog.close();
    };
  }, []);

  return (
    <dialog
      className="about-dialog"
      ref={dialogRef}
      aria-labelledby="about-dialog-title"
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="about-dialog-content">
        <div className="about-dialog-heading">
          <button
            className="about-dialog-close"
            type="button"
            aria-label="关闭关于窗口"
            title="关闭"
            onClick={onClose}
          >
            <X size={8} strokeWidth={2.5} aria-hidden="true" />
          </button>
          <h2 id="about-dialog-title" ref={titleRef} tabIndex={-1}>
            关于 A1Z Console
          </h2>
          <span aria-hidden="true" />
        </div>

        <section className="about-repositories" aria-labelledby="about-repositories-title">
          <h3 id="about-repositories-title">GitHub 仓库</h3>
          <div className="about-repository-list">
            {relatedRepositories.map((repository) => (
              <a
                className="about-repository-link"
                key={repository.url}
                href={repository.url}
                target="_blank"
                rel="noreferrer"
                aria-label={`${repository.name}（在浏览器中打开 GitHub）`}
              >
                <span className="about-repository-name">
                  <strong>{repository.name}</strong>
                  {"current" in repository && repository.current ? (
                    <span className="about-current-project">本项目</span>
                  ) : null}
                </span>
                <ExternalLink size={15} strokeWidth={1.8} aria-hidden="true" />
              </a>
            ))}
          </div>
        </section>
      </div>
    </dialog>
  );
}

export default function App() {
  const [activeNavigation, setActiveNavigation] = useState(navigation[0]);
  const [openMenu, setOpenMenu] = useState<string | null>(null);
  const [themeMode, setThemeMode] = useState<ThemeMode>(readThemeMode);
  const [deploymentMode, setDeploymentMode] =
    useState<DeploymentMode>(readDeploymentMode);
  const [deploymentSettingsOpen, setDeploymentSettingsOpen] = useState(false);
  const [aboutOpen, setAboutOpen] = useState(false);
  const [startupAssistantOpen, setStartupAssistantOpen] = useState(true);
  const [startupParameters, setStartupParameters] =
    useState<StartupParameters>(readStartupParameters);
  const [isWindowMaximized, setIsWindowMaximized] = useState(false);
  const [isWindowFocused, setIsWindowFocused] = useState(document.hasFocus());
  const [showJointLabels, setShowJointLabels] = useState(
    () => window.localStorage.getItem("a1z-console:model-joint-labels") === "true",
  );
  const desktopApi = window.a1zDesktop;
  const robotTelemetry = useRobotTelemetry(
    deploymentMode,
    !startupAssistantOpen && !developmentMode,
  );

  useEffect(() => {
    if (!desktopApi) return;
    void desktopApi.getWindowState().then(({ maximized }) => setIsWindowMaximized(maximized));
    return desktopApi.onWindowMaximizedChange(setIsWindowMaximized);
  }, [desktopApi]);

  useEffect(() => {
    const reportFocused = () => setIsWindowFocused(true);
    const reportBlurred = () => setIsWindowFocused(false);
    window.addEventListener("focus", reportFocused);
    window.addEventListener("blur", reportBlurred);
    return () => {
      window.removeEventListener("focus", reportFocused);
      window.removeEventListener("blur", reportBlurred);
    };
  }, []);

  useEffect(() => {
    if (!openMenu) return;
    const closeOutside = (event: PointerEvent) => {
      if (!(event.target instanceof Element) || !event.target.closest(".menu-item")) {
        setOpenMenu(null);
      }
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpenMenu(null);
    };
    window.addEventListener("pointerdown", closeOutside);
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      window.removeEventListener("pointerdown", closeOutside);
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [openMenu]);

  useEffect(() => {
    storeThemeMode(themeMode);
    document.documentElement.style.colorScheme = themeMode;
  }, [themeMode]);

  useEffect(() => {
    storeDeploymentMode(deploymentMode);
  }, [deploymentMode]);

  useEffect(() => {
    storeStartupParameters(startupParameters);
  }, [startupParameters]);

  useEffect(() => {
    window.localStorage.setItem(
      "a1z-console:model-joint-labels",
      String(showJointLabels),
    );
  }, [showJointLabels]);

  return (
    <div
      className={`app-shell ${startupAssistantOpen ? "has-startup-assistant" : ""}`}
      data-theme={themeMode}
    >
      <header className="top-bar">
        <nav className="menu-bar" aria-label="应用菜单" inert={startupAssistantOpen}>
          <Menu
            label="设置"
            entries={[
              {
                label: "部署方式…",
                onSelect: () => setDeploymentSettingsOpen(true),
              },
              {
                label: "浅色模式",
                selected: themeMode === "light",
                onSelect: () => setThemeMode("light"),
              },
              {
                label: "深色模式",
                selected: themeMode === "dark",
                onSelect: () => setThemeMode("dark"),
              },
            ]}
            open={openMenu === "settings"}
            onToggle={() => setOpenMenu((value) => (value === "settings" ? null : "settings"))}
            onSelect={() => setOpenMenu(null)}
          />
          <Menu
            label="帮助"
            entries={[
              {
                label: "关于 A1Z Console",
                onSelect: () => setAboutOpen(true),
              },
            ]}
            open={openMenu === "help"}
            onToggle={() => setOpenMenu((value) => (value === "help" ? null : "help"))}
            onSelect={() => setOpenMenu(null)}
          />
        </nav>

        {desktopApi ? (
          <div
            className={`window-controls ${isWindowFocused ? "" : "is-inactive"}`}
            aria-label="窗口控制"
          >
            <button
              className="window-control-button minimize-window-button"
              type="button"
              aria-label="最小化窗口"
              title="最小化"
              onClick={() => desktopApi.minimizeWindow()}
            >
              <Minus size={8} strokeWidth={2} aria-hidden="true" />
            </button>
            <button
              className="window-control-button maximize-window-button"
              type="button"
              aria-label={isWindowMaximized ? "还原窗口" : "最大化窗口"}
              aria-pressed={isWindowMaximized}
              title={isWindowMaximized ? "还原" : "最大化"}
              onClick={() => desktopApi.toggleMaximizeWindow()}
            >
              {isWindowMaximized ? (
                <span className="restore-window-icon" aria-hidden="true" />
              ) : (
                <Square size={7} strokeWidth={2} aria-hidden="true" />
              )}
            </button>
            <button
              className="window-control-button close-window-button"
              type="button"
              aria-label="关闭窗口"
              title="关闭"
              onClick={() => desktopApi.closeWindow()}
            >
              <X size={8} strokeWidth={2} aria-hidden="true" />
            </button>
          </div>
        ) : null}
      </header>

      <div className="app-body" inert={startupAssistantOpen}>
        <aside className="side-navigation" aria-label="功能列表">
          {navigation.map((item) => {
            const Icon = item.icon;
            const active = activeNavigation.id === item.id;
            return (
              <button
                className={`navigation-button ${active ? "is-active" : ""}`}
                key={item.id}
                onClick={() => setActiveNavigation(item)}
                type="button"
                aria-label={item.label}
                aria-current={active ? "page" : undefined}
                title={item.label}
              >
                <Icon size={20} strokeWidth={1.7} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </aside>

        <main className="workspace-grid">
          <section
            className="panel primary-workspace"
            aria-label={activeNavigation.label}
          >
            <JointReadback
              telemetry={robotTelemetry}
              deploymentMode={deploymentMode}
              developmentMode={developmentMode}
              showModelLabels={showJointLabels}
              onShowModelLabelsChange={setShowJointLabels}
            />
          </section>

          <TerminalPanel theme={themeMode} />

          <section className="panel viewport-panel" aria-label="模型">
            <div className="viewport-content">
              <RobotViewport
                theme={themeMode}
                jointPositionsDeg={robotTelemetry.jointsDeg}
                showJointLabels={showJointLabels}
              />
            </div>
          </section>
        </main>
      </div>

      {deploymentSettingsOpen ? (
        <DeploymentSettingsDialog
          mode={deploymentMode}
          onModeChange={setDeploymentMode}
          onClose={() => setDeploymentSettingsOpen(false)}
        />
      ) : null}

      {aboutOpen ? <AboutDialog onClose={() => setAboutOpen(false)} /> : null}

      {startupAssistantOpen ? (
        <StartupAssistant
          deploymentMode={deploymentMode}
          theme={themeMode}
          parameters={startupParameters}
          allowSkip={developmentMode}
          onParametersChange={setStartupParameters}
          onComplete={() => setStartupAssistantOpen(false)}
        />
      ) : null}
    </div>
  );
}
