import { reactive, computed } from 'vue'
import { api, setMilestoneId } from '../api'

const STORAGE_KEY = 'bm_milestone_id'

export const milestoneStore = reactive({
  items: [],
  currentId: null,
  loaded: false,
})

export const currentMilestone = computed(() =>
  milestoneStore.items.find(m => m.id === milestoneStore.currentId) || null
)

export const isReadonly = computed(() =>
  !!currentMilestone.value && currentMilestone.value.status !== 'active'
)

function readSavedId() {
  try {
    return Number(localStorage.getItem(STORAGE_KEY)) || null
  } catch (e) {
    return null
  }
}

export function selectMilestone(id) {
  milestoneStore.currentId = id
  setMilestoneId(id)
  try {
    if (id) localStorage.setItem(STORAGE_KEY, String(id))
    else localStorage.removeItem(STORAGE_KEY)
  } catch (e) { /* ignore */ }
}

export async function loadMilestones() {
  const r = await api.listMilestones()
  milestoneStore.items = r.items || []
  const saved = readSavedId()
  let target = milestoneStore.items.find(m => m.id === saved)
  if (!target) target = milestoneStore.items.find(m => m.status === 'active')
  if (!target) target = milestoneStore.items[milestoneStore.items.length - 1]
  selectMilestone(target ? target.id : null)
  milestoneStore.loaded = true
}

export async function createMilestone() {
  const created = await api.createMilestone()
  await loadMilestones()
  selectMilestone(created.id)
  return created
}

export async function saveCurrentMilestone() {
  const cur = currentMilestone.value
  if (!cur) return null
  await api.saveMilestone(cur.id)
  const keep = cur.id
  await loadMilestones()
  selectMilestone(keep)
  return cur
}
