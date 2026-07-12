<template>
  <div>
    <h2 style="margin-bottom:20px;">设置</h2>

    <el-row :gutter="16">
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header><h3>登录管理</h3></template>
          <p style="color:#999;font-size:13px;margin-bottom:12px;">在浏览器中登录 BOSS 直聘，登录后 Cookie 自动保存。</p>
          <el-alert v-if="cookieVerifyMsg" :title="cookieVerifyMsg" :type="cookieValid ? 'success' : 'error'" :closable="false" style="margin-bottom:12px;" />
          <p style="color:#999;font-size:13px;margin-bottom:8px;">方式一：点击按钮扫码登录。方式二：用 EditThisCookie 插件导出 JSON，粘贴到下方。</p>
          <el-button type="primary" @click="doLogin" :loading="loggingIn">打开登录页面</el-button>
          <el-button @click="doVerify" :loading="verifying" style="margin-left:8px;">验证登录状态</el-button>
          <el-input v-model="cookieJson" type="textarea" :rows="4" placeholder="粘贴 EditThisCookie 导出的 JSON..." style="margin-top:12px;font-family:monospace;font-size:12px;" />
          <el-button :disabled="!cookieJson.trim()" @click="doImportCookies" style="margin-top:8px;">导入 Cookies</el-button>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card shadow="hover">
          <template #header><h3>数据同步</h3></template>
          <p style="color:#999;font-size:13px;margin-bottom:12px;">拉取最新的联系人和聊天记录</p>

          <div style="display:flex;align-items:center;gap:8px;margin-bottom:16px;font-size:14px;">
            <span>仅同步最近</span>
            <el-input-number v-model="syncDays" :min="0" :max="365" size="small" @change="saveConfig" />
            <span>天内的消息（0 = 全部）</span>
          </div>

          <div v-if="syncing" style="margin-bottom:16px;">
            <el-progress :percentage="progressPct" :stroke-width="8" :color="'#10b981'" />
            <p style="font-size:14px;margin-top:8px;color:#333;">{{ progressMsg }}</p>
            <p style="font-size:12px;color:#999;">{{ progressDetail }}</p>
          </div>

          <el-button type="primary" @click="doSync" :disabled="syncing" :loading="syncing">
            {{ syncing ? '同步中...' : '同步聊天记录' }}
          </el-button>

          <el-alert v-if="syncResult" type="success" :closable="false" style="margin-top:12px;">
            <template #title>
              同步完成 — 联系人: {{ syncResult.friends }} | 新消息: {{ syncResult.new_messages }}
              <template v-if="syncResult.skipped_bosses">| 超出范围已跳过: {{ syncResult.skipped_bosses }} 人</template>
            </template>
          </el-alert>
          <el-alert v-if="syncResult?.errors?.length" type="warning" :closable="false" style="margin-top:8px;" :title="syncResult.errors.join('; ')" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top:16px;">
      <el-col :span="12">
        <el-card shadow="hover" style="border:1px solid #fecaca;">
          <template #header><h3 style="color:#ef4444;">危险操作</h3></template>
          <p style="color:#999;font-size:13px;margin-bottom:12px;">删除所有投递记录和聊天消息，此操作不可撤销。</p>
          <el-button type="danger" @click="deleteAll">删除所有数据</el-button>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'

const cookieValid = ref(false)
const cookieVerifyMsg = ref('')
const verifying = ref(false)
const loggingIn = ref(false)
const cookieJson = ref('')
const syncing = ref(false)
const progressMsg = ref('')
const progressDetail = ref('')
const progressPct = ref(0)
const syncResult = ref(null)
const syncDays = ref(0)

onMounted(async () => {
  try {
    const cfg = await api.getConfig()
    syncDays.value = cfg.sync_days || 0
  } catch (e) { /* ignore */ }
})

async function doLogin() {
  loggingIn.value = true
  try {
    const r = await api.loginAndCapture()
    if (r.success) {
      cookieValid.value = true
      cookieVerifyMsg.value = '✅ 登录成功，Cookie 已自动保存'
    } else {
      cookieVerifyMsg.value = '❌ ' + r.message
    }
  } catch (e) {
    cookieVerifyMsg.value = '❌ ' + e.message
  } finally {
    loggingIn.value = false
  }
}

async function doImportCookies() {
  try {
    const r = await api.importCookies(cookieJson.value)
    if (r.ok) {
      cookieValid.value = true
      cookieVerifyMsg.value = `✅ 已导入 ${r.count} 个 Cookie`
      cookieJson.value = ''
    } else {
      cookieVerifyMsg.value = '❌ 导入失败'
    }
  } catch (e) {
    cookieVerifyMsg.value = '❌ 格式错误: ' + e.message
  }
}

async function saveConfig() {
  await api.updateConfig({ sync_days: syncDays.value || 0 })
}

async function doVerify() {
  verifying.value = true
  cookieVerifyMsg.value = ''
  try {
    const r = await api.checkMessengerLogin()
    cookieValid.value = r.valid
    cookieVerifyMsg.value = r.valid ? `✅ ${r.message}` : `❌ ${r.message}`
  } catch (e) {
    cookieValid.value = false
    cookieVerifyMsg.value = '❌ 验证失败: ' + e.message
  } finally {
    verifying.value = false
  }
}

async function doSync() {
  syncing.value = true
  syncResult.value = null
  progressPct.value = 0
  progressMsg.value = '准备中...'
  progressDetail.value = ''

  try {
    const resp = await fetch('/api/sync', { method: 'POST' })
    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = ''
      let eventType = ''
      for (const line of lines) {
        if (line.startsWith('event: ')) {
          eventType = line.slice(7).trim()
        } else if (line.startsWith('data: ')) {
          const data = JSON.parse(line.slice(6))
          handleEvent(eventType, data)
          eventType = ''
        } else if (line !== '') {
          buffer += line + '\n'
        }
      }
    }
  } catch (e) {
    progressMsg.value = '同步失败: ' + e.message
  } finally {
    syncing.value = false
  }
}

function handleEvent(type, data) {
  switch (type) {
    case 'start':
      progressMsg.value = data.message
      break
    case 'progress':
      progressMsg.value = data.message
      progressDetail.value = data.boss_name || ''
      if (data.total) progressPct.value = Math.round((data.current / data.total) * 100)
      break
    case 'boss_done':
      progressDetail.value = `${data.boss_name} — ${data.new_messages} 条新消息`
      break
    case 'done':
      progressPct.value = 100
      progressMsg.value = '同步完成'
      syncResult.value = { friends: data.friends, new_messages: data.new_messages, errors: data.errors || [] }
      break
    case 'error':
      progressMsg.value = '出错: ' + data.message
      break
  }
}

async function deleteAll() {
  try {
    await ElMessageBox.confirm('确定要删除所有投递记录和聊天消息吗？此操作不可撤销。', '警告', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    const r = await api.deleteAllBosses()
    ElMessage.success(`已删除 ${r.deleted} 条记录`)
  } catch (e) { /* cancelled */ }
}
</script>
