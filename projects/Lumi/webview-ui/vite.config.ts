import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    // [경로 수정됨] 출력 경로를 'webview-ui/dist'로 단순화
    outDir: 'dist',
    rollupOptions: {
      output: {
        entryFileNames: `assets/[name].js`,
        chunkFileNames: `assets/[name].js`,
        assetFileNames: `assets/[name].[ext]`
      }
    }
  },
  // VSCode 웹뷰는 상대 경로에 문제가 있을 수 있으므로 base를 './'로 설정
  base: './' 
})