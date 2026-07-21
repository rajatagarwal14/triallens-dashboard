import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { SearchProvider } from '@/context/SearchContext'
import { Sidebar } from '@/components/Layout/Sidebar'
import { DiscoveryPage } from '@/pages/DiscoveryPage'
import { LandscapePage } from '@/pages/LandscapePage'
import { CompetitionPage } from '@/pages/CompetitionPage'
import { ResearchPage } from '@/pages/ResearchPage'
import { GeoPage } from '@/pages/GeoPage'
import { SitesPage } from '@/pages/SitesPage'
import { ProtocolPage } from '@/pages/ProtocolPage'

const pageVariants = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.22, ease: 'easeOut' } },
  exit:    { opacity: 0, y: -6, transition: { duration: 0.15 } },
}

function PageWrapper({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      variants={pageVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      className="flex flex-col h-full"
    >
      {children}
    </motion.div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <SearchProvider>
      <div className="flex h-screen overflow-hidden bg-iq-bg">
        <Sidebar />
        <main className="flex-1 overflow-hidden flex flex-col min-w-0">
          <AnimatePresence mode="wait">
            <Routes>
              <Route path="/" element={<PageWrapper><DiscoveryPage /></PageWrapper>} />
              <Route path="/landscape" element={<PageWrapper><LandscapePage /></PageWrapper>} />
              <Route path="/competition" element={<PageWrapper><CompetitionPage /></PageWrapper>} />
              <Route path="/research" element={<PageWrapper><ResearchPage /></PageWrapper>} />
              <Route path="/geo" element={<PageWrapper><GeoPage /></PageWrapper>} />
              <Route path="/sites" element={<PageWrapper><SitesPage /></PageWrapper>} />
              <Route path="/protocol" element={<PageWrapper><ProtocolPage /></PageWrapper>} />
              <Route path="/protocol/:nctId" element={<PageWrapper><ProtocolPage /></PageWrapper>} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </AnimatePresence>
        </main>
      </div>
      </SearchProvider>
    </BrowserRouter>
  )
}
