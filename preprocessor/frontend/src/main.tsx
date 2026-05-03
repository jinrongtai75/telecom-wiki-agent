import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ConfigProvider, theme } from 'antd'
import koKR from 'antd/locale/ko_KR'
import App from './App.tsx'

const { darkAlgorithm } = theme

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ConfigProvider
      locale={koKR}
      theme={{
        algorithm: darkAlgorithm,
        token: {
          colorPrimary: '#E6007E',
          colorBgContainer: '#1e1e35',
          colorBgElevated: '#252540',
          colorBgLayout: '#0f0f17',
          colorBorder: 'rgba(255,255,255,0.1)',
          colorBorderSecondary: 'rgba(255,255,255,0.06)',
          borderRadius: 8,
          fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Apple SD Gothic Neo', sans-serif",
        },
        components: {
          Layout: {
            siderBg: '#161622',
            bodyBg: '#0f0f17',
            headerBg: '#161622',
          },
          Button: {
            colorBgContainer: '#252540',
          },
          Modal: {
            contentBg: '#1e1e35',
            headerBg: '#1e1e35',
          },
        },
      }}
    >
      <App />
    </ConfigProvider>
  </StrictMode>,
)
