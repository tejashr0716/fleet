import {state,el,clock,stale} from "./config.js";
let chart;
const capitalize = text => text.charAt(0).toUpperCase()+text.slice(1);
export function initializePanels() {
  el("vehicle-search").addEventListener("input",event=>{state.query=event.target.value.toLowerCase();renderList();});
  document.querySelectorAll(".filter").forEach(button=>button.addEventListener("click",()=>{state.filter=button.dataset.kind;document.querySelectorAll(".filter").forEach(b=>{const active=b===button;b.classList.toggle("active",active);b.setAttribute("aria-pressed",String(active));});renderList();}));
  if(typeof Chart!=="undefined") {
    const colors=getComputedStyle(document.documentElement);
    chart=new Chart(el("speed-chart"), {type:"line",data:{datasets:[{label:"Observed speed",data:[],borderColor:colors.getPropertyValue("--purple").trim(),backgroundColor:colors.getPropertyValue("--purple").trim(),pointRadius:2,borderWidth:2,tension:0,fill:false,clip:8}]},options:{responsive:true,maintainAspectRatio:false,animation:false,parsing:false,normalized:true,interaction:{mode:"nearest",intersect:false,axis:"x"},plugins:{legend:{display:false},tooltip:{callbacks:{title:items=>items.length?new Date(items[0].parsed.x).toLocaleString():"",label:item=>`${item.parsed.y.toFixed(1)} km/h`}}},scales:{x:{type:"linear",grid:{display:false},ticks:{maxTicksLimit:4,color:colors.getPropertyValue("--muted").trim(),font:{size:12},callback:value=>clock(value)}},y:{min:0,max:120,ticks:{stepSize:30,color:colors.getPropertyValue("--muted").trim(),font:{size:12}},grid:{color:colors.getPropertyValue("--grid").trim()}}}}});
  }
}
export function renderList() {
  const filtered=state.vehicles.filter(v=>(state.filter==="all"||v.kind===state.filter)&&`${v.name} ${v.registration}`.toLowerCase().includes(state.query));
  const container=el("vehicle-list");const oldScroll=container.scrollTop;const focusedId=document.activeElement?.closest(".vehicle-row")?.dataset.vehicleId;container.replaceChildren();
  el("list-count").textContent=`${filtered.length} of ${state.vehicles.length}`;
  if (!filtered.length){const p=document.createElement("p");p.className="empty";p.textContent="No matching vehicles.";container.append(p);return;}
  for(const v of filtered) {
    const point=state.positions.get(v.id);const button=document.createElement("button");button.type="button";button.className=`vehicle-row ${v.id===state.selected?"selected":""}`;button.setAttribute("aria-pressed",String(v.id===state.selected));button.dataset.vehicleId=v.id;
    const icon=document.createElement("span");icon.className="vehicle-avatar";icon.textContent=String(v.id).padStart(2,"0");
    const copy=document.createElement("span");copy.className="vehicle-copy";const name=document.createElement("strong");name.textContent=v.name;const reg=document.createElement("span");reg.textContent=v.registration;copy.append(name,reg);
    const speed=document.createElement("span");speed.className="vehicle-speed";speed.textContent=point?point.speed_kmh.toFixed(0):"—";const unit=document.createElement("small");unit.textContent=stale(point)?"stale":"km/h";speed.append(unit);button.append(icon,copy,speed);button.addEventListener("click",()=>state.onSelect(v.id));container.append(button);
  }container.scrollTop=oldScroll;if(focusedId){const target=container.querySelector(`[data-vehicle-id="${focusedId}"]`);if(target)target.focus({preventScroll:true});}
}
export function renderDetails() {
  const v=state.vehicles.find(v=>v.id===state.selected);if(!v)return;
  const p=state.positions.get(v.id);el("detail-title").textContent=v.name;el("detail-registration").textContent=v.registration;el("detail-kind").textContent=capitalize(v.kind);
  el("detail-speed").textContent=p?p.speed_kmh.toFixed(0):"—";
  const status=stale(p)?"Stale":p.speed_kmh>state.speedLimit?"Speeding":p.speed_kmh>5?"Moving":"Stopped";
  el("detail-status").textContent=status;el("detail-status").className=`tag ${status.toLowerCase()}`;
  el("detail-last").textContent=p?clock(p.recorded_at):"No position";
  el("detail-coordinates").textContent=p?`${p.lat.toFixed(4)}, ${p.lon.toFixed(4)}`:"Not available";
  el("detail-heading").textContent=p?`${p.heading.toFixed(0)}°`:"Not available";
  const points=(state.histories.get(v.id)||[]).slice(-60);
  el("chart-empty").hidden=Boolean(chart&&points.length>=2);
  if(!chart)el("chart-empty").textContent="Chart unavailable. Exact values are in the observations table.";
  if(chart&&points.length) {
    chart.data.datasets[0].data=points.map(p=>({x:Date.parse(p.recorded_at),y:p.speed_kmh}));
    const maximum=Math.max(120,...points.map(p=>p.speed_kmh)); const step=maximum>150?50:30;
    chart.options.scales.y.max=Math.ceil(maximum/step)*step;chart.options.scales.y.ticks.stepSize=step;
    chart.update("none");
  }
  const caption=points.length?`${v.name}: ${points.length} observed samples, from ${clock(points[0].recorded_at)} to ${clock(points.at(-1).recorded_at)}. Latest speed ${points.at(-1).speed_kmh.toFixed(1)} km/h. ${state.mode==="simulation"?"Synthetic browser data.":"Backend-observed telemetry."}`:"No speed observations available.";
  el("chart-summary").textContent=caption;el("speed-chart").setAttribute("aria-label",caption);
  el("speed-values").replaceChildren();for(const point of points){const row=document.createElement("tr");const time=document.createElement("td"),speed=document.createElement("td");time.textContent=clock(point.recorded_at);speed.textContent=point.speed_kmh.toFixed(1);row.append(time,speed);el("speed-values").append(row);}
}
export function renderAlerts() {
  el("alert-count").textContent=`${state.alerts.length} alerts`;const container=el("alert-list");container.replaceChildren();
  if(!state.alerts.length){const p=document.createElement("p");p.className="empty";p.textContent="No alert events yet. The simulator includes a deliberate speeding fixture.";container.append(p);return;}
  for(const a of state.alerts.slice(0,10)) {
    const row=document.createElement("div");row.className="alert-row";const icon=document.createElement("span");icon.className="alert-icon";icon.textContent=a.kind==="speeding"?"!":"↔";
    const body=document.createElement("div");body.className="alert-body";const title=document.createElement("p");title.textContent=`${state.vehicles.find(v=>v.id===a.vehicle_id)?.name||`Vehicle ${a.vehicle_id}`} · ${a.kind.replaceAll("_"," ")}`;
    const text=document.createElement("p");text.className="muted";text.textContent=a.kind==="speeding"?`${Number(a.details.speed_kmh).toFixed(1)} km/h; limit ${a.details.limit_kmh} km/h`:a.details.geofence_name;body.append(title,text);
    const time=document.createElement("span");time.className="alert-time";time.textContent=clock(a.recorded_at);row.append(icon,body,time);container.append(row);
  }
}
export function renderPanels() {
  el("stat-total").textContent=state.vehicles.length;
  el("stat-moving").textContent=[...state.positions.values()].filter(p=>!stale(p)&&p.speed_kmh>5).length;
  el("stat-stale").textContent=state.vehicles.filter(v=>stale(state.positions.get(v.id))).length;
  el("stat-source").textContent=state.sourceNote;el("ttl-label").textContent=state.ttl;
  renderList();renderDetails();renderAlerts();
}
