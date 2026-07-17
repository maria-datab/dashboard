/**
 * Vue application entry — mounts App.vue on #app.
 */
import { createApp } from 'vue'
import '@dashboard/shared/styles/tokens.css'
import '@/styles/app.css'
import App from './App.vue'

createApp(App).mount('#app')
