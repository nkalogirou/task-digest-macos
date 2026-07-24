from __future__ import annotations

import json


TOUR_STEPS = [
    {
        "selector": ".focus-section",
        "title": "Start with Today’s Plan",
        "body": "Task Digest recommends a small, ordered focus list from due dates, blockers, review requests, unread updates, and your local priorities.",
    },
    {
        "selector": ".dashboard-controls",
        "title": "Search and filter instantly",
        "body": "Use plain text or structured searches such as is:failing, is:waiting, repo:example-org/web-app, or pr:142. Press Command-K to open the command palette.",
    },
    {
        "selector": ".dashboard-metrics",
        "title": "See workload at a glance",
        "body": "The primary metrics keep action, reviews, waiting work, and unread updates visible without overwhelming the dashboard.",
    },
    {
        "selector": ".dashboard-primary .task",
        "title": "Understand why a task needs attention",
        "body": "Task cards combine Asana status, working-day age, due dates, linked pull requests, checks, review state, and local notes in one place.",
    },
    {
        "selector": ".dashboard-secondary",
        "title": "Keep context separate from focus",
        "body": "GitHub reviews, authored PR blockers, source health, summaries, and optional investigations stay available without crowding the main work queue.",
    },
    {
        "selector": ".app-nav",
        "title": "More than a task list",
        "body": "Generate stand-ups, edit prioritization rules, inspect dependencies, review history, manage backups, and diagnose local services from the sidebar.",
    },
]


def inject_demo_tour(page: str, *, auto_start: bool = True) -> str:
    """Add a self-contained guided tour to a rendered demo dashboard."""

    steps_json = json.dumps(TOUR_STEPS, ensure_ascii=False).replace("</", "<\\/")
    auto_start_js = "startTour();" if auto_start else ""
    assets = f"""
<style id="task-digest-tour-styles">
.tour-launch {{
  position: fixed; top: 18px; right: 20px; z-index: 10020;
  border: 1px solid color-mix(in srgb,var(--accent) 55%,var(--border));
  background: var(--accent); color: #fff; border-radius: 999px;
  padding: 10px 15px; font-weight: 720; box-shadow: var(--shadow-md);
}}
.tour-launch:hover {{ background: color-mix(in srgb,var(--accent) 88%,#000); }}
.tour-backdrop {{
  position: fixed; inset: 0; z-index: 10000; display: none;
  background: rgba(4,8,18,.64); backdrop-filter: blur(2px);
}}
.tour-backdrop.active {{ display: block; }}
.tour-highlight {{
  position: relative !important; z-index: 10010 !important;
  border-radius: var(--radius-md); box-shadow: 0 0 0 4px var(--accent), 0 20px 70px rgba(0,0,0,.45) !important;
}}
.tour-popover {{
  position: fixed; z-index: 10030; width: min(390px,calc(100vw - 28px));
  padding: 20px; border: 1px solid var(--border-strong); border-radius: 18px;
  background: var(--surface-solid); color: var(--text); box-shadow: 0 24px 80px rgba(0,0,0,.34);
  display: none;
}}
.tour-popover.active {{ display: block; }}
.tour-progress {{ color: var(--accent); font-size: 11px; font-weight: 780; letter-spacing: .09em; text-transform: uppercase; }}
.tour-popover h2 {{ margin: 8px 0 8px; font-size: 22px; letter-spacing: -.025em; }}
.tour-popover p {{ margin: 0; color: var(--muted); font-size: 14px; line-height: 1.55; }}
.tour-actions {{ display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-top: 18px; }}
.tour-actions div {{ display: flex; gap: 8px; }}
.tour-actions button {{ min-width: 78px; }}
.tour-skip {{ border: 0; background: transparent; color: var(--muted); padding-inline: 3px; }}
.tour-skip:hover {{ background: transparent; box-shadow: none; color: var(--text); }}
@media(max-width:700px) {{
  .tour-launch {{ top: auto; bottom: 16px; right: 16px; }}
  .tour-popover {{ left: 14px !important; right: 14px !important; bottom: 14px !important; top: auto !important; width: auto; }}
}}
@media(prefers-reduced-motion:no-preference) {{
  .tour-popover {{ animation: tour-enter .18s ease-out; }}
  @keyframes tour-enter {{ from {{ opacity:0; transform:translateY(7px); }} to {{ opacity:1; transform:none; }} }}
}}
</style>
<button type="button" class="tour-launch" id="tour-launch">Start guided tour</button>
<div class="tour-backdrop" id="tour-backdrop" aria-hidden="true"></div>
<section class="tour-popover" id="tour-popover" role="dialog" aria-modal="true" aria-labelledby="tour-title" aria-describedby="tour-body">
  <div class="tour-progress" id="tour-progress"></div>
  <h2 id="tour-title"></h2>
  <p id="tour-body"></p>
  <div class="tour-actions">
    <button type="button" class="tour-skip" id="tour-skip">Exit tour</button>
    <div><button type="button" id="tour-prev">Back</button><button type="button" class="primary" id="tour-next">Next</button></div>
  </div>
</section>
<script>
(() => {{
  const steps={steps_json};
  const launch=document.getElementById('tour-launch');
  const backdrop=document.getElementById('tour-backdrop');
  const popover=document.getElementById('tour-popover');
  const progress=document.getElementById('tour-progress');
  const title=document.getElementById('tour-title');
  const body=document.getElementById('tour-body');
  const previous=document.getElementById('tour-prev');
  const next=document.getElementById('tour-next');
  const skip=document.getElementById('tour-skip');
  let index=0; let current=null; let active=false;

  function clearHighlight() {{
    if(current) current.classList.remove('tour-highlight');
    current=null;
  }}
  function placePopover(target) {{
    if(matchMedia('(max-width:700px)').matches) return;
    const rect=target.getBoundingClientRect();
    const width=Math.min(390,window.innerWidth-28);
    const height=popover.offsetHeight||240;
    let left=rect.right+18;
    if(left+width>window.innerWidth-14) left=Math.max(14,rect.left-width-18);
    let top=Math.max(14,Math.min(rect.top,window.innerHeight-height-14));
    popover.style.left=left+'px'; popover.style.top=top+'px';
  }}
  function visibleSteps() {{ return steps.filter(step=>document.querySelector(step.selector)); }}
  function showStep(nextIndex) {{
    const available=visibleSteps();
    if(!available.length) return stopTour();
    index=Math.max(0,Math.min(nextIndex,available.length-1));
    const step=available[index];
    clearHighlight(); current=document.querySelector(step.selector);
    current.classList.add('tour-highlight');
    current.scrollIntoView({{behavior:'smooth',block:'center',inline:'nearest'}});
    progress.textContent=`Step ${{index+1}} of ${{available.length}}`;
    title.textContent=step.title; body.textContent=step.body;
    previous.disabled=index===0;
    next.textContent=index===available.length-1?'Finish':'Next';
    setTimeout(()=>placePopover(current),220);
  }}
  function startTour() {{
    active=true; backdrop.classList.add('active'); popover.classList.add('active');
    showStep(0); next.focus();
  }}
  function stopTour() {{
    active=false; clearHighlight(); backdrop.classList.remove('active'); popover.classList.remove('active');
    launch.focus();
  }}
  launch.addEventListener('click',startTour);
  skip.addEventListener('click',stopTour);
  backdrop.addEventListener('click',stopTour);
  previous.addEventListener('click',()=>showStep(index-1));
  next.addEventListener('click',()=>{{ const available=visibleSteps(); if(index>=available.length-1) stopTour(); else showStep(index+1); }});
  addEventListener('resize',()=>{{if(active&&current)placePopover(current)}});
  addEventListener('keydown',event=>{{
    if(!active) return;
    if(event.key==='Escape') stopTour();
    if(event.key==='ArrowRight') next.click();
    if(event.key==='ArrowLeft'&&!previous.disabled) previous.click();
  }});
  {auto_start_js}
}})();
</script>
"""
    marker = "</body>"
    if marker not in page:
        return page + assets
    return page.replace(marker, assets + marker, 1)
