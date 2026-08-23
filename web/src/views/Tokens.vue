<template>
  <div>
    <el-card shadow="never">
      <div class="toolbar">
        <div>
          <el-select v-if="auth.isAdmin" v-model="userId" placeholder="按用户筛选" clearable class="w-200" @change="load">
            <el-option v-for="u in users" :key="u.id" :label="`${u.username} (${u.id})`" :value="u.id" />
          </el-select>
        </div>
        <el-button type="primary" @click="openCreate">新建令牌</el-button>
      </div>

      <el-table :data="tokens" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column label="名称" min-width="150">
          <template #default="{ row }">{{ row.username ? `${row.username} / ` : '' }}{{ row.name }}</template>
        </el-table-column>
        <el-table-column label="属主" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.username" size="small" type="info">{{ row.username }}</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="额度上限" width="110">
          <template #default="{ row }">{{ row.quota_limit || '不限' }}</template>
        </el-table-column>
        <el-table-column label="已用" width="100">
          <template #default="{ row }">{{ row.used_quota ?? '-' }}</template>
        </el-table-column>
        <el-table-column label="并发上限" width="100">
          <template #default="{ row }">{{ row.max_concurrency ?? 0 }}</template>
        </el-table-column>
        <el-table-column label="IP白名单" min-width="150">
          <template #default="{ row }">
            <span v-if="!row.allowed_ips || !row.allowed_ips.length">不限</span>
            <el-tag v-for="ip in row.allowed_ips" :key="ip" size="small" class="ip-tag">{{ ip }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="160" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openUpdate(row)">编辑</el-button>
            <el-button v-if="row.status === 'active'" link type="warning" @click="toggleStatus(row, 'disabled')">停用</el-button>
            <el-button v-else link type="success" @click="toggleStatus(row, 'active')">启用</el-button>
            <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialog.visible" :title="dialog.isEdit ? '编辑令牌' : '新建令牌'" width="520px" :close-on-click-modal="false">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="令牌名称" />
        </el-form-item>
        <el-form-item v-if="!dialog.isEdit" label="额度上限" prop="quotaLimit">
          <el-input-number v-model="form.quotaLimit" :min="0" placeholder="留空不限" style="width: 100%" />
          <div class="tip">留空或 0 表示不限制令牌总消耗上限</div>
        </el-form-item>
        <el-form-item v-if="!dialog.isEdit" label="并发上限" prop="maxConcurrency">
          <el-input-number v-model="form.maxConcurrency" :min="0" style="width: 100%" />
          <div class="tip">0 表示不限制并发</div>
        </el-form-item>
        <el-form-item label="IP白名单">
          <el-select v-model="form.allowedIps" multiple filterable allow-create default-first-option :reserve-keyword="false" placeholder="输入IP后回车，留空表示不限制" style="width: 100%">
            <el-option v-for="ip in form.allowedIps" :key="ip" :label="ip" :value="ip" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="keyVisible" title="令牌创建成功" width="560px" :close-on-click-modal="false">
      <el-alert type="success" :closable="false" class="key-alert" title="请立即复制保存明文 API Key，关闭后将无法再次查看！" />
      <div class="api-key">{{ createdKey }}</div>
      <template #footer>
        <el-button type="primary" @click="copyKey">复制 API Key</el-button>
        <el-button @click="keyVisible = false">我已保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { list, create, update, remove } from '../api/tokens'
import { list as listUsers } from '../api/users'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const tokens = ref([])
const users = ref([])
const userId = ref(null)
const loading = ref(false)
const submitting = ref(false)
const keyVisible = ref(false)
const createdKey = ref('')
const formRef = ref()

const dialog = reactive({ visible: false, isEdit: false, id: null })
const form = reactive({
  name: '',
  quotaLimit: null,
  maxConcurrency: 0,
  allowedIps: []
})

const rules = {
  name: [{ required: true, message: '请输入令牌名称', trigger: 'blur' }]
}

async function load() {
  loading.value = true
  try {
    const data = await list({ userId: userId.value || undefined })
    tokens.value = Array.isArray(data) ? data : data.items || data.records || []
  } finally {
    loading.value = false
  }
}

async function loadUsers() {
  if (!auth.isAdmin) return
  const data = await listUsers({ page: 1, size: 1000 })
  users.value = data.items || data.records || data.list || []
}

function resetForm() {
  form.name = ''
  form.quotaLimit = null
  form.maxConcurrency = 0
  form.allowedIps = []
}

function openCreate() {
  resetForm()
  dialog.isEdit = false
  dialog.visible = true
}

function openUpdate(row) {
  resetForm()
  dialog.isEdit = true
  dialog.id = row.id
  form.name = row.name
  form.allowedIps = row.allowed_ips || []
  dialog.visible = true
}

async function submit() {
  await formRef.value.validate()
  submitting.value = true
  try {
    const payload = {
      name: form.name,
      allowed_ips: form.allowedIps || []
    }
    if (!dialog.isEdit) {
      if (form.quotaLimit) payload.quota_limit = form.quotaLimit
      if (form.maxConcurrency) payload.max_concurrency = form.maxConcurrency
      const data = await create(payload)
      if (data && (data.api_key || data.key)) {
        createdKey.value = data.api_key || data.key
        keyVisible.value = true
      } else {
        ElMessage.success('创建成功')
      }
    } else {
      await update(dialog.id, { name: form.name, allowed_ips: form.allowedIps })
      ElMessage.success('更新成功')
    }
    dialog.visible = false
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

async function handleDelete(row) {
  await ElMessageBox.confirm(`确定删除令牌「${row.name}」吗？`, '提示', { type: 'warning' })
  await remove(row.id)
  ElMessage.success('删除成功')
  load()
}

async function copyKey() {
  try {
    await navigator.clipboard.writeText(createdKey.value)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.warning('复制失败，请手动复制')
  }
}

function handleCloseKey() {
  keyVisible.value = false
}

onMounted(() => {
  load()
  loadUsers()
})
</script>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  margin-bottom: 14px;
}
.w-200 { width: 200px; }
.ip-tag { margin-right: 4px; }
.tip {
  color: #909399;
  font-size: 12px;
  line-height: 1.4;
  margin-top: 2px;
}
.key-alert {
  margin-bottom: 16px;
}
.api-key {
  background: #f5f7fa;
  border: 1px dashed #c0c4cc;
  border-radius: 4px;
  padding: 12px;
  font-family: monospace;
  font-size: 14px;
  word-break: break-all;
  user-select: all;
}
</style>
