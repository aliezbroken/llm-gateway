<template>
  <div>
    <el-card shadow="never">
      <template #header>
        <span>上游配置</span>
      </template>
      <el-form label-width="100px" style="max-width: 640px">
        <el-form-item label="上游地址">
          <el-input v-model="upstreamUrl" placeholder="http://127.0.0.1:8000" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="saving" @click="saveSettings">保存配置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <span>模型倍率</span>
      </template>
      <el-form label-width="100px">
        <el-form-item label="倍率配置">
          <el-input v-model="ratiosText" type="textarea" :rows="8" class="ratio-input" placeholder='{"gpt-4o":{"prompt":1,"completion":1}}' />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="saving" @click="saveSettings">保存倍率</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-header">
          <span>上游健康检查</span>
          <el-button size="small" :loading="healthLoading" @click="loadHealth">刷新</el-button>
        </div>
      </template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="状态">
          <el-tag :type="healthData.online ? 'success' : 'danger'">{{ healthData.online ? '在线' : '离线' }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="延迟">{{ healthData.latency_ms != null ? `${healthData.latency_ms} ms` : '-' }}</el-descriptions-item>
        <el-descriptions-item label="最近检查时间">{{ healthData.last_check || '-' }}</el-descriptions-item>
        <el-descriptions-item label="消息">{{ healthData.message || '-' }}</el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getSettings, updateSettings, health } from '../api/system'

const upstreamUrl = ref('')
const ratiosText = ref('')
const saving = ref(false)
const healthLoading = ref(false)
const healthData = ref({ online: false, latency_ms: null, last_check: '', message: '' })

async function loadSettings() {
  const data = (await getSettings()) || {}
  upstreamUrl.value = data.upstream_url || data.upstreamUrl || ''
  const ratios = data.model_ratios || data.ratios || {} 
  ratiosText.value = JSON.stringify(ratios, null, 2)
}

async function saveSettings() {
  let ratios
  try {
    ratios = ratiosText.value.trim() ? JSON.parse(ratiosText.value) : {}
  } catch {
    ElMessage.error('模型倍率不是合法的 JSON')
    return
  }
  saving.value = true
  try {
    await updateSettings({
      upstream_url: upstreamUrl.value,
      model_ratios: ratios
    })
    ElMessage.success('保存成功')
  } finally {
    saving.value = false
  }
}

async function loadHealth() {
  healthLoading.value = true
  try {
    healthData.value = (await health()) || {}
  } finally {
    healthLoading.value = false
  }
}

onMounted(() => {
  loadSettings()
  loadHealth()
})
</script>

<style scoped>
.ratio-input {
  font-family: monospace;
  width: 100%;
  max-width: 640px;
}
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
</style>
