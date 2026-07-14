<template>
  <div>
    <h2 style="margin-bottom:20px;">统计分析</h2>

    <el-row :gutter="16">
      <el-col :span="24" style="margin-bottom:16px;">
        <el-card shadow="hover">
          <template #header>
            <div style="display:flex;align-items:center;justify-content:space-between;">
              <h3>每日沟通人数</h3>
              <div style="display:flex;gap:12px;">
                <el-date-picker v-model="selectedMonth" type="month" placeholder="选择月份" format="YYYY-MM" value-format="YYYY-MM" @change="onFilterChange" />
                <el-select v-model="selectedWeek" placeholder="周" style="width:120px;" @change="onFilterChange">
                  <el-option label="全部" value="all" />
                  <el-option label="第一周" value="1" />
                  <el-option label="第二周" value="2" />
                  <el-option label="第三周" value="3" />
                  <el-option label="第四周" value="4" />
                  <el-option label="第五周" value="5" />
                </el-select>
              </div>
            </div>
          </template>
          <VChart :option="dailyOption" autoresize v-if="filteredDaily.length" style="height:350px;" />
          <el-empty v-else description="暂无数据" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-bottom:16px;">
      <el-col :span="24">
        <el-card shadow="hover">
          <template #header>
            <div style="display:flex;align-items:center;justify-content:space-between;">
              <h3>每日发送简历趋势</h3>
              <div style="display:flex;gap:12px;">
                <el-date-picker v-model="resumeMonth" type="month" placeholder="选择月份" format="YYYY-MM" value-format="YYYY-MM" @change="onResumeFilterChange" />
                <el-select v-model="resumeWeek" placeholder="周" style="width:120px;" @change="onResumeFilterChange">
                  <el-option label="全部" value="all" />
                  <el-option label="第一周" value="1" />
                  <el-option label="第二周" value="2" />
                  <el-option label="第三周" value="3" />
                  <el-option label="第四周" value="4" />
                  <el-option label="第五周" value="5" />
                </el-select>
              </div>
            </div>
          </template>
          <VChart :option="resumeDailyOption" autoresize v-if="filteredResumeDaily.length" style="height:350px;" />
          <el-empty v-else description="暂无数据" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header><h3>城市分布</h3></template>
          <VChart :option="cityOption" autoresize v-if="cityData.length" style="height:350px;" />
          <el-empty v-else description="暂无数据" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header><h3>岗位分布</h3></template>
          <VChart :option="posOption" autoresize v-if="posData.length" style="height:350px;" />
          <el-empty v-else description="暂无数据" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, GridComponent, LegendComponent, DataZoomComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { api } from '../api'

use([BarChart, LineChart, PieChart, TitleComponent, TooltipComponent, GridComponent, LegendComponent, DataZoomComponent, CanvasRenderer])

const cityData = ref([])
const posData = ref([])
const allDaily = ref([])

const selectedMonth = ref(null)
const selectedWeek = ref('all')

function getWeekOfMonth(dateStr) {
  const d = new Date(dateStr)
  const day = d.getDate()
  return Math.min(Math.ceil(day / 7), 5)
}

const filteredDaily = computed(() => {
  let data = allDaily.value
  if (!selectedMonth.value) return data

  const ym = selectedMonth.value  // e.g. "2026-07"
  data = data.filter(d => d.date.startsWith(ym))

  if (selectedWeek.value !== 'all') {
    const w = parseInt(selectedWeek.value)
    data = data.filter(d => getWeekOfMonth(d.date) === w)
  }
  return data
})

const dailyOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  xAxis: { type: 'category', data: filteredDaily.value.map(d => d.date), axisLabel: { rotate: 45, fontSize: 10 } },
  yAxis: { type: 'value', name: '人数', minInterval: 1 },
  series: [{ data: filteredDaily.value.map(d => d.count), type: 'bar', itemStyle: { color: '#10b981' } }],
  grid: { left: 50, bottom: 80, right: 20, top: 10 },
}))

const cityOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  xAxis: { type: 'category', data: cityData.value.map(c => c.name), axisLabel: { rotate: 30 } },
  yAxis: { type: 'value' },
  series: [{ data: cityData.value.map(c => c.value), type: 'bar', itemStyle: { color: '#10b981' } }],
  grid: { left: 40, bottom: 80, right: 20, top: 10 },
}))

const posOption = computed(() => ({
  tooltip: { trigger: 'item' },
  series: [{ type: 'pie', radius: ['40%', '70%'], data: posData.value, label: { show: true, formatter: '{b}: {c}' } }],
}))

function onFilterChange() { /* computed reacts automatically */ }

// 简历趋势
const allResumeDaily = ref([])
const resumeMonth = ref(null)
const resumeWeek = ref('all')

const filteredResumeDaily = computed(() => {
  let data = allResumeDaily.value
  if (!resumeMonth.value) return data
  const ym = resumeMonth.value
  data = data.filter(d => d.date.startsWith(ym))
  if (resumeWeek.value !== 'all') {
    const w = parseInt(resumeWeek.value)
    data = data.filter(d => getWeekOfMonth(d.date) === w)
  }
  return data
})

const resumeDailyOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  xAxis: { type: 'category', data: filteredResumeDaily.value.map(d => d.date), axisLabel: { rotate: 45, fontSize: 10 } },
  yAxis: { type: 'value', name: '简历数', minInterval: 1 },
  series: [{
    data: filteredResumeDaily.value.map(d => d.count),
    type: 'line',
    smooth: false,
    lineStyle: { color: '#f59e0b', width: 2 },
    itemStyle: { color: '#f59e0b' },
    areaStyle: { color: 'rgba(245, 158, 11, 0.1)' },
  }],
  grid: { left: 50, bottom: 80, right: 20, top: 10 },
}))

function onResumeFilterChange() { /* computed reacts automatically */ }

onMounted(async () => {
  try {
    cityData.value = await api.getCityStats()
    posData.value = await api.getPositionStats()
    allDaily.value = await api.getDailyStats()
    allResumeDaily.value = await api.getDailyResumeStats()
  } catch (e) { /* ignore */ }
})
</script>
