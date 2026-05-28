<script setup lang="ts">
const props = withDefaults(
    defineProps<{
        loading?: boolean
        disabled?: boolean
    }>(),
    {
        loading: false,
        disabled: false,
    },
)

const emit = defineEmits<{
    confirm: []
}>()

function handleClick() {
    emit('confirm')
}
</script>

<template>
    <el-button
        type="danger"
        size="small"
        :loading="loading"
        :disabled="disabled"
        @click="handleClick"
    >
        <slot>删除</slot>
    </el-button>
</template>
