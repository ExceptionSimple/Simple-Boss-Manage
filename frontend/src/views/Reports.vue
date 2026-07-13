<template>
  <div>
    <h2 style="margin-bottom:20px;">生成报告</h2>

    <el-row :gutter="16">
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header><h3>📊 周报</h3></template>
          <p style="color:#999;font-size:13px;margin-bottom:16px;">统计本周沟通数据，对比上周趋势</p>
          <el-button type="primary" @click="generate('weekly')" :loading="generating">生成周报</el-button>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header><h3>📈 月报</h3></template>
          <p style="color:#999;font-size:13px;margin-bottom:16px;">统计本月沟通数据，对比上月趋势</p>
          <el-button type="primary" @click="generate('monthly')" :loading="generating">生成月报</el-button>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top:20px;">
      <el-col :span="24">
        <el-card shadow="hover">
          <template #header><h3>历史报告</h3></template>
          <el-table v-if="reportList.length" :data="reportList" stripe size="small">
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
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../api'

const generating = ref(false)
const reportList = ref([])

onMounted(async () => {
  try { reportList.value = await api.listReports() } catch (e) { /* ignore */ }
})

async function generate(type) {
  generating.value = true
  try {
    const r = await api.generateReport(type)
    ElMessage.success('报告已生成')
    window.open(r.url, '_blank')
    reportList.value = await api.listReports()
  } catch (e) { ElMessage.error('生成失败: ' + e.message) }
  finally { generating.value = false }
}

function openReport(url) {
  window.open(url, '_blank')
}
</script>
