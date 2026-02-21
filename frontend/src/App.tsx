/**
 * App — root component with layout shell and client-side routing.
 *
 * Layout: Sidebar (left, fixed width) + main content area (scrollable right).
 * Routes:
 *   /              → Dashboard
 *   /trades        → Trades list
 *   /decisions     → Decisions list
 *   /decisions/:id → Decision detail
 */

import { Routes, Route, Navigate } from 'react-router-dom'
import { Sidebar } from '@/components/Sidebar'
import { Dashboard } from '@/pages/Dashboard'
import { Trades } from '@/pages/Trades'
import { Decisions } from '@/pages/Decisions'
import { DecisionDetail } from '@/pages/DecisionDetail'
import { Backtest } from '@/pages/Backtest'

export function App() {
  return (
    <div
      className="min-h-screen bg-gray-900 text-gray-100 flex"
      style={{ minWidth: '1280px' }}
    >
      {/* Fixed-width sidebar navigation */}
      <Sidebar />

      {/* Scrollable content area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/trades" element={<Trades />} />
          <Route path="/decisions" element={<Decisions />} />
          <Route path="/decisions/:id" element={<DecisionDetail />} />
          <Route path="/backtest" element={<Backtest />} />
          {/* Catch-all redirect */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </div>
  )
}
