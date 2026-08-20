<template>
  <div>
    <el-card shadow="never" class="filter-card">
      <div class="filter-row">
        <el-date-picker
          v-model="query.range"
          type="datetimerange"
          range-separator="至"
          start-placeholder="开始时间"
          end-placeholder="结束时间"
          size="default"
        />
        <el-input v-model="query.userId" placeholder="用户ID" clearable class="w-140" />
        <el-input v-model="query.tokenId" placeholder="令牌ID" clearable class="w-140" />
        <el-input v-model="query.model" placeholder="模型" clearable class="w-180" />
        <el-select v-model="query.status" placeholder="状态" clearable class="w-140">
          <el-option label="成功" value="ok" />
          <el-option label="拒绝" value="rejected" />
          <el-option label="上游错误" value="upstream_error" />
          <el-option label="配额不足" value="quota_blocked" />
        </el-select>
        <el-button type="primary" @click="handleSearch">查询</el-button>
        <el-button @click="handleReset">重置</el-button>
      </div>
    </el-card>

    <el-card shadow="never">
      <el-table :data="logs" v-loading="loading" stripe>
        <el-table-column prop="ts" label="时间" min-width="160" />
        <el-table-column prop="user_id" label="用户ID" width="100" />
        <el-table-column prop="token_name" label="令牌" min-width="120" show-overflow-tooltip />
        <el-table-column prop="client_ip" label="IP" width="130" />
        <el-table-column prop="model" label="模型" min-width="130" show-overflow-tooltip />
        <el-table-column label="Token" width="160">
          <template #default="{ row }">
            {{ row.prompt_tokens ?? 0 }}/{{ row.completion_tokens ?? 0 }}/{{ row.total_tokens ?? 0 }}
          </template>
        </el-table-column>
        <el-table-column prop="quota_cost" label="配额" width="90" />
        <el-table-column prop="latency_ms" label="延迟(ms)" width="90" />
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="showDetail(row)">详情</el-button>
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

    <el-drawer v-model="detailVisible" title="请求详情" size="480px">
      <el-descriptions :column="1" border v-if="detail">
        <el-descriptions-item label="时间">{{ detail.ts }}</el-descriptions-item>
        <el-descriptions-item label="用户ID">{{ detail.user_id }}</el-descriptions-item>
        <el-descriptions-item label="令牌">{{ detail.token_name }} ({{ detail.token_id }})</el-descriptions-item>
        <el-descriptions-item label="客户端IP">{{ detail.client_ip }}</el-descriptions-item>
        <el-descriptions-item label="模型">{{ detail.model }}</el-descriptions-item>
        <el-descriptions-item label="接口">{{ detail.endpoint }}</el-descriptions-item>
        <el-descriptions-item label="Prompt Tokens">{{ detail.prompt_tokens }}</el-descriptions-item>
        <el-descriptions-item label="Completion Tokens">{{ detail.completion_tokens }}</el-descriptions-item>
        <el-descriptions-item label="Total Tokens">{{ detail.total_tokens }}</el-descriptions-item>
        <el-descriptions-item label="配额消耗">{{ detail.quota_cost }}</el-descriptions-item>
        <el-descriptions-item label="延迟">{{ detail.latency_ms }} ms</el-descriptions-item>
        <el-descriptions-item label="状态">{{ detail.status }}</el-descriptions-item>
        <el-descriptions-item label="错误码">{{ detail.error_code || '-' }}</el-descriptions-item>
        <el-descriptions-item label="请求ID">{{ detail.request_id || '-' }}</el-descriptions-item>
      </el-descriptions>
    </el-drawer>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { list, get } from '../api/logs'

const logs = ref([])
const total = ref(0)
const page = ref(1)
const size = ref(20)
const loading = ref(false)
const detailVisible = ref(false)
const detail = ref(null)

const query = reactive({
  range: [],
  userId: '',
  tokenId: '',
  model: '',
  status: ''
})

function buildParams() {
  const [from, to] = query.range || []
  return {
    page: page.value,
    size: size.value,
    from: from ? from.toISOString() : undefined,
    to: to ? to.toISOString() : undefined,
    userId: query.userId || undefined,
    tokenId: query.tokenId || undefined,
    model: query.model || undefined,
    status: query.status || undefined
  }
}

function statusType(s) {
  if (s === 'ok') return 'success'
  if (s === 'rejected') return 'warning'
  if (s === 'upstream_error') return 'danger'
  if (s === 'quota_blocked') return 'info'
  return 'info'
}

async function load() {
  loading.value = true
  try {
    const data = await list(buildParams())
    logs.value = data.items || data.records || data.list || []
    total.value = data.total ?? logs.value.length
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  load()
}

function handleReset() {
  query.range = []
  query.userId = ''
  query.tokenId = ''
  query.model = ''
  query.status = ''
  page.value = 1
  load()
}

async function showDetail(row) {
  detail.value = await get(row.id)
  detailVisible.value = true
}

onMounted(load)
</script>

<style scoped>
.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.w-140 { width: 140px; }
.w-180 { width: 180px; }
.pagination {
  margin-top: 14px;
  display: flex;
  justify-content: flex-end;
}
</style>
