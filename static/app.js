import {state,el,listeners,changed,acceptPosition,addAlert,toast} from "./config.js";
import {initializeMap,renderMap,fitFleet,showFences,showTrace,clearTrace} from "./map.js";
import {initializePanels,renderPanels} from "./panels.js";
import {connect,disconnect,api,refreshCloudDemo} from "./live.js";
let routes=[],timer=null,tick=0;
function routePoint(route,step){const part=step/120,seg=Math.floor(part)%(route.length-1),f=part%1;return {lat:route[seg][0]+(route[seg+1][0]-route[seg][0])*f,lon:route[seg][1]+(route[seg+1][1]-route[seg][1])*f};}
function simulate() {
  if(state.mode!=="simulation"||state.paused)return;
  for(let i=0;i<state.vehicles.length;i++) {
    const v=state.vehicles[i],pos=routePoint(routes[i%routes.length],tick+i*37),prior=state.positions.get(v.id);
    let speed=Math.max(0,35+15*Math.sin(tick/9+i*.8));if(i===0&&tick%40>=15&&tick%40<=17)speed=92;
    const point={id:tick*12+i+1,vehicle_id:v.id,...pos,speed_kmh:Math.round(speed*10)/10,heading:(tick*2+i*30)%360,recorded_at:new Date().toISOString()};
    acceptPosition(point);
    if(speed>80&&(!prior||prior.speed_kmh<=80))addAlert({vehicle_id:v.id,kind:"speeding",recorded_at:point.recorded_at,details:{speed_kmh:point.speed_kmh,limit_kmh:80}});
    if(prior){const distance=p=>Math.hypot((p.lat-12.9716)*111320,(p.lon-77.5946)*108480);const before=distance(prior)<=1200,after=distance(point)<=1200;if(before!==after)addAlert({vehicle_id:v.id,kind:after?"geofence_enter":"geofence_exit",recorded_at:point.recorded_at,details:{geofence_name:"Central Bengaluru demo zone"}});}
  }tick++;changed();
}
function startSimulation() {
  disconnect();state.mode="simulation";state.paused=false;tick=0;state.token=null;state.sourceNote="Browser fixtures";state.vehicles=Array.from({length:12},(_,i)=>({id:i+1,name:`Fleet ${String(i+1).padStart(2,"0")}`,registration:`DEMO-${String(i+1).padStart(3,"0")}`,kind:["delivery","cab","bus"][i%3]}));state.selected=1;state.positions.clear();state.histories.clear();state.alerts=[];clearTrace();
  el("mode-name").textContent="Browser simulation";el("mode-subtitle").textContent="Synthetic GPS • no live backend";el("mode-dot").className="dot warning";el("source-explanation").textContent="This is sample data, not live vehicle telemetry. The public showcase runs in your browser. Connect a running backend to demonstrate FastAPI, PostgreSQL and Redis.";el("pipeline-status").textContent="Not connected";el("pipeline-note").textContent="Simulation bypasses this pipeline. Use Connect live API to test the real services.";el("return-demo").hidden=true;el("pause-simulation").hidden=false;el("pause-simulation").textContent="Pause simulation";el("map-context").textContent="Illustrative Bengaluru paths";el("connect-button").textContent="Connect live API";
  showFences([{name:"Central Bengaluru demo zone",lat:12.9716,lon:77.5946,radius_m:1200}]);simulate();fitFleet();
}
async function main() {
  initializeMap();initializePanels();listeners.add(()=>{renderPanels();renderMap();});
  state.onSelect=id=>{state.selected=id;clearTrace();changed();};
  try{const response=await fetch("demo/replay.json");if(!response.ok)throw new Error("Fixture load failed");routes=(await response.json()).routes;}catch{el("source-explanation").textContent="Sample data could not be loaded. Serve this folder over HTTP (not file://), or connect the live backend.";toast("Could not load sample routes.");return;}
  startSimulation();timer=setInterval(()=>{if(state.mode==="simulation"&&!state.paused)simulate();else changed();},1000);
  el("pause-simulation").addEventListener("click",()=>{state.paused=!state.paused;el("pause-simulation").textContent=state.paused?"Resume simulation":"Pause simulation";el("mode-subtitle").textContent=state.paused?"Paused • synthetic GPS data":"Synthetic GPS • no live backend";});
  el("return-demo").addEventListener("click",startSimulation);
  el("cloud-gps-button")?.addEventListener("click",async()=>{
    if(state.mode!=="live"||!state.cloudDemo)return;const button=el("cloud-gps-button");button.disabled=true;
    try{const stopping=state.cloudGPSRunning;await api(stopping?"/demo/stop":"/demo/start",{method:"POST",body:stopping?undefined:JSON.stringify({duration_seconds:300})});await refreshCloudDemo();toast(stopping?"Sample GPS stopped. Stored observations remain in PostgreSQL.":"Five-minute synthetic GPS session started through the real backend.");}catch(error){toast(error.message);}finally{button.disabled=false;}
  });
  el("show-history").addEventListener("click",async()=>{
    try{let points=state.histories.get(state.selected)||[];if(state.mode==="live"){const result=await api(`/vehicles/${state.selected}/positions?limit=200`);points=result.points;state.histories.set(state.selected,points);el("history-context").textContent=`${points.length} stored PostgreSQL observations${result.has_more?"; most recent 200 shown":""}. No map matching or fabricated traces.`;}else{el("history-context").textContent=`${points.length} synthetic browser observations. These are not persisted in PostgreSQL.`;}if(points.length<2){toast("Wait for two observed positions first.");return;}showTrace(points);changed();}catch(error){toast(error.message);}
  });
  el("nearest-button").addEventListener("click",async()=>{
    const point=state.positions.get(state.selected);if(!point){toast("No position available yet.");return;}
    try{if(state.mode==="live"){const result=await api(`/fleet/nearest?lat=${point.lat}&lon=${point.lon}&limit=5`);const text=result.positions.map(p=>`${state.vehicles.find(v=>v.id===p.vehicle_id)?.name||p.vehicle_id}: ${p.distance_m} m`).join("; ");toast(`${result.source_used}: ${text||"no fresh vehicles within 25 km"}`);}else{toast("Simulation only. Connect the backend to demonstrate Redis GEO nearest-vehicle queries and PostgreSQL fallback.");}}catch(error){toast(error.message);}
  });
  el("connect-button").addEventListener("click",()=>{el("api-origin").value=state.apiBase||(location.pathname.startsWith("/static/")?location.origin:"");el("login-user").value="admin";el("login-password").value="";el("connect-error").hidden=true;el("connect-dialog").showModal();});
  el("close-dialog").addEventListener("click",()=>el("connect-dialog").close());
  el("connect-form").addEventListener("submit",async event=>{event.preventDefault();el("submit-connect").disabled=true;el("connect-error").hidden=true;try{await connect(el("api-origin").value,el("login-user").value,el("login-password").value);el("login-password").value="";el("connect-dialog").close();fitFleet();toast("Connected. The GPS source is synthetic, but the backend data flow is real.");}catch(error){el("connect-error").textContent=error instanceof TypeError?"API connection failed. Check that the backend is running and this page origin is included in ALLOWED_ORIGINS. For localhost, open the dashboard served by the API at port 8000.":error.message;el("connect-error").hidden=false;}finally{el("submit-connect").disabled=false;}});
  addEventListener("pagehide",()=>{clearInterval(timer);disconnect();});
}
main();
