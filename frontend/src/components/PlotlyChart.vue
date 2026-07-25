<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import Plotly from "plotly.js-basic-dist-min";

type PlotlyValue = string | number | boolean | null | PlotlyValue[] | {
  [key: string]: PlotlyValue;
};
type PlotlyObject = Record<string, PlotlyValue>;

const props = defineProps<{
  data: PlotlyObject[];
  layout: PlotlyObject;
}>();

const chart = ref<HTMLElement | null>(null);

async function render() {
  await nextTick();
  if (!chart.value) return;
  await Plotly.react(chart.value, props.data, props.layout, {
    responsive: true,
    displaylogo: false,
    displayModeBar: false,
  });
}

watch(() => [props.data, props.layout], render, { deep: true });
onMounted(render);
onBeforeUnmount(() => {
  if (chart.value) Plotly.purge(chart.value);
});
</script>

<template>
  <div ref="chart" class="plotly-chart" />
</template>

