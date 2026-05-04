import React, { useEffect, useState } from 'react';
import { aiClassifyEtf, aiClassifyInstrument, getCategories, getEtfAllocations, listInstrumentProfiles, replaceEtfAllocations, upsertInstrumentProfile } from '../../api_instrument_profiles';

export default function InstrumentProfilesPage() {
  const [profiles, setProfiles] = useState<any[]>([]);
  const [selected, setSelected] = useState<any | null>(null);
  const [sectors, setSectors] = useState<any[]>([]);
  const [countries, setCountries] = useState<any[]>([]);
  const [allocations, setAllocations] = useState<any[]>([]);
  const [etfText, setEtfText] = useState('');
  const [suggestion, setSuggestion] = useState<any | null>(null);

  const load = async () => {
    const [p, s, c] = await Promise.all([listInstrumentProfiles(), getCategories('SECTOR'), getCategories('COUNTRY')]);
    setProfiles(p || []); setSectors(s || []); setCountries(c || []);
  };
  useEffect(() => { void load(); }, []);
  useEffect(() => { if (selected?.instrument_type === 'ETF') void getEtfAllocations(selected.ticker).then((r:any)=>setAllocations(r||[])); }, [selected]);

  return <div className='p-4 space-y-4'>
    <h1 className='text-xl font-semibold'>Instrument Profiles</h1>
    <table className='w-full text-sm border'><thead><tr><th>Ticker</th><th>Type</th><th>Sector</th><th>Country</th><th>Status</th><th>Actions</th></tr></thead>
      <tbody>{profiles.map((p)=><tr key={p.ticker} className='border-t'><td>{p.ticker}</td><td>{p.instrument_type}</td><td>{p.sector_name}</td><td>{p.country_name}</td><td className={p.status!=='verified'?'text-amber-600 font-medium':''}>{p.status}</td><td><button onClick={()=>setSelected({...p})}>Edit</button></td></tr>)}</tbody></table>
    {selected && <div className='border p-3 space-y-2'>
      <h2 className='font-medium'>{selected.ticker}</h2>
      <div className='flex gap-2'>
        <select value={selected.instrument_type} onChange={(e)=>setSelected({...selected, instrument_type:e.target.value})}><option>STOCK</option><option>ETF</option></select>
        <select value={selected.sector_name||''} onChange={(e)=>setSelected({...selected, sector_name:e.target.value})}>{sectors.map(s=><option key={s.id}>{s.name}</option>)}</select>
        <select value={selected.country_name||''} onChange={(e)=>setSelected({...selected, country_name:e.target.value})}>{countries.map(c=><option key={c.id}>{c.name}</option>)}</select>
        <button onClick={async()=>setSuggestion(await aiClassifyInstrument(selected.ticker,{name:selected.ticker,description:''}))}>AI Suggest</button>
        <button onClick={async()=>{await upsertInstrumentProfile({...selected, source:'manual', status:'verified'}); await load();}}>Save</button>
      </div>
      {suggestion && <pre className='bg-gray-100 p-2 text-xs overflow-auto'>{JSON.stringify(suggestion,null,2)}</pre>}
      {selected.instrument_type==='ETF' && <div className='space-y-2'>
        <textarea className='w-full border p-2' value={etfText} onChange={(e)=>setEtfText(e.target.value)} placeholder='Paste ETF breakdown text' />
        <button onClick={async()=>{const r:any=await aiClassifyEtf(selected.ticker, etfText); setSuggestion(r); setAllocations(r.allocations||[]);}}>Generate from AI</button>
        <table className='w-full text-sm border'><thead><tr><th>Type</th><th>Category</th><th>Weight %</th></tr></thead><tbody>{allocations.map((a,idx)=><tr key={idx}><td>{a.type}</td><td><input value={a.category_name||a.category_name} onChange={(e)=>{const n=[...allocations];n[idx]={...n[idx],category_name:e.target.value};setAllocations(n);}}/></td><td><input type='number' value={a.weight} onChange={(e)=>{const n=[...allocations];n[idx]={...n[idx],weight:Number(e.target.value)};setAllocations(n);}}/></td></tr>)}</tbody></table>
        <button onClick={async()=>{await replaceEtfAllocations(selected.ticker, allocations);}}>Save ETF Allocations</button>
      </div>}
    </div>}
  </div>;
}
