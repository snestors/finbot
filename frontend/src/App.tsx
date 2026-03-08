import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Layout from './components/layout/Layout';
import Dashboard from './pages/Dashboard';
import Chat from './pages/Chat';
import Gastos from './pages/Gastos';
import Cuentas from './pages/Cuentas';
import Tarjetas from './pages/Tarjetas';
import Deudas from './pages/Deudas';
import Cobros from './pages/Cobros';
import Presupuestos from './pages/Presupuestos';
import TipoCambio from './pages/TipoCambio';
import Config from './pages/Config';
import Consumos from './pages/Consumos';
import Analytics from './pages/Analytics';
import GastosFijos from './pages/GastosFijos';
import Logs from './pages/Logs';
import Login from './pages/Login';
import Panel from './pages/Panel';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 30_000,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/panel" element={<Panel />} />
          <Route element={<Layout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/chat" element={<Chat />} />
            <Route path="/gastos" element={<Gastos />} />
            <Route path="/cuentas" element={<Cuentas />} />
            <Route path="/tarjetas" element={<Tarjetas />} />
            <Route path="/deudas" element={<Deudas />} />
            <Route path="/cobros" element={<Cobros />} />
            <Route path="/consumos" element={<Consumos />} />
            <Route path="/presupuestos" element={<Presupuestos />} />
            <Route path="/tipo-cambio" element={<TipoCambio />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/gastos-fijos" element={<GastosFijos />} />
            <Route path="/logs" element={<Logs />} />
            <Route path="/config" element={<Config />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
