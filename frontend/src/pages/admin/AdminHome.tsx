import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpRight, ListTree, PiggyBank, ShieldCheck, SlidersHorizontal, Wrench } from 'lucide-react';

const groups = [
  {
    title: 'Dane i konfiguracja',
    description: 'Zarządzaj strukturą portfeli i powiązaniami symboli.',
    tiles: [
      { title: 'Narzędzia portfeli', description: 'Importuj dane i zarządzaj portfelami.', to: '/admin/portfolios', icon: ListTree },
      { title: 'Kopie bezpieczeństwa', description: 'Sprawdź ostatnią kopię, zapisz nową lub przywróć bazę.', to: '/admin/backups', icon: ShieldCheck },
      { title: 'Mapowanie symboli', description: 'Sprawdź powiązania nazw aktywów z tickerami i walutami.', to: '/admin/symbol-mapping', icon: SlidersHorizontal },
    ],
  },
  {
    title: 'Diagnostyka i naprawa',
    description: 'Sprawdź jakość danych i uruchom potrzebne operacje serwisowe.',
    tiles: [
      { title: 'Audyt spójności', description: 'Wykryj rozbieżności między portfelami i transakcjami.', to: '/admin/consistency-audit', icon: ShieldCheck },
      { title: 'Audyt cen', description: 'Sprawdź kompletność i jakość historii cen.', to: '/admin/price-history-audit', icon: Wrench },
      { title: 'Serwis budżetu', description: 'Wykonaj operacje naprawcze dotyczące danych budżetu.', to: '/admin/budget', icon: PiggyBank },
    ],
  },
];

const AdminHome: React.FC = () => (
  <div className="page-stack">
    <div className="page-heading">
      <p className="page-eyebrow">Ustawienia i diagnostyka</p>
      <h1 className="text-2xl font-semibold text-gray-900">Centrum narzędzi</h1>
      <p className="mt-2 max-w-2xl text-sm text-gray-600">Wybierz obszar, który chcesz skonfigurować lub sprawdzić.</p>
    </div>
    {groups.map(group => (
      <section key={group.title} aria-label={group.title}>
        <div className="mb-5">
          <h2 className="text-lg font-semibold text-gray-900">{group.title}</h2>
          <p className="mt-1 text-sm text-gray-600">{group.description}</p>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {group.tiles.map(tile => {
            const Icon = tile.icon;
            return (
              <Link key={tile.to} to={tile.to} className="group surface-card flex min-h-36 flex-col justify-between p-5 transition-colors hover:bg-[var(--surface-muted)]">
                <div className="flex items-start justify-between gap-4">
                  <span className="rounded-xl bg-[var(--surface-muted)] p-2.5 text-[var(--accent)]"><Icon className="h-5 w-5" /></span>
                  <ArrowUpRight className="h-4 w-4 text-[var(--muted)] transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" aria-hidden="true" />
                </div>
                <div className="mt-4">
                  <h3 className="font-semibold text-gray-900">{tile.title}</h3>
                  <p className="mt-1 text-sm text-gray-600">{tile.description}</p>
                </div>
              </Link>
            );
          })}
        </div>
      </section>
    ))}
  </div>
);

export default AdminHome;
