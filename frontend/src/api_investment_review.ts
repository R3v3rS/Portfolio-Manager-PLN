import {createApiClient} from './apiConfig';
const api=createApiClient('/portfolio');
export type InvestmentEvent={id:number;date:string;type:string;ticker?:string;quantity:number;price:number;total_value:number;realized_profit:number|null;strategy_name:string|null;remaining_quantity?:number;note_title?:string};
export type InstrumentReview={ticker:string;company_name:string|null;quantity:number;current_value:number|null;total_result:number|null;dividends:number;realized_profit:number;archived:boolean;price_basis:string|null;events:InvestmentEvent[]};
export type StrategyRow={id:number;name:string;archived:boolean;frozen:boolean;started_at:string|null;closed_at:string|null;starting_capital:number;additional_capital:number;value:number|null;result:number|null;return_percent:number|null;valuation_status:string;xirr_percent:number|null};
export const reviewApi={
 instrument:(id:number,ticker:string)=>api.get<InstrumentReview>(`/${id}/instrument-history`,{params:{ticker}}),
 strategies:(id:number)=>api.get<{parent_id:number;items:StrategyRow[]}>(`/${id}/strategy-comparison`),
 events:(id:number,from:string,to:string)=>api.get<{items:InvestmentEvent[];count:number;truncated:boolean}>(`/${id}/events`,{params:{from,to}}),
};
export const eventName:Record<string,string>={BUY:'Zakup',SELL:'Sprzedaż',DIVIDEND:'Dywidenda',INTEREST:'Odsetki',DEPOSIT:'Wpłata',WITHDRAW:'Wypłata',ASSET_IN:'Przeniesienie do',ASSET_OUT:'Przeniesienie z',JOURNAL:'Wpis dziennika'};
