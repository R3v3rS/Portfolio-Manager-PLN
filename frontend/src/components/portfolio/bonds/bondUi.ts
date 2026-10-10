export const bondMoney=(n:number|null|undefined)=>n==null?'—':new Intl.NumberFormat('pl-PL',{style:'currency',currency:'PLN'}).format(n);
export const bondDate=(value:string|undefined|null)=>value?new Date(value+'T12:00:00').toLocaleDateString('pl-PL',{day:'numeric',month:'short',year:'numeric'}):'—';
export const bondToday=()=>new Date().toLocaleDateString('sv-SE');
export const bondPercent=(n:number)=>`${n.toLocaleString('pl-PL',{maximumFractionDigits:2})}%`;
export const kindLabels={OTS:'OTS · 3 miesiące',ROR:'ROR · 1 rok',DOR:'DOR · 2 lata',TOS:'TOS · 3 lata',COI:'COI · 4 lata',EDO:'EDO · 10 lat',ROS:'ROS · 6 lat',ROD:'ROD · 12 lat',CUSTOM:'Własna obligacja · stała stopa'};
