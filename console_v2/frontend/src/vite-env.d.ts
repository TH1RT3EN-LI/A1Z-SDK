/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_A1Z_DEVELOPMENT_MODE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
