import { createApp } from 'vue'
import App from './App.vue'
import router from './router.js'
import './assets/base.css'
import {focusTrap} from './directives/focusTrap.js'

createApp(App).use(router).directive('focus-trap',focusTrap).mount('#app')
