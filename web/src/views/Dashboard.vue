<template>
  <div class="dashboard">
    <el-card class="filter-card" shadow="never">
      <div class="filter-row">
        <span class="label">时间范围</span>
        <el-date-picker
          v-model="range"
          type="datetimerange"
          range-separator="至"
          start-placeholder="开始时间"
          end-placeholder="结束时间"
          :shortcuts="shortcuts"
          @change="loadAll"
        />
        <template v-if="auth.isAdmin">
          <span class="label">用户</span>
          <el-select v-model="userFilter" placeholder="全部用户（总览）" clearable filterable class="w-180" @change="loadAll">
            <el-option v-for="u in users" :key="u.id" :label="`${u.username} (${u.id})`" :value="u.id" />
          </el-select>
        </template>
        <el-button type="primary" :loading="loading" @click="loadAll">刷新</el-button>
      </div>
    </el-card>

    <el-row :gutter="16" class="stat-row">
      <el-col :span="6" v-for="card in cards" :key="card.key">
        <el-card shadow="hover">
          <div class="stat-card">
            <div class="stat-label">{{ card.label }}</div>
            <div class="stat-value">{{ card.value }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="chart-row">
      <el-col :span="16">
        <el-card shadow="never" header="请求量与 Token 趋势">
          <div ref="trendRef" class="chart"></div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never" header="响应延迟 P50/P95/P99">
          <div ref="latencyRef" class="chart"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="chart-row">
      <el-col :span="16">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>用量分布</span>
              <el-radio-group v-model="by" size="small" @change="loadDistribution">
                <el-radio-button value="model">模型</el-radio-button>
                <el-radio-button value="token">令牌</el-radio-button>
                <el-radio-button v-if="auth.isAdmin" value="user">用户</el-radio-button>
              </el-radio-group>
            </div>
          </template>
          <div ref="distRef" class="chart"></div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, reactive, ref } from 'vue'
import * as echarts from 'echarts'
import { overview, trend, latency, distribution } from '../api/stats'
import { list as listUsers } from '../api/users'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const users = ref([])
const userFilter = ref(null)
const range = ref(defaultRange())
const loading = ref(false)
const by = ref('model')
const overviewData = ref({})
const trendData = ref([])
const latencyData = ref({})
const distributionData = ref([])

const trendRef = ref()
const latencyRef = ref()
const distRef = ref()
let trendChart, latencyChart, distChart

const shortcuts = [
  { text: '近24小时', value: () => { const e = new Date(); const s = new Date(e.getTime() - 24 * 3600 * 1000); return [s, e] } },
  { text: '近7天', value: () => { const e = new Date(); const s = new Date(e.getTime() - 7 * 24 * 3600 * 1000); return [s, e] } },
  { text: '近30天', value: () => { const e = new Date(); const s = new Date(e.getTime() - 30 * 24 * 3600 * 1000); return [s, e] } }
]

function defaultRange() {
  const end = new Date()
  const start = new Date(end.getTime() - 7 * 24 * 3600 * 1000)
  return [start, end]
}

function params() {
  const [from, to] = range.value || []
  const p = {
    from: from ? from.toISOString() : undefined,
    to: to ? to.toISOString() : undefined
  }
  if (auth.isAdmin && userFilter.value) {
    p.userId = userFilter.value
  }
  return p
}

const cards = computed(() => [
  // 剩余配额是实时余额（/api/auth/me），不要与统计口径混淆
  { key: 'quota', label: '剩余配额', value: auth.user?.quota ?? '-' },
  { key: 'requests', label: '请求数', value: overviewData.value.requests ?? '-' },
  { key: 'tokens', label: '总 Token', value: overviewData.value.total_tokens ?? '-' },
  { key: 'latency', label: '平均延迟 (ms)', value: overviewData.value.avg_latency_ms ?? '-' }
])

async function loadAll() {
  loading.value = true
  try {
    await Promise.all([auth.fetchMe().catch(() => {}), loadOverview(), loadTrend(), loadLatency()])
  } finally {
    loading.value = false
  }
}

async function loadOverview() {
  overviewData.value = await overview(params())
}

async function loadTrend() {
  trendData.value = await trend({ ...params(), granularity: 'hour' })
  renderTrend()
}

async function loadLatency() {
  latencyData.value = await latency(params())
  renderLatency()
}

async function loadDistribution() {
  distributionData.value = await distribution({ ...params(), by: by.value })
  renderDistribution()
}

function renderTrend() {
  if (!trendChart) return
  const d = trendData.value || {}
  const labels = Array.isArray(d.labels) ? d.labels : []
  const requests = Array.isArray(d.requests) ? d.requests : []
  const tokens = Array.isArray(d.tokens) ? d.tokens : []
  trendChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['请求量', 'Token'] },
    grid: { left: 50, right: 60, top: 40, bottom: 30 },
    xAxis: { type: 'category', data: labels.map((l) => String(l).slice(0, 13)) },
    yAxis: [
      { type: 'value', name: '请求量' },
      { type: 'value', name: 'Token' }
    ],
    series: [
      { name: '请求量', type: 'line', smooth: true, areaStyle: {}, data: requests },
      { name: 'Token', type: 'line', yAxisIndex: 1, smooth: true, areaStyle: {}, data: tokens }
    ]
  })
}

function renderLatency() {
  if (!latencyChart) return
  const d = latencyData.value || {}
  latencyChart.setOption({
    tooltip: {},
    grid: { left: 46, right: 16, top: 24, bottom: 36 },
    xAxis: { type: 'category', data: ['P50', 'P95', 'P99'], axisTick: { alignWithLabel: true } },
    yAxis: { type: 'value', name: 'ms', scale: true },
    series: [
      {
        type: 'bar',
        barWidth: 36,
        data: [
          { name: 'P50', value: d.p50 ?? 0 },
          { name: 'P95', value: d.p95 ?? 0 },
          { name: 'P99', value: d.p99 ?? 0 }
        ],
        itemStyle: { color: '#409eff', borderRadius: [4, 4, 0, 0] },
        label: { show: true, position: 'top', fontSize: 12 }
      }
    ]
  })
}

function renderDistribution() {
  if (!distChart) return
  const data = Array.isArray(distributionData.value) ? distributionData.value : []
  distChart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { orient: 'horizontal', bottom: 0, left: 10, right: 10, type: 'scroll', textStyle: { fontSize: 12 } },
    series: [
      {
        type: 'pie',
        radius: ['30%', '46%'],
        center: ['50%', '46%'],
        minAngle: 3,
        data: data.map((d) => ({ name: d.name ?? d.key ?? '-', value: d.value ?? d.total_tokens ?? 0 })),
        label: { show: false },
        labelLine: { show: false },
        emphasis: { label: { show: true, formatter: '{b}\n{c} ({d}%)', fontSize: 12, lineHeight: 15 }, itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0,0,0,0.5)' } }
      }
    ]
  })
}

function resizeCharts() {
  trendChart?.resize()
  latencyChart?.resize()
  distChart?.resize()
}

onMounted(() => {
  trendChart = echarts.init(trendRef.value)
  latencyChart = echarts.init(latencyRef.value)
  distChart = echarts.init(distRef.value)
  window.addEventListener('resize', resizeCharts)
  loadAll()
  loadDistribution()
  if (auth.isAdmin) {
    listUsers({ page: 1, size: 1000 }).then((data) => {
      users.value = (data && (data.items || data.records || data.list)) || []
    })
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeCharts)
  trendChart?.dispose()
  latencyChart?.dispose()
  distChart?.dispose()
})
</script>

<style scoped>
.filter-card {
  margin-bottom: 20px;
}
.filter-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.label {
  color: #606266;
  white-space: nowrap;
}
.stat-row {
  margin-bottom: 20px;
}
.stat-card {
  padding: 2px 4px;
}
.stat-label {
  color: #909399;
  font-size: 13px;
}
.stat-value {
  font-size: 26px;
  font-weight: 600;
  margin-top: 6px;
  color: #303133;
  line-height: 1.2;
}
.chart-row {
  margin-bottom: 20px;
}
.chart {
  height: 380px;
}
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.w-180 {
  width: 180px;
}
</style>
