/** 纯函数工具，不依赖 Vue 或 Vite，便于 Node 直接冒烟。 */

/** 收敛分页参数：page 至少 1，size 默认 10、上限 100。 */
export function normalizePage(params = {}) {
  const page = Math.max(1, Number(params.page) || 1)
  const rawSize = Number(params.size) || 10
  const size = Math.min(Math.max(1, rawSize), 100)
  return { ...params, page, size }
}
