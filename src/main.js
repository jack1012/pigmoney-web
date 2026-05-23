import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { ModuleRegistry, AllCommunityModule } from 'ag-grid-community'
import './style.css'
import App from './App.vue'

ModuleRegistry.registerModules([AllCommunityModule])

createApp(App).use(createPinia()).mount('#app')
