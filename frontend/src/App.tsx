import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import RequireAuth from '@/layouts/RequireAuth'
import WorkbenchLayout from '@/layouts/WorkbenchLayout'
import AuthPage from '@/pages/AuthPage'
import CandidatesPage from '@/pages/CandidatesPage'
import CreatePage from '@/pages/CreatePage'
import LandingPage from '@/pages/LandingPage'
import PlaceholderPage from '@/pages/PlaceholderPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* 公开页：落地页与认证页 */}
        <Route path="/" element={<LandingPage />} />
        <Route path="/auth" element={<AuthPage />} />

        {/* 受保护路由：守卫在外层统一拦截 */}
        <Route element={<RequireAuth />}>
          {/* 工作台：嵌套在左侧导航布局内 */}
          <Route element={<WorkbenchLayout />}>
            <Route path="/create" element={<CreatePage />} />
            <Route path="/candidates/:runId" element={<CandidatesPage />} />
            <Route
              path="/editor"
              element={<PlaceholderPage title="编辑器" description="功能开发中" />}
            />
            <Route
              path="/batch"
              element={<PlaceholderPage title="批量处理" description="功能开发中" />}
            />
          </Route>

          {/* 独立页面：不在工作台布局内 */}
          <Route
            path="/marketing"
            element={<PlaceholderPage title="营销物料" description="功能开发中" />}
          />
        </Route>

        {/* 未知路由一律回到落地页 */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
