import { useEffect, useRef, useState } from "react";
import { FitAddon } from "@xterm/addon-fit";
import { WebLinksAddon } from "@xterm/addon-web-links";
import { Terminal } from "@xterm/xterm";
import { terminalThemes, type ThemeMode } from "../theme";

type ConnectionState = "connecting" | "connected" | "disconnected";

function buildTerminalSocketUrl() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/api/terminal`;
}

export default function TerminalPanel({ theme }: { theme: ThemeMode }) {
  const terminalHost = useRef<HTMLDivElement>(null);
  const terminalInstance = useRef<Terminal | null>(null);
  const themeRef = useRef(theme);
  themeRef.current = theme;
  const [connectionState, setConnectionState] = useState<ConnectionState>("connecting");

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
      theme: terminalThemes[themeRef.current],
    });
    terminalInstance.current = terminal;
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
      if (terminalInstance.current === terminal) terminalInstance.current = null;
    };
  }, []);

  useEffect(() => {
    if (terminalInstance.current) {
      terminalInstance.current.options.theme = terminalThemes[theme];
    }
  }, [theme]);

  return (
    <section
      className="panel terminal-panel"
      aria-label="终端"
      data-connection-state={connectionState}
    >
      {connectionState === "connected" ? null : (
        <span className={`connection-state is-${connectionState}`}>
          <i />
          {connectionState === "connecting" ? "连接中" : "已断开"}
        </span>
      )}
      <div className="terminal-surface" ref={terminalHost} />
    </section>
  );
}
