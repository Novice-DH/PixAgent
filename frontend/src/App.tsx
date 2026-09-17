import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import WorkbenchLayout from '@/layouts/WorkbenchLayout'
import LandingPage from '@/pages/LandingPage'
import PlaceholderPage from '@/pages/PlaceholderPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />

        {/* 工作台：嵌套在左侧导航布局内 */}
        <Route element={<WorkbenchLayout />}>
          <Route
            path="/create"
            element={<PlaceholderPage title="创作" description="一句话生成商品图，后续期次实现。" />}
          />
          <Route
            path="/editor"
            element={<PlaceholderPage title="编辑器" description="画布编辑与图层操作，后续期次实现。" />}
          />
          <Route
            path="/batch"
            element={<PlaceholderPage title="批量处理" description="批量出图与多尺寸导出，后续期次实现。" />}
          />
        </Route>

        {/* 独立页面：不在工作台布局内 */}
        <Route
          path="/candidates"
          element={<PlaceholderPage title="候选" description="候选图挑选，后续期次实现。" />}
        />
        <Route
          path="/marketing"
          element={<PlaceholderPage title="营销物料" description="营销尺寸导出，后续期次实现。" />}
        />

        {/* 未知路由一律回到落地页 */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
