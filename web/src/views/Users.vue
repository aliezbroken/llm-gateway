<template>
  <div>
    <el-card shadow="never">
      <div class="toolbar">
        <div class="filters">
          <el-input v-model="query.keyword" placeholder="用户名搜索" clearable class="w-180" @change="handleSearch" />
          <el-select v-model="query.role" placeholder="角色" clearable class="w-120" @change="handleSearch">
            <el-option label="管理员" value="admin" />
            <el-option label="普通用户" value="user" />
          </el-select>
          <el-select v-model="query.status" placeholder="状态" clearable class="w-120" @change="handleSearch">
            <el-option label="启用" value="active" />
            <el-option label="停用" value="disabled" />
          </el-select>
          <el-button type="primary" @click="handleSearch">查询</el-button>
        </div>
        <el-button type="primary" @click="openCreate">新增用户</el-button>
      </div>

      <el-table :data="users" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="username" label="用户名" min-width="120" />
        <el-table-column label="角色" width="100">
          <template #default="{ row }">
            <el-tag :type="row.role === 'admin' ? 'danger' : 'primary'" size="small">{{ row.role }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="quota" label="配额余额" width="100" />
        <el-table-column prop="consumed" label="已用额度" width="100">
          <template #default="{ row }">{{ row.consumed ?? 0 }}</template>
        </el-table-column>
        <el-table-column prop="request_count" label="请求数" width="90">
          <template #default="{ row }">{{ row.request_count ?? 0 }}</template>
        </el-table-column>
        <el-table-column label="并发上限" width="100">
          <template #default="{ row }">{{ row.max_concurrency ?? 0 }}</template>
        </el-table-column>
        <el-table-column prop="remark" label="备注" min-width="150" show-overflow-tooltip />
        <el-table-column prop="created_at" label="创建时间" width="160" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openQuota(row)">配额</el-button>
            <el-button v-if="expanded[row.id]" link type="primary" @click="openConcurrency(row)">并发</el-button>
            <el-button v-if="expanded[row.id]" link type="info" @click="openLedger(row)">流水</el-button>
            <el-button v-if="row.status === 'active' && expanded[row.id]" link type="warning" @click="toggleStatus(row, 'disabled')">停用</el-button>
            <el-button v-else-if="expanded[row.id]" link type="success" @click="toggleStatus(row, 'active')">启用</el-button>
            <el-button v-if="expanded[row.id]" link type="danger" @click="handleDelete(row)">删除</el-button>
            <el-button link type="primary" @click="toggleExpand(row)">
              {{ expanded[row.id] ? '收起' : '更多' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="size"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @change="load"
        />
      </div>
    </el-card>

    <el-dialog v-model="createVisible" title="新增用户" width="480px" :close-on-click-modal="false">
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-width="90px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="createForm.username" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="createForm.password" type="password" show-password />
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-select v-model="createForm.role" style="width: 100%">
            <el-option label="普通用户" value="user" />
            <el-option label="管理员" value="admin" />
          </el-select>
        </el-form-item>
        <el-form-item label="初始额度" prop="quota">
          <el-input-number v-model="createForm.quota" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="并发上限">
          <el-input-number v-model="createForm.maxConcurrency" :min="0" style="width: 100%" />
          <div class="tip">0 表示不限制该用户下所有令牌的总并发</div>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="createForm.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitCreate">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="concurrencyVisible" title="设置并发上限" width="420px" :close-on-click-modal="false">
      <el-form label-width="120px">
        <el-form-item label="用户">{{ currentUser?.username }}</el-form-item>
        <el-form-item label="用户级并发上限">
          <el-input-number v-model="concurrencyForm.maxConcurrency" :min="0" style="width: 100%" />
          <div class="tip">0 表示不限制；该用户下所有令牌共享此并发配额</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="concurrencyVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitConcurrency">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="quotaVisible" title="发放配额" width="440px" :close-on-click-modal="false">
      <el-form ref="quotaFormRef" :model="quotaForm" :rules="quotaRules" label-width="90px">
        <el-form-item label="用户">{{ currentUser?.username }}</el-form-item>
        <el-form-item label="当前余额">{{ currentUser?.quota }}</el-form-item>
        <el-form-item label="配额增减" prop="delta">
          <el-input-number v-model="quotaForm.delta" :step="100" style="width: 100%" />
          <div class="tip">正数增加、负数扣减</div>
        </el-form-item>
        <el-form-item label="原因" prop="reason">
          <el-input v-model="quotaForm.reason" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="quotaVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitQuota">发放</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="ledgerVisible" :title="`配额流水 - ${currentUser?.username}`" size="560px">
      <el-table :data="ledgerData" v-loading="ledgerLoading" size="small">
        <el-table-column prop="ts" label="时间" width="160" />
        <el-table-column prop="delta" label="变动" width="80">
          <template #default="{ row }">
            <span :style="{ color: row.delta >= 0 ? '#67c23a' : '#f56c6c' }">{{ row.delta >= 0 ? '+' : '' }}{{ row.delta }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="balance_after" label="余额" width="80" />
        <el-table-column prop="operator_id" label="操作者" width="80" />
        <el-table-column prop="reason" label="原因" min-width="120" show-overflow-tooltip />
      </el-table>
      <div class="pagination">
        <el-pagination
          v-model:current-page="ledgerPage"
          v-model:page-size="ledgerSize"
          :total="ledgerTotal"
          layout="total, prev, pager, next"
          @change="loadLedger"
        />
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { list, create, update, remove, grantQuota, ledger } from '../api/users'

const users = ref([])
const total = ref(0)
const page = ref(1)
const size = ref(20)
const loading = ref(false)
const submitting = ref(false)
const expanded = reactive({})
const createVisible = ref(false)
const createFormRef = ref()
const concurrencyVisible = ref(false)
const concurrencyForm = reactive({ maxConcurrency: 0 })
const quotaVisible = ref(false)
const quotaFormRef = ref()
const currentUser = ref(null)
const ledgerVisible = ref(false)
const ledgerData = ref([])
const ledgerTotal = ref(0)
const ledgerPage = ref(1)
const ledgerSize = ref(20)
const ledgerLoading = ref(false)

const query = reactive({ keyword: '', role: '', status: '' })

const createForm = reactive({ username: '', password: '', role: 'user', quota: 0, maxConcurrency: 0, remark: '' })
const createRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

const quotaForm = reactive({ delta: 0, reason: '' })
const quotaRules = {
  reason: [{ required: true, message: '请输入原因', trigger: 'blur' }]
}

function buildParams() {
  return {
    page: page.value,
    size: size.value,
    keyword: query.keyword || undefined,
    role: query.role || undefined,
    status: query.status || undefined
  }
}

async function load() {
  loading.value = true
  try {
    const data = await list(buildParams())
    users.value = data.items || data.records || data.list || []
    total.value = data.total ?? users.value.length
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  load()
}

function openCreate() {
  Object.assign(createForm, { username: '', password: '', role: 'user', quota: 0, maxConcurrency: 0, remark: '' })
  createVisible.value = true
}

async function submitCreate() {
  await createFormRef.value.validate()
  submitting.value = true
  try {
    await create({
      username: createForm.username,
      password: createForm.password,
      role: createForm.role,
      quota: createForm.quota,
      max_concurrency: createForm.maxConcurrency,
      remark: createForm.remark
    })
    ElMessage.success('创建成功')
    createVisible.value = false
    load()
  } finally {
    submitting.value = false
  }
}

function openConcurrency(row) {
  currentUser.value = row
  concurrencyForm.maxConcurrency = row.max_concurrency ?? 0
  concurrencyVisible.value = true
}

async function submitConcurrency() {
  submitting.value = true
  try {
    await update(currentUser.value.id, { max_concurrency: concurrencyForm.maxConcurrency })
    ElMessage.success('已更新')
    concurrencyVisible.value = false
    load()
  } finally {
    submitting.value = false
  }
}

async function toggleStatus(row, status) {
  await update(row.id, { status })
  ElMessage.success(status === 'active' ? '已启用' : '已停用')
  load()
}

function toggleExpand(row) {
  expanded[row.id] = !expanded[row.id]
}

async function handleDelete(row) {
  await ElMessageBox.confirm(`确定删除用户「${row.username}」吗？其名下令牌将级联停用。`, '提示', { type: 'warning' })
  await remove(row.id)
  ElMessage.success('删除成功')
  load()
}

function openQuota(row) {
  currentUser.value = row
  quotaForm.delta = 0
  quotaForm.reason = ''
  quotaVisible.value = true
}

async function submitQuota() {
  await quotaFormRef.value.validate()
  submitting.value = true
  try {
    await grantQuota(currentUser.value.id, { delta: quotaForm.delta, reason: quotaForm.reason })
    ElMessage.success('发放成功')
    quotaVisible.value = false
    load()
  } finally {
    submitting.value = false
  }
}

function openLedger(row) {
  currentUser.value = row
  ledgerPage.value = 1
  ledgerVisible.value = true
  loadLedger()
}

async function loadLedger() {
  ledgerLoading.value = true
  try {
    const data = await ledger(currentUser.value.id, { page: ledgerPage.value, size: ledgerSize.value })
    ledgerData.value = data.items || data.records || data.list || []
    ledgerTotal.value = data.total ?? ledgerData.value.length
  } finally {
    ledgerLoading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  margin-bottom: 14px;
}
.filters {
  display: flex;
  gap: 10px;
}
.w-180 { width: 180px; }
.w-120 { width: 120px; }
.pagination {
  margin-top: 14px;
  display: flex;
  justify-content: flex-end;
}
.tip {
  color: #909399;
  font-size: 12px;
  margin-top: 2px;
}
</style>
