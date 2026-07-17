import { createApp } from 'vue'
import '@dashboard/shared/styles/tokens.css'
import App from './App.vue'
import router from './router.js'

createApp(App).use(router).mount('#app')
