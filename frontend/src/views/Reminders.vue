<template>
  <div>
    <h2 style="margin-bottom:16px;">消息提醒</h2>

    <!-- 失败队列 -->
    <el-card v-if="failedItems.length" shadow="hover" style="margin-bottom:20px;border:1px solid #f56c6c;">
      <template #header>
        <div style="display:flex;align-items:center;justify-content:space-between;">
          <span style="color:#f56c6c;font-weight:600;">⚠ 发送失败队列 ({{ failedItems.length }})</span>
          <div style="display:flex;gap:8px;">
            <el-button size="small" type="danger" @click="retryFailed([])" :loading="retryingFailed">
              重试全部
            </el-button>
            <el-button size="small" @click="clearFailedQueue([])" :disabled="retryingFailed">
              清空队列
            </el-button>
          </div>
        </div>
      </template>
      <el-table :data="failedItems" size="small" stripe @selection-change="onFailedSelect" max-height="250">
        <el-table-column type="selection" width="35" />
        <el-table-column prop="boss_name" label="BOSS" width="100" />
        <el-table-column label="消息" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.message }}</template>
        </el-table-column>
        <el-table-column prop="error" label="失败原因" width="150" show-overflow-tooltip />
        <el-table-column prop="retry_count" label="重试" width="55" align="center" />
        <el-table-column prop="created_at" label="时间" width="140" />
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="retryFailed([row.id])">重试</el-button>
            <el-button type="danger" link size="small" @click="clearFailedQueue([row.id])">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div v-if="failedSelected.length" style="margin-top:8px;">
        <el-button size="small" type="danger" @click="retryFailed(failedSelected.map(r => r.id))">
          重试选中 ({{ failedSelected.length }})
        </el-button>
        <el-button size="small" @click="clearFailedQueue(failedSelected.map(r => r.id))">
          删除选中 ({{ failedSelected.length }})
        </el-button>
      </div>
    </el-card>

    <p style="color:#999;font-size:13px;margin-bottom:16px;">以下 BOSS 的最后一条消息由你发送且未被对方阅读。</p>

    <el-table :data="items" v-loading="loading" stripe border @selection-change="onSelect"
      style="width:100%;margin-bottom:16px;">
      <el-table-column type="selection" width="40" />
      <el-table-column label="BOSS" width="115">
        <template #default="{ row }">
          <div style="display:flex;align-items:center;gap:8px;">
            <el-avatar v-if="row.avatar_url" :src="'/avatar/' + row.avatar_url" :size="28" />
            <span>{{ row.name }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="brand_name" label="公司" width="170" show-overflow-tooltip />
      <el-table-column prop="job_name" label="岗位" width="125" show-overflow-tooltip />
      <el-table-column label="城市" width="90">
        <template #default="{ row }">{{ row.location_name || row.job_city }}</template>
      </el-table-column>
      <el-table-column label="最近联系" width="110" sortable>
        <template #default="{ row }">{{ fmtDate(row.last_msg_time) }}</template>
      </el-table-column>
      <el-table-column label="连续未回" width="110" align="center" sortable prop="unanswered_count">
        <template #default="{ row }">
          <el-tag :type="row.unanswered_count > 1 ? 'danger' : 'warning'" size="small">
            {{ row.unanswered_count }} 条
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="最近消息预览" min-width="160" show-overflow-tooltip>
        <template #default="{ row }">{{ row.last_msg_preview }}</template>
      </el-table-column>
      <el-table-column label="操作" width="100">
        <template #default="{ row }">
          <el-button type="primary" link @click="openChat(row)">聊天记录</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div style="display:flex;gap:12px;align-items:center;">
      <el-button type="primary" :disabled="selected.length === 0" @click="doPreview" :loading="previewing">
        生成预览 ({{ selected.length }})
      </el-button>
    </div>

    <!-- 预览弹窗 -->
    <el-dialog v-model="showPreview" title="消息预览" width="700px">
      <el-table :data="previewItems" border stripe max-height="400">
        <el-table-column prop="name" label="BOSS" width="100" />
        <el-table-column prop="boss_title" label="职位" width="80" />
        <el-table-column prop="message" label="将发送的消息" min-width="300" show-overflow-tooltip />
      </el-table>
      <template #footer>
        <el-button @click="showPreview = false">取消</el-button>
        <el-button type="primary" @click="doSend" :loading="sending">确认发送</el-button>
      </template>
    </el-dialog>

    <!-- 聊天记录弹窗 -->
    <el-dialog v-model="showChat" :title="chatBoss?.name + ' 的聊天记录'" width="750px">
      <div class="chat-container" v-if="chatMsgs.length">
        <div v-for="m in chatMsgs" :key="m.id" class="chat-row" :class="'chat-' + m.side">
          <div class="chat-bubble" :class="{ mine: m.side === 'right' }">
            {{ m.body_content || m.push_text }}
          </div>
          <div class="chat-meta">{{ fmtTime(m.time) }}</div>
        </div>
      </div>
      <el-empty v-else description="暂无聊天记录" />
    </el-dialog>

    <div style="margin-top:16px;text-align:center;">
      <el-pagination v-model:current-page="page" v-model:page-size="size"
        :page-sizes="[10,20,50]" :total="total"
        layout="total,sizes,prev,pager,next" @change="fetchData" />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'

const items = ref([])
const loading = ref(false)
const page = ref(1)
const size = ref(20)
const total = ref(0)
const selected = ref([])

const showPreview = ref(false)
const previewItems = ref([])
const previewing = ref(false)
const sending = ref(false)

const showChat = ref(false)
const chatBoss = ref(null)
const chatMsgs = ref([])

// 失败队列
const failedItems = ref([])
const failedSelected = ref([])
const retryingFailed = ref(false)

async function fetchFailedQueue() {
  try { failedItems.value = (await api.getFailedQueue()).items } catch (e) { /* ignore */ }
}

function onFailedSelect(val) { failedSelected.value = val }

async function retryFailed(ids) {
  retryingFailed.value = true
  try {
    const r = await api.retryFailedQueue(ids)
    const ok = r.results?.filter(x => x.success).length || 0
    const fail = r.results?.filter(x => !x.success).length || 0
    ElMessage.success(`重试完成：${ok} 成功, ${fail} 失败`)
    await fetchFailedQueue()
  } catch (e) { ElMessage.error('重试失败: ' + e.message) }
  finally { retryingFailed.value = false }
}

async function clearFailedQueue(ids) {
  try {
    const r = await api.deleteFailedQueue(ids)
    ElMessage.success(`已清除 ${r.deleted} 条记录`)
    await fetchFailedQueue()
  } catch (e) { ElMessage.error('清除失败: ' + e.message) }
}

async function fetchData() {
  loading.value = true
  try {
    const r = await api.getReminders({ page: page.value, size: size.value })
    items.value = r.items
    total.value = r.total
  } catch (e) { /* ignore */ }
  loading.value = false
}

function onSelect(val) { selected.value = val }

async function openChat(row) {
  chatBoss.value = row
  try {
    const r = await api.getMessages(row.encrypt_boss_id, { size: 100 })
    chatMsgs.value = r.items
  } catch (e) { chatMsgs.value = [] }
  showChat.value = true
}

async function doPreview() {
  // 立即打开 Dialog
  previewItems.value = selected.value.map(b => ({
    encrypt_boss_id: b.encrypt_boss_id,
    name: b.name,
    boss_title: b.boss_title || '',
    message: '生成中...',
  }))
  showPreview.value = true
  previewing.value = true

  // 逐个生成（流式）
  for (let i = 0; i < selected.value.length; i++) {
    const b = selected.value[i]
    try {
      const msg = await api.generateMessage(
        { name: b.name, boss_title: b.boss_title || '' },
        (text) => { previewItems.value[i].message = text }
      )
      previewItems.value[i].message = msg
    } catch (e) {
      previewItems.value[i].message = '生成失败: ' + e.message
    }
  }
  previewing.value = false
}

async function doSend() {
  sending.value = true
  try {
    const items = previewItems.value.map(p => ({ name: p.name, message: p.message }))
    const r = await api.sendRemindersWithMessages({ items })
    const ok = r.results?.filter(x => x.success).length || 0
    const fail = r.results?.filter(x => !x.success).length || 0
    ElMessage.success(`发送完成：${ok} 成功, ${fail} 失败。浏览器保持打开，请手动关闭。`)
    showPreview.value = false
    fetchData()
    fetchFailedQueue()
  } catch (e) { ElMessage.error('发送失败: ' + e.message) }
  finally { sending.value = false }
}

function fmtTime(ts) {
  if (!ts) return ''
  return new Date(ts).toLocaleString('zh-CN')
}

function fmtDate(ts) {
  if (!ts) return '-'
  return new Date(ts).toLocaleDateString('zh-CN')
}

onMounted(() => { fetchData(); fetchFailedQueue() })
</script>

<style scoped>
.chat-container { max-height: 400px; overflow-y: auto; display: flex; flex-direction: column; gap: 12px; padding: 8px; background: #f0f2f5; border-radius: 8px; }
.chat-row { display: flex; flex-direction: column; max-width: 70%; }
.chat-row.chat-left { align-self: flex-start; }
.chat-row.chat-right { align-self: flex-end; align-items: flex-end; }
.chat-bubble { padding: 8px 12px; border-radius: 8px; font-size: 13px; background: #f8f8f8; max-width: 100%; }
.chat-bubble.mine { background: rgba(0,190,189,.2); }
.chat-meta { font-size: 11px; color: #999; margin-top: 2px; }
</style>
