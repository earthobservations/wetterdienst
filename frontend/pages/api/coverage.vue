<script setup lang="ts">
// forward to backend api
import { useRoute, useFetch } from '#imports'

const route = useRoute()

const data = useFetch('/api/coverage', {
    params: route.query,
    method: 'GET'
})
</script>
<template>
</template>