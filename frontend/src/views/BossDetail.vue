<template>
  <div class="boss-detail-page">
    <el-button text @click="$router.push('/bosses')">← 返回列表</el-button>

    <el-card v-if="boss" style="margin-top:12px;" shadow="hover">
      <div style="display:flex;gap:16px;align-items:center;">
        <el-avatar v-if="boss.avatar_url" :src="avatarSrc(boss.avatar_url)" :size="56" />
        <div>
          <h2>{{ boss.name }}</h2>
          <p>{{ boss.company_name }} · {{ boss.job_name }}</p>
          <p style="font-size:13px;color:#999;margin-top:4px;">
            {{ boss.location_name || boss.job_city }}
            <template v-if="boss.salary_desc"> · {{ boss.salary_desc }}</template>
            <template v-if="boss.job_type_desc"> · {{ boss.job_type_desc }}</template>
            <el-tag v-if="boss.has_interview" type="warning" size="small" style="margin-left:8px;">有面试</el-tag>
            <el-tag v-if="boss.is_resume_sent" type="primary" size="small" style="margin-left:4px;">📎 简历已发送</el-tag>
          </p>
          <p v-if="boss.first_msg_time" style="font-size:13px;color:#999;margin-top:2px;">
            📅 {{ fmtDate(boss.first_msg_time) }} → {{ fmtDate(boss.last_msg_time) }}
          </p>
        </div>
      </div>
    </el-card>

    <div style="display:flex;align-items:center;gap:12px;margin-top:16px;">
      <h3 style="margin:0;">聊天记录 ({{ msgTotal }})</h3>
      <el-button type="primary" size="small" @click="showSendDialog = true" :icon="Promotion">发送消息</el-button>
    </div>

    <el-dialog v-model="showSendDialog" title="发送消息" width="450px">
      <el-input v-model="sendMsg" type="textarea" :rows="4" placeholder="输入要发送的消息..." />
      <template #footer>
        <el-button @click="showSendDialog = false">取消</el-button>
        <el-button type="primary" @click="doSend" :loading="sending" :disabled="!sendMsg.trim()">发送</el-button>
      </template>
    </el-dialog>
    <div class="chat-container" v-if="messages.length">
      <div v-for="m in messages" :key="m.id" class="chat-row" :class="'chat-' + m.side">
        <div class="chat-msg">
          <div class="chat-bubble" :class="{ mine: m.side === 'right' }">
            <img v-if="isSticker(m)" :src="m.body_content" class="sticker-img" />
            <div v-else class="chat-text" v-html="renderText(m.body_content || m.push_text)"></div>
          </div>
          <div class="chat-meta">
            <span class="chat-time">{{ formatTime(m.time) }}</span>
            <span class="chat-status" v-if="m.side === 'right'">{{ m.status === 2 ? '已读' : '未读' }}</span>
          </div>
        </div>
      </div>
    </div>
    <el-empty v-if="msgTotal === 0" description="暂无聊天记录" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Promotion } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { api } from '../api'

const route = useRoute()
const bossId = route.params.id

const boss = ref(null)
const messages = ref([])
const msgTotal = ref(0)
const showSendDialog = ref(false)
const sendMsg = ref('')
const sending = ref(false)

async function doSend() {
  if (!sendMsg.value.trim()) return
  sending.value = true
  try {
    await api.sendMessage({ boss_name: boss.value.name, message: sendMsg.value })
    ElMessage.success('消息已发送')
    showSendDialog.value = false
    sendMsg.value = ''
  } catch (e) {
    ElMessage.error('发送失败: ' + e.message)
  } finally {
    sending.value = false
  }
}

function formatTime(ts) {
  if (!ts) return ''
  return new Date(ts).toLocaleString('zh-CN')
}

function fmtDate(ts) {
  if (!ts) return ''
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

function avatarSrc(url) {
  if (!url) return ''
  if (url.startsWith('http')) return url
  return '/avatar/' + url
}

onMounted(async () => {
  try {
    boss.value = await api.getBoss(bossId)
    const r = await api.getMessages(bossId, { size: 200 })
    messages.value = r.items
    msgTotal.value = r.total
  } catch (e) { /* ignore */ }
})
</script>

<style scoped>
.boss-detail-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 80px);
  overflow: hidden;
}
.boss-detail-page > .el-button {
  display: flex;
  justify-content: left;
  width: fit-content;
}
.chat-container {
  background: #fff;
  border-radius: 8px;
  margin-top: 10px;
  padding: 24px 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  flex: 1;
  overflow-y: auto;
  min-height: 0;
  scrollbar-width: thin;
  scrollbar-color: #ccc transparent;
}
.chat-container::-webkit-scrollbar {
  width: 4px;
  background: transparent;
}
.chat-container::-webkit-scrollbar-thumb {
  background: #ccc;
  border-radius: 2px;
}
.chat-row { display: flex; }
.chat-left { justify-content: flex-start; }
.chat-right { justify-content: flex-end; }
.chat-bubble {
  display: inline-block;
  background-color: #f8f8f8;
  border-radius: 8px;
  color: #333;
  font-size: 14px;
  line-height: 22px;
  max-width: 420px;
  padding: 8px 12px;
  position: relative;
  vertical-align: top;
  word-break: break-all;
  white-space: pre-wrap;
  text-align: left;
}
.chat-left .chat-bubble { border-top-left-radius: 0; }
.chat-right .chat-msg { text-align: right; }
.chat-right .chat-bubble { background-color: rgba(0, 190, 189, .2); border-top-right-radius: 0; }
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
