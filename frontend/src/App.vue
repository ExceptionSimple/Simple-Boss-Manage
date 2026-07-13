<template>
  <el-container class="app-container">
    <el-aside width="200px" class="app-aside">
      <div class="logo">BOSS 管理</div>
      <el-menu
        :default-active="route.path"
        router
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#10b981"
      >
        <el-menu-item index="/">
          <el-icon><DataBoard /></el-icon>
          <span>概览</span>
        </el-menu-item>
        <el-menu-item index="/bosses">
          <el-icon><List /></el-icon>
          <span>投递列表</span>
        </el-menu-item>
        <el-menu-item index="/reminders">
          <el-icon><Bell /></el-icon>
          <span>消息提醒</span>
        </el-menu-item>
        <el-menu-item index="/reports">
          <el-icon><Document /></el-icon>
          <span>生成报告</span>
        </el-menu-item>
        <el-menu-item index="/stats">
          <el-icon><PieChart /></el-icon>
          <span>统计分析</span>
        </el-menu-item>
        <el-menu-item index="/settings">
          <el-icon><Setting /></el-icon>
          <span>设置</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { useRoute } from 'vue-router'
import { DataBoard, List, PieChart, Setting, Bell, Document } from '@element-plus/icons-vue'
const route = useRoute()
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
a { color: inherit; text-decoration: none; }
.app-container { height: 100vh; }
.app-aside { background: #304156; overflow-y: auto; }
.logo { color: #fff; font-size: 18px; font-weight: 700; text-align: center; padding: 20px 0; border-bottom: 1px solid rgba(255,255,255,.1); margin-bottom: 8px; }
.el-main { background: #f0f2f5; }
</style>
