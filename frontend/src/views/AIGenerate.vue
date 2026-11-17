<template>
  <div class="page ai-page">
    <div class="page-header">
      <div class="page-title">生成和上传案例</div>
      <el-button text type="primary" @click="$router.push('/ai-records')">
        <el-icon class="mr-4"><Document /></el-icon>我的生成记录
      </el-button>
    </div>

    <el-tabs v-model="activeTab" class="gen-tabs">
      <el-tab-pane label="AI 智能生成" name="ai">
        <div class="ai-layout">
      <!-- 左侧参数配置 -->
      <div class="config card">
        <el-form label-position="top">
          <el-form-item label="思政方向" required>
            <el-select v-model="form.ideological" placeholder="请选择思政标签" style="width: 100%">
              <el-option v-for="t in IDEOLOGICAL_TAGS" :key="t" :label="t" :value="t" />
            </el-select>
          </el-form-item>
          <el-form-item label="关键词" required>
            <el-input
              v-model="form.knowledge"
              type="textarea"
              :rows="4"
              placeholder="请输入关键词，例如：软件工程中的代码安全、网络安全"
            />
          </el-form-item>
          <el-form-item label="适用专业">
            <el-select
              v-model="form.profession"
              placeholder="选填，可多选"
              multiple
              filterable
              style="width: 100%"
            >
              <el-option v-for="p in PROFESSIONS" :key="p" :label="p" :value="p" />
            </el-select>
          </el-form-item>
          <el-button
            type="primary"
            size="large"
            class="generate-btn"
            :loading="generating"
            :disabled="!form.ideological || !form.knowledge"
            @click="handleGenerate"
          >
            <el-icon class="mr-4"><MagicStick /></el-icon>{{ generating ? '正在生成…' : '生成案例' }}
          </el-button>
        </el-form>
      </div>

      <!-- 右侧结果展示 -->
      <div class="result-col">
        <div class="result card">
          <div class="result-title">
            生成结果
            <template v-if="done">
              <el-tag size="small" type="success" effect="light">生成完成</el-tag>
            </template>
          </div>
          <div class="result-body">
            <div v-if="!resultText && !generating" class="placeholder">
              <el-icon :size="48" color="#c0c4cc"><DocumentAdd /></el-icon>
              <p>配置左侧参数后点击「生成案例」，AI 将流式生成专属思政案例</p>
            </div>
            <div v-else-if="!resultText && generating" class="placeholder">
              <el-icon :size="40" color="#409eff" class="is-loading"><Loading /></el-icon>
              <p>{{ progressText || '正在生成…' }}</p>
            </div>
            <div v-else class="stream-text" :class="{ typing: generating }">{{ resultText }}</div>
          </div>

          <!-- AI 辅助评价（V1.0 §3.7 / FR-38，非审核结论） -->
          <div v-if="done && evaluation" class="eval-section">
            <div class="eval-head">
              <span class="ref-title">AI 辅助评价</span>
              <el-tag size="small" type="warning" effect="light">仅供参考，非审核结论</el-tag>
            </div>
            <div class="eval-total">综合得分 <b>{{ evaluation.totalScore }}</b> 分 · {{ evaluation.issue }}</div>
            <div class="eval-dims">
              <div v-for="d in evaluation.dimensions" :key="d.name" class="eval-dim">
                <span class="eval-dim-name">{{ d.name }}</span>
                <el-progress :percentage="d.score" :stroke-width="8" style="flex: 1" />
              </div>
            </div>
            <ul class="eval-suggest">
              <li v-for="(s, i) in evaluation.suggestions" :key="i">{{ s }}</li>
            </ul>
            <div v-if="drafts.length" class="draft-scores">
              <span>候选稿得分：</span>
              <el-tag v-for="d in drafts" :key="d.index" size="small" effect="plain" class="mr-4">
                第{{ d.index }}稿 {{ d.totalScore }}分
              </el-tag>
            </div>
          </div>
          <div v-if="done" class="result-actions">
            <el-button @click="reGenerate">
              <el-icon class="mr-4"><Refresh /></el-icon>重新生成
            </el-button>
            <el-button @click="copyText">
              <el-icon class="mr-4"><CopyDocument /></el-icon>复制文本
            </el-button>
            <el-button @click="exportDoc">
              <el-icon class="mr-4"><Download /></el-icon>导出文档
            </el-button>
            <el-button @click="handleSaveDraft">
              <el-icon class="mr-4"><Document /></el-icon>保存草稿
            </el-button>
            <el-button type="primary" @click="submitVisible = true">
              <el-icon class="mr-4"><Upload /></el-icon>提交审核
            </el-button>
            <el-button type="primary" plain :icon="ChatDotRound" @click="showChat = !showChat">
              {{ showChat ? '关闭问答' : 'AI 问答' }}
            </el-button>
          </div>
        </div>

        <!-- 参考案例（基于案例库生成） -->
        <div v-if="references.length" class="ref-section">
          <div class="ref-title">本次生成参考了案例库中的案例</div>
          <div class="ref-list">
            <div v-for="r in references" :key="r.id" class="ref-card">
              <div class="ref-name clamp-1">{{ r.title }}</div>
              <el-tag size="small" type="primary" effect="light">{{ r.category }}</el-tag>
            </div>
          </div>
        </div>

        <!-- AI 问答 -->
        <AIChatPanel v-if="showChat && done" :title="generatedTitle" :case-data="generatedCase" />
      </div>
    </div>
    </el-tab-pane>

      <el-tab-pane label="手动输入" name="manual">
        <ManualUploadForm />
      </el-tab-pane>
    </el-tabs>

    <!-- 提交审核弹窗 -->
    <el-dialog v-model="submitVisible" title="提交案例审核" width="720px">
      <el-form ref="submitFormRef" :model="submitForm" :rules="submitRules" label-width="100px">
        <el-form-item label="案例标题" prop="title">
          <el-input v-model="submitForm.title" placeholder="请输入案例标题" />
        </el-form-item>
        <el-form-item label="案例分类" prop="category">
          <el-select v-model="submitForm.category" placeholder="请选择" style="width: 100%">
            <el-option v-for="c in CASE_CATEGORIES" :key="c" :label="c" :value="c" />
          </el-select>
        </el-form-item>
        <el-form-item label="适用专业">
          <el-select v-model="submitForm.profession" multiple filterable placeholder="选填" style="width: 100%">
            <el-option v-for="p in PROFESSIONS" :key="p" :label="p" :value="p" />
          </el-select>
        </el-form-item>
        <el-form-item label="思政元素">
          <el-select v-model="submitForm.ideological_elements" multiple filterable placeholder="选择思政标签" style="width: 100%">
            <el-option v-for="t in IDEOLOGICAL_TAGS" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="案例背景">
          <el-input v-model="submitForm.background" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="实施过程">
          <el-input v-model="submitForm.process" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="实施结果">
          <el-input v-model="submitForm.result" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="教学价值">
          <el-input v-model="submitForm.teaching_value" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="submitVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确认提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch, computed } from 'vue'
import { ChatDotRound, Loading } from '@element-plus/icons-vue'
import { generateCaseStreamApi, submitCaseApi, saveDraftApi } from '@/api'
import { CASE_CATEGORIES, PROFESSIONS, IDEOLOGICAL_TAGS } from '@/api/constants'
import { useAppStore } from '@/stores/app'
import { ElMessage } from 'element-plus'
import ManualUploadForm from '@/components/ManualUploadForm.vue'
import AIChatPanel from '@/components/AIChatPanel.vue'

const appStore = useAppStore()

const activeTab = ref('ai')

const generating = ref(false)
const done = ref(false)
const resultText = ref('')
const progressText = ref('')
const evaluation = ref(null)
const drafts = ref([])
const currentRecord = ref(null)
const references = ref([])
const generatedCase = ref(null)
const showChat = ref(false)
const generatedTitle = computed(() => (generatedCase.value?.title || 'AI 生成的案例'))

const form = reactive({
  ideological: '',
  knowledge: '',
  profession: [],
})

async function handleGenerate() {
  if (!form.ideological || !form.knowledge) {
    ElMessage.warning('请填写完整的生成参数')
    return
  }
  generating.value = true
  done.value = false
  resultText.value = ''
  progressText.value = ''
  evaluation.value = null
  drafts.value = []
  try {
    const res = await generateCaseStreamApi(form, {
      // 过程事件：分稿进度 / 评分中（V1.0 FR-29）
      onEvent: (e) => {
        if (e && e.message) progressText.value = e.message
      },
      onChunk: (seg, received) => {
        progressText.value = ''
        resultText.value = received
      },
    })
    if (res.code === 0) {
      currentRecord.value = { id: res.data.id, content: res.data.content }
      references.value = res.data.references || []
      generatedCase.value = res.data.data || null
      evaluation.value = res.data.evaluation || null
      drafts.value = res.data.drafts || []
      done.value = true
    } else {
      ElMessage.error(res.message)
    }
  } finally {
    generating.value = false
  }
}

function reGenerate() {
  resultText.value = ''
  done.value = false
  currentRecord.value = null
  handleGenerate()
}

async function copyText() {
  try {
    await navigator.clipboard.writeText(resultText.value)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败，请手动复制')
  }
}

function exportDoc() {
  const content = resultText.value
  const blob = new Blob(['﻿' + content], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `AI生成案例_${Date.now()}.md`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
  ElMessage.success('文档已导出')
}

// 提交审核
const submitVisible = ref(false)
const submitting = ref(false)
const submitFormRef = ref(null)
const submitForm = reactive({
  title: '',
  category: '',
  profession: [],
  ideological_elements: [],
  background: '',
  process: '',
  result: '',
  teaching_value: '',
})
const submitRules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  category: [{ required: true, message: '请选择案例分类', trigger: 'change' }],
}

function parseGeneratedContent(text) {
  const sections = {}
  const lines = text.split('\n')
  let current = ''
  for (const line of lines) {
    const m = line.match(/^【(.+?)】$/)
    if (m) {
      current = m[1]
      sections[current] = []
    } else if (current && line.trim()) {
      sections[current].push(line.trim())
    }
  }
  const join = (key) => (sections[key] || []).join('\n')
  const ideological = join('思政切入点')
    .split(/[、,，;；]/)
    .map((s) => s.trim())
    .filter((s) => IDEOLOGICAL_TAGS.includes(s))
  return {
    title: sections['案例标题']?.[0] || '',
    background: join('案例背景'),
    process: join('案例正文'),
    result: join('教学成效'),
    teaching_value: join('配套思考题'),
    ideological,
  }
}

function openSubmit() {
  const parsed = parseGeneratedContent(resultText.value)
  Object.assign(submitForm, {
    title: parsed.title,
    category: '行业案例',
    profession: [...form.profession],
    ideological_elements: parsed.ideological.length ? parsed.ideological : [form.ideological].filter(Boolean),
    background: parsed.background,
    process: parsed.process,
    result: parsed.result,
    teaching_value: parsed.teaching_value,
  })
}

// 生成结果另存为草稿（FR-31）
async function handleSaveDraft() {
  const parsed = parseGeneratedContent(resultText.value)
  const payload = {
    title: parsed.title,
    category: '行业案例',
    profession: [...form.profession],
    ideological_elements: parsed.ideological.length ? parsed.ideological : [form.ideological].filter(Boolean),
    background: parsed.background,
    process: parsed.process,
    result: parsed.result,
    teaching_value: parsed.teaching_value,
  }
  const res = await saveDraftApi(payload)
  if (res.code === 0) ElMessage.success(res.message || '草稿已保存')
  else ElMessage.error(res.message)
}

async function handleSubmit() {
  await submitFormRef.value.validate()
  submitting.value = true
  try {
    const res = await submitCaseApi(submitForm)
    if (res.code === 0) {
      ElMessage.success(res.message || '提交成功')
      submitVisible.value = false
    } else {
      ElMessage.error(res.message)
    }
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  // 详情弹窗/生成记录跳转时预填参数
  const pre = appStore.aiPrefill
  if (pre) {
    form.ideological = pre.ideological || ''
    form.knowledge = pre.knowledge || ''
    form.profession = pre.profession || []
    appStore.setAiPrefill(null)
  }
})

// 打开提交弹窗时预填
watch(submitVisible, (v) => {
  if (v) openSubmit()
})
</script>

<style scoped>
.mr-4 {
  margin-right: 4px;
}
.ai-layout {
  display: flex;
  gap: 20px;
  align-items: flex-start;
}
.config {
  width: 320px;
  flex-shrink: 0;
}
.index-radio {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.generate-btn {
  width: 100%;
}
.result-col {
  flex: 1;
  min-width: 0;
}
.ref-section {
  margin-top: 16px;
}
.ref-title {
  font-size: 14px;
  font-weight: 600;
  color: #606266;
  margin-bottom: 10px;
}
.ref-list {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.ref-card {
  flex: 0 0 200px;
  padding: 10px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: #fafbfc;
}
.ref-name {
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 6px;
}
.result-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 12px;
}
.result-body {
  min-height: 360px;
  background: #fafbfc;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 16px;
  position: relative;
}
.placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 320px;
  color: #c0c4cc;
  gap: 8px;
  text-align: center;
}
.stream-text {
  white-space: pre-wrap;
  font-size: 14px;
  line-height: 1.9;
  color: #303133;
  min-height: 320px;
}
.stream-text.typing::after {
  content: '▋';
  color: #409eff;
  animation: blink 1s step-end infinite;
}
@keyframes blink {
  50% {
    opacity: 0;
  }
}
.result-actions {
  display: flex;
  gap: 10px;
  margin-top: 16px;
  flex-wrap: wrap;
}
.eval-section {
  margin-top: 16px;
  padding: 14px 16px;
  border: 1px solid #faecd8;
  background: #fdf6ec;
  border-radius: 8px;
}
.eval-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.eval-total {
  font-size: 14px;
  color: #303133;
  margin-bottom: 10px;
}
.eval-total b {
  color: #e6a23c;
  font-size: 18px;
}
.eval-dims {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.eval-dim {
  display: flex;
  align-items: center;
  gap: 10px;
}
.eval-dim-name {
  width: 80px;
  font-size: 13px;
  color: #606266;
  flex-shrink: 0;
}
.eval-suggest {
  margin: 10px 0 0;
  padding-left: 18px;
  font-size: 13px;
  color: #606266;
  line-height: 1.8;
}
.draft-scores {
  margin-top: 8px;
  font-size: 13px;
  color: #909399;
}
.mr-4 {
  margin-right: 4px;
}
</style>
