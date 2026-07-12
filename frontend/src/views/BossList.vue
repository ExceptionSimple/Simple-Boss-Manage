<template>
  <div>
    <h2 style="margin-bottom: 16px;">投递列表</h2>

    <el-row :gutter="12" style="margin-bottom: 16px;">
      <el-col :span="5">
        <el-input v-model="filters.keyword" placeholder="搜索公司 / 岗位..." clearable @input="search" />
      </el-col>
      <el-col :span="4">
        <el-input v-model="filters.city" placeholder="城市..." clearable @input="search" />
      </el-col>
      <el-col :span="4">
        <el-input v-model="filters.position" placeholder="职位..." clearable @input="search" />
      </el-col>
      <el-col :span="3">
        <el-select v-model="filters.has_interview" placeholder="面试" clearable @change="doSearch" style="width:100%">
          <el-option label="有面试" :value="1" />
          <el-option label="无面试" :value="0" />
        </el-select>
      </el-col>
      <el-col :span="3">
        <el-select v-model="filters.is_resume_sent" placeholder="简历" clearable @change="doSearch" style="width:100%">
          <el-option label="已发送" :value="1" />
          <el-option label="未发送" :value="0" />
        </el-select>
      </el-col>
      <el-col :span="3">
        <el-select v-model="filters.has_written_test" placeholder="笔试" clearable @change="doSearch" style="width:100%">
          <el-option label="有笔试" :value="1" />
          <el-option label="无笔试" :value="0" />
        </el-select>
      </el-col>
    </el-row>

    <div style="display:flex;gap:12px;align-items:center;margin-bottom:12px;">
      <el-button type="primary" :disabled="selectedNames.length === 0" @click="showBatchDialog = true">
        批量发消息 ({{ selectedNames.length }})
      </el-button>
      <span v-if="selectedNames.length" style="font-size:13px;color:#999;">已选：{{ selectedNames.join(', ') }}</span>
    </div>

    <el-dialog v-model="showBatchDialog" title="批量发送消息" width="500px">
      <p style="margin-bottom:12px;color:#666;">将发送给 {{ selectedNames.length }} 人</p>
      <el-input v-model="batchMsg" type="textarea" :rows="5" placeholder="输入要发送的消息..." />
      <template #footer>
        <el-button @click="showBatchDialog = false">取消</el-button>
        <el-button type="primary" @click="doBatchSend" :loading="batchSending" :disabled="!batchMsg.trim()">发送</el-button>
      </template>
    </el-dialog>

    <el-table :data="bosses" v-loading="loading" stripe border style="width:100%"
      @sort-change="handleSortChange" :default-sort="{ prop: 'last_msg_time', order: 'descending' }"
      @selection-change="onSelectionChange" ref="tableRef">
      <el-table-column type="selection" width="40" />
      <el-table-column label="BOSS" min-width="140">
        <template #default="{ row }">
          <div style="display:flex;align-items:center;gap:8px;">
            <el-avatar v-if="row.avatar_url" :src="avatarSrc(row.avatar_url)" :size="28" />
            <span>{{ row.name }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="brand_name" label="公司" min-width="120" />
      <el-table-column prop="boss_title" label="职位" width="80" />
      <el-table-column prop="job_name" label="岗位" min-width="160" show-overflow-tooltip />
      <el-table-column label="城市" width="90">
        <template #default="{ row }">{{ row.location_name || row.job_city }}</template>
      </el-table-column>
      <el-table-column prop="salary_desc" label="薪资" width="110" />
      <el-table-column prop="first_msg_time" label="首次联系" width="110" sortable="custom">
        <template #default="{ row }">{{ fmtDate(row.first_msg_time) }}</template>
      </el-table-column>
      <el-table-column prop="last_msg_time" label="最近联系" width="110" sortable="custom">
        <template #default="{ row }">{{ fmtDate(row.last_msg_time) }}</template>
      </el-table-column>
      <el-table-column label="面试" width="70" align="center">
        <template #default="{ row }">
          <el-checkbox :model-value="!!row.has_interview" @change="toggle(row, 'has_interview')" />
        </template>
      </el-table-column>
      <el-table-column label="简历" width="70" align="center">
        <template #default="{ row }">
          <el-checkbox :model-value="!!row.is_resume_sent" @change="toggle(row, 'is_resume_sent')" />
        </template>
      </el-table-column>
      <el-table-column label="笔试" width="70" align="center">
        <template #default="{ row }">
          <el-checkbox :model-value="!!row.has_written_test" @change="toggle(row, 'has_written_test')" />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="80" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" link @click="$router.push(`/bosses/${row.encrypt_boss_id}`)">查看</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div style="margin-top:16px;text-align:center;">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="size"
        :page-sizes="[10, 20, 50, 100]"
        :total="total"
        layout="total, sizes, prev, pager, next"
        @change="fetchData"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../api'

const bosses = ref([])
const loading = ref(false)
const page = ref(1)
const size = ref(20)
const total = ref(0)
const tableRef = ref(null)
const selectedBosses = ref([])
const selectedNames = computed(() => selectedBosses.value.map(b => b.name))
const showBatchDialog = ref(false)
const batchMsg = ref('')
const batchSending = ref(false)
const filters = reactive({
  keyword: '', city: '', position: '',
  has_interview: null, is_resume_sent: null, has_written_test: null,
  sort_by: 'last_msg_time', order: 'desc',
})

let timer = null

async function fetchData() {
  loading.value = true
  const params = { page: page.value, size: size.value }
  for (const [k, v] of Object.entries(filters)) {
    if (v !== null && v !== '') params[k] = v
  }
  try {
    const r = await api.getBosses(params)
    bosses.value = r.items
    total.value = r.total
  } catch (e) { /* ignore */ }
  loading.value = false
}

function search() {
  clearTimeout(timer)
  timer = setTimeout(() => { page.value = 1; fetchData() }, 300)
}
function doSearch() { page.value = 1; fetchData() }

function handleSortChange({ prop, order }) {
  if (prop && order) {
    filters.sort_by = prop
    filters.order = order === 'descending' ? 'desc' : 'asc'
  } else {
    filters.sort_by = 'last_msg_time'
    filters.order = 'desc'
  }
  fetchData()
}

function onSelectionChange(val) { selectedBosses.value = val }

async function doBatchSend() {
  if (!batchMsg.value.trim() || selectedNames.value.length === 0) return
  batchSending.value = true
  try {
    const r = await api.sendBatchMessage({
      boss_names: selectedNames.value,
      message: batchMsg.value,
    })
    const ok = r.results?.filter(x => x.success).length || 0
    const fail = r.results?.filter(x => !x.success).length || 0
    ElMessage.success(`发送完成：${ok} 成功, ${fail} 失败`)
    showBatchDialog.value = false
    batchMsg.value = ''
    tableRef.value?.clearSelection()
  } catch (e) {
    ElMessage.error('批量发送失败: ' + e.message)
  } finally {
    batchSending.value = false
  }
}

async function toggle(boss, field) {
  const newVal = !boss[field]
  boss[field] = newVal ? 1 : 0
  try {
    await api.updateBoss(boss.encrypt_boss_id, { [field]: newVal })
  } catch (e) {
    boss[field] = newVal ? 0 : 1
  }
}

function avatarSrc(url) {
  if (!url) return ''
  if (url.startsWith('http')) return url
  return '/avatar/' + url
}

function fmtDate(ts) {
  if (!ts) return '-'
  return new Date(ts).toLocaleDateString('zh-CN')
}

onMounted(fetchData)
</script>
