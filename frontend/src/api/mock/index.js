/**
 * API 函数层 —— Mock 实现，函数与《需求规格文档 V1.0》§6 接口清单端点一一对应
 *
 * 案例字段与筛选逻辑对齐 docs/prompt_generate_v2.txt 字段规范。
 * 每个函数顶部注释了真实后端端点，联调时把函数体替换为 request.js 的调用即可。
 * 全局返回结构（V1.0 §6.1）：{ code, message, data }，code=0 为成功；
 * 分页 data 为 { records, total, page, size }；接口前缀 /api/v1
 */
import {
  delay,
  deepClone,
  now,
  todayCompact,
  CASE_CATEGORIES,
  REVIEW_STATUSES,
  IDEOLOGICAL_TAGS,
  PROFESSIONS,
  mockUsers,
  mockCases,
  getFavorites,
  toggleFavorite,
  mockAiRecords,
  mockAskRecords,
  mockSubmits,
  mockStats,
  mockHomeIndex,
  mockProfessions,
  mockAuditLogs,
} from '../mockData.js'

// ============ 统一返回包装（V1.0 §6.1：{ code, message, data }，code=0 为成功） ============
export function mockResponse(data, code = 0, message = 'success') {
  return { code, message, data }
}

async function mock({ data, code = 0, message = 'success', delayMs = 300 }) {
  await delay(delayMs)
  return mockResponse(data, code, message)
}

function findUser(username) {
  return mockUsers.find((u) => u.username === username)
}

function currentUser() {
  try {
    return JSON.parse(localStorage.getItem('userInfo') || 'null')
  } catch {
    return null
  }
}

/** 思政标签列表（可被管理页增删，初始为规范 V1.0 §5.5 的 18 个） */
let tagList = IDEOLOGICAL_TAGS.map((name, i) => ({ id: i + 1, name, useCount: 0, status: 1, createTime: '2026-08-01' }))

// ============ 操作记录 / 审计日志（FR-07） ============
function addAuditLog(action, target, detail) {
  const u = currentUser()
  mockAuditLogs.unshift({
    id: Date.now(),
    operator: u ? u.nickName || u.username : '系统',
    username: u ? u.username : 'system',
    action,
    target,
    detail,
    time: now(),
  })
}

function nextCaseId() {
  let max = 0
  for (const c of mockCases) {
    const num = Number(String(c.id).replace('case_', ''))
    if (num > max) max = num
  }
  return 'case_' + String(max + 1).padStart(3, '0')
}

// ============ 模块1：登录与用户信息 ============

// POST /api/v1/auth/login
export async function loginApi({ username, password, role }) {
  const user = mockUsers.find(
    (u) => u.username === username && u.password === password && u.role === role
  )
  if (!user) {
    return mock({ code: 400, message: '账号、密码或角色不匹配', data: null, delayMs: 500 })
  }
  if (user.status === 1) {
    return mock({ code: 400, message: '该账号已被冻结，请联系管理员', data: null, delayMs: 500 })
  }
  return mock({
    delayMs: 600,
    data: {
      token: `mock-token-${user.id}-${Date.now()}`,
      username: user.username,
      role: user.role,
      avatar: user.avatar,
    },
  })
}

// POST /api/v1/auth/logout
export async function logoutApi() {
  return mock({ data: null, delayMs: 200 })
}

// GET /api/v1/users/me
export async function getUserInfoApi() {
  const info = currentUser()
  if (!info) return mock({ code: 401, message: '未登录', data: null })
  const user = findUser(info.username)
  if (!user) return mock({ code: 401, message: '用户不存在', data: null })
  return mock({
    data: {
      username: user.username,
      role: user.role,
      avatar: user.avatar,
      nickName: user.nickName,
      phone: user.phone,
      intro: user.intro,
    },
  })
}

// PATCH /api/v1/users/me  body: nickName/phone/intro/avatar
export async function updateUserInfoApi(payload) {
  const info = currentUser()
  if (!info) return mock({ code: 401, message: '未登录', data: null })
  const user = findUser(info.username)
  if (!user) return mock({ code: 401, message: '用户不存在', data: null })
  Object.assign(user, {
    nickName: payload.nickName ?? user.nickName,
    phone: payload.phone ?? user.phone,
    intro: payload.intro ?? user.intro,
    avatar: payload.avatar ?? user.avatar,
  })
  const updated = {
    username: user.username,
    role: user.role,
    avatar: user.avatar,
    nickName: user.nickName,
    phone: user.phone,
    intro: user.intro,
  }
  localStorage.setItem('userInfo', JSON.stringify(updated))
  return mock({ data: updated })
}

// PUT /api/v1/users/me/password  body: oldPwd/newPwd
export async function changePasswordApi({ oldPwd, newPwd }) {
  const info = currentUser()
  if (!info) return mock({ code: 401, message: '未登录', data: null })
  const user = findUser(info.username)
  if (!user) return mock({ code: 401, message: '用户不存在', data: null })
  if (user.password !== oldPwd) return mock({ code: 400, message: '原密码不正确', data: null })
  user.password = newPwd
  return mock({ data: null, message: '密码修改成功' })
}

// ============ 模块2：案例浏览、检索、收藏 ============

/**
 * GET /api/v1/cases
 * query: keyword / category / profession / tag(思政标签) / page / size / sort
 * 公开列表默认只返回 review_status === '已发布' 的案例
 */
export async function getCaseListApi({
  keyword = '',
  category,
  profession,
  tag,
  page = 1,
  size = 9,
  sort = 'new',
  includeAll = false,
  status,
} = {}) {
  let list = mockCases.filter((c) => includeAll || c.review_status === '已发布')
  if (status) list = list.filter((c) => c.review_status === status)

  if (keyword) {
    const kw = keyword.toLowerCase()
    list = list.filter(
      (c) =>
        c.title.toLowerCase().includes(kw) ||
        c.keywords.some((k) => k.toLowerCase().includes(kw)) ||
        c.profession.some((p) => p.toLowerCase().includes(kw)) ||
        c.teaching_value.includes(keyword) ||
        c.content.includes(keyword)
    )
  }
  if (category) list = list.filter((c) => c.category === category)
  if (profession) list = list.filter((c) => c.profession.includes(profession))
  if (tag) list = list.filter((c) => c.ideological_elements.includes(tag))

  if (sort === 'views') {
    list = [...list].sort((a, b) => b.views - a.views)
  } else {
    list = [...list].sort((a, b) => b.publish_date.localeCompare(a.publish_date))
  }

  const total = list.length
  const start = (page - 1) * size
  const records = list.slice(start, start + size).map((c) => {
    const user = currentUser()
    if (user) c.isFavorite = getFavorites(user.username).includes(c.id)
    return c
  })
  return mock({ data: { total, records, page: Number(page), size: Number(size) } })
}

// GET /api/v1/cases/{id}
export async function getCaseDetailApi(id) {
  const c = mockCases.find((item) => item.id === String(id))
  if (!c) return mock({ code: 404, message: '案例不存在', data: null })
  const user = currentUser()
  const detail = deepClone(c)
  if (user) detail.isFavorite = getFavorites(user.username).includes(detail.id)
  return mock({ data: detail })
}

// POST /api/v1/cases/{id}/favorite  body: caseId
export async function addFavoriteApi(caseId) {
  const user = currentUser()
  if (!user) return mock({ code: 401, message: '未登录', data: null })
  toggleFavorite(user.username, String(caseId))
  return mock({ data: { caseId, favorited: true }, message: '收藏成功' })
}

// DELETE /api/v1/cases/{id}/favorite
export async function removeFavoriteApi(caseId) {
  const user = currentUser()
  if (!user) return mock({ code: 401, message: '未登录', data: null })
  toggleFavorite(user.username, String(caseId))
  return mock({ data: { caseId, favorited: false }, message: '已取消收藏' })
}

// GET /api/v1/users/me/favorites  query: page/size
export async function getFavoriteListApi({ page = 1, size = 9 } = {}) {
  const user = currentUser()
  if (!user) return mock({ code: 401, message: '未登录', data: null })
  const ids = getFavorites(user.username)
  let list = mockCases.filter((c) => ids.includes(c.id))
  const total = list.length
  const start = (page - 1) * size
  const records = list.slice(start, start + size).map((c) => ({ ...c, isFavorite: true }))
  return mock({ data: { total, records, page: Number(page), size: Number(size) } })
}

// ============ 模块3：AI 案例生成（SSE 流式） ============

/**
 * 按 prompt_generate_v2 规范拼装生成内容
 * 输出结构：id/title/source/source_url/publish_date/collect_date/version/category/
 *           review_status/background/content/process/result/profession/keywords/
 *           professional_knowledge/ideological_elements/teaching_value
 */
function buildGeneratedCase({ ideologicalDirection, topic, profession, length, variant = 0 }) {
  const base = { short: 2, medium: 4, long: 6 }[length] || 3
  const paraCount = Math.max(2, base + (variant - 1))
  const professionName = Array.isArray(profession) && profession.length ? profession[0] : '相关专业'
  const angles = ['教学环节', '实践任务', '研讨活动', '项目驱动', '案例分析', '反思总结']
  const angle = angles[variant % angles.length]
  const paras = []
  for (let i = 1; i <= paraCount; i++) {
    paras.push(
      `在第${i}阶段，围绕"${topic}"这一主题，教学团队以${angle}为载体，将专业知识点与"${ideologicalDirection}"有机融合，设计递进式教学环节，引导学生在分析问题、解决问题的过程中，内化价值认同，实现知识传授与价值塑造的同向同行。`
    )
  }
  const background =
    `本案例面向${professionName}领域，聚焦专业知识点"${topic}"，结合当前经济社会发展中的鲜活实践，挖掘其中蕴含的思政元素，使专业教学与价值引领深度融合。`
  const process = paras.join('\n')
  const result =
    `通过本案例教学，学生能够运用专业知识分析现实问题，深化对"${ideologicalDirection}"的理解与认同，达到"润物细无声"的育人效果。`
  const teachingValue =
    `适用于${professionName}等相关专业课程。结合"${topic}"知识点，引导学生思考${ideologicalDirection}的时代价值与实践路径，发挥课程思政育人作用。`
  // 主方向外再补充 2 个思政标签
  const extraTags = IDEOLOGICAL_TAGS.filter((t) => t !== ideologicalDirection).slice(0, 2)

  return {
    id: 'case_' + String(Math.floor(Math.random() * 9000) + 1000),
    title: `基于"${ideologicalDirection}"的${professionName}教学案例`,
    source: 'AI生成',
    sourceType: 'AI生成',
    source_url: '',
    publish_date: todayCompact(),
    collect_date: todayCompact(),
    version: 'V1.0',
    category: '行业案例',
    review_status: '草稿', // V1.0 §3.3.4：AI 生成结果先存为草稿，再提交审核
    background,
    content: 'https://case.example.com/files/generated.pdf',
    process,
    result,
    profession: Array.isArray(profession) && profession.length ? profession : ['软件工程'],
    keywords: [topic, '课程思政', '教学案例'],
    professional_knowledge: [topic],
    ideological_elements: [ideologicalDirection, ...extraTags],
    teaching_value: teachingValue,
  }
}

/**
 * 辅助评价：对候选稿按既定维度评分（V1.0 §3.7、FR-37/38）
 * 分稿数与评分维度为服务端配置，不向用户暴露。
 */
function evaluateDraft(draft, variant) {
  const dimensions = [
    { name: '思政相关性', score: 80 + ((variant * 7) % 18) },
    { name: '内容质量', score: 78 + ((variant * 11) % 20) },
    { name: '结构完整', score: 82 + ((variant * 5) % 15) },
    { name: '语言表达', score: 76 + ((variant * 13) % 22) },
  ]
  const totalScore = Math.round(dimensions.reduce((s, d) => s + d.score, 0) / dimensions.length)
  const suggestions = [
    '建议补充原文来源链接，增强可追溯性。',
    `可进一步结合"${draft.professional_knowledge[0] || '专业知识点'}"细化实施过程。`,
    '教学价值部分可补充具体课程与学情说明。',
  ]
  return {
    totalScore,
    dimensions,
    suggestions,
    issue: totalScore >= 88 ? '整体质量良好' : '部分字段可进一步充实',
  }
}

// POST /api/v1/ai/generate  body: ideological/knowledge/profession
// SSE 流式：先推送过程事件（分稿进度 / 评分中），确定最优稿后流式返回其正文（V1.0 FR-29 / §3.7 / FR-37/38）
export async function generateCaseStreamApi(params, { onChunk, onEvent } = {}) {
  const { ideological, knowledge, profession } = params
  if (!ideological || !knowledge) {
    return mock({ code: 400, message: '请选择思政方向并填写知识点', data: null })
  }
  const ideologicalDirection = ideological
  const emit = (payload) => onEvent && onEvent(payload)
  const draftCount = 3

  // 内部多稿生成（分稿数不向用户暴露）
  const drafts = []
  for (let i = 0; i < draftCount; i++) {
    emit({ type: 'progress', message: `正在生成候选案例（${i + 1}/${draftCount}）…`, step: i + 1, total: draftCount })
    await delay(350 + Math.floor(Math.random() * 300))
    const draft = buildGeneratedCase({ ideologicalDirection, topic: knowledge, profession, length: 'medium', variant: i })
    drafts.push({ index: i + 1, case: draft, evaluation: evaluateDraft(draft, i) })
  }

  // 逐稿评分并择优
  emit({ type: 'progress', message: 'AI 辅助评价中，正在择优…', step: draftCount, total: draftCount })
  await delay(500)
  const best = drafts.reduce((a, b) => (b.evaluation.totalScore > a.evaluation.totalScore ? b : a))
  const generated = best.case

  // 从案例库选取相关案例作为参考（体现"基于案例库已有案例生成"）
  const references = mockCases
    .filter(
      (c) =>
        c.review_status === '已发布' &&
        (c.ideological_elements.includes(ideologicalDirection) || c.category === generated.category)
    )
    .slice(0, 3)
    .map((c) => ({ id: c.id, title: c.title, category: c.category, sourceType: c.sourceType }))

  const refLine = references.length
    ? `【参考案例】基于案例库已有案例生成，参考：${references.map((r) => r.title).join('、')}`
    : ''
  const text = [
    `【案例标题】${generated.title}`,
    '',
    `【案例背景】${generated.background}`,
    '',
    `【思政切入点】${generated.ideological_elements.join('、')}`,
    '',
    `【案例正文】`,
    generated.process,
    '',
    `【教学成效】${generated.result}`,
    '',
    `【配套思考题】1. 结合本案例，谈谈你对"${knowledge}"中蕴含思政价值的理解；2. 请从专业角度分析这一思政导向在同类场景中的迁移应用。`,
    refLine,
  ]
    .filter((l) => l !== '')
    .join('\n')

  emit({ type: 'progress', message: '已确定最优稿，正在输出正文…', step: draftCount, total: draftCount })

  // 按 2~4 个字符切成小块，模拟流式
  const segments = []
  for (let i = 0; i < text.length; ) {
    const step = 2 + Math.floor(Math.random() * 3)
    segments.push(text.slice(i, i + step))
    i += step
  }

  let received = ''
  for (const seg of segments) {
    await delay(30 + Math.floor(Math.random() * 60))
    received += seg
    if (onChunk) onChunk(seg, received)
  }

  // 后端自动存储生成记录（含辅助评价与分稿得分，V1.0 FR-32）
  const user = currentUser()
  const record = {
    id: Date.now(),
    username: user ? user.username : 'guest',
    createTime: now(),
    category: generated.category,
    topic: knowledge,
    ideological_direction: ideologicalDirection,
    profession: generated.profession,
    contentPreview: generated.process.slice(0, 120) + '……',
    content: text,
    publish_date: generated.publish_date,
    version: generated.version,
    evaluation: best.evaluation,
    draftCount,
    drafts: drafts.map((d) => ({ index: d.index, totalScore: d.evaluation.totalScore })),
    generatedData: generated,
  }
  mockAiRecords.unshift(record)

  return mockResponse(
    {
      id: record.id,
      content: text,
      data: generated,
      references,
      evaluation: best.evaluation,
      drafts: record.drafts,
    },
    0,
    '生成完成'
  )
}

// GET /api/v1/ai/records  query: page/size
export async function getAiRecordListApi({ page = 1, size = 10 } = {}) {
  const user = currentUser()
  if (!user) return mock({ code: 401, message: '未登录', data: null })
  const list = mockAiRecords.filter((r) => r.username === user.username)
  const total = list.length
  const start = (page - 1) * size
  const records = list.slice(start, start + size)
  return mock({ data: { total, records, page: Number(page), size: Number(size) } })
}

// GET /api/v1/ai/records/{id}
export async function getAiRecordApi(id) {
  const rec = mockAiRecords.find((r) => r.id === Number(id))
  if (!rec) return mock({ code: 404, message: '记录不存在', data: null })
  return mock({ data: rec })
}

// DELETE /api/v1/ai/records/{id}
export async function deleteAiRecordApi(id) {
  const idx = mockAiRecords.findIndex((r) => r.id === Number(id))
  if (idx >= 0) mockAiRecords.splice(idx, 1)
  return mock({ data: null, message: '删除成功' })
}

// POST /api/v1/ai/ask/{caseId}  body: question （SSE 流式问答，基于传入案例上下文）
// 说明：前端基于当前查看/生成的案例组织上下文，后端据此回答；mock 用分段回调模拟打字机。
export async function chatAskApi(caseData, question, { onChunk } = {}) {
  if (!question || !question.trim()) {
    return mock({ code: 400, message: '请输入问题', data: null })
  }
  const c = caseData || {}
  const answer = [
    `关于「${c.title || '该案例'}」的解答：`,
    ``,
    `案例背景：${c.background || '（暂无背景信息）'}`,
    ``,
    `实施过程要点：${c.process || '（暂无过程信息）'}`,
    ``,
    `最终成效：${c.result || '（暂无结果信息）'}`,
    ``,
    `针对您的问题"${question}"，建议结合思政元素（${(c.ideological_elements || []).join('、') || '无'}）与专业知识点（${(c.professional_knowledge || []).join('、') || '无'}）思考，并参考教学价值（${c.teaching_value || '无'}）进行延伸分析。`,
  ].join('\n')

  const segments = []
  for (let i = 0; i < answer.length; ) {
    const step = 2 + Math.floor(Math.random() * 3)
    segments.push(answer.slice(i, i + step))
    i += step
  }
  let received = ''
  for (const seg of segments) {
    await delay(25 + Math.floor(Math.random() * 50))
    received += seg
    if (onChunk) onChunk(seg, received)
  }
  // 记录本人问答记录（FR-36）
  const au = currentUser()
  if (au) {
    mockAskRecords.unshift({
      id: Date.now(),
      username: au.username,
      caseId: c.id || '',
      caseTitle: c.title || '',
      question,
      answer: received,
      createTime: now(),
    })
  }
  return mockResponse({ answer: received }, 0, '回答完成')
}

// ============ 模块4：案例生产与提交审核（教师工作区） ============

// 把表单数据规整为案例记录字段
function normalizeCaseFields(data) {
  return {
    title: data.title || '',
    source: data.source || '教师投稿',
    category: data.category || '',
    profession: data.profession || [],
    keywords: data.keywords || [],
    professional_knowledge: data.professional_knowledge || [],
    ideological_elements: data.ideological_elements || [],
    teaching_value: data.teaching_value || '',
    background: data.background || '',
    process: data.process || '',
    result: data.result || '',
    content: data.content || '',
  }
}

// POST /api/v1/cases  （新建/保存案例草稿，FR-20/21）
export async function saveDraftApi(data) {
  const user = currentUser()
  if (!user) return mock({ code: 401, message: '未登录', data: null })
  if (data.id) {
    const rec = mockSubmits.find((s) => s.id === Number(data.id) && s.username === user.username)
    if (!rec) return mock({ code: 404, message: '案例不存在', data: null })
    Object.assign(rec, normalizeCaseFields(data), { id: rec.id, status: '草稿', updateTime: now() })
    return mock({ data: rec, message: '草稿已保存' })
  }
  const record = {
    id: Date.now(),
    username: user.username,
    submitterName: user.nickName,
    ...normalizeCaseFields(data),
    status: '草稿',
    submitTime: now(),
    rejectReason: '',
  }
  mockSubmits.unshift(record)
  return mock({ data: record, message: '草稿已保存' })
}

// POST /api/v1/cases/{id}/submit  （提交审核，FR-23；无 id 则新建后提交）
export async function submitCaseApi(data) {
  const user = currentUser()
  if (!user) return mock({ code: 401, message: '未登录', data: null })
  if (!data.title || !data.category) {
    return mock({ code: 400, message: '请填写标题与案例分类', data: null })
  }
  if (data.id) {
    const rec = mockSubmits.find((s) => s.id === Number(data.id) && s.username === user.username)
    if (!rec) return mock({ code: 404, message: '案例不存在', data: null })
    Object.assign(rec, normalizeCaseFields(data), { id: rec.id, status: '待审核', submitTime: now(), rejectReason: '' })
    return mock({ data: { submitId: rec.id, status: '待审核' }, message: '提交成功，等待审核' })
  }
  const record = {
    id: Date.now(),
    username: user.username,
    submitterName: user.nickName,
    ...normalizeCaseFields(data),
    status: '待审核',
    submitTime: now(),
    rejectReason: '',
  }
  mockSubmits.unshift(record)
  return mock({ data: { submitId: record.id, status: '待审核' }, message: '提交成功，等待审核' })
}

// GET /api/v1/users/me/cases  （本人全部案例，各状态，FR-24）
export async function getMyCasesApi({ page = 1, size = 10, status } = {}) {
  const user = currentUser()
  if (!user) return mock({ code: 401, message: '未登录', data: null })
  let list = mockSubmits.filter((s) => s.username === user.username)
  if (status) list = list.filter((s) => s.status === status)
  const total = list.length
  const start = (page - 1) * size
  return mock({ data: { total, records: list.slice(start, start + size), page: Number(page), size: Number(size) } })
}

// 兼容旧调用
export const getSubmitListApi = getMyCasesApi

// DELETE /api/v1/cases/{id}  （删除本人草稿，仅草稿可删，FR-26）
export async function deleteDraftApi(id) {
  const user = currentUser()
  if (!user) return mock({ code: 401, message: '未登录', data: null })
  const idx = mockSubmits.findIndex((s) => s.id === Number(id) && s.username === user.username)
  if (idx < 0) return mock({ code: 404, message: '案例不存在', data: null })
  if (mockSubmits[idx].status !== '草稿') return mock({ code: 400, message: '仅「草稿」状态的案例可删除', data: null })
  mockSubmits.splice(idx, 1)
  return mock({ data: null, message: '已删除' })
}

// GET /api/v1/cases/{id}/review  （查看审核结果与意见，FR-25）
export async function getReviewOpinionApi(id) {
  const user = currentUser()
  if (!user) return mock({ code: 401, message: '未登录', data: null })
  const rec = mockSubmits.find((s) => s.id === Number(id) && s.username === user.username)
  if (!rec) return mock({ code: 404, message: '案例不存在', data: null })
  return mock({
    data: {
      status: rec.status,
      opinion: rec.rejectReason || '',
      reviewer: '管理员',
      time: rec.updateTime || rec.submitTime,
    },
  })
}

// POST /api/v1/cases/parse  （上传原文并抽取候选字段，FR-22）
export async function parseCaseApi(text) {
  const user = currentUser()
  if (!user) return mock({ code: 401, message: '未登录', data: null })
  const raw = String(text || '').trim()
  if (!raw) return mock({ code: 400, message: '文件内容为空', data: null })
  await delay(500)
  const firstLine = raw.split('\n').map((l) => l.trim()).find(Boolean) || '未命名案例'
  return mock({
    data: {
      title: firstLine.slice(0, 30),
      background: raw.slice(0, 120),
      process: raw.slice(120, 240),
      result: raw.slice(240, 360),
    },
    message: '已抽取候选字段，请核对补全',
  })
}

// GET /api/v1/users/me/ask-records  （本人问答记录，FR-36）
export async function getAskRecordsApi({ page = 1, size = 10 } = {}) {
  const user = currentUser()
  if (!user) return mock({ code: 401, message: '未登录', data: null })
  const list = mockAskRecords.filter((r) => r.username === user.username)
  const total = list.length
  const start = (page - 1) * size
  return mock({ data: { total, records: list.slice(start, start + size), page: Number(page), size: Number(size) } })
}

// ============ 模块5：管理员后台 ============

// 5.1 案例审核管理

// GET /api/v1/admin/reviews  query: page/size/status
export async function getReviewListApi({ page = 1, size = 10, status } = {}) {
  let list = deepClone(mockSubmits)
  if (status && status !== '') {
    list = list.filter((s) => s.status === status)
  }
  const total = list.length
  const start = (page - 1) * size
  const records = list.slice(start, start + size)
  return mock({ data: { total, records, page: Number(page), size: Number(size) } })
}

// POST /api/v1/admin/cases/{id}/review  body: status(已发布/需补充/审核驳回)/opinion
export async function reviewCaseApi({ caseSubmitId, status, rejectReason = '' }) {
  const rec = mockSubmits.find((s) => s.id === Number(caseSubmitId))
  if (!rec) return mock({ code: 404, message: '提交记录不存在', data: null })
  rec.status = status
  rec.rejectReason = rejectReason
  if (status === '已发布') {
    // 通过：并入案例库
    mockCases.push({
      id: nextCaseId(),
      title: rec.title,
      source: rec.source,
      source_url: '',
      publish_date: todayCompact(),
      collect_date: todayCompact(),
      version: 'V1.1',
      category: rec.category,
      review_status: '已发布',
      background: rec.background,
      content: rec.content,
      process: rec.process,
      result: rec.result,
      profession: rec.profession,
      keywords: rec.keywords,
      professional_knowledge: rec.professional_knowledge,
      ideological_elements: rec.ideological_elements,
      teaching_value: rec.teaching_value,
      isFavorite: false,
      views: 0,
      createTime: rec.submitTime,
      submitterName: rec.submitterName,
    })
  }
  addAuditLog(
    status === '已发布' ? '审核通过' : '审核' + status,
    `case_${rec.id}`,
    `${rec.title}｜${rejectReason || '无意见'}`
  )
  return mock({ data: { caseSubmitId, status: rec.status }, message: '操作成功' })
}

// PATCH /api/v1/admin/cases/{id}
export async function updateCaseApi(id, data) {
  const c = mockCases.find((item) => item.id === String(id))
  if (!c) return mock({ code: 404, message: '案例不存在', data: null })
  Object.assign(c, data, { id: c.id })
  return mock({ data: c, message: '更新成功' })
}

// DELETE /api/v1/admin/cases/{id}
export async function deleteCaseApi(id) {
  const idx = mockCases.findIndex((item) => item.id === String(id))
  if (idx >= 0) mockCases.splice(idx, 1)
  return mock({ data: null, message: '删除成功' })
}

// POST /api/v1/admin/cases/{id}/offline  body: reason —— 已发布案例下线（V1.0 §3.2.4 / FR-40）
export async function offlineCaseApi(id, reason = '') {
  const c = mockCases.find((item) => item.id === String(id))
  if (!c) return mock({ code: 404, message: '案例不存在', data: null })
  if (c.review_status !== '已发布') {
    return mock({ code: 400, message: '仅“已发布”案例可下线', data: null })
  }
  c.review_status = '已下线'
  c.offlineReason = reason
  addAuditLog('下线案例', c.id, `下线原因：${reason || '未填写'}`)
  return mock({ data: c, message: '已下线' })
}

// POST /api/v1/admin/cases/import  Form: Excel/CSV 文件流（mock 用 JSON/CSV 行）
export async function importCasesApi(rows) {
  let success = 0
  const fail = []
  for (const row of rows) {
    if (!row.title || !row.category) {
      fail.push(row.title || '(未命名)')
      continue
    }
    mockCases.push({
      id: nextCaseId(),
      title: row.title,
      source: row.source || '批量导入',
      source_url: row.source_url || '',
      publish_date: row.publish_date || todayCompact(),
      collect_date: todayCompact(),
      version: row.version || 'V1.1',
      category: row.category,
      review_status: '已发布',
      background: row.background || '',
      content: row.content || '',
      process: row.process || '',
      result: row.result || '',
      profession: Array.isArray(row.profession) ? row.profession : (row.profession ? String(row.profession).split('|') : []),
      keywords: Array.isArray(row.keywords) ? row.keywords : (row.keywords ? String(row.keywords).split('|') : []),
      professional_knowledge: row.professional_knowledge || [],
      ideological_elements: Array.isArray(row.ideological_elements) ? row.ideological_elements : (row.ideological_elements ? String(row.ideological_elements).split('|') : []),
      teaching_value: row.teaching_value || '',
      isFavorite: false,
      views: 0,
      createTime: now(),
      submitterName: '批量导入',
    })
    success++
  }
  return mock({ data: { success, fail }, message: `导入完成：成功 ${success} 条` })
}

// GET /api/v1/admin/cases/export  → 直接返回文件流（mock 用 CSV 下载）
export async function exportCasesApi() {
  const header = ['id', 'title', 'source', 'publish_date', 'category', 'review_status', 'profession', 'keywords', 'ideological_elements']
  const lines = mockCases
    .filter((c) => c.review_status === '已发布')
    .map((c) =>
      [
        c.id, c.title, c.source, c.publish_date, c.category, c.review_status,
        (c.profession || []).join('|'), (c.keywords || []).join('|'), (c.ideological_elements || []).join('|'),
      ].join(',')
    )
  const csv = '﻿' + [header.join(','), ...lines].join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `思政案例导出_${todayCompact()}.csv`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
  return mock({ data: null, message: `已导出 ${lines.length} 条案例` })
}

// 5.2 分类体系（思政标签）

// GET /api/v1/admin/tags  （思政标签）
export async function getTagListApi() {
  return mock({ data: deepClone(tagList) })
}
// POST /api/v1/admin/tags
export async function addTagApi(data) {
  const id = Math.max(...tagList.map((t) => t.id)) + 1
  tagList.push({ id, name: data.name, useCount: 0, createTime: now().slice(0, 10) })
  return mock({ data: tagList.find((t) => t.id === id), message: '新增成功' })
}
// PATCH /api/v1/admin/tags/{id}
export async function updateTagApi(id, data) {
  const t = tagList.find((item) => item.id === Number(id))
  if (!t) return mock({ code: 404, message: '标签不存在', data: null })
  Object.assign(t, data, { id: t.id })
  return mock({ data: t, message: '更新成功' })
}
// DELETE /api/v1/admin/tags/{id}
export async function deleteTagApi(id) {
  const idx = tagList.findIndex((item) => item.id === Number(id))
  if (idx >= 0) tagList.splice(idx, 1)
  return mock({ data: null, message: '删除成功' })
}

// 5.3 用户管理

// GET /api/v1/users  query: page/size/keyword/role
export async function getUserListApi({ page = 1, size = 10, keyword = '', role = '' } = {}) {
  let list = mockUsers
  if (keyword) list = list.filter((u) => u.username.includes(keyword) || u.nickName.includes(keyword))
  if (role) list = list.filter((u) => u.role === role)
  const total = list.length
  const start = (page - 1) * size
  const records = list.slice(start, start + size).map((u) => ({
    id: u.id,
    username: u.username,
    nickName: u.nickName,
    role: u.role,
    status: u.status,
    phone: u.phone,
    createTime: u.createTime,
  }))
  return mock({ data: { total, records, page: Number(page), size: Number(size) } })
}

const ROLE_NAMES = { student: '学生', teacher: '教师', admin: '管理员' }

// POST /api/v1/users  body: username/nickName/role/phone/intro —— 管理员创建账号（FR-06）
export async function createUserApi(data) {
  if (!data.username) return mock({ code: 400, message: '请填写登录名', data: null })
  if (mockUsers.some((u) => u.username === data.username)) {
    return mock({ code: 400, message: '登录名已存在', data: null })
  }
  const id = Math.max(0, ...mockUsers.map((u) => u.id)) + 1
  const user = {
    id,
    username: data.username,
    password: data.password || '123456',
    role: data.role || 'student',
    nickName: data.nickName || data.username,
    avatar: '',
    phone: data.phone || '',
    intro: data.intro || '',
    status: 0,
    createTime: todayCompact(),
  }
  mockUsers.push(user)
  addAuditLog('创建账号', user.username, `角色：${ROLE_NAMES[user.role] || user.role}`)
  return mock({ data: { id: user.id, username: user.username, initialPwd: user.password }, message: '账号已创建' })
}

// PATCH /api/v1/users/{id}  body: userId/role/status
export async function updateUserApi({ userId, role, status }) {
  const u = mockUsers.find((item) => item.id === Number(userId))
  if (!u) return mock({ code: 404, message: '用户不存在', data: null })
  if (role !== undefined && role !== u.role) {
    addAuditLog('调整角色', u.username, `角色：${ROLE_NAMES[u.role] || u.role} → ${ROLE_NAMES[role] || role}`)
    u.role = role
  }
  if (status !== undefined && Number(status) !== u.status) {
    const st = Number(status)
    addAuditLog(st === 1 ? '冻结账号' : '解冻账号', u.username, st === 1 ? '账号冻结，令牌失效' : '账号恢复')
    u.status = st
  }
  return mock({ data: u, message: '更新成功' })
}

// GET /api/v1/audit-logs  query: page/size —— 关键操作记录（FR-07）
export async function getAuditLogsApi({ page = 1, size = 10 } = {}) {
  const list = deepClone(mockAuditLogs)
  const total = list.length
  const start = (page - 1) * size
  const records = list.slice(start, start + size)
  return mock({ data: { total, records, page: Number(page), size: Number(size) } })
}

// ============ 专业字典（FR-43） ============
// GET /api/v1/admin/professions
export async function getProfessionListApi() {
  return mock({ data: deepClone(mockProfessions) })
}
// POST /api/v1/admin/professions  body: name
export async function addProfessionApi(data) {
  if (!data.name) return mock({ code: 400, message: '请填写专业名称', data: null })
  if (mockProfessions.some((p) => p.name === data.name)) {
    return mock({ code: 400, message: '该专业已存在', data: null })
  }
  const id = Math.max(0, ...mockProfessions.map((p) => p.id)) + 1
  const item = { id, name: data.name, caseCount: 0, status: 1, createTime: todayCompact() }
  mockProfessions.push(item)
  return mock({ data: item, message: '新增成功' })
}
// PATCH /api/v1/admin/professions/{id}  body: name/status
export async function updateProfessionApi(id, data) {
  const p = mockProfessions.find((item) => item.id === Number(id))
  if (!p) return mock({ code: 404, message: '专业不存在', data: null })
  Object.assign(p, data, { id: p.id })
  return mock({ data: p, message: '更新成功' })
}

// POST /api/v1/users/{id}/reset-password  body: userId
export async function resetUserPwdApi(userId) {
  const u = mockUsers.find((item) => item.id === Number(userId))
  if (!u) return mock({ code: 404, message: '用户不存在', data: null })
  u.password = '123456'
  addAuditLog('重置密码', u.username, '重置为初始密码')
  return mock({ data: { userId: u.id, initialPwd: '123456' }, message: '密码已重置为 123456' })
}

// 5.4 数据统计

// GET /api/v1/admin/statistics/home
export async function getStatisticsApi() {
  return mock({ data: deepClone(mockStats) })
}

// ============ 模块6：首页平台数据 ============

// GET /api/v1/home/index-data  （首页平台数据：案例总数、来源、标签、AI 生成量）
export async function getHomeIndexApi() {
  return mock({ data: deepClone(mockHomeIndex) })
}

