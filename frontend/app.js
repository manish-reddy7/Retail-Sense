const $ = id => document.getElementById(id);
const inputIds = ["anchor", "historical", "volatility", "weather", "trend", "event", "tau", "onHand", "onOrder"];

function number(id) { return Number($(id).value); }
function agent(id, forecast, confidence, factor) {
  const width = Math.max(3, forecast * (1 - confidence) * 1.35);
  return { id, forecast: Math.max(0, forecast), confidence, factor, low: Math.max(0, forecast - width), high: forecast + width };
}
function calculate() {
  const anchor = number("anchor"), history = number("historical"), volatility = number("volatility");
  const weather = number("weather"), trend = number("trend"), event = $("event").value;
  const historical = agent("Historical", history, Math.min(.95, Math.max(.3, 1 - volatility / history)), "Recent demand pattern");
  const weatherAgent = agent("Weather", anchor * (1 + Math.max(-.4, Math.min(.6, .07 * weather))), Math.max(.3, .75 - (Math.abs(weather) < .5 ? .25 : 0)), `Weather anomaly ${weather >= 0 ? "+" : ""}${weather.toFixed(1)}`);
  const trendAgent = agent("Trend", anchor * (1 + Math.max(-.3, Math.min(.5, .09 * trend))), Math.max(.2, .60 - (Math.abs(trend) < 1 ? .25 : 0)), `Trend z-score ${trend >= 0 ? "+" : ""}${trend.toFixed(1)}`);
  const eventMultiplier = event === "holiday" ? 1.25 : event === "sport" ? 1.12 : 1;
  const calendar = agent("Calendar", anchor * eventMultiplier * 1.04, .80 - (event === "none" ? 0 : .15), event === "none" ? "Known weekday seasonality" : event === "sport" ? "Sporting event" : "Holiday");
  const agents = [historical, weatherAgent, trendAgent, calendar];
  const weighted = list => {
    const total = list.reduce((s, x) => s + x.confidence, 0);
    const mean = list.reduce((s, x) => s + x.forecast * x.confidence, 0) / total;
    const variance = list.reduce((s, x) => s + x.confidence * (x.forecast - mean) ** 2, 0) / total;
    return { mean, d: Math.sqrt(variance) / Math.max(mean, .000001) };
  };
  let stats = weighted(agents), critic = null, revised = agents;
  const triggered = stats.d >= number("tau");
  if (triggered) {
    const allLow = agents.every(a => a.confidence < .55);
    const outlier = agents.reduce((a,b) => Math.abs(a.forecast - stats.mean) > Math.abs(b.forecast - stats.mean) ? a : b);
    if (allLow) {
      critic = { type:"T3", summary:"All available forecasts have low confidence. This looks like irreducible uncertainty, so the interval is widened without forcing movement.", resolvable:false };
    } else {
      const type = outlier.id === "Historical" ? "T1" : "T4";
      critic = { type, summary:`${type}: forecasts span ${(Math.max(...agents.map(a=>a.forecast))-Math.min(...agents.map(a=>a.forecast))).toFixed(1)} units. ${outlier.id} is furthest from the confidence-weighted consensus.`, resolvable:true };
      revised = agents.map(a => {
        const bound = {Historical:.20, Weather:.35, Trend:.40, Calendar:.25}[a.id] * a.forecast;
        const shift = Math.max(-bound, Math.min(bound, .35 * (stats.mean - a.forecast)));
        return {...a, before:a.forecast, forecast:a.forecast + shift, held:Math.abs(shift)<.01};
      });
      stats = weighted(revised);
    }
  }
  const averageUncertainty = revised.reduce((s,a)=>s+(1-a.confidence)*a.confidence,0) / revised.reduce((s,a)=>s+a.confidence,0);
  let margin = Math.max(2, 1.28 * (stats.d * stats.mean + averageUncertainty * stats.mean));
  if (triggered && critic && !critic.resolvable) margin *= 1.5;
  const low = Math.max(0, stats.mean-margin), high = stats.mean+margin;
  const sigma = (high-low)/(2*1.28), safety=1.28*sigma*Math.sqrt(3), reorder=stats.mean*3+safety;
  const inventory = number("onHand")+number("onOrder"), target=stats.mean*10+safety;
  const action = inventory < reorder ? "RESTOCK" : inventory > target*1.2 ? "REDUCE" : "HOLD";
  const quantity = action === "RESTOCK" ? Math.round(Math.max(0,target-inventory)) : 0;
  render({agents, revised, stats, triggered, critic, low, high, action, quantity, reorder, safety});
}
function render(r) {
  $("forecast").textContent = `${r.stats.mean.toFixed(0)} units`;
  $("interval").textContent = `${r.low.toFixed(0)}–${r.high.toFixed(0)}`;
  $("disagreement").textContent = r.stats.d.toFixed(3);
  $("path").textContent = r.triggered ? "Deliberate" : "Fast consensus";
  $("agents").innerHTML = r.agents.map(a => `<tr><td>${a.id}</td><td>${a.forecast.toFixed(1)}</td><td>${Math.round(a.confidence*100)}%</td><td>${a.factor}</td><td class="status">Active</td></tr>`).join("");
  $("criticPanel").style.display = r.critic ? "block" : "none";
  if (r.critic) {
    $("criticTitle").textContent = `Critic: ${r.critic.type}`;
    $("criticSummary").textContent = r.critic.summary;
    $("revision").innerHTML = r.critic.resolvable ? r.revised.map(a => `<b>${a.id}</b>: ${a.before.toFixed(1)} → ${a.forecast.toFixed(1)}${a.held ? " (held)" : ""}`).join(" &nbsp; · &nbsp; ") : "<b>Recommendation:</b> Widen interval; preserve pre-deliberation point forecast.";
  }
  $("action").textContent = `${r.action} — ${r.quantity} units`;
  $("actionDetail").textContent = `Reorder point: ${r.reorder.toFixed(1)} · Safety stock: ${r.safety.toFixed(1)}`;
  $("rationale").textContent = r.action === "RESTOCK" ? "Inventory position is below the deterministic reorder point." : r.action === "REDUCE" ? "Inventory is materially above the review-period target." : "Inventory is within the policy band. Quantity is computed only by policy inputs.";
}
inputIds.forEach(id => {
  const el = $(id);
  if (el.type === "range") { $(id+"Out").textContent = el.value; el.addEventListener("input", () => { $(id+"Out").textContent = el.value; calculate(); }); }
  else el.addEventListener("input", calculate);
  el.addEventListener("change", calculate);
});
calculate();

