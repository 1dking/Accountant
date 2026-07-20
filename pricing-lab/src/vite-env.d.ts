/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_OBRAIN_ADMIN_TOKEN?: string
  readonly VITE_OBRAIN_API_BASE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
