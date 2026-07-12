import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'
import BossList from '../views/BossList.vue'
import BossDetail from '../views/BossDetail.vue'
import Stats from '../views/Stats.vue'
import Settings from '../views/Settings.vue'

const routes = [
  { path: '/', name: 'Dashboard', component: Dashboard },
  { path: '/bosses', name: 'BossList', component: BossList },
  { path: '/bosses/:id', name: 'BossDetail', component: BossDetail, props: true },
  { path: '/stats', name: 'Stats', component: Stats },
  { path: '/settings', name: 'Settings', component: Settings },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
