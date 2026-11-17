/**
 * API 函数层 —— 真实后端请求实现。
 *
 * 函数名、参数与返回形状保持与旧 mock 版一致，页面不需要感知切换。
 * 设置 `VITE_USE_MOCK=true` 时回退到 `./mock/index.js`，便于演示兜底。
 */
import { get, post, put, patch, del } from './request.js'
import { streamSSE } from './sse.js'
import { normalizePage } from './utils.js'

const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'
let mockImpl = null

export function mockResponse(data, code = 0, message = 'success') {
  return { code, message, data }
}

async function withMock(name, args, call) {
  if (!USE_MOCK) return call()
  if (!mockImpl) mockImpl = await import('./mock/index.js')
  return mockImpl[name](...args)
}

// ============ 账号与权限 ============

export async function loginApi(form) {
  return withMock('loginApi', [form], () => post('/auth/login', form))
}

export async function logoutApi() {
  return withMock('logoutApi', [], () => post('/auth/logout'))
}

export async function getUserInfoApi() {
  return withMock('getUserInfoApi', [], () => get('/users/me'))
}

export async function updateUserInfoApi(payload) {
  return withMock('updateUserInfoApi', [payload], () => patch('/users/me', payload))
}

export async function changePasswordApi({ oldPwd, newPwd }) {
  return withMock('changePasswordApi', [{ oldPwd, newPwd }], () =>
    put('/users/me/password', { oldPwd, newPwd })
  )
}

export async function getUserListApi({ page = 1, size = 10, keyword = '', role = '' } = {}) {
  return withMock('getUserListApi', [{ page, size, keyword, role }], () =>
    get('/users', { page, size, keyword, role })
  )
}

export async function createUserApi(data) {
  return withMock('createUserApi', [data], () => post('/users', data))
}

export async function updateUserApi({ userId, role, status }) {
  return withMock('updateUserApi', [{ userId, role, status }], () =>
    patch(`/users/${userId}`, { role, status })
  )
}

export async function resetUserPwdApi(userId) {
  return withMock('resetUserPwdApi', [userId], () => post(`/users/${userId}/reset-password`))
}

export async function getAuditLogsApi({ page = 1, size = 10 } = {}) {
  return withMock('getAuditLogsApi', [{ page, size }], () => get('/audit-logs', { page, size }))
}

// ============ 案例检索、浏览与收藏 ============

export async function getCaseListApi(params = {}) {
  return withMock('getCaseListApi', [params], () => {
    const { page, size } = normalizePage({ page: params.page ?? 1, size: params.size ?? 9 })
    return get('/cases', { ...params, page, size })
  })
}

export async function getCaseDetailApi(id) {
  return withMock('getCaseDetailApi', [id], () => get(`/cases/${id}`))
}

export async function addFavoriteApi(caseId) {
  return withMock('addFavoriteApi', [caseId], () => post(`/cases/${caseId}/favorite`))
}

export async function removeFavoriteApi(caseId) {
  return withMock('removeFavoriteApi', [caseId], () => del(`/cases/${caseId}/favorite`))
}

export async function getFavoriteListApi({ page = 1, size = 9 } = {}) {
  return withMock('getFavoriteListApi', [{ page, size }], () =>
    get('/users/me/favorites', { page, size })
  )
}

// ============ AI 案例生成与问答 ============

export async function generateCaseStreamApi(params, callbacks = {}) {
  if (USE_MOCK) {
    if (!mockImpl) mockImpl = await import('./mock/index.js')
    return mockImpl.generateCaseStreamApi(params, callbacks)
  }

  const result = await streamSSE('/ai/generate', params, callbacks)
  return {
    code: 0,
    message: '生成完成',
    data: {
      id: result.recordId,
      content: result.content,
      data: result.data,
      references: result.references,
      evaluation: result.evaluation,
      drafts: result.drafts,
    },
  }
}

export async function getAiRecordListApi({ page = 1, size = 10 } = {}) {
  return withMock('getAiRecordListApi', [{ page, size }], () =>
    get('/ai/records', { page, size })
  )
}

export async function getAiRecordApi(id) {
  return withMock('getAiRecordApi', [id], () => get(`/ai/records/${id}`))
}

export async function deleteAiRecordApi(id) {
  return withMock('deleteAiRecordApi', [id], () => del(`/ai/records/${id}`))
}

export async function chatAskApi(caseData, question, callbacks = {}) {
  if (USE_MOCK) {
    if (!mockImpl) mockImpl = await import('./mock/index.js')
    return mockImpl.chatAskApi(caseData, question, callbacks)
  }

  const context = caseData || {}
  // 生成页的临时案例尚未入库，走 draft 上下文；已发布案例用真实编号以便落记录。
  const caseId = context.id && context.review_status !== '草稿' ? context.id : 'draft'
  const result = await streamSSE(`/ai/ask/${caseId}`, { question, caseContext: context }, callbacks)
  return { code: 0, message: '回答完成', data: { answer: result.answer } }
}

// ============ 案例生产（教师工作区） ============

export async function saveDraftApi(data) {
  return withMock('saveDraftApi', [data], () => post('/cases', data))
}

export async function submitCaseApi(data) {
  return withMock('submitCaseApi', [data], async () => {
    let caseId = data.id
    if (!caseId) {
      const created = await post('/cases', data)
      if (created.code !== 0) return created
      caseId = created.data.id
    }
    return post(`/cases/${caseId}/submit`)
  })
}

export async function getMyCasesApi({ page = 1, size = 10, status } = {}) {
  return withMock('getMyCasesApi', [{ page, size, status }], () =>
    get('/users/me/cases', { page, size, status })
  )
}

export const getSubmitListApi = getMyCasesApi

export async function deleteDraftApi(id) {
  return withMock('deleteDraftApi', [id], () => del(`/cases/${id}`))
}

export async function getReviewOpinionApi(id) {
  return withMock('getReviewOpinionApi', [id], () => get(`/cases/${id}/review`))
}

export async function parseCaseApi(text) {
  return withMock('parseCaseApi', [text], () => post('/cases/parse', { text }))
}

export async function getAskRecordsApi({ page = 1, size = 10 } = {}) {
  return withMock('getAskRecordsApi', [{ page, size }], () =>
    get('/users/me/ask-records', { page, size })
  )
}

// ============ 管理后台 ============

export async function getReviewListApi({ page = 1, size = 10, status } = {}) {
  return withMock('getReviewListApi', [{ page, size, status }], () =>
    get('/admin/reviews', { page, size, status })
  )
}

export async function reviewCaseApi({ caseSubmitId, status, rejectReason = '' }) {
  return withMock('reviewCaseApi', [{ caseSubmitId, status, rejectReason }], () =>
    post(`/admin/cases/${caseSubmitId}/review`, { status, opinion: rejectReason })
  )
}

export async function updateCaseApi(id, data) {
  return withMock('updateCaseApi', [id, data], () => patch(`/admin/cases/${id}`, data))
}

export async function deleteCaseApi(id) {
  return withMock('deleteCaseApi', [id], () => del(`/admin/cases/${id}`))
}

export async function offlineCaseApi(id, reason = '') {
  return withMock('offlineCaseApi', [id, reason], () =>
    post(`/admin/cases/${id}/offline`, { reason })
  )
}

export async function importCasesApi(rows) {
  return withMock('importCasesApi', [rows], () => post('/admin/cases/import', rows))
}

export async function exportCasesApi() {
  if (USE_MOCK) {
    if (!mockImpl) mockImpl = await import('./mock/index.js')
    return mockImpl.exportCasesApi()
  }

  const token = localStorage.getItem('token')
  const response = await fetch('/api/v1/admin/cases/export', {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!response.ok) throw new Error('导出失败')

  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `思政案例导出_${new Date().toISOString().slice(0, 10)}.csv`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
  return { code: 0, message: '已导出', data: null }
}

export async function getTagListApi() {
  return withMock('getTagListApi', [], () => get('/admin/tags'))
}

export async function addTagApi(data) {
  return withMock('addTagApi', [data], () => post('/admin/tags', data))
}

export async function updateTagApi(id, data) {
  return withMock('updateTagApi', [id, data], () => patch(`/admin/tags/${id}`, data))
}

export async function deleteTagApi(id) {
  return withMock('deleteTagApi', [id], () => del(`/admin/tags/${id}`))
}

export async function getProfessionListApi() {
  return withMock('getProfessionListApi', [], () => get('/admin/professions'))
}

export async function addProfessionApi(data) {
  return withMock('addProfessionApi', [data], () => post('/admin/professions', data))
}

export async function updateProfessionApi(id, data) {
  return withMock('updateProfessionApi', [id, data], () => patch(`/admin/professions/${id}`, data))
}

export async function getStatisticsApi() {
  return withMock('getStatisticsApi', [], () => get('/admin/statistics/home'))
}

// ============ 首页 ============

export async function getHomeIndexApi() {
  return withMock('getHomeIndexApi', [], () => get('/home/index-data'))
}
