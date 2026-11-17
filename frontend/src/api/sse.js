/** SSE 流式请求解析。
 *
 * 不走 axios，因为 axios 浏览器端不支持逐步读取响应体；这里用 fetch +
 * ReadableStream 按 `event:` / `data:` 解析后端事件，并转换为现有回调。
 */

const API_PREFIX = '/api/v1'

function parseEvent(raw) {
  let event = 'message'
  let data = ''
  for (const line of raw.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) data += line.slice(5).trim()
  }
  return { event, data }
}

export async function streamSSE(url, body, { onEvent, onChunk } = {}) {
  const token = localStorage.getItem('token')
  const response = await fetch(`${API_PREFIX}${url}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body || {}),
  })

  if (!response.ok) {
    const error = new Error(`请求失败（HTTP ${response.status}）`)
    error.status = response.status
    throw error
  }
  if (!response.body) throw new Error('当前浏览器不支持流式响应')

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  let accumulated = ''
  const result = {
    data: null,
    content: '',
    evaluation: null,
    references: [],
    drafts: [],
    recordId: null,
    answer: '',
  }

  const handle = ({ event, data }) => {
    if (!data) return
    let payload
    try {
      payload = JSON.parse(data)
    } catch {
      return
    }

    if (event === 'progress') {
      onEvent && onEvent({
        type: 'progress',
        message: payload.message || '',
        step: payload.index,
        total: payload.total,
      })
    } else if (event === 'content') {
      accumulated += payload.delta || ''
      result.content = accumulated
      onChunk && onChunk(payload.delta || '', accumulated)
    } else if (event === 'references') {
      result.references = payload.items || []
    } else if (event === 'evaluation') {
      result.evaluation = payload
    } else if (event === 'done') {
      result.data = payload.data || null
      result.evaluation = payload.evaluation || result.evaluation
      result.drafts = payload.drafts || []
      result.references = payload.references || result.references
      result.recordId = payload.record_id || null
      result.answer = payload.answer || accumulated
    } else if (event === 'error') {
      const error = new Error(payload.message || 'AI 服务暂不可用')
      error.code = payload.code
      throw error
    }
  }

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let index = buffer.indexOf('\n\n')
    while (index >= 0) {
      const raw = buffer.slice(0, index)
      buffer = buffer.slice(index + 2)
      handle(parseEvent(raw))
      index = buffer.indexOf('\n\n')
    }
  }

  return result
}
