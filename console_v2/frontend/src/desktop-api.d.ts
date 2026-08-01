export {};

type TerminalDataPayload = {
  sessionId: string;
  data: string;
};

type TerminalExitPayload = {
  sessionId: string;
  exitCode: number;
  signal?: number;
};

declare global {
  interface Window {
    a1zDesktop?: {
      startTerminal(options: {
        sessionId: string;
        columns: number;
        rows: number;
      }): Promise<{ sessionId: string }>;
      writeTerminal(sessionId: string, data: string): void;
      resizeTerminal(sessionId: string, columns: number, rows: number): void;
      closeTerminal(sessionId: string): void;
      onTerminalData(callback: (payload: TerminalDataPayload) => void): () => void;
      onTerminalExit(callback: (payload: TerminalExitPayload) => void): () => void;
    };
  }
}
