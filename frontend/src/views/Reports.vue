<template>
  <div>
    <h2 style="margin-bottom:20px;">生成报告</h2>

    <el-row :gutter="16">
      <el-col :span="6" v-for="card in reportCards" :key="card.key">
        <el-card shadow="hover">
          <template #header><h3>{{ card.title }}</h3></template>
          <p style="color:#999;font-size:13px;margin-bottom:16px;">{{ card.desc }}</p>
          <el-button type="primary" @click="generate(card.key)" :loading="generating">{{ card.btn }}</el-button>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header><h3>自定义范围</h3></template>
          <p style="color:#999;font-size:13px;margin-bottom:12px;">选择日期范围，对比上一个等长周期</p>
          <el-date-picker v-model="customDateRange" type="daterange" range-separator="至"
            start-placeholder="开始日期" end-placeholder="结束日期" format="YYYY-MM-DD" value-format="YYYY-MM-DD"
            style="width:100%;margin-bottom:12px;" />
          <el-button type="primary" @click="generateCustom" :loading="generatingCustom" :disabled="!customDateRange[0] || !customDateRange[1]">
            {{ generatingCustom ? '生成中...' : '生成' }}
          </el-button>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top:20px;">
      <el-col :span="24">
        <el-card shadow="hover">
          <template #header>
            <div style="display:flex;align-items:center;justify-content:space-between;">
              <h3>历史报告</h3>
              <div style="display:flex;gap:12px;">
                <el-select v-model="filterType" placeholder="类型" clearable style="width:100px;" @change="loadList">
                  <el-option label="周报" value="weekly" />
                  <el-option label="月报" value="monthly" />
                </el-select>
                <el-button type="danger" size="small" :disabled="selected.length===0" @click="doDelete">删除选中 ({{ selected.length }})</el-button>
              </div>
            </div>
          </template>
          <el-table v-if="filteredList.length" :data="filteredList" stripe size="small" @selection-change="onSelect">
            <el-table-column type="selection" width="40" />
            <el-table-column prop="type" label="类型" width="80" />
            <el-table-column prop="name" label="文件" min-width="200" />
            <el-table-column prop="time" label="生成时间" width="160" />
            <el-table-column label="操作" width="80">
              <template #default="{ row }">
                <el-button type="primary" link @click="openReport(row.url)">查看</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-else description="暂无报告" :image-size="60" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../api'

const generating = ref(false)
const reportList = ref([])
const selected = ref([])
const filterType = ref('')

const reportCards = [
  { key: 'weekly-current', title: '本周', desc: '本周至今，对比上周', btn: '生成本周报' },
  { key: 'weekly', title: '上周', desc: '完整上周数据，对比上上周', btn: '生成周报' },
  { key: 'monthly-current', title: '本月', desc: '本月至今，对比上月', btn: '生成本月报' },
  { key: 'monthly', title: '上月', desc: '完整上月数据，对比上上月', btn: '生成月报' },
]
const customDateRange = ref([null, null])
const generatingCustom = ref(false)

const filteredList = computed(() => {
  if (!filterType.value) return reportList.value
  const prefix = filterType.value  // 'weekly' matches weekly*, 'monthly' matches monthly*
  return reportList.value.filter(r => r.name.startsWith(prefix))
})

onMounted(loadList)
async function loadList() {
  try { reportList.value = await api.listReports() } catch (e) { /* ignore */ }
}

function onSelect(val) { selected.value = val }

async function generate(type) {
  generating.value = true
  try {
    const r = await api.generateReport(type)
    ElMessage.success('报告已生成')
    window.open(r.url, '_blank')
    await loadList()
  } catch (e) { ElMessage.error('生成失败: ' + e.message) }
  finally { generating.value = false }
}

async function generateCustom() {
  if (!customDateRange.value[0] || !customDateRange.value[1]) return
  generatingCustom.value = true
  try {
    const r = await api.generateCustomReport(customDateRange.value[0], customDateRange.value[1])
    ElMessage.success('报告已生成')
    window.open(r.url, '_blank')
    await loadList()
  } catch (e) { ElMessage.error('生成失败: ' + e.message) }
  finally { generatingCustom.value = false }
}

async function doDelete() {
  try {
    await ElMessageBox.confirm(`确定要删除 ${selected.value.length} 个报告吗？`, '警告', { type: 'warning' })
    const names = selected.value.map(r => r.name)
    await api.deleteReports(names)
    ElMessage.success('已删除')
    selected.value = []
    await loadList()
  } catch (e) { /* cancelled */ }
}

function openReport(url) {
  window.open(url, '_blank')
}
</script>
