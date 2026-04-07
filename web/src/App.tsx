import { Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "./components/layout";
import { KBDetailPage } from "./pages/kb-detail-page";
import { KBListPage } from "./pages/kb-list-page";
import { SearchPage } from "./pages/search-page";

export function App() {
  return (
    <AppLayout>
      <Routes>
        <Route path="/" element={<KBListPage />} />
        <Route path="/kbs" element={<KBListPage />} />
        <Route path="/kbs/:kbRef" element={<KBDetailPage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppLayout>
  );
}
