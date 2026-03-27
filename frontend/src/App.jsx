import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { PrivateRoute, AdminRoute, AnalystRoute } from './components/PrivateRoute'
import Layout       from './components/Layout'
import Login        from './pages/Login'
import Dashboard    from './pages/Dashboard'
import Entities     from './pages/Entities'
import EntityDetail from './pages/EntityDetail'
import Mentions     from './pages/Mentions'
import Alerts       from './pages/Alerts'
import AlertRules   from './pages/AlertRules'
import Reports      from './pages/Reports'
import Users        from './pages/Users'
import Profile      from './pages/Profile'
import Chat         from './pages/Chat'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Pública */}
        <Route path="/login" element={<Login />} />

        {/* Privadas — requieren auth */}
        <Route element={<PrivateRoute />}>
          <Route element={<Layout />}>
            <Route path="/"                  element={<Dashboard />} />
            <Route path="/entities"          element={<Entities />} />
            <Route path="/entities/:id"      element={<EntityDetail />} />
            <Route path="/mentions"          element={<Mentions />} />
            <Route path="/alerts"            element={<Alerts />} />
            <Route path="/reports"           element={<Reports />} />
            <Route path="/chat"              element={<Chat />} />
            <Route path="/profile"           element={<Profile />} />

            {/* Solo analyst/admin */}
            <Route element={<AnalystRoute />}>
              <Route path="/settings/rules"  element={<AlertRules />} />
            </Route>

            {/* Solo admin */}
            <Route element={<AdminRoute />}>
              <Route path="/admin/users"     element={<Users />} />
            </Route>
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
