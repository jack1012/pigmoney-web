// 版本資訊單一來源：UI 顯示與系統錯誤回報共用，避免兩邊各寫一份而失準。
// APP_VERSION 人工維護；BUILD_TIME 由 vite 於打包時注入，
// 用來確認線上跑的到底是哪一次 build（人工版本號忘了改時仍可判定）。
export const APP_VERSION = '2.2.0'
export const BUILD_TIME = typeof __BUILD_TIME__ === 'string' ? __BUILD_TIME__ : 'dev'
