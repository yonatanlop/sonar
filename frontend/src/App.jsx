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
import Platforms       from './pages/Platforms'
import TwitterExplorer  from './pages/TwitterExplorer'
import YoutubeExplorer  from './pages/YoutubeExplorer'
import FacebookExplorer  from './pages/FacebookExplorer'
import InstagramExplorer from './pages/InstagramExplorer'
import TiktokExplorer    from './pages/TiktokExplorer'
import Compare         from './pages/Compare'
import ResponseTool    from './pages/ResponseTool'
import MentionInbox    from './pages/MentionInbox'
import Audit                from './pages/Audit'
import Rizoma               from './pages/Rizoma'
import LegalInbox           from './pages/LegalInbox'
import TwitterKeywordSearch from './pages/TwitterKeywordSearch'
import MediaSearch          from './pages/MediaSearch'
import ReplyAccounts       from './pages/ReplyAccounts'
import TopicKeywords       from './pages/TopicKeywords'
import FacebookGroups      from './pages/FacebookGroups'
import Cases               from './pages/Cases'

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
            <Route path="/platforms"          element={<Platforms />} />
            <Route path="/twitter-explorer"  element={<TwitterExplorer />} />
            <Route path="/youtube-explorer"  element={<YoutubeExplorer />} />
            <Route path="/facebook-explorer"  element={<FacebookExplorer />} />
            <Route path="/instagram-explorer" element={<InstagramExplorer />} />
            <Route path="/tiktok-explorer"    element={<TiktokExplorer />} />
            <Route path="/compare"           element={<Compare />} />
            <Route path="/response-tool"     element={<ResponseTool />} />
            <Route path="/inbox"             element={<MentionInbox />} />
            <Route path="/rizoma"            element={<Rizoma />} />
            <Route path="/legal"             element={<LegalInbox />} />
            <Route path="/profile"           element={<Profile />} />
            <Route path="/media-search"      element={<MediaSearch />} />

            {/* Solo analyst/admin */}
            <Route element={<AnalystRoute />}>
              <Route path="/settings/rules"  element={<AlertRules />} />
              <Route path="/topic-keywords"  element={<TopicKeywords />} />
              <Route path="/grupos"          element={<FacebookGroups />} />
            </Route>

            {/* Solo admin */}
            <Route element={<AdminRoute />}>
              <Route path="/admin/users"           element={<Users />} />
              <Route path="/admin/audit"           element={<Audit />} />
              <Route path="/admin/twitter-search"  element={<TwitterKeywordSearch />} />
              <Route path="/admin/reply-accounts"  element={<ReplyAccounts />} />
              {/* Seguimiento a caso — hoy solo admin. Para abrir a analistas:
                  mover esta ruta a <AnalystRoute> y ajustar CASE_MANAGER_ROLES en el backend. */}
              <Route path="/cases"                 element={<Cases />} />
            </Route>
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
