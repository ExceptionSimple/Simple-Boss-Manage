<template>
  <div>
    <h2 style="margin-bottom: 20px;">概览</h2>

    <div class="stat-row">
      <div class="stat-card" v-for="item in topCards" :key="item.label">
        <div class="stat-icon" :style="{ background: item.color }">{{ item.icon }}</div>
        <div class="stat-info">
          <div class="stat-num">{{ item.value }}</div>
          <div class="stat-label">{{ item.label }}</div>
        </div>
      </div>
    </div>

    <el-row :gutter="16" style="margin-top: 16px;">
      <el-col :span="4" v-for="item in subCards" :key="item.label">
        <el-card shadow="hover" :body-style="{ textAlign: 'center', padding: '16px' }">
          <div class="sub-num">{{ item.value }} <span :class="item.trend >= 0 ? 'up' : 'down'">{{ trendIcon(item.trend) }}</span></div>
          <div class="sub-label">{{ item.label }}</div>
          <div class="sub-hint">较{{ item.prevLabel }} {{ item.prev }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top: 16px;">
      <el-col :span="4" v-for="item in monthCards" :key="item.label">
        <el-card shadow="hover" :body-style="{ textAlign: 'center', padding: '16px' }">
          <div class="sub-num month">{{ item.value }} <span :class="item.trend >= 0 ? 'up' : 'down'">{{ trendIcon(item.trend) }}</span></div>
          <div class="sub-label">{{ item.label }}</div>
          <div class="sub-hint">较上月 {{ item.prev }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top: 20px;">
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header><h3>聊天记录 TOP 3</h3></template>
          <div v-if="topChatters.length">
            <div v-for="(t, i) in topChatters" :key="i" class="top-item">
              <span class="top-rank">{{ ['🥇','🥈','🥉'][i] }}</span>
              <span class="top-name">{{ t.name }}</span>
              <span class="top-brand">{{ t.brand }}</span>
              <span class="top-cnt">{{ t.count }} 条</span>
            </div>
          </div>
          <el-empty v-else description="暂无数据" :image-size="60" />
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header><h3>最近发送简历</h3></template>
          <div v-if="recentResumes.length">
            <div v-for="(r, i) in recentResumes" :key="i" class="resume-item">
              <div class="resume-info">
                <div class="resume-company">{{ r.brand }}</div>
                <div class="resume-job">{{ r.job }}</div>
              </div>
              <div class="resume-date">{{ fmtDate(r.datetime) }}</div>
            </div>
          </div>
          <el-empty v-else description="暂无数据" :image-size="60" />
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header><h3>同步日志</h3></template>
          <el-table v-if="syncLogs.length" :data="syncLogs" size="small" stripe max-height="220">
            <el-table-column prop="sync_time" label="时间" width="140" />
            <el-table-column label="范围" width="55">
              <template #default="{ row }">{{ row.sync_days ? row.sync_days + '天' : '全部' }}</template>
            </el-table-column>
            <el-table-column prop="new_messages" label="新消息" width="60" align="center" />
            <el-table-column prop="skipped" label="跳过" width="50" align="center" />
          </el-table>
          <el-empty v-else description="暂无数据" :image-size="60" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'

const topCards = ref([
  { label: '投递公司', value: 0, icon: '📨', color: '#ecfdf5' },
  { label: '沟通次数', value: 0, icon: '💬', color: '#eff6ff' },
  { label: '约面次数', value: 0, icon: '🤝', color: '#fefce8' },
  { label: '覆盖城市', value: 0, icon: '🏙️', color: '#fdf2f8' },
  { label: '职位方向', value: 0, icon: '🎯', color: '#f5f3ff' },
])

const subCards = ref([
  { label: '今日沟通', value: 0, prev: 0, trend: 0, prevLabel: '昨日' },
  { label: '本周沟通', value: 0, prev: 0, trend: 0, prevLabel: '上周' },
  { label: '本周发简历', value: 0, prev: 0, trend: 0, prevLabel: '上周' },
])

const monthCards = ref([
  { label: '本月沟通', value: 0, prev: 0, trend: 0 },
  { label: '本月发简历', value: 0, prev: 0, trend: 0 },
])
const topChatters = ref([])
const recentResumes = ref([])
const syncLogs = ref([])

function trendIcon(t) { return t > 0 ? '↑' : t < 0 ? '↓' : '→' }
function fmtDate(ts) { if (!ts) return '-'; return new Date(ts).toLocaleDateString('zh-CN') }

onMounted(async () => {
  try {
    const o = await api.getOverview()
    topCards.value[0].value = o.total_resume_sent || 0
    topCards.value[1].value = o.total_communications || 0
    topCards.value[2].value = o.total_interviews || 0
    topCards.value[3].value = o.total_cities || 0
    topCards.value[4].value = o.total_positions || 0

    subCards.value[0].value = o.today.value; subCards.value[0].prev = o.today.prev; subCards.value[0].trend = o.today.value - o.today.prev
    subCards.value[1].value = o.week.value; subCards.value[1].prev = o.week.prev; subCards.value[1].trend = o.week.value - o.week.prev
    subCards.value[2].value = o.week_resume.value; subCards.value[2].prev = o.week_resume.prev; subCards.value[2].trend = o.week_resume.value - o.week_resume.prev
    monthCards.value[0].value = o.month.value; monthCards.value[0].prev = o.month.prev; monthCards.value[0].trend = o.month.value - o.month.prev
    monthCards.value[1].value = o.month_resume.value; monthCards.value[1].prev = o.month_resume.prev; monthCards.value[1].trend = o.month_resume.value - o.month_resume.prev
    topChatters.value = o.top_chatters || []
    recentResumes.value = await api.getRecentResumes()
    syncLogs.value = await api.getDashboardSyncLogs()
  } catch (e) { /* empty */ }
})
</script>

<style scoped>
.stat-row { display: flex; gap: 12px; margin-bottom: 16px; }
.stat-card {
  flex: 1;
  background: #fff;
  border-radius: 12px;
  padding: 20px 16px;
  display: flex;
  align-items: center;
  gap: 14px;
  box-shadow: 0 1px 3px rgba(0,0,0,.04);
  transition: box-shadow .2s;
}
.stat-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,.08); }
.stat-icon { width: 44px; height: 44px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 20px; flex-shrink: 0; }
.stat-num { font-size: 22px; font-weight: 700; color: #1f2937; }
.stat-label { font-size: 13px; color: #9ca3af; margin-top: 2px; }
.sub-num { font-size: 22px; font-weight: 700; color: #6366f1; }
.sub-num.month { font-size: 26px; color: #f59e0b; }
.sub-label { font-size: 12px; color: #999; margin-top: 4px; }
.sub-hint { font-size: 11px; color: #bbb; margin-top: 2px; }
.up { color: #10b981; font-size: 14px; margin-left: 4px; }
.down { color: #ef4444; font-size: 14px; margin-left: 4px; }
.top-item { display: flex; align-items: center; gap: 8px; padding: 8px 0; border-bottom: 1px solid #f5f5f5; }
.top-item:last-child { border-bottom: none; }
.top-rank { font-size: 18px; width: 28px; text-align: center; }
.top-name { flex: 1; font-weight: 600; }
.top-brand { color: #999; font-size: 13px; }
.top-cnt { color: #10b981; font-weight: 600; font-size: 13px; }
.resume-item { display: flex; justify-content: space-between; align-items: center; padding: 6px 0; border-bottom: 1px solid #f5f5f5; }
.resume-item:last-child { border-bottom: none; }
.resume-company { font-weight: 600; font-size: 13px; }
.resume-job { color: #999; font-size: 12px; }
.resume-date { color: #6366f1; font-size: 12px; white-space: nowrap; }
</style>
