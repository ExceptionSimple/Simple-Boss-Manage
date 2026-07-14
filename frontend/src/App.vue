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
    <el-container>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import { DataBoard, List, PieChart, Setting, Bell, Document, DArrowLeft, DArrowRight } from '@element-plus/icons-vue'
const route = useRoute()
const collapsed = ref(false)
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
.el-main { background: #f0f2f5; }
</style>
