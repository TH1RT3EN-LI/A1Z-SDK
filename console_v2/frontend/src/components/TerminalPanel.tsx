import { useEffect, useRef, useState } from "react";
import { Maximize2, Minimize2, RotateCcw, TerminalSquare } from "lucide-react";
import { FitAddon } from "@xterm/addon-fit";
import { WebLinksAddon } from "@xterm/addon-web-links";
import { Terminal } from "@xterm/xterm";

type ConnectionState = "connecting" | "connected" | "disconnected";

function buildTerminalSocketUrl() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/api/terminal`;
}

export default function TerminalPanel() {
  const terminalHost = useRef<HTMLDivElement>(null);
  const [session, setSession] = useState(0);
  const [connectionState, setConnectionState] = useState<ConnectionState>("connecting");
  const [maximized, setMaximized] = useState(false);

  useEffect(() => {
    if (!maximized) return undefined;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMaximized(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [maximized]);

  useEffect(() => {
    const host = terminalHost.current;
    if (!host) return undefined;

    setConnectionState("connecting");
    const terminal = new Terminal({
      cursorBlink: true,
      cursorStyle: "bar",
      fontFamily: '"JetBrains Mono", "Cascadia Code", "Noto Sans Mono", monospace',
      fontSize: 12,
      lineHeight: 1.25,
      scrollback: 5000,
      allowTransparency: true,
      theme: {
        background: "#0b0f15",
        foreground: "#d7e0e8",
        cursor: "#77d4f4",
        cursorAccent: "#0b0f15",
        selectionBackground: "#29495a",
        black: "#11161c",
        red: "#ef767a",
        green: "#72d8a0",
        yellow: "#e9c46a",
        blue: "#6cb6ff",
        magenta: "#c099ff",
        cyan: "#67d4df",
        white: "#d7e0e8",
        brightBlack: "#66717d",
      },
    });
    const fitAddon = new FitAddon();
    terminal.loadAddon(fitAddon);
    terminal.loadAddon(new WebLinksAddon());
    terminal.open(host);

    const desktop = window.a1zDesktop;
    const desktopSessionId = desktop ? crypto.randomUUID() : undefined;
    let socket: WebSocket | undefined;
    let disposed = false;
    let removeDesktopDataListener: (() => void) | undefined;
    let removeDesktopExitListener: (() => void) | undefined;

    const reportConnected = () => {
      if (disposed) return;
      setConnectionState("connected");
      fitAddon.fit();
      terminal.focus();
    };
    const reportDisconnected = () => {
      if (disposed) return;
      setConnectionState("disconnected");
      terminal.writeln("\r\n\x1b[38;5;203m[本地终端连接已关闭]\x1b[0m");
    };

    if (desktop && desktopSessionId) {
      removeDesktopDataListener = desktop.onTerminalData((payload) => {
        if (payload.sessionId === desktopSessionId) terminal.write(payload.data);
      });
      removeDesktopExitListener = desktop.onTerminalExit((payload) => {
        if (payload.sessionId === desktopSessionId) reportDisconnected();
      });
      void desktop
        .startTerminal({
          sessionId: desktopSessionId,
          columns: terminal.cols,
          rows: terminal.rows,
        })
        .then(reportConnected)
        .catch(reportDisconnected);
    } else {
      socket = new WebSocket(buildTerminalSocketUrl());
      socket.binaryType = "arraybuffer";
      const decoder = new TextDecoder();
      socket.addEventListener("open", reportConnected);
      socket.addEventListener("message", (event) => {
        if (event.data instanceof ArrayBuffer) {
          terminal.write(decoder.decode(event.data, { stream: true }));
        } else {
          terminal.write(String(event.data));
        }
      });
      socket.addEventListener("close", reportDisconnected);
      socket.addEventListener("error", () => {
        if (!disposed) setConnectionState("disconnected");
      });
    }

    const sendResize = () => {
      if (desktop && desktopSessionId) {
        desktop.resizeTerminal(desktopSessionId, terminal.cols, terminal.rows);
      } else if (socket?.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: "resize", cols: terminal.cols, rows: terminal.rows }));
      }
    };

    const dataSubscription = terminal.onData((data) => {
      if (desktop && desktopSessionId) {
        desktop.writeTerminal(desktopSessionId, data);
      } else if (socket?.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: "input", data }));
      }
    });
    const resizeObserver = new ResizeObserver(() => {
      fitAddon.fit();
      sendResize();
    });
    resizeObserver.observe(host);

    return () => {
      disposed = true;
      dataSubscription.dispose();
      resizeObserver.disconnect();
      removeDesktopDataListener?.();
      removeDesktopExitListener?.();
      if (desktop && desktopSessionId) desktop.closeTerminal(desktopSessionId);
      socket?.close();
      terminal.dispose();
    };
  }, [session]);

  return (
    <section className={`panel terminal-panel ${maximized ? "is-maximized" : ""}`}>
      <div className="panel-header terminal-header">
        <div className="terminal-heading">
          <TerminalSquare size={17} strokeWidth={1.7} />
          <div>
            <span className="eyebrow">LOCAL PTY</span>
            <h2>终端</h2>
          </div>
        </div>
        <div className="terminal-tools">
          <span className={`connection-state is-${connectionState}`}>
            <i />
            {connectionState === "connected" ? "已连接" : connectionState === "connecting" ? "连接中" : "已断开"}
          </span>
          <button
            type="button"
            title="新建终端会话"
            aria-label="新建终端会话"
            onClick={() => setSession((value) => value + 1)}
          >
            <RotateCcw size={14} />
          </button>
          <button
            type="button"
            title={maximized ? "还原终端" : "最大化终端"}
            aria-label={maximized ? "还原终端" : "最大化终端"}
            onClick={() => setMaximized((value) => !value)}
          >
            {maximized ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
          </button>
        </div>
      </div>
      <div className="terminal-surface" ref={terminalHost} />
    </section>
  );
}
