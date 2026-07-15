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
      <el-table-column prop="company_name" label="公司" width="170" show-overflow-tooltip />
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

    <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;">
      <el-select v-model="activeSchemeIdx" style="width:100px;" size="default">
        <el-option label="方案1" :value="0" />
        <el-option label="方案2" :value="1" />
        <el-option label="方案3" :value="2" />
      </el-select>
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
          <div class="chat-msg">
            <div class="chat-bubble" :class="{ mine: m.side === 'right' }">
              <img v-if="isSticker(m)" :src="m.body_content" class="sticker-img" />
              <div v-else class="chat-text" v-html="renderText(m.body_content || m.push_text)"></div>
            </div>
            <div class="chat-meta">
              <span class="chat-time">{{ fmtTime(m.time) }}</span>
              <span class="chat-status" v-if="m.side === 'right'">{{ m.status === 2 ? '已读' : '未读' }}</span>
            </div>
          </div>
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
const activeSchemeIdx = ref(0)

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
        { name: b.name, boss_title: b.boss_title || '', scheme_index: activeSchemeIdx.value },
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

function isSticker(msg) {
  return msg.body_type === 20 && (msg.body_content || '').startsWith('data:image')
}

const EMOJI_LIST = [
  "微笑", "憨笑", "偷笑", "呲牙", "开心", "害羞", "调皮", "发呆", "坏笑", "淘气",
  "鼓掌", "抠鼻", "流汗", "奋斗", "尴尬", "感动", "委屈", "笑哭", "难过", "流泪",
  "石化", "offer", "面试", "牛", "生病", "疑问", "不屑", "生气", "无奈", "惊呆",
  "酷", "钱", "敬礼", "困", "衰", "喝可乐", "晕", "等待", "吃惊", "挑眉",
  "呵呵", "晚安", "捂脸", "比心", "机智", "社会社会", "裂开", "加油", "期待", "",
  "", "", "爱心", "心碎", "猫头", "狗头", "干杯", "玫瑰", "闹钟", "月亮",
  "太阳", "幽灵", "抱抱", "格局", "辛苦了", "冲鸭", "", "", "", "hi",
  "握手", "赞", "来", "OK", "祈祷", "抱拳", "", "", "", "鸡腿",
  "可", "卷", "get", "emo",
]
const EMOJI_MAP = {}
EMOJI_LIST.forEach((name, i) => { if (name) EMOJI_MAP[name] = i + 1 })

function renderText(text) {
  if (!text) return ''
  const escaped = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  return escaped.replace(/\[([^\]]+)\]/g, (match, name) => {
    const idx = EMOJI_MAP[name]
    if (idx) return `<i class="emoj emoj-${idx}" title="${name}"></i>`
    return match
  })
}

onMounted(() => { fetchData(); fetchFailedQueue() })
</script>

<style scoped>
.chat-container { max-height: 400px; overflow-y: auto; display: flex; flex-direction: column; gap: 12px; padding: 8px; background: #f0f2f5; border-radius: 8px; scrollbar-width: thin; scrollbar-color: #ccc transparent; }
.chat-container::-webkit-scrollbar { width: 4px; background: transparent; }
.chat-container::-webkit-scrollbar-thumb { background: #ccc; border-radius: 2px; }
.chat-row { display: flex; }
.chat-row.chat-left { justify-content: flex-start; }
.chat-row.chat-right { justify-content: flex-end; }
.chat-bubble { display: inline-block; background: #f8f8f8; border-radius: 8px; font-size: 14px; line-height: 22px; max-width: 420px; padding: 8px 12px; word-break: break-all; white-space: pre-wrap; text-align: left; }
.chat-left .chat-bubble { border-top-left-radius: 0; }
.chat-right .chat-msg { text-align: right; }
.chat-right .chat-bubble { background: rgba(0,190,189,.2); border-top-right-radius: 0; }
.chat-meta { display: flex; gap: 8px; margin-top: 4px; font-size: 11px; color: #999; padding: 0 4px; }
.chat-right .chat-meta { justify-content: flex-end; }
.chat-status { color: #10b981; }
.sticker-img { max-width: 120px; max-height: 120px; border-radius: 4px; display: block; }
</style>

<style>
@import '/css/emoj.css';
.emoj-1 { background-position: 0 0; }
.emoj-2 { background-position: 0 -25px; }
.emoj-3 { background-position: 0 -50px; }
.emoj-4 { background-position: 0 -75px; }
.emoj-5 { background-position: 0 -100px; }
.emoj-6 { background-position: 0 -125px; }
.emoj-7 { background-position: 0 -150px; }
.emoj-8 { background-position: 0 -175px; }
.emoj-9 { background-position: 0 -200px; }
.emoj-10 { background-position: 0 -225px; }
.emoj-11 { background-position: 0 -250px; }
.emoj-12 { background-position: 0 -275px; }
.emoj-13 { background-position: 0 -300px; }
.emoj-14 { background-position: 0 -325px; }
.emoj-15 { background-position: 0 -350px; }
.emoj-16 { background-position: 0 -375px; }
.emoj-17 { background-position: 0 -400px; }
.emoj-18 { background-position: 0 -425px; }
.emoj-19 { background-position: 0 -450px; }
.emoj-20 { background-position: 0 -475px; }
.emoj-21 { background-position: 0 -500px; }
.emoj-22 { background-position: 0 -525px; }
.emoj-23 { background-position: 0 -550px; }
.emoj-24 { background-position: 0 -575px; }
.emoj-25 { background-position: 0 -600px; }
.emoj-26 { background-position: 0 -625px; }
.emoj-27 { background-position: 0 -650px; }
.emoj-28 { background-position: 0 -675px; }
.emoj-29 { background-position: 0 -700px; }
.emoj-30 { background-position: 0 -725px; }
.emoj-31 { background-position: 0 -750px; }
.emoj-32 { background-position: 0 -775px; }
.emoj-33 { background-position: 0 -800px; }
.emoj-34 { background-position: 0 -825px; }
.emoj-35 { background-position: 0 -850px; }
.emoj-36 { background-position: 0 -875px; }
.emoj-37 { background-position: 0 -900px; }
.emoj-38 { background-position: 0 -925px; }
.emoj-39 { background-position: 0 -950px; }
.emoj-40 { background-position: 0 -975px; }
.emoj-41 { background-position: 0 -1000px; }
.emoj-42 { background-position: 0 -1025px; }
.emoj-43 { background-position: 0 -1050px; }
.emoj-44 { background-position: 0 -1075px; }
.emoj-45 { background-position: 0 -1100px; }
.emoj-46 { background-position: 0 -1125px; }
.emoj-47 { background-position: 0 -1150px; }
.emoj-48 { background-position: 0 -1175px; }
.emoj-49 { background-position: 0 -1200px; }
.emoj-53 { background-position: 0 -1300px; }
.emoj-54 { background-position: 0 -1325px; }
.emoj-55 { background-position: 0 -1350px; }
.emoj-56 { background-position: 0 -1375px; }
.emoj-57 { background-position: 0 -1400px; }
.emoj-58 { background-position: 0 -1425px; }
.emoj-59 { background-position: 0 -1450px; }
.emoj-60 { background-position: 0 -1475px; }
.emoj-61 { background-position: 0 -1500px; }
.emoj-62 { background-position: 0 -1525px; }
.emoj-63 { background-position: 0 -1550px; }
.emoj-64 { background-position: 0 -1575px; }
.emoj-65 { background-position: 0 -1600px; }
.emoj-66 { background-position: 0 -1625px; }
.emoj-70 { background-position: 0 -1725px; }
.emoj-71 { background-position: 0 -1750px; }
.emoj-72 { background-position: 0 -1775px; }
.emoj-73 { background-position: 0 -1800px; }
.emoj-74 { background-position: 0 -1825px; }
.emoj-75 { background-position: 0 -1850px; }
.emoj-80 { background-position: 0 -1975px; }
.emoj-81 { background-position: 0 -2000px; }
.emoj-82 { background-position: 0 -2025px; }
.emoj-83 { background-position: 0 -2050px; }
.emoj-84 { background-position: 0 -2075px; }
.emoj-85 { background-position: 0 -2100px; }
</style>
