export function PlanningMessages({error,notice}:{error:string;notice:string}){
  return <>{error&&<p role="alert" className="budget-feedback is-error">{error}</p>}{notice&&<p role="status" className="budget-feedback is-success">{notice}</p>}</>;
}
