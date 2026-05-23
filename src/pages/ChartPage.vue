<script setup>
import { useMoneyStore } from '../stores/money.js'

const store = useMoneyStore()
</script>

<template>
  <div class="p-3">
    <section class="panel">
      <span class="panel-title">月支出趨勢</span>
      <div class="text-[13px] text-zinc-500 py-4">
        待實作：Chart.js 折線圖，X 軸為月份，Y 軸為支出金額（現金 + 信用卡）。
      </div>
      <div class="text-[12px] text-zinc-400">資料筆數：{{ store.transactions.length }}</div>
    </section>
  </div>
</template>
