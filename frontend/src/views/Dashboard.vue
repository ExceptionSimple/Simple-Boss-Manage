<template>
  <div>
    <h2 style="margin-bottom: 20px;">概览</h2>
    <el-row :gutter="16">
      <el-col :span="6" v-for="item in cards" :key="item.label">
        <el-card shadow="hover" :body-style="{ textAlign: 'center', padding: '24px' }">
          <el-statistic :value="item.value" :title="item.label" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top: 24px;">
      <el-col :span="8" v-for="link in links" :key="link.to">
        <el-card shadow="hover" @click="$router.push(link.to)" style="cursor: pointer;">
          <div style="text-align: center; padding: 8px;">{{ link.label }} →</div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'

const cards = ref([
  { label: '投递公司', value: 0 },
  { label: '沟通次数', value: 0 },
  { label: '约面次数', value: 0 },
  { label: '覆盖城市', value: 0 },
  { label: '职位方向', value: 0 },
])

const links = [
  { to: '/bosses', label: '查看投递列表' },
  { to: '/stats', label: '查看统计分析' },
  { to: '/settings', label: '同步数据' },
]

onMounted(async () => {
  try {
    const o = await api.getOverview()
    cards.value[0].value = o.total_resume_sent || 0
    cards.value[1].value = o.total_communications || 0
    cards.value[2].value = o.total_interviews || 0
    cards.value[3].value = o.total_cities || 0
    cards.value[4].value = o.total_positions || 0
  } catch (e) { /* empty */ }
})
</script>
