<template>
  <div class="page">
    <div class="page-header">
      <div class="page-title">我的案例</div>
      <el-button type="primary" @click="$router.push('/ai-generate')">
        <el-icon class="mr-4"><Plus /></el-icon>新建案例
      </el-button>
    </div>

    <div class="card">
      <el-radio-group v-model="statusFilter" class="status-filter" @change="reload">
        <el-radio-button value="">全部</el-radio-button>
        <el-radio-button v-for="s in REVIEW_STATUSES" :key="s" :value="s">{{ s }}</el-radio-button>
      </el-radio-group>

      <el-table v-loading="loading" :data="list" stripe>
        <el-table-column label="案例标题" min-width="220">
          <template #default="{ row }">
            <span>{{ row.title || '（未命名草稿）' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="案例分类" prop="category" width="110" align="center" />
        <el-table-column label="最近更新" width="160" align="center">
          <template #default="{ row }">{{ row.updateTime || row.submitTime }}</template>
        </el-table-column>
        <el-table-column label="状态" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="260" fixed="right" align="center">
          <template #default="{ row }">
            <el-button
              v-if="row.status === '草稿' || row.status === '需补充' || row.status === '审核驳回'"
              size="small"
              @click="openEdit(row)"
            >编辑</el-button>
            <el-button
              v-if="row.status === '草稿' || row.status === '需补充' || row.status === '审核驳回'"
              size="small"
              type="primary"
              plain
              @click="submitCase(row)"
            >提交审核</el-button>
            <el-button
              v-if="row.status !== '草稿'"
              size="small"
              @click="viewOpinion(row)"
            >查看意见</el-button>
            <el-button
              v-if="row.status === '草稿'"
              size="small"
              type="danger"
              plain
              @click="removeDraft(row)"
            >删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !list.length" description="暂无案例" class="mt-24" />
      <div class="pagination">
        <el-pagination
          background
          layout="total, prev, pager, next"
          :total="total"
          :page-size="form.size"
          :current-page="form.page"
          @current-change="pageChange"
        />
      </div>
    </div>

    <!-- 编辑案例 -->
    <el-dialog v-model="editVisible" title="编辑案例" width="820px" top="6vh" destroy-on-close>
      <ManualUploadForm :initial="editData" @submitted="onEdited" @saved="onEdited" />
    </el-dialog>

    <!-- 审核意见 -->
    <el-dialog v-model="opinionVisible" title="审核意见" width="480px">
      <el-descriptions :column="1" border size="small">
        <el-descriptions-item label="当前状态">{{ opinion.status }}</el-descriptions-item>
        <el-descriptions-item label="审核人">{{ opinion.reviewer }}</el-descriptions-item>
        <el-descriptions-item label="时间">{{ opinion.time }}</el-descriptions-item>
      </el-descriptions>
      <div class="opinion-body">{{ opinion.opinion || '暂无审核意见' }}</div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import {
  getMyCasesApi,
  submitCaseApi,
  deleteDraftApi,
  getReviewOpinionApi,
} from '@/api'
import { REVIEW_STATUSES } from '@/api/constants'
import ManualUploadForm from '@/components/ManualUploadForm.vue'

const list = ref([])
const total = ref(0)
const loading = ref(false)
const statusFilter = ref('')
const form = reactive({ page: 1, size: 10 })

const statusTypeMap = {
  草稿: 'info',
  待审核: 'warning',
  需补充: 'warning',
  审核驳回: 'danger',
  已发布: 'success',
  已下线: 'info',
}
const statusType = (s) => statusTypeMap[s] || 'info'

async function fetchList() {
  loading.value = true
  try {
    const res = await getMyCasesApi({ page: form.page, size: form.size, status: statusFilter.value || undefined })
    if (res.code === 0) {
      list.value = res.data.records
      total.value = res.data.total
    }
  } finally {
    loading.value = false
  }
}
function reload() {
  form.page = 1
  fetchList()
}
function pageChange(p) {
  form.page = p
  fetchList()
}

// 编辑
const editVisible = ref(false)
const editData = ref(null)
function openEdit(row) {
  editData.value = { ...row }
  editVisible.value = true
}
function onEdited() {
  editVisible.value = false
  fetchList()
}

// 提交审核
async function submitCase(row) {
  try {
    await ElMessageBox.confirm(`确认提交「${row.title || '未命名草稿'}」进入审核？`, '提示', { type: 'warning' })
  } catch {
    return
  }
  const res = await submitCaseApi(row)
  if (res.code === 0) {
    ElMessage.success(res.message || '已提交审核')
    fetchList()
  } else {
    ElMessage.error(res.message)
  }
}

// 删除草稿
async function removeDraft(row) {
  try {
    await ElMessageBox.confirm('确定删除该草稿吗？', '提示', { type: 'warning' })
  } catch {
    return
  }
  const res = await deleteDraftApi(row.id)
  if (res.code === 0) {
    ElMessage.success(res.message || '已删除')
    fetchList()
  } else {
    ElMessage.error(res.message)
  }
}

// 查看审核意见
const opinionVisible = ref(false)
const opinion = ref({})
async function viewOpinion(row) {
  const res = await getReviewOpinionApi(row.id)
  if (res.code === 0) {
    opinion.value = res.data
    opinionVisible.value = true
  }
}

onMounted(fetchList)
</script>

<style scoped>
.mr-4 {
  margin-right: 4px;
}
.status-filter {
  margin-bottom: 16px;
}
.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
.opinion-body {
  margin-top: 16px;
  padding: 12px 16px;
  background: #fafbfc;
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.8;
  color: #303133;
}
</style>
