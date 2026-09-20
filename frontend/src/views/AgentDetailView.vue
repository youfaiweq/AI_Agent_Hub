<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { approveAgentRun, getAgent, listAgentRuns, rejectAgentRun, runAgent } from '@/api/agents'
import { getApiErrorMessage } from '@/api/http'
import type { Agent, AgentRun } from '@/types/agent'

const route = useRoute()
const router = useRouter()
const agentId = computed(() => String(route.params.id))
const agent = ref<Agent | null>(null)
const runs = ref<AgentRun[]>([])
const message = ref('')
const loading = ref(false)
const running = ref(false)
const error = ref<string | null>(null)
const approvalBusy = ref(false)

async function load(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    const [loadedAgent, loadedRuns] = await Promise.all([getAgent(agentId.value), listAgentRuns(agentId.value)])
    agent.value = loadedAgent
    runs.value = loadedRuns.items
  } catch (requestError) {
    error.value = getApiErrorMessage(requestError, 'Unable to load this Agent.')
  } finally {
    loading.value = false
  }
}

async function execute(): Promise<void> {
  if (!message.value.trim()) return
  running.value = true
  error.value = null
  try {
    const run = await runAgent(agentId.value, message.value)
    runs.value = [run, ...runs.value]
    message.value = ''
    ElMessage.success(run.status === 'completed' ? 'Agent run completed.' : `Agent run ${run.status}.`)
  } catch (requestError) {
    error.value = getApiErrorMessage(requestError, 'Agent run failed.')
  } finally {
    running.value = false
  }
}

async function decideApproval(approve: boolean): Promise<void> {
  const pending = runs.value.find((item) => item.status === 'waiting_approval' && item.approval?.status === 'pending')
  if (!pending) return
  approvalBusy.value = true
  error.value = null
  try {
    const updated = approve
      ? await approveAgentRun(agentId.value, pending.id)
      : await rejectAgentRun(agentId.value, pending.id)
    runs.value = runs.value.map((item) => (item.id === updated.id ? updated : item))
    ElMessage.success(approve ? 'Approval accepted and run resumed.' : 'Approval rejected.')
  } catch (requestError) {
    error.value = getApiErrorMessage(requestError, 'Unable to decide this approval.')
  } finally {
    approvalBusy.value = false
  }
}

function statusType(status: string): 'success' | 'warning' | 'danger' | 'info' {
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'running' || status === 'pending') return 'warning'
  return 'info'
}

onMounted(() => void load())
</script>

<template>
  <div class="workspace-page">
    <div class="breadcrumb-row">
      <el-button link @click="router.push('/agents')">← Agents</el-button>
    </div>
    <el-alert v-if="error" :title="error" type="error" show-icon />
    <section v-if="agent" class="detail-hero">
      <div>
        <p class="page-eyebrow">Agent runtime</p>
        <h2>{{ agent.name }}</h2>
        <p class="page-copy">{{ agent.description || 'Bounded non-streaming Agent runtime.' }}</p>
      </div>
      <div class="detail-actions">
        <el-tag type="info">{{ agent.model_name }}</el-tag>
      </div>
    </section>

    <el-card shadow="never" class="content-card agent-run-card" v-loading="loading">
      <div class="section-heading compact-heading">
        <div>
          <p class="page-eyebrow">Run Agent</p>
          <h3>Ask a question</h3>
        </div>
        <span class="table-secondary">Non-streaming · max {{ agent?.max_steps }} steps · {{ agent?.timeout_seconds }}s timeout</span>
      </div>
      <el-input v-model="message" type="textarea" :rows="4" maxlength="20000" show-word-limit placeholder="Ask the Agent to use its configured tools" />
      <div class="run-actions">
        <el-button type="primary" :loading="running" :disabled="!message.trim()" @click="execute">Run Agent</el-button>
      </div>
    </el-card>

    <el-card
      v-if="runs.some((item) => item.status === 'waiting_approval' && item.approval?.status === 'pending')"
      shadow="never"
      class="content-card approval-card"
    >
      <div class="section-heading compact-heading">
        <div>
          <p class="page-eyebrow">Human approval required</p>
          <h3>Review dangerous Tool call</h3>
        </div>
        <el-tag type="warning">Waiting</el-tag>
      </div>
      <template v-for="run in runs" :key="`approval-${run.id}`">
        <div v-if="run.status === 'waiting_approval' && run.approval?.status === 'pending'">
          <p class="page-copy">Tool <strong>{{ run.approval.tool_name }}</strong> requested an external side effect.</p>
          <pre class="approval-arguments">{{ JSON.stringify(run.approval.arguments, null, 2) }}</pre>
          <div class="run-actions">
            <el-button :loading="approvalBusy" type="danger" @click="decideApproval(false)">Reject</el-button>
            <el-button :loading="approvalBusy" type="primary" @click="decideApproval(true)">Approve and resume</el-button>
          </div>
        </div>
      </template>
    </el-card>

    <el-card shadow="never" class="content-card">
      <div class="section-heading compact-heading">
        <div>
          <p class="page-eyebrow">Observability foundation</p>
          <h3>Run history <span class="count-badge">{{ runs.length }}</span></h3>
        </div>
      </div>
      <el-empty v-if="runs.length === 0" description="No Agent runs yet" />
      <el-table v-else :data="runs">
        <el-table-column label="Input" min-width="260">
          <template #default="{ row }">
            <div class="table-primary">{{ row.input_text }}</div>
            <div v-if="row.answer" class="table-secondary agent-answer">{{ row.answer }}</div>
            <div v-if="row.error_message" class="table-secondary agent-error">{{ row.error_message }}</div>
          </template>
        </el-table-column>
        <el-table-column label="Status" width="125">
          <template #default="{ row }"><el-tag :type="statusType(row.status)" size="small">{{ row.status }}</el-tag></template>
        </el-table-column>
        <el-table-column label="Steps" width="90">
          <template #default="{ row }">{{ row.step_count }}/{{ row.max_steps }}</template>
        </el-table-column>
        <el-table-column label="Tools" width="100">
          <template #default="{ row }">{{ row.tool_calls.length }}</template>
        </el-table-column>
        <el-table-column label="Started" width="190">
          <template #default="{ row }">{{ row.created_at ? new Date(row.created_at).toLocaleString() : '—' }}</template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>
