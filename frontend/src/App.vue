<template>
  <el-container class="app-container">
    <el-aside :width="collapsed ? '64px' : '200px'" class="app-aside" :class="{ collapsed }">
      <div class="logo">{{ collapsed ? 'BM' : 'BOSS 管理' }}</div>
      <el-menu
        :default-active="route.path"
        router
        :collapse="collapsed"
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#10b981"
      >
        <el-menu-item index="/">
          <el-icon><DataBoard /></el-icon>
          <template #title>概览</template>
        </el-menu-item>
        <el-menu-item index="/bosses">
          <el-icon><List /></el-icon>
          <template #title>投递列表</template>
        </el-menu-item>
        <el-menu-item index="/reminders">
          <el-icon><Bell /></el-icon>
          <template #title>消息提醒</template>
        </el-menu-item>
        <el-menu-item index="/reports">
          <el-icon><Document /></el-icon>
          <template #title>生成报告</template>
        </el-menu-item>
        <el-menu-item index="/stats">
          <el-icon><PieChart /></el-icon>
          <template #title>统计分析</template>
        </el-menu-item>
        <el-menu-item index="/settings">
          <el-icon><Setting /></el-icon>
          <template #title>设置</template>
        </el-menu-item>
      </el-menu>
      <div class="collapse-btn" @click="collapsed = !collapsed">
        <el-icon :size="18"><DArrowLeft v-if="!collapsed" /><DArrowRight v-else /></el-icon>
      </div>
    </el-aside>
    <el-container direction="vertical">
      <el-header class="app-header" height="56px">
        <div v-if="milestoneStore.loaded && milestoneStore.items.length" class="milestone-bar">
          <el-tag :type="isEditing ? 'success' : 'info'" size="small">
            {{ isEditing ? '编辑中' : '已保存' }}
          </el-tag>
          <el-select v-model="selectedId" size="small" style="width: 190px;">
            <el-option
              v-for="m in milestoneStore.items"
              :key="m.id"
              :label="`${m.name}${m.status === 'active' ? '（编辑中）' : '（已保存）'}`"
              :value="m.id"
            />
          </el-select>
          <el-button size="small" type="primary" :disabled="!isEditing" :loading="saving" @click="handleSave">
            保存里程碑
          </el-button>
          <el-button size="small" :loading="creating" @click="handleCreate">新建里程碑</el-button>
        </div>
        <div v-else-if="milestoneStore.loaded" class="milestone-bar">
          <span class="hint">还没有里程碑</span>
          <el-button size="small" type="primary" :loading="creating" @click="handleCreate">创建第一个里程碑</el-button>
        </div>
      </el-header>
      <el-main>
        <div v-if="!milestoneStore.loaded" class="loading-state">加载中...</div>
        <div v-else-if="!milestoneStore.items.length" class="empty-state">
          <h2>欢迎使用 BOSS 管理</h2>
          <p>请先创建一个里程碑，之后同步和编辑的数据都会归属到这个里程碑。</p>
          <el-button type="primary" size="large" :loading="creating" @click="handleCreate">创建 M1</el-button>
        </div>
        <template v-else>
          <el-alert
            v-if="isReadonly"
            :title="readonlyText"
            type="info"
            :closable="false"
            show-icon
            class="readonly-alert"
          />
          <router-view :key="milestoneStore.currentId" />
        </template>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { DataBoard, List, PieChart, Setting, Bell, Document, DArrowLeft, DArrowRight } from '@element-plus/icons-vue'
import {
  milestoneStore, currentMilestone, isReadonly,
  loadMilestones, selectMilestone, createMilestone, saveCurrentMilestone,
} from './store/milestone'

const route = useRoute()
const collapsed = ref(false)
const creating = ref(false)
const saving = ref(false)

const selectedId = computed({
  get: () => milestoneStore.currentId,
  set: (id) => selectMilestone(id),
})
const isEditing = computed(() => currentMilestone.value?.status === 'active')
const readonlyText = computed(() => {
  const m = currentMilestone.value
  if (!m) return ''
  const at = m.frozen_at ? `（${m.frozen_at} 保存）` : ''
  return `正在查看 ${m.name}${at}，当前为只读模式，不能修改数据`
})

async function handleCreate() {
  if (milestoneStore.items.some(m => m.status === 'active')) {
    try {
      await ElMessageBox.confirm(
        '当前有正在编辑的里程碑，新建时会先自动保存它。是否继续？',
        '新建里程碑',
        { type: 'warning', confirmButtonText: '继续', cancelButtonText: '取消' },
      )
    } catch (e) {
      return
    }
  }
  creating.value = true
  try {
    const m = await createMilestone()
    ElMessage.success(`已创建 ${m.name}`)
  } catch (e) {
    ElMessage.error('创建失败: ' + e.message)
  } finally {
    creating.value = false
  }
}

async function handleSave() {
  if (!isEditing.value) return
  try {
    await ElMessageBox.confirm(
      `保存后 ${currentMilestone.value.name} 将变为只读，确定保存吗？`,
      '保存里程碑',
      { type: 'warning', confirmButtonText: '保存', cancelButtonText: '取消' },
    )
  } catch (e) {
    return
  }
  saving.value = true
  try {
    await saveCurrentMilestone()
    ElMessage.success('已保存')
  } catch (e) {
    ElMessage.error('保存失败: ' + e.message)
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  try {
    await loadMilestones()
  } catch (e) {
    ElMessage.error('加载里程碑失败: ' + e.message)
    milestoneStore.loaded = true
  }
})
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
a { color: inherit; text-decoration: none; }
.app-container { height: 100vh; }
.app-aside { background: #304156; overflow-y: auto; overflow-x: hidden; position: relative; transition: width 0.3s; }
.logo { color: #fff; font-size: 18px; font-weight: 700; text-align: center; padding: 20px 0; border-bottom: 1px solid rgba(255,255,255,.1); margin-bottom: 8px; white-space: nowrap; overflow: hidden; }
.collapsed .logo { font-size: 22px; }
.collapse-btn { position: absolute; bottom: 12px; width: 100%; text-align: center; color: #bfcbd9; cursor: pointer; padding: 6px 0; }
.collapse-btn:hover { background: rgba(255,255,255,.1); color: #fff; }
.app-aside .el-menu { border-right: none; }
.app-header { background: #fff; border-bottom: 1px solid #e5e7eb; display: flex; align-items: center; padding: 0 16px; }
.milestone-bar { display: flex; align-items: center; gap: 10px; width: 100%; }
.milestone-bar .hint { color: #9ca3af; font-size: 13px; }
.loading-state { padding: 60px; text-align: center; color: #9ca3af; }
.empty-state { max-width: 520px; margin: 80px auto; text-align: center; background: #fff; border-radius: 12px; padding: 40px; box-shadow: 0 1px 3px rgba(0,0,0,.06); }
.empty-state h2 { font-size: 22px; color: #1f2937; margin-bottom: 10px; }
.empty-state p { color: #6b7280; font-size: 14px; margin-bottom: 22px; }
.readonly-alert { margin-bottom: 14px; }
.el-main { background: #f0f2f5; }
</style>
