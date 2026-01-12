import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './layout/Layout';
import LandingPage from './pages/LandingPage';
import InputPage from './pages/InputPage';
import OverviewPage from './pages/OverviewPage';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<LandingPage />} />
          <Route path="input" element={<InputPage />} />
          <Route path="overview" element={<OverviewPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
