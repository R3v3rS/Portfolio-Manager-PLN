export function shortfallPeriods(points:{date:string;available:number}[],through:string){
  const result:{start:string;end:string;open:boolean}[]=[];
  let period:{start:string;end:string;open:boolean}|null=null;
  for(const point of points.filter(p=>p.date<=through)){
    if(point.available<0){if(!period)period={start:point.date,end:point.date,open:true};else period.end=point.date;}
    else if(period){period.open=false;result.push(period);period=null;}
  }
  if(period)result.push(period);
  return result;
}
