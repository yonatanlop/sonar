import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { PrivateRoute, AdminRoute, AnalystRoute } from './shared/components/PrivateRoute'
import Layout from './shared/components/Layout'

import Login          from './modules/identity/pages/Login'
import Profile        from './modules/identity/pages/Profile'
import Users          from './modules/identity/pages/Users'
import Dashboard      from './modules/dashboard/pages/Dashboard'
import Entities       from './modules/monitoring/pages/Entities'
import Platforms      from './modules/monitoring/pages/Platforms'
import Mentions       from './modules/collection/pages/Mentions'
import Alerts         from './modules/alerting/pages/Alerts'
import AlertRules     from './modules/alerting/pages/AlertRules'
import Intelligence   from './modules/intelligence/pages/Intelligence'
import Reports        from './modules/reporting/pages/Reports'
import LegalCases     from './modules/legal/pages/LegalCases'
import LegalCaseDetail from './modules/legal/pages/LegalCaseDetail'
import ActorMap       from './modules/actor_map/pages/ActorMap'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />

        <Route element={<PrivateRoute />}>
          <Route element={<Layout />}>
            <Route path="/"              element={<Dashboard />} />
            <Route path="/entities"      element={<Entities />} />
            <Route path="/platforms"     element={<Platforms />} />
            <Route path="/mentions"      element={<Mentions />} />
            <Route path="/alerts"        element={<Alerts />} />
            <Route path="/intelligence"  element={<Intelligence />} />
            <Route path="/reports"       element={<Reports />} />
            <Route path="/legal"         element={<LegalCases />} />
            <Route path="/legal/:id"     element={<LegalCaseDetail />} />
            <Route path="/actor-map"     element={<ActorMap />} />
            <Route path="/profile"       element={<Profile />} />

            <Route element={<AnalystRoute />}>
              <Route path="/settings/rules" element={<AlertRules />} />
            </Route>

            <Route element={<AdminRoute />}>
              <Route path="/admin/users" element={<Users />} />
            </Route>
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
