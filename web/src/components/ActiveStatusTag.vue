<script setup lang="ts">
import type { ActiveStatus } from '@/types/status'

const props = defineProps<{
    status: ActiveStatus
}>()
</script>

<template>
    <el-tag :type="props.status === 'ACTIVE' ? 'success' : 'info'">
        {{ props.status === 'ACTIVE' ? '启用' : '停用' }}
    </el-tag>
</template>
